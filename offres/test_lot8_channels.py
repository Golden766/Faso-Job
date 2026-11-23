"""Tests du lot 8 (8A-2) : statistiques d audience et adaptateurs de messagerie.

Couvre le rapport d'activite enrichi, l'export CSV et le comportement des
adaptateurs de messagerie, qui doivent preparer sans simuler d'envoi.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import channels
from .models import (
    Offer,
    OfferClick,
    OfferReport,
    OfferSubmission,
    OfferView,
    OutboundMessage,
)


def make_offer(**overrides):
    data = {
        'title': 'Offre de test',
        'company_name': 'Employeur de test',
        'description': 'Description de test.',
        'status': Offer.STATUS_PUBLISHED,
        'is_source_confirmed': True,
    }
    data.update(overrides)
    return Offer.objects.create(**data)


class AudienceStatisticsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_report_counts_views_and_clicks(self):
        offer = make_offer()
        # Deux sessions distinctes consultent la fiche.
        from django.test import Client

        first_client = Client()
        first_client.get(f'/offre/{offer.slug}/')
        second_client = Client()
        second_client.get(f'/offre/{offer.slug}/')
        OfferClick.objects.create(
            offer=offer,
            channel=OfferClick.CHANNEL_WHATSAPP,
            session_key='session-a',
        )

        response = self.client.get(reverse('admin-activity-report'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['view_total'], 2)
        self.assertEqual(response.context['click_total'], 1)

    def test_report_lists_the_most_viewed_offers(self):
        first = make_offer(title='Offre populaire')
        second = make_offer(title='Offre calme')
        first.view_count = 7
        first.save()
        second.view_count = 2
        second.save()

        response = self.client.get(reverse('admin-activity-report'))

        titles = [row['title'] for row in response.context['top_viewed_offers']]
        self.assertIn('Offre populaire', titles)
        self.assertIn('Offre calme', titles)
        self.assertEqual(titles[0], 'Offre populaire')

    def test_report_breaks_clicks_down_by_channel(self):
        offer = make_offer()
        for index in range(3):
            OfferClick.objects.create(
                offer=offer,
                channel=OfferClick.CHANNEL_WHATSAPP,
                session_key=f'session-{index}',
            )
        OfferClick.objects.create(
            offer=offer,
            channel=OfferClick.CHANNEL_EMAIL,
            session_key='session-mail',
        )

        response = self.client.get(reverse('admin-activity-report'))

        rows = {
            row['label']: row['count']
            for row in response.context['click_channel_rows']
        }
        self.assertEqual(rows['WhatsApp'], 3)
        self.assertEqual(rows['E-mail'], 1)
        self.assertEqual(rows['En ligne'], 0)

    def test_report_shows_an_empty_state_without_audience(self):
        response = self.client.get(reverse('admin-activity-report'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['view_total'], 0)
        self.assertEqual(response.context['click_total'], 0)
        self.assertEqual(response.context['top_viewed_offers'], [])

    def test_report_page_shows_the_audience_sections(self):
        response = self.client.get(reverse('admin-activity-report'))

        self.assertContains(response, 'Offres les plus consult')
        self.assertContains(response, 'Clics sortants par canal')

    def test_csv_export_contains_the_audience_data(self):
        offer = make_offer(title='Offre exportee')
        offer.view_count = 4
        offer.save()
        OfferClick.objects.create(
            offer=offer,
            channel=OfferClick.CHANNEL_WHATSAPP,
            session_key='session-export',
        )

        response = self.client.get(reverse('admin-activity-report-csv'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8-sig')
        self.assertIn('Consultations de fiches;4', content)
        self.assertIn('Clics vers un canal de candidature;1', content)
        self.assertIn('Offre exportee', content)
        self.assertIn('Clics sortants par canal', content)

    def test_csv_monthly_rows_include_audience_columns(self):
        response = self.client.get(reverse('admin-activity-report-csv'))

        content = response.content.decode('utf-8-sig')
        self.assertIn(
            'Mois;Offres publiées;Propositions reçues;Signalements reçus;Consultations;Clics sortants',
            content,
        )


class OutboundMessageAdminTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_journal_is_reachable(self):
        OutboundMessage.objects.create(
            channel=OutboundMessage.CHANNEL_WHATSAPP,
            recipient='+226 70 00 00 00',
            body='Message de test',
        )

        response = self.client.get(
            reverse('admin:offres_outboundmessage_changelist')
        )

        self.assertEqual(response.status_code, 200)

    def test_journal_is_not_public(self):
        self.client.logout()

        response = self.client.get(
            reverse('admin:offres_outboundmessage_changelist')
        )

        self.assertEqual(response.status_code, 302)

    def test_messages_cannot_be_added_by_hand(self):
        response = self.client.get(
            reverse('admin:offres_outboundmessage_add')
        )

        self.assertEqual(response.status_code, 403)


class AdapterTest(TestCase):
    def test_whatsapp_adapter_records_without_sending(self):
        offer = make_offer()

        result = channels.send_message(
            OutboundMessage.CHANNEL_WHATSAPP,
            '+226 70 00 00 00',
            'Bonjour',
            offer=offer,
        )

        self.assertFalse(result.is_sent)
        self.assertEqual(result.status, OutboundMessage.STATUS_NOT_CONFIGURED)

        message = OutboundMessage.objects.get()
        self.assertEqual(message.channel, OutboundMessage.CHANNEL_WHATSAPP)
        self.assertEqual(message.recipient, '+226 70 00 00 00')
        self.assertEqual(message.body, 'Bonjour')
        self.assertEqual(message.offer, offer)
        self.assertIsNone(message.sent_at)

    def test_sms_adapter_records_without_sending(self):
        channels.send_message(
            OutboundMessage.CHANNEL_SMS,
            '+226 70 00 00 00',
            'Bonjour',
        )

        message = OutboundMessage.objects.get()
        self.assertEqual(message.status, OutboundMessage.STATUS_NOT_CONFIGURED)
        self.assertEqual(message.channel, OutboundMessage.CHANNEL_SMS)

    def test_unknown_channel_does_not_raise(self):
        result = channels.send_message(
            'canal-inconnu',
            '+226 70 00 00 00',
            'Bonjour',
        )

        self.assertIsNotNone(result)
        self.assertFalse(result.is_sent)

    def test_empty_recipient_or_body_is_ignored(self):
        self.assertIsNone(channels.send_message('whatsapp', '', 'Bonjour'))
        self.assertIsNone(channels.send_message('whatsapp', '+22670000000', ''))
        self.assertEqual(OutboundMessage.objects.count(), 0)

    def test_email_adapter_sends_through_django(self):
        from django.core import mail

        result = channels.send_message(
            OutboundMessage.CHANNEL_EMAIL,
            'contact@example.bf',
            'Bonjour',
        )

        self.assertTrue(result.is_sent)
        self.assertEqual(len(mail.outbox), 1)

        message = OutboundMessage.objects.get()
        self.assertEqual(message.status, OutboundMessage.STATUS_SENT)
        self.assertIsNotNone(message.sent_at)

    def test_adapter_is_not_configured_by_default(self):
        adapter = channels.get_adapter(OutboundMessage.CHANNEL_WHATSAPP)

        self.assertFalse(adapter.is_configured())


class PrepareSubmissionMessageTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_action_prepares_a_message_without_sending(self):
        submission = OfferSubmission.objects.create(
            title='Proposition test',
            company_name='Entreprise test',
            contact_phone='+226 70 00 00 00',
            status=OfferSubmission.STATUS_ACCEPTED,
        )

        self.client.post(
            reverse('admin:offres_offersubmission_changelist'),
            {
                'action': 'prepare_submission_message',
                '_selected_action': [str(submission.pk)],
            },
            follow=True,
        )

        message = OutboundMessage.objects.get()
        self.assertEqual(message.recipient, '+226 70 00 00 00')
        self.assertEqual(message.submission, submission)
        self.assertEqual(message.status, OutboundMessage.STATUS_NOT_CONFIGURED)
        self.assertIn('Proposition test', message.body)

    def test_action_skips_submissions_without_phone(self):
        submission = OfferSubmission.objects.create(
            title='Proposition sans contact',
            company_name='Entreprise test',
            status=OfferSubmission.STATUS_ACCEPTED,
        )

        self.client.post(
            reverse('admin:offres_offersubmission_changelist'),
            {
                'action': 'prepare_submission_message',
                '_selected_action': [str(submission.pk)],
            },
            follow=True,
        )

        self.assertEqual(OutboundMessage.objects.count(), 0)

    def test_action_does_not_change_the_submission_status(self):
        submission = OfferSubmission.objects.create(
            title='Proposition test',
            company_name='Entreprise test',
            contact_phone='+226 70 00 00 00',
            status=OfferSubmission.STATUS_ACCEPTED,
        )

        self.client.post(
            reverse('admin:offres_offersubmission_changelist'),
            {
                'action': 'prepare_submission_message',
                '_selected_action': [str(submission.pk)],
            },
            follow=True,
        )

        submission.refresh_from_db()
        self.assertEqual(submission.status, OfferSubmission.STATUS_ACCEPTED)

    def test_message_body_links_to_the_created_offer(self):
        offer = make_offer()
        submission = OfferSubmission.objects.create(
            title='Proposition liee',
            company_name='Entreprise test',
            contact_phone='+226 70 00 00 00',
            status=OfferSubmission.STATUS_ACCEPTED,
            offer=offer,
        )

        self.client.post(
            reverse('admin:offres_offersubmission_changelist'),
            {
                'action': 'prepare_submission_message',
                '_selected_action': [str(submission.pk)],
            },
            follow=True,
        )

        message = OutboundMessage.objects.get()
        self.assertIn(offer.slug, message.body)
