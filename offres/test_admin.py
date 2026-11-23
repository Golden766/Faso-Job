import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Offer, OfferReport, OfferSubmission


def make_offer(title, status=Offer.STATUS_PENDING, **overrides):
    data = {
        'title': title,
        'company_name': 'Employeur de test',
        'description': 'Description de test.',
        'status': status,
    }
    data.update(overrides)
    return Offer.objects.create(**data)


class ActivityReportAccessTest(TestCase):
    def test_activity_report_requires_staff(self):
        response = self.client.get(reverse('admin-activity-report'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.url)

    def test_activity_csv_requires_staff(self):
        response = self.client.get(reverse('admin-activity-report-csv'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.url)

    def test_non_staff_user_cannot_open_report(self):
        user = get_user_model().objects.create_user(
            username='visiteur', password='test-password'
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin-activity-report'))

        self.assertEqual(response.status_code, 302)

    def test_moderator_can_open_report_but_not_manage_users(self):
        user = get_user_model().objects.create_user(
            username='moderatrice', password='test-password'
        )
        call_command(
            'setup_editorial_roles',
            '--username=moderatrice',
            '--role=moderator',
            stdout=StringIO(),
        )
        self.client.force_login(user)

        report_response = self.client.get(reverse('admin-activity-report'))
        user_response = self.client.get(reverse('admin:auth_user_changelist'))

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(user_response.status_code, 403)


class ActivityReportContentTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='administrateur',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)

        self.published = make_offer(
            'Offre publiée',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )
        make_offer('Offre en attente', status=Offer.STATUS_PENDING)
        make_offer('Offre rejetée', status=Offer.STATUS_REJECTED)
        OfferSubmission.objects.create(
            title='Proposition acceptée',
            company_name='Entreprise A',
            status=OfferSubmission.STATUS_ACCEPTED,
        )
        OfferSubmission.objects.create(
            title='Proposition en attente',
            company_name='Entreprise B',
            status=OfferSubmission.STATUS_PENDING,
        )
        OfferReport.objects.create(
            reason=OfferReport.REASON_FEES,
            suspect_title='Annonce frauduleuse',
            status=OfferReport.STATUS_OPEN,
        )
        OfferReport.objects.create(
            reason=OfferReport.REASON_MLM,
            suspect_organization='Réseau suspect',
            status=OfferReport.STATUS_RESOLVED,
        )

    def test_report_counts_real_database_values(self):
        response = self.client.get(reverse('admin-activity-report'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['offer_total'], 3)
        self.assertEqual(response.context['published_total'], 1)
        self.assertEqual(response.context['submission_total'], 2)
        self.assertEqual(response.context['report_total'], 2)
        self.assertEqual(response.context['open_reports'], 1)
        self.assertEqual(response.context['handled_reports'], 1)
        self.assertEqual(response.context['acceptance_rate'], 50.0)
        self.assertEqual(response.context['handling_rate'], 50.0)
        self.assertEqual(response.context['verification_rate'], 100.0)

    def test_report_page_shows_real_sections(self):
        response = self.client.get(reverse('admin-activity-report'))

        self.assertContains(response, 'Rapport d’activité')
        self.assertContains(response, 'Activité des six derniers mois')
        self.assertContains(response, 'Statut des offres')
        self.assertContains(response, 'Motifs de signalement')
        self.assertContains(response, 'Exporter en CSV')
        self.assertContains(response, 'Offres publiées')

    def test_csv_export_contains_real_counts_and_bom(self):
        response = self.client.get(reverse('admin-activity-report-csv'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('.csv', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))

        content = response.content.decode('utf-8-sig')
        self.assertIn('Indicateur;Valeur', content)
        self.assertIn('Offres publiées;1', content)
        self.assertIn('Offres enregistrées;3', content)
        self.assertIn('Propositions reçues;2', content)
        self.assertIn('Signalements reçus;2', content)
        self.assertIn(
            'Mois;Offres publiées;Propositions reçues;Signalements reçus',
            content,
        )

    def test_dashboard_shows_open_report_alert_and_activity_link(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 signalement à traiter')
        self.assertContains(response, reverse('admin-activity-report'))
        self.assertContains(response, reverse('admin-activity-report-csv'))

    def test_offer_changelist_uses_status_badges(self):
        response = self.client.get(reverse('admin:offres_offer_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fj-admin-badge--success')
        self.assertContains(response, 'Publiée')
        self.assertContains(response, 'Source vérifiée')


class ExpiredOffersAdminTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin-offres-expirees',
            email='expired@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)

    def make_published_offer(self, title, **overrides):
        data = {
            'title': title,
            'company_name': 'Employeur de test',
            'description': 'Description de test.',
            'status': Offer.STATUS_PUBLISHED,
            'is_source_confirmed': True,
        }
        data.update(overrides)
        return Offer.objects.create(**data)

    def test_dashboard_separates_active_and_expired_offers(self):
        today = timezone.localdate()
        self.make_published_offer(
            'Offre expirée',
            deadline=today - datetime.timedelta(days=1),
        )
        self.make_published_offer(
            'Offre active',
            deadline=today + datetime.timedelta(days=1),
        )

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_offers_count'], 1)
        self.assertEqual(response.context['expired_offers_count'], 1)
        self.assertContains(response, reverse('admin-expired-offers'))

    def test_expired_list_offers_edit_and_archive_actions(self):
        expired = self.make_published_offer(
            'Offre à traiter',
            deadline=timezone.localdate() - datetime.timedelta(days=1),
        )
        self.make_published_offer(
            'Offre encore active',
            deadline=timezone.localdate() + datetime.timedelta(days=1),
        )
        self.make_published_offer(
            'Offre déjà archivée',
            deadline=timezone.localdate() - datetime.timedelta(days=2),
            status=Offer.STATUS_ARCHIVED,
        )
        self.make_published_offer(
            'Offre à échéance sans heure',
            deadline=timezone.localdate(),
        )
        self.make_published_offer(
            'Offre expirée ce matin',
            deadline=timezone.localdate(),
            deadline_time=datetime.time(0, 0),
        )

        response = self.client.get(reverse('admin-expired-offers'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Offre à traiter')
        self.assertContains(response, 'Offre expirée ce matin')
        self.assertNotContains(response, 'Offre encore active')
        self.assertNotContains(response, 'Offre déjà archivée')
        self.assertNotContains(response, 'Offre à échéance sans heure')
        self.assertContains(
            response,
            reverse('admin:offres_offer_change', args=[expired.pk]),
        )
        self.assertContains(response, 'Archiver')

        archive_response = self.client.post(
            reverse('admin-expired-offers'),
            {'offer_id': expired.pk},
        )

        self.assertRedirects(archive_response, reverse('admin-expired-offers'))
        expired.refresh_from_db()
        self.assertEqual(expired.status, Offer.STATUS_ARCHIVED)
        self.assertFalse(expired.is_published)
        self.assertNotContains(
            self.client.get(reverse('admin-expired-offers')),
            'Offre à traiter',
        )

    def test_expired_offer_is_available_from_the_admin_sidebar(self):
        response = self.client.get(reverse('admin:offres_offer_changelist'))

        self.assertContains(
            response,
            reverse('admin-expired-offers'),
            status_code=200,
        )

    def test_view_only_staff_cannot_archive_expired_offers(self):
        offer = self.make_published_offer(
            'Offre expirée en lecture seule',
            deadline=timezone.localdate() - datetime.timedelta(days=1),
        )
        viewer = get_user_model().objects.create_user(
            username='lecteur-offres-expirees',
            password='test-password',
            is_staff=True,
        )
        view_permission = Permission.objects.get(
            content_type__app_label='offres',
            codename='view_offer',
        )
        viewer.user_permissions.add(view_permission)
        self.client.force_login(viewer)

        response = self.client.get(reverse('admin-expired-offers'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse('admin:offres_offer_change', args=[offer.pk]),
        )
        self.assertNotContains(response, 'expired-offer-archive')
        self.assertEqual(
            self.client.post(
                reverse('admin-expired-offers'),
                {'offer_id': offer.pk},
            ).status_code,
            403,
        )
