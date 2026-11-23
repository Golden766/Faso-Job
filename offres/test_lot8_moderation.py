"""Tests du lot 8 (8A) : croisement liste noire, quarantaine et suivi.

Couvre le module de moderation, le blocage de publication, les compteurs
de consultations et l'archivage automatique.
"""

import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from . import moderation
from .models import (
    BlacklistedContact,
    Offer,
    OfferClick,
    OfferSubmission,
    OfferView,
    PlatformSettings,
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


def make_blacklist(phone='', organization='', email=''):
    return BlacklistedContact.objects.create(
        phone_number=phone or '+226 70 00 00 00',
        organization=organization or 'Entité test',
        email=email,
    )


class NormalizationTest(TestCase):
    def test_normalize_digits_keeps_only_digits(self):
        self.assertEqual(moderation.normalize_digits('+226 70-00 00.00'), '22670000000')

    def test_normalize_digits_handles_empty_value(self):
        self.assertEqual(moderation.normalize_digits(''), '')
        self.assertEqual(moderation.normalize_digits(None), '')

    def test_normalize_email_lowercases(self):
        self.assertEqual(moderation.normalize_email('  Contact@Example.BF '), 'contact@example.bf')

    def test_normalize_text_removes_accents_and_punctuation(self):
        self.assertEqual(moderation.normalize_text('Frais de dossier !'), 'frais de dossier')
        self.assertEqual(moderation.normalize_text('dossier'), 'dossier')

    def test_parse_keywords_reads_one_per_line(self):
        raw = 'frais de dossier\n\n  caution  \n# commentaire\n'

        self.assertEqual(
            moderation.parse_keywords(raw),
            ['frais de dossier', 'caution'],
        )

    def test_parse_keywords_handles_empty_value(self):
        self.assertEqual(moderation.parse_keywords(''), [])
        self.assertEqual(moderation.parse_keywords(None), [])


class KeywordMatchTest(TestCase):
    def test_keyword_is_found_ignoring_case_and_accents(self):
        matches = moderation.find_keyword_matches(
            ['Vous devez payer des FRAIS DE DOSSIER'],
            ['frais de dossier'],
        )

        self.assertEqual(matches, ['frais de dossier'])

    def test_word_inside_another_word_is_not_a_match(self):
        matches = moderation.find_keyword_matches(
            ['Vous devez joindre un dossier de candidature'],
            ['dossiers'],
        )

        self.assertEqual(matches, [])

    def test_whole_word_is_a_match(self):
        matches = moderation.find_keyword_matches(
            ['Dossier de candidature'],
            ['dossier'],
        )

        self.assertEqual(matches, ['dossier'])

    def test_empty_keyword_is_ignored(self):
        matches = moderation.find_keyword_matches(['Texte'], ['', '   '])

        self.assertEqual(matches, [])

    def test_no_match_returns_empty_list(self):
        matches = moderation.find_keyword_matches(['Poste de comptable'], ['caution'])

        self.assertEqual(matches, [])


class BlacklistMatchTest(TestCase):
    def test_matching_phone_is_detected(self):
        make_blacklist(phone='+226 70 11 22 33')

        reasons = moderation.find_blacklist_matches(phone='+226 70 11 22 33')

        self.assertEqual(len(reasons), 1)
        self.assertIn('liste noire', reasons[0])

    def test_phone_formatting_does_not_hide_a_match(self):
        make_blacklist(phone='+226 70 11 22 33')

        reasons = moderation.find_blacklist_matches(phone='22670112233')

        self.assertEqual(len(reasons), 1)

    def test_matching_email_is_detected(self):
        make_blacklist(phone='+226 70 00 00 00', email='arnaque@example.bf')

        reasons = moderation.find_blacklist_matches(email='ARNAQUE@example.bf')

        self.assertEqual(len(reasons), 1)

    def test_matching_organization_is_detected(self):
        make_blacklist(organization='Sahel Express Logistique')

        reasons = moderation.find_blacklist_matches(organization='sahel express logistique')

        self.assertEqual(len(reasons), 1)

    def test_different_contact_is_not_flagged(self):
        make_blacklist(phone='+226 70 11 22 33', organization='Sahel Express')

        reasons = moderation.find_blacklist_matches(
            phone='+226 70 99 88 77',
            organization='Entreprise Fiable',
        )

        self.assertEqual(reasons, [])

    def test_empty_values_are_not_flagged(self):
        make_blacklist(phone='', organization='Entité test')

        reasons = moderation.find_blacklist_matches(phone='', email='', organization='')

        self.assertEqual(reasons, [])


class QuarantineOnOfferTest(TestCase):
    def test_offer_matching_blacklist_is_quarantined(self):
        make_blacklist(phone='+226 70 11 22 33')

        offer = make_offer(
            status=Offer.STATUS_PENDING,
            application_phone='+226 70 11 22 33',
        )

        moderation.screen_offers([offer])
        offer.refresh_from_db()

        self.assertTrue(offer.quarantine_reason)
        self.assertIn('liste noire', offer.quarantine_reason)
        self.assertIsNotNone(offer.quarantined_at)

    def test_offer_with_keyword_is_quarantined(self):
        settings_row = PlatformSettings.load()
        settings_row.quarantine_keywords = 'frais de dossier\ncaution obligatoire'
        settings_row.save()

        offer = make_offer(
            status=Offer.STATUS_PENDING,
            description='Merci de payer des frais de dossier.',
        )

        moderation.screen_offers([offer])
        offer.refresh_from_db()

        self.assertTrue(offer.quarantine_reason)
        self.assertIn('frais de dossier', offer.quarantine_reason)

    def test_clean_offer_is_not_quarantined(self):
        offer = make_offer()

        moderation.screen_offers([offer])
        offer.refresh_from_db()

        self.assertFalse(offer.quarantine_reason)

    def test_quarantined_offer_cannot_be_published(self):
        offer = make_offer(status=Offer.STATUS_PENDING)
        offer.quarantine_reason = 'Numéro présent sur la liste noire.'
        offer.quarantined_at = timezone.now()

        with self.assertRaises(Exception) as context:
            offer.status = Offer.STATUS_PUBLISHED
            offer.save()

        self.assertIn('quarantaine', str(context.exception).lower())

    def test_reviewed_quarantine_allows_publication(self):
        offer = make_offer(status=Offer.STATUS_PENDING)
        offer.quarantine_reason = 'Numéro présent sur la liste noire.'
        offer.quarantined_at = timezone.now()
        offer.quarantine_reviewed_at = timezone.now()

        offer.status = Offer.STATUS_PUBLISHED
        offer.save()
        offer.refresh_from_db()

        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)
        self.assertTrue(offer.is_published)


class QuarantineOnSubmissionTest(TestCase):
    def test_submission_matching_blacklist_is_quarantined(self):
        make_blacklist(phone='+226 70 11 22 33')

        submission = OfferSubmission.objects.create(
            title='Proposition',
            company_name='Entreprise',
            contact_phone='+226 70 11 22 33',
        )

        moderation.screen_submissions([submission])
        submission.refresh_from_db()

        self.assertTrue(submission.quarantine_reason)

    def test_quarantined_submission_stays_pending(self):
        make_blacklist(phone='+226 70 11 22 33')

        submission = OfferSubmission.objects.create(
            title='Proposition',
            company_name='Entreprise',
            contact_phone='+226 70 11 22 33',
        )

        moderation.screen_submissions([submission])
        submission.refresh_from_db()

        self.assertEqual(submission.status, OfferSubmission.STATUS_PENDING)
        self.assertIsNone(submission.offer_id)


class PublicSubmissionFlowTest(TestCase):
    def valid_payload(self, **overrides):
        payload = {
            'title': 'Assistant comptable',
            'company_name': 'Cabinet Faso',
            'employer_kind': Offer.EMPLOYER_COMPANY,
            'location': 'Ouagadougou',
            'employment_type': 'CDI',
            'details': 'Missions et profil detailles dans l annonce.',
            'source_name': 'Site de l entreprise',
            'application_method': 'email',
            'application_email': 'recrutement@example.bf',
            'contact_email': 'contact@example.bf',
            'declarant_role': OfferSubmission.DECLARANT_EMPLOYER,
            'ethics_commitment': 'on',
        }
        payload.update(overrides)
        return payload

    def test_submission_is_screened_on_arrival(self):
        make_blacklist(phone='+226 70 11 22 33')

        response = self.client.post(
            '/proposer-une-annonce/',
            self.valid_payload(contact_phone='+226 70 11 22 33'),
        )

        self.assertEqual(response.status_code, 302)
        submission = OfferSubmission.objects.get()
        self.assertTrue(submission.quarantine_reason)

    def test_regular_submission_is_not_quarantined(self):
        response = self.client.post(
            '/proposer-une-annonce/',
            self.valid_payload(contact_phone='+226 70 99 88 77'),
        )

        self.assertEqual(response.status_code, 302)
        submission = OfferSubmission.objects.get()
        self.assertFalse(submission.quarantine_reason)

    def test_submission_with_blacklisted_email_is_quarantined(self):
        make_blacklist(email='contact@example.bf')

        response = self.client.post(
            '/proposer-une-annonce/',
            self.valid_payload(),
        )

        self.assertEqual(response.status_code, 302)
        submission = OfferSubmission.objects.get()
        self.assertTrue(submission.quarantine_reason)


class ViewCounterTest(TestCase):
    def test_offer_view_is_counted_once_per_session(self):
        offer = make_offer()

        self.client.get(f'/offre/{offer.slug}/')
        self.client.get(f'/offre/{offer.slug}/')

        offer.refresh_from_db()
        self.assertEqual(offer.view_count, 1)
        self.assertEqual(OfferView.objects.count(), 1)

    def test_view_is_not_counted_for_staff(self):
        offer = make_offer()
        user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(user)

        self.client.get(f'/offre/{offer.slug}/')

        offer.refresh_from_db()
        self.assertEqual(offer.view_count, 0)

    def test_counter_can_be_disabled(self):
        settings_row = PlatformSettings.load()
        settings_row.view_counter_enabled = False
        settings_row.save()
        offer = make_offer()

        self.client.get(f'/offre/{offer.slug}/')

        offer.refresh_from_db()
        self.assertEqual(offer.view_count, 0)

    def test_counter_is_not_shown_to_the_public(self):
        offer = make_offer()
        self.client.get(f'/offre/{offer.slug}/')
        offer.refresh_from_db()
        self.assertEqual(offer.view_count, 1)

        response = self.client.get(f'/offre/{offer.slug}/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'consultation')
        self.assertNotContains(response, 'Consultations')


class ArchiveExpiredOffersCommandTest(TestCase):
    def setUp(self):
        self.settings_row = PlatformSettings.load()
        self.settings_row.auto_archive_days = 7
        self.settings_row.save()

    def test_expired_offer_is_archived(self):
        offer = make_offer(
            deadline=timezone.localdate() - datetime.timedelta(days=10),
        )

        call_command('archive_expired_offers', stdout=StringIO())

        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.STATUS_ARCHIVED)
        self.assertFalse(offer.is_published)

    def test_recently_expired_offer_is_kept(self):
        offer = make_offer(
            deadline=timezone.localdate() - datetime.timedelta(days=2),
        )

        call_command('archive_expired_offers', stdout=StringIO())

        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)

    def test_offer_without_deadline_is_kept(self):
        offer = make_offer(deadline=None)

        call_command('archive_expired_offers', stdout=StringIO())

        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)

    def test_dry_run_changes_nothing(self):
        offer = make_offer(
            deadline=timezone.localdate() - datetime.timedelta(days=10),
        )

        call_command('archive_expired_offers', '--dry-run', stdout=StringIO())

        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)

    def test_archiving_is_disabled_when_delay_is_zero(self):
        self.settings_row.auto_archive_days = 0
        self.settings_row.save()
        offer = make_offer(
            deadline=timezone.localdate() - datetime.timedelta(days=30),
        )

        call_command('archive_expired_offers', stdout=StringIO())

        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)


class NotificationTest(TestCase):
    def test_no_email_is_sent_when_notifications_are_disabled(self):
        from django.core import mail

        PlatformSettings.load()
        submission = OfferSubmission.objects.create(
            title='Proposition',
            company_name='Entreprise',
        )

        from . import notifications

        result = notifications.notify_new_submission(submission)

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_is_sent_when_enabled_and_address_is_set(self):
        from django.core import mail

        settings_row = PlatformSettings.load()
        settings_row.notifications_enabled = True
        settings_row.alert_email = 'equipe@example.bf'
        settings_row.save()
        submission = OfferSubmission.objects.create(
            title='Proposition test',
            company_name='Entreprise',
        )

        from . import notifications

        result = notifications.notify_new_submission(submission)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('equipe@example.bf', mail.outbox[0].to)
        self.assertIn('Proposition test', mail.outbox[0].subject)

    def test_no_email_without_alert_address(self):
        from django.core import mail

        settings_row = PlatformSettings.load()
        settings_row.notifications_enabled = True
        settings_row.alert_email = ''
        settings_row.save()
        submission = OfferSubmission.objects.create(
            title='Proposition',
            company_name='Entreprise',
        )

        from . import notifications

        result = notifications.notify_new_submission(submission)

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)


class AdminModerationActionTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_rescreen_action_quarantines_matching_offer(self):
        make_blacklist(phone='+226 70 11 22 33')
        offer = make_offer(
            status=Offer.STATUS_PENDING,
            application_phone='+226 70 11 22 33',
        )

        self.client.post(
            '/admin/offres/offer/',
            {
                'action': 'rescreen_offers',
                '_selected_action': [str(offer.pk)],
            },
            follow=True,
        )

        offer.refresh_from_db()
        self.assertTrue(offer.quarantine_reason)

    def test_mark_reviewed_allows_publication(self):
        offer = make_offer(status=Offer.STATUS_PENDING)
        offer.quarantine_reason = 'Numéro présent sur la liste noire.'
        offer.quarantined_at = timezone.now()
        offer.save()

        self.client.post(
            '/admin/offres/offer/',
            {
                'action': 'mark_quarantine_reviewed',
                '_selected_action': [str(offer.pk)],
            },
            follow=True,
        )

        offer.refresh_from_db()
        self.assertIsNotNone(offer.quarantine_reviewed_at)
        self.assertEqual(offer.quarantine_reviewed_by, self.user)

    def test_clear_quarantine_removes_the_reason(self):
        offer = make_offer(status=Offer.STATUS_PENDING)
        offer.quarantine_reason = 'Motif de test'
        offer.quarantined_at = timezone.now()
        offer.save()

        self.client.post(
            '/admin/offres/offer/',
            {
                'action': 'clear_quarantine',
                '_selected_action': [str(offer.pk)],
            },
            follow=True,
        )

        offer.refresh_from_db()
        self.assertFalse(offer.quarantine_reason)
        self.assertIsNone(offer.quarantined_at)

    def test_quarantine_badge_appears_in_the_list(self):
        offer = make_offer(status=Offer.STATUS_PENDING)
        offer.quarantine_reason = 'Motif de test'
        offer.quarantined_at = timezone.now()
        offer.save()

        response = self.client.get('/admin/offres/offer/')

        self.assertContains(response, 'En quarantaine')


class VerificationPanelRenderingTest(TestCase):
    """Le panneau de verification doit etre rendu comme du HTML."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_panel_is_rendered_as_html_not_escaped_text(self):
        offer = make_offer(status=Offer.STATUS_PENDING)

        response = self.client.get('/admin/offres/offer/%s/change/' % offer.pk)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fj-admin-checks')
        self.assertContains(response, 'fj-admin-check')
        self.assertNotContains(response, '&lt;div class=&quot;fj-admin-check')

    def test_quarantine_reason_appears_in_the_panel(self):
        offer = make_offer(status=Offer.STATUS_PENDING)
        offer.quarantine_reason = 'Motif de test'
        offer.quarantined_at = timezone.now()
        offer.save()

        response = self.client.get('/admin/offres/offer/%s/change/' % offer.pk)

        self.assertContains(response, 'publication refus')
        self.assertContains(response, 'Motif de test')
