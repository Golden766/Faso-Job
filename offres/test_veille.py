"""Tests du lot 1 : modeles de la veille automatisee.

Le lot 1 pose les fondations :

- les champs de surveillance sur `Source`, avec la regle d autorisation
  explicite ;
- les trois champs d analyse supplementaires sur `Offer` ;
- `CollectedAnnouncement`, la trace de ce que la veille a trouve ;
- `VeilleRun`, l historique des passages de collecte.

Ces tests verrouillent surtout deux garanties : une annonce collectee
n est jamais publiee automatiquement, et la trace d une collecte survit
a la suppression de sa source.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import (
    CollectedAnnouncement,
    Offer,
    Source,
    VeilleRun,
)


class SourceWatchTestCase(TestCase):
    """Regles de surveillance d une source."""

    def test_a_new_source_is_not_watchable(self):
        source = Source.objects.create(name='Presse du pays')

        self.assertFalse(source.is_watched)
        self.assertFalse(source.is_watchable)

    def test_a_watched_source_with_authorization_is_watchable(self):
        source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.bf/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='Accord de republication signe le 3 mars 2026.',
        )

        self.assertTrue(source.is_watchable)

    def test_a_watched_source_without_authorization_is_not_watchable(self):
        """Une surveillance ne demarre pas sans autorisation ecrite."""
        source = Source.objects.create(
            name='Emploi du Faso',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
        )

        self.assertFalse(source.is_watchable)

    def test_a_blank_authorization_does_not_count(self):
        """Une note made de spaces n est pas une autorisation."""
        source = Source.objects.create(
            name='Emploi du Faso',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='    \n  ',
        )

        self.assertFalse(source.is_watchable)

    def test_manual_modes_are_not_watchable(self):
        """Facebook, WhatsApp et la saisie manuelle restent semi-automatiques."""
        for method in (
            Source.COLLECTION_METHOD_FACEBOOK,
            Source.COLLECTION_METHOD_WHATSAPP,
            Source.COLLECTION_METHOD_MANUAL_URL,
            Source.COLLECTION_METHOD_MANUAL_TEXT,
        ):
            with self.subTest(method=method):
                source = Source.objects.create(
                    name=f'Source {method}',
                    collection_method=method,
                    is_watched=True,
                    authorization_note='Autorisation accordee.',
                )

                self.assertFalse(source.is_watchable)


class OfferAnalysisFieldsTestCase(TestCase):
    """Les trois champs ajoutes a l offre."""

    def test_the_new_fields_are_empty_by_default(self):
        offer = Offer.objects.create(
            title='Assistant comptable',
            company_name='Entreprise test',
            description='Description',
            status=Offer.STATUS_DRAFT,
        )

        self.assertEqual(offer.missions, '')
        self.assertEqual(offer.required_profile, '')
        self.assertEqual(offer.required_education, '')

    def test_a_draft_offer_keeps_the_extracted_fields(self):
        offer = Offer.objects.create(
            title='Assistant comptable',
            company_name='Entreprise test',
            description='Description',
            missions='Tenir la comptabilite',
            required_profile='Bac+2 en comptabilite',
            required_education='Licence',
            status=Offer.STATUS_DRAFT,
        )

        offer.refresh_from_db()

        self.assertEqual(offer.missions, 'Tenir la comptabilite')
        self.assertEqual(offer.required_profile, 'Bac+2 en comptabilite')
        self.assertEqual(offer.required_education, 'Licence')


class CollectedOfferSafetyTestCase(TestCase):
    """Une annonce collectee ne part pas seule sur le site public."""

    def test_a_draft_offer_is_not_visible_on_the_public_site(self):
        offer = Offer.objects.create(
            title='Offre collectee',
            company_name='Entreprise test',
            description='Description',
            status=Offer.STATUS_DRAFT,
        )

        self.assertNotIn(offer, Offer.objects.public(timezone.localtime()))

    def test_a_draft_offer_cannot_be_published_without_verification(self):
        """La regle de publication exige toujours un controle humain."""
        offer = Offer(
            title='Offre collectee',
            company_name='Entreprise test',
            description='Description',
            status=Offer.STATUS_PUBLISHED,
        )

        with self.assertRaises(ValidationError):
            offer.full_clean()


class CollectedAnnouncementTestCase(TestCase):
    """La trace de collecte."""

    def setUp(self):
        self.source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.bf/emplois/1',
        )

    def create_announcement(self, **kwargs):
        defaults = {
            'source': self.source,
            'source_name': 'Emploi du Faso',
            'source_url': 'https://exemple.bf/emplois/1',
            'collection_method': Source.COLLECTION_METHOD_WEB,
            'raw_content': 'Nous recrutons un assistant comptable.',
            'content_hash': 'a' * 64,
        }
        defaults.update(kwargs)
        return CollectedAnnouncement.objects.create(**defaults)

    def test_the_default_state_is_detected(self):
        announcement = self.create_announcement()

        self.assertEqual(announcement.status, CollectedAnnouncement.STATUS_DETECTED)
        self.assertEqual(
            announcement.extraction_status,
            CollectedAnnouncement.EXTRACTION_PENDING,
        )
        self.assertEqual(
            announcement.duplicate_status,
            CollectedAnnouncement.DUPLICATE_NONE,
        )
        self.assertFalse(announcement.has_extraction)
        self.assertFalse(announcement.is_duplicate_flagged)

    def test_the_original_content_and_the_provenance_are_kept(self):
        announcement = self.create_announcement()

        self.assertEqual(
            announcement.raw_content,
            'Nous recrutons un assistant comptable.',
        )
        self.assertEqual(announcement.source_name, 'Emploi du Faso')
        self.assertEqual(
            announcement.source_url,
            'https://exemple.bf/emplois/1',
        )
        self.assertEqual(announcement.collection_method, 'web')
        self.assertIsNotNone(announcement.collected_at)

    def test_the_trace_survives_the_deletion_of_the_source(self):
        """Supprimer la source ne doit pas effacer l origine de l annonce."""
        announcement = self.create_announcement()
        source_id = self.source.pk

        Source.objects.filter(pk=source_id).delete()

        announcement.refresh_from_db()

        self.assertIsNone(announcement.source_id)
        self.assertEqual(announcement.source_name, 'Emploi du Faso')
        self.assertEqual(
            announcement.source_url,
            'https://exemple.bf/emplois/1',
        )

    def test_the_announcement_points_to_the_draft_offer(self):
        offer = Offer.objects.create(
            title='Offre collectee',
            company_name='Entreprise test',
            description='Description',
            status=Offer.STATUS_DRAFT,
        )
        announcement = self.create_announcement(offer=offer)

        self.assertEqual(announcement.offer, offer)
        self.assertIn(announcement, offer.collected_announcements.all())

    def test_a_suspected_duplicate_is_flagged(self):
        offer = Offer.objects.create(
            title='Offre deja connue',
            company_name='Entreprise test',
            description='Description',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )
        announcement = self.create_announcement(
            duplicate_status=CollectedAnnouncement.DUPLICATE_SUSPECTED,
            duplicate_of=offer,
            duplicate_score=0.87,
            duplicate_reasons='Titre et entreprise identiques',
        )

        self.assertTrue(announcement.is_duplicate_flagged)
        self.assertEqual(announcement.duplicate_of, offer)

    def test_mark_reviewed_records_the_user_and_the_date(self):
        user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
        )
        announcement = self.create_announcement()

        announcement.mark_reviewed(user)

        self.assertEqual(announcement.reviewed_by, user)
        self.assertIsNotNone(announcement.reviewed_at)


class VeilleRunTestCase(TestCase):
    """L historique des passages de collecte."""

    def test_a_new_run_is_running_and_manual(self):
        run = VeilleRun.objects.create(started_at=timezone.now())

        self.assertEqual(run.status, VeilleRun.STATUS_RUNNING)
        self.assertEqual(run.triggered_by, VeilleRun.TRIGGER_MANUAL)
        self.assertIsNone(run.finished_at)

    def test_the_counters_start_at_zero(self):
        run = VeilleRun.objects.create(started_at=timezone.now())

        self.assertEqual(run.found_count, 0)
        self.assertEqual(run.created_count, 0)
        self.assertEqual(run.duplicate_count, 0)
        self.assertEqual(run.error_count, 0)
        self.assertEqual(run.duration_seconds, 0)

    def test_a_run_keeps_its_source(self):
        source = Source.objects.create(name='Emploi du Faso')
        run = VeilleRun.objects.create(
            source=source,
            started_at=timezone.now(),
            status=VeilleRun.STATUS_SUCCESS,
            found_count=4,
            created_count=2,
        )

        self.assertEqual(run.source, source)
        self.assertEqual(run.found_count, 4)
        self.assertEqual(run.created_count, 2)
