"""Tests du croisement automatique liste noire et offres (lot 8, suite).

Couvre le comportement attendu :

- une offre ou une proposition correspondant a un contact de la liste
  noire est signalee des sa creation ;
- un contact bloque definitivement ne peut jamais etre publie ;
- un contact sous surveillance bloque la publication tant qu un controle
  humain n est pas enregistre ;
- inscrire un contact sur la liste noire signale aussitot les offres
  deja publiees qui utilisent ses coordonnees ;
- le statut d une offre publiee n est jamais modifie automatiquement.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from . import moderation
from .models import (
    BlacklistedContact,
    Offer,
    OfferSubmission,
)


def make_offer(**overrides):
    data = {
        'title': 'Offre de test',
        'company_name': 'Employeur de test',
        'description': 'Description de test.',
        'status': Offer.STATUS_PENDING,
    }
    data.update(overrides)
    return Offer.objects.create(**data)


def make_blacklist(phone='+226 70 11 22 33', organization='Entité test',
                   status=BlacklistedContact.STATUS_WATCH, email=''):
    return BlacklistedContact.objects.create(
        phone_number=phone,
        organization=organization,
        email=email,
        status=status,
    )


class AutomaticCrossingOnOfferTest(TestCase):
    def test_offer_matching_blacklist_is_flagged_on_creation(self):
        make_blacklist(phone='+226 70 11 22 33')

        offer = make_offer(application_phone='+226 70 11 22 33')

        self.assertTrue(offer.quarantine_reason)
        self.assertIn('liste noire', offer.quarantine_reason)
        self.assertIsNotNone(offer.quarantined_at)

    def test_severity_is_recorded(self):
        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_BLOCKED,
        )

        offer = make_offer(application_phone='+226 70 11 22 33')

        self.assertEqual(offer.quarantine_severity, moderation.SEVERITY_BLOCKED)

    def test_watch_severity_for_surveillance_contact(self):
        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_WATCH,
        )

        offer = make_offer(application_phone='+226 70 11 22 33')

        self.assertEqual(offer.quarantine_severity, moderation.SEVERITY_WATCH)

    def test_clean_offer_is_not_flagged(self):
        make_blacklist(phone='+226 70 11 22 33')

        offer = make_offer(application_phone='+226 70 99 88 77')

        self.assertFalse(offer.quarantine_reason)
        self.assertEqual(offer.quarantine_severity, '')

    def test_keyword_triggers_quarantine_on_creation(self):
        from .models import PlatformSettings

        settings_row = PlatformSettings.load()
        settings_row.quarantine_keywords = 'frais de dossier'
        settings_row.save()

        offer = make_offer(description='Merci de régler des frais de dossier.')

        self.assertTrue(offer.quarantine_reason)
        self.assertIn('frais de dossier', offer.quarantine_reason)

    def test_blacklisted_offer_cannot_be_published(self):
        make_blacklist(phone='+226 70 11 22 33')

        offer = make_offer(application_phone='+226 70 11 22 33')

        with self.assertRaises(ValidationError):
            offer.status = Offer.STATUS_PUBLISHED
            offer.save()

    def test_blocked_contact_can_never_be_published(self):
        """Meme apres un controle humain, un contact bloque definitivement
        ne peut pas etre publie."""
        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_BLOCKED,
        )

        offer = make_offer(application_phone='+226 70 11 22 33')

        with self.assertRaises(ValidationError):
            offer.status = Offer.STATUS_PUBLISHED
            offer.quarantine_reviewed_at = moderation._now()
            offer.save()

    def test_watch_contact_can_be_published_after_review(self):
        from django.utils import timezone

        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_WATCH,
        )

        offer = make_offer(
            application_phone='+226 70 11 22 33',
            is_source_confirmed=True,
        )
        offer.quarantine_reviewed_at = timezone.now()

        offer.status = Offer.STATUS_PUBLISHED
        offer.save()
        offer.refresh_from_db()

        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)


class AutomaticCrossingOnSubmissionTest(TestCase):
    def test_submission_matching_blacklist_is_flagged(self):
        make_blacklist(phone='+226 70 11 22 33')

        submission = OfferSubmission.objects.create(
            title='Proposition',
            company_name='Entreprise',
            contact_phone='+226 70 11 22 33',
        )

        self.assertTrue(submission.quarantine_reason)
        self.assertEqual(
            submission.quarantine_severity,
            moderation.SEVERITY_WATCH,
        )

    def test_submission_stays_pending_when_flagged(self):
        make_blacklist(phone='+226 70 11 22 33')

        submission = OfferSubmission.objects.create(
            title='Proposition',
            company_name='Entreprise',
            contact_phone='+226 70 11 22 33',
        )

        self.assertEqual(submission.status, OfferSubmission.STATUS_PENDING)
        self.assertIsNone(submission.offer_id)

    def test_blocked_submission_carries_blocked_severity(self):
        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_BLOCKED,
        )

        submission = OfferSubmission.objects.create(
            title='Proposition',
            company_name='Entreprise',
            contact_phone='+226 70 11 22 33',
        )

        self.assertEqual(
            submission.quarantine_severity,
            moderation.SEVERITY_BLOCKED,
        )


class BlacklistChangeTriggersRescreenTest(TestCase):
    def test_adding_a_contact_flags_already_published_offers(self):
        """Inscrire un contact signale aussitot les offres concernees."""
        offer = make_offer(
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
            application_phone='+226 70 11 22 33',
        )

        self.assertFalse(offer.quarantine_reason)

        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_BLOCKED,
        )

        offer.refresh_from_db()
        self.assertTrue(offer.quarantine_reason)
        self.assertEqual(
            offer.quarantine_severity,
            moderation.SEVERITY_BLOCKED,
        )

    def test_flagging_a_published_offer_does_not_unpublish_it(self):
        """La liste noire signale, elle ne retire pas l offre du catalogue.

        Suspendre une offre reste une decision humaine.
        """
        make_offer(
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
            application_phone='+226 70 11 22 33',
        )

        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_BLOCKED,
        )

        offer = Offer.objects.get()
        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)
        self.assertTrue(offer.is_published)

    def test_flagging_a_published_offer_does_not_raise(self):
        """Le recontrole ne doit pas bloquer l enregistrement."""
        make_offer(
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
            application_phone='+226 70 11 22 33',
        )

        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_BLOCKED,
        )

        self.assertEqual(Offer.objects.count(), 1)

    def test_matching_organization_is_flagged(self):
        make_offer(
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
            company_name='Sahel Express Logistique',
        )

        make_blacklist(
            phone='+226 70 55 44 33',
            organization='Sahel Express Logistique',
            status=BlacklistedContact.STATUS_BLOCKED,
        )

        offer = Offer.objects.get()
        self.assertTrue(offer.quarantine_reason)

    def test_matching_email_is_flagged(self):
        make_offer(
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
            application_email='contact@arnaque.bf',
        )

        make_blacklist(
            phone='+226 70 55 44 33',
            organization='Autre entité',
            email='contact@arnaque.bf',
            status=BlacklistedContact.STATUS_BLOCKED,
        )

        offer = Offer.objects.get()
        self.assertTrue(offer.quarantine_reason)


class RescreenActionTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_global_rescreen_flags_matching_offers(self):
        offer = make_offer(application_phone='+226 70 11 22 33')
        make_blacklist(phone='+226 70 11 22 33')

        self.client.post(
            reverse('admin:offres_offer_changelist'),
            {
                'action': 'rescreen_everything',
                '_selected_action': [str(offer.pk)],
            },
            follow=True,
        )

        offer.refresh_from_db()
        self.assertTrue(offer.quarantine_reason)

    def test_global_rescreen_clears_obsolete_quarantine(self):
        """Un controle complet leve une quarantaine devenue sans objet."""
        offer = make_offer(application_phone='+226 70 99 88 77')
        offer.quarantine_reason = 'Ancien motif'
        offer.quarantine_severity = moderation.SEVERITY_WATCH
        offer.save()

        self.client.post(
            reverse('admin:offres_offer_changelist'),
            {
                'action': 'rescreen_everything',
                '_selected_action': [str(offer.pk)],
            },
            follow=True,
        )

        offer.refresh_from_db()
        self.assertFalse(offer.quarantine_reason)
        self.assertEqual(offer.quarantine_severity, moderation.SEVERITY_NONE)


class SeverityEvaluationTest(TestCase):
    def test_evaluate_offer_returns_reasons_and_severity(self):
        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_BLOCKED,
        )
        offer = make_offer(application_phone='+226 70 11 22 33')

        reasons, severity = moderation.evaluate_offer(offer)

        self.assertTrue(reasons)
        self.assertEqual(severity, moderation.SEVERITY_BLOCKED)

    def test_evaluate_offer_without_match(self):
        offer = make_offer(application_phone='+226 70 99 88 77')

        reasons, severity = moderation.evaluate_offer(offer)

        self.assertEqual(reasons, [])
        self.assertEqual(severity, moderation.SEVERITY_NONE)

    def test_worst_severity_keeps_the_strongest(self):
        self.assertEqual(
            moderation.worst_severity(
                moderation.SEVERITY_WATCH, moderation.SEVERITY_BLOCKED
            ),
            moderation.SEVERITY_BLOCKED,
        )
        self.assertEqual(
            moderation.worst_severity(
                moderation.SEVERITY_BLOCKED, moderation.SEVERITY_WATCH
            ),
            moderation.SEVERITY_BLOCKED,
        )

    def test_neutralized_contact_does_not_flag(self):
        """Un contact dont les coordonnees sont neutralisees ne bloque plus."""
        make_blacklist(
            phone='+226 70 11 22 33',
            status=BlacklistedContact.STATUS_NEUTRALIZED,
        )
        offer = make_offer(application_phone='+226 70 11 22 33')

        reasons, severity = moderation.evaluate_offer(offer)

        self.assertEqual(reasons, [])
        self.assertEqual(severity, moderation.SEVERITY_NONE)
