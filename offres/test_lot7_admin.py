"""Tests du lot 7 — administration restylée.

Couvre la liste noire, les paramètres de la plateforme, le panneau de
vérification des offres et la matrice des rôles éditoriaux.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import (
    BlacklistedContact,
    Offer,
    OfferReport,
    OfferSubmission,
    PlatformSettings,
)


def make_offer(title, status=Offer.STATUS_PENDING, **overrides):
    data = {
        'title': title,
        'company_name': 'Employeur de test',
        'description': 'Description de test.',
        'status': status,
    }
    data.update(overrides)
    return Offer.objects.create(**data)


def create_editorial_user(username, role):
    user = get_user_model().objects.create_user(
        username=username,
        password='test-password',
    )
    call_command(
        'setup_editorial_roles',
        f'--username={username}',
        f'--role={role}',
        stdout=StringIO(),
    )
    user.refresh_from_db()
    return user


class BlacklistModelTest(TestCase):
    def test_contact_requires_a_phone_number(self):
        contact = BlacklistedContact(phone_number='  ', organization='Entité')

        with self.assertRaises(Exception):
            contact.full_clean()

    def test_contact_requires_an_organization(self):
        contact = BlacklistedContact(phone_number='+226 70 00 00 00', organization='  ')

        with self.assertRaises(Exception):
            contact.full_clean()

    def test_normalized_number_keeps_only_digits(self):
        contact = BlacklistedContact(
            phone_number='+226 70-00 00.00',
            organization='Entité',
        )

        self.assertEqual(contact.normalized_number, '22670000000')

    def test_status_starts_under_surveillance_not_blocked(self):
        """Un contact inscrit n'est jamais bloqué automatiquement."""
        contact = BlacklistedContact.objects.create(
            phone_number='+226 70 00 00 00',
            organization='Entité',
        )

        self.assertEqual(contact.status, BlacklistedContact.STATUS_WATCH)

    def test_alert_date_follows_the_checkbox(self):
        contact = BlacklistedContact.objects.create(
            phone_number='+226 70 00 00 00',
            organization='Entite',
        )
        self.assertIsNone(contact.alert_disseminated_at)

        contact.alert_disseminated = True
        contact.save()
        contact.refresh_from_db()
        self.assertIsNotNone(contact.alert_disseminated_at)

        contact.alert_disseminated = False
        contact.save()
        contact.refresh_from_db()
        self.assertIsNone(contact.alert_disseminated_at)

    def test_alert_dissemination_is_manual(self):
        contact = BlacklistedContact.objects.create(
            phone_number='+226 70 00 00 00',
            organization='Entité',
        )

        self.assertFalse(contact.alert_disseminated)
        self.assertIsNone(contact.alert_disseminated_at)


class PlatformSettingsModelTest(TestCase):
    def test_settings_are_a_single_row(self):
        first = PlatformSettings.load()
        second = PlatformSettings.load()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PlatformSettings.objects.count(), 1)

    def test_saving_never_creates_a_second_row(self):
        PlatformSettings.load()
        other = PlatformSettings(site_name='Autre nom')

        other.save()

        self.assertEqual(PlatformSettings.objects.count(), 1)
        self.assertEqual(PlatformSettings.objects.first().site_name, 'Autre nom')

    def test_defaults_match_the_public_brand(self):
        settings = PlatformSettings.load()

        self.assertEqual(settings.site_name, 'Faso Job')
        self.assertEqual(
            settings.site_tagline,
            'Opportunités professionnelles au Burkina Faso',
        )

    def test_reset_restores_defaults_and_keeps_one_row(self):
        settings = PlatformSettings.load()
        settings.site_name = 'Nom modifié'
        settings.save()

        PlatformSettings.reset_to_defaults()

        self.assertEqual(PlatformSettings.objects.count(), 1)
        self.assertEqual(PlatformSettings.load().site_name, 'Faso Job')


class BlacklistAdminTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='administrateur',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_list_is_reachable(self):
        response = self.client.get(
            reverse('admin:offres_blacklistedcontact_changelist')
        )

        self.assertEqual(response.status_code, 200)

    def test_admin_is_not_public(self):
        self.client.logout()

        response = self.client.get(
            reverse('admin:offres_blacklistedcontact_changelist')
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.url)

    def test_add_action_creates_a_blacklist_entry_from_a_report(self):
        report = OfferReport.objects.create(
            reason=OfferReport.REASON_FEES,
            suspect_title='Annonce frauduleuse',
            suspect_organization='Société fictive',
            suspect_phone='+226 70 11 22 33',
            details='Demande de frais de dossier.',
        )

        response = self.client.post(
            reverse('admin:offres_offerreport_changelist'),
            {
                'action': 'add_to_blacklist',
                '_selected_action': [str(report.pk)],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        entry = BlacklistedContact.objects.get()
        self.assertEqual(entry.phone_number, '+226 70 11 22 33')
        self.assertEqual(entry.organization, 'Société fictive')
        self.assertEqual(entry.report, report)
        self.assertEqual(entry.status, BlacklistedContact.STATUS_WATCH)

    def test_add_action_does_not_change_the_offer_status(self):
        """Inscrire un contact ne retire jamais une offre de la publication."""
        offer = make_offer(
            'Offre publiée',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )
        report = OfferReport.objects.create(
            reason=OfferReport.REASON_FEES,
            offer=offer,
            suspect_title='Annonce frauduleuse',
            suspect_phone='+226 70 11 22 33',
            details='Demande de frais de dossier.',
        )

        self.client.post(
            reverse('admin:offres_offerreport_changelist'),
            {
                'action': 'add_to_blacklist',
                '_selected_action': [str(report.pk)],
            },
            follow=True,
        )

        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)
        self.assertTrue(offer.is_published)

    def test_add_action_does_not_change_the_report_status(self):
        report = OfferReport.objects.create(
            reason=OfferReport.REASON_FEES,
            suspect_title='Annonce frauduleuse',
            suspect_phone='+226 70 11 22 33',
            details='Demande de frais de dossier.',
        )

        self.client.post(
            reverse('admin:offres_offerreport_changelist'),
            {
                'action': 'add_to_blacklist',
                '_selected_action': [str(report.pk)],
            },
            follow=True,
        )

        report.refresh_from_db()
        self.assertEqual(report.status, OfferReport.STATUS_OPEN)

    def test_add_action_ignores_duplicate_numbers(self):
        for _ in range(2):
            report = OfferReport.objects.create(
                reason=OfferReport.REASON_FEES,
                suspect_title='Annonce frauduleuse',
                suspect_phone='+226 70 11 22 33',
                details='Demande de frais de dossier.',
            )
            self.client.post(
                reverse('admin:offres_offerreport_changelist'),
                {
                    'action': 'add_to_blacklist',
                    '_selected_action': [str(report.pk)],
                },
                follow=True,
            )

        self.assertEqual(BlacklistedContact.objects.count(), 1)

    def test_add_action_skips_reports_without_a_phone_number(self):
        report = OfferReport.objects.create(
            reason=OfferReport.REASON_FAKE_COMPANY,
            suspect_title='Annonce sans contact',
            details='Aucune coordonnée fournie par le déclarant.',
        )

        self.client.post(
            reverse('admin:offres_offerreport_changelist'),
            {
                'action': 'add_to_blacklist',
                '_selected_action': [str(report.pk)],
            },
            follow=True,
        )

        self.assertEqual(BlacklistedContact.objects.count(), 0)


class PlatformSettingsAdminTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='administrateur',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_change_view_is_reachable(self):
        PlatformSettings.load()

        response = self.client.get(
            reverse('admin:offres_platformsettings_change', args=[1])
        )

        self.assertEqual(response.status_code, 200)

    def test_list_redirects_to_the_single_row(self):
        PlatformSettings.load()

        response = self.client.get(
            reverse('admin:offres_platformsettings_changelist')
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse('admin:offres_platformsettings_change', args=[1]),
            response.url,
        )

    def test_add_is_refused_once_the_row_exists(self):
        PlatformSettings.load()

        response = self.client.get(
            reverse('admin:offres_platformsettings_add')
        )

        self.assertEqual(response.status_code, 403)

    def test_delete_is_refused(self):
        PlatformSettings.load()

        response = self.client.get(
            reverse('admin:offres_platformsettings_delete', args=[1])
        )

        self.assertEqual(response.status_code, 403)

    def test_settings_can_be_updated(self):
        PlatformSettings.load()

        response = self.client.post(
            reverse('admin:offres_platformsettings_change', args=[1]),
            {
                'site_name': 'Faso Job',
                'site_tagline': 'Opportunités professionnelles au Burkina Faso',
                'contact_email': 'contact@example.bf',
                'alert_email': 'alerte@example.bf',
                'emergency_phone': '+226 00 00 00 00',
                'emergency_whatsapp': '+226 00 00 00 00',
                'moderation_guideline': 'Vérifier la source avant publication.',
                'quarantine_keywords': 'caution',
                'auto_archive_days': '30',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        settings = PlatformSettings.load()
        self.assertEqual(settings.contact_email, 'contact@example.bf')
        self.assertEqual(
            settings.moderation_guideline,
            'Vérifier la source avant publication.',
        )
        self.assertEqual(PlatformSettings.objects.count(), 1)


class VerificationPanelTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='administrateur',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_panel_shows_the_three_distinct_checks(self):
        offer = make_offer(
            'Offre contrôlée',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )

        response = self.client.get(
            reverse('admin:offres_offer_change', args=[offer.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Source vérifiée')
        self.assertContains(response, 'Employeur vérifié')
        self.assertContains(response, 'Toujours disponible')

    def test_panel_warns_when_publication_requirements_are_missing(self):
        offer = make_offer(
            'Offre sans vérification',
            status=Offer.STATUS_PENDING,
            is_source_confirmed=False,
            is_employer_verified=False,
        )

        response = self.client.get(
            reverse('admin:offres_offer_change', args=[offer.pk])
        )

        self.assertContains(response, 'Publication impossible')

    def test_panel_counts_open_reports(self):
        offer = make_offer(
            'Offre signalée',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )
        OfferReport.objects.create(
            offer=offer,
            reason=OfferReport.REASON_FEES,
            suspect_title='Annonce frauduleuse',
            details='Demande de frais de dossier.',
        )

        response = self.client.get(
            reverse('admin:offres_offer_change', args=[offer.pk])
        )

        self.assertContains(response, 'Signalements en cours')


class DashboardBlacklistTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='administrateur',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_dashboard_shows_real_blacklist_counts(self):
        BlacklistedContact.objects.create(
            phone_number='+226 70 00 00 00',
            organization='Entité bloquée',
            status=BlacklistedContact.STATUS_BLOCKED,
        )
        BlacklistedContact.objects.create(
            phone_number='+226 70 00 00 01',
            organization='Entité surveillée',
            status=BlacklistedContact.STATUS_WATCH,
        )

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['blacklist_total_count'], 2)
        self.assertEqual(response.context['blacklist_blocked_count'], 1)
        self.assertEqual(response.context['blacklist_watch_count'], 1)
        self.assertContains(response, 'Liste noire')

    def test_dashboard_shows_an_empty_state_without_entries(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['blacklist_total_count'], 0)


class EditorialRolesPermissionTest(TestCase):
    def test_editor_can_view_but_not_change_the_blacklist(self):
        user = create_editorial_user('editeur', 'editor')
        self.client.force_login(user)

        list_response = self.client.get(
            reverse('admin:offres_blacklistedcontact_changelist')
        )
        entry = BlacklistedContact.objects.create(
            phone_number='+226 70 00 00 00',
            organization='Entité',
        )
        change_url = reverse('admin:offres_blacklistedcontact_change', args=[entry.pk])

        self.assertEqual(list_response.status_code, 200)
        # L'éditeur peut consulter l'entrée, mais pas la modifier.
        self.assertEqual(self.client.get(change_url).status_code, 200)
        self.assertEqual(
            self.client.post(change_url, {'status': 'blocked'}).status_code,
            403,
        )
        entry.refresh_from_db()
        self.assertEqual(entry.status, BlacklistedContact.STATUS_WATCH)

    def test_moderator_can_change_the_blacklist(self):
        user = create_editorial_user('moderateur', 'moderator')
        self.client.force_login(user)
        entry = BlacklistedContact.objects.create(
            phone_number='+226 70 00 00 00',
            organization='Entité',
        )

        response = self.client.get(
            reverse('admin:offres_blacklistedcontact_change', args=[entry.pk])
        )

        self.assertEqual(response.status_code, 200)

    def test_moderator_can_change_the_platform_settings(self):
        user = create_editorial_user('moderatrice', 'moderator')
        self.client.force_login(user)
        PlatformSettings.load()

        response = self.client.get(
            reverse('admin:offres_platformsettings_change', args=[1])
        )

        self.assertEqual(response.status_code, 200)

    def test_editor_can_view_the_platform_settings(self):
        user = create_editorial_user('editeur2', 'editor')
        self.client.force_login(user)
        PlatformSettings.load()

        response = self.client.get(
            reverse('admin:offres_platformsettings_change', args=[1])
        )

        self.assertEqual(response.status_code, 200)

    def test_moderator_cannot_manage_users(self):
        user = create_editorial_user('moderateur2', 'moderator')
        self.client.force_login(user)

        response = self.client.get(reverse('admin:auth_user_changelist'))

        self.assertEqual(response.status_code, 403)

    def test_blacklist_is_absent_from_the_sidebar_without_permission(self):
        """Un compte staff sans permission ne voit pas le registre."""
        from django.contrib.auth.models import Permission

        user = get_user_model().objects.create_user(
            username='lecteur-seul',
            password='test-password',
            is_staff=True,
        )
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label='offres',
                codename='view_offer',
            )
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse('admin:offres_blacklistedcontact_changelist'),
        )

    def test_editor_sees_the_blacklist_in_the_sidebar(self):
        user = create_editorial_user('editeur3', 'editor')
        self.client.force_login(user)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('admin:offres_blacklistedcontact_changelist'),
        )


class PublicSiteStaysPrivateTest(TestCase):
    """La liste noire et les paramètres ne doivent jamais fuiter au public."""

    def test_blacklist_has_no_public_route(self):
        for path in ('/liste-noire/', '/admin/liste-noire/'):
            response = self.client.get(path)
            self.assertNotEqual(response.status_code, 200)

    def test_public_pages_do_not_mention_the_blacklist(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Liste noire')

    def test_platform_settings_are_not_exposed_publicly(self):
        PlatformSettings.load().site_name = 'Faso Job'

        response = self.client.get(reverse('catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Paramètres de la plateforme')


class SubmissionAcceptanceStillCreatesPendingOfferTest(TestCase):
    """Règle métier : une soumission acceptée reste à contrôler."""

    def test_accepting_a_submission_creates_a_pending_offer(self):
        user = get_user_model().objects.create_superuser(
            username='administrateur',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(user)
        submission = OfferSubmission.objects.create(
            title='Proposition reçue',
            company_name='Entreprise A',
            location='Ouagadougou',
            employment_type='CDI',
            application_method='whatsapp',
            whatsapp_number='+226 70 00 00 00',
        )

        self.client.post(
            reverse('admin:offres_offersubmission_changelist'),
            {
                'action': 'accept_submission',
                '_selected_action': [str(submission.pk)],
            },
            follow=True,
        )

        submission.refresh_from_db()
        self.assertEqual(submission.status, OfferSubmission.STATUS_ACCEPTED)
        offer = submission.offer
        self.assertIsNotNone(offer)
        self.assertEqual(offer.status, Offer.STATUS_PENDING)
        self.assertFalse(offer.is_published)
        self.assertFalse(offer.is_source_confirmed)
        self.assertFalse(offer.is_employer_verified)
