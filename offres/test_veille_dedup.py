"""Tests du lot 4 : rapprochement des annonces collectees.

Ce qui est verifie :

- une annonce reprise d'une source deja connue est signalee ;
- une annonce vraiment differente ne l'est pas ;
- les motifs sont lisibles par l'equipe ;
- **rien n'est supprime** ;
- une annonce collectee deux fois est reconnue grace a son empreinte.
"""

from django.test import TestCase

from .models import CollectedAnnouncement, Offer, Source
from .veille import dedup


class TextSimilarityTestCase(TestCase):
    """La mesure de ressemblance entre deux textes."""

    def test_the_same_text_gives_a_score_of_one(self):
        self.assertEqual(dedup.text_similarity('Assistant comptable', 'Assistant comptable'), 1.0)

    def test_a_reformulation_keeps_a_high_score(self):
        score = dedup.text_similarity(
            'Assistant comptable', 'Assistant en comptabilite'
        )

        self.assertGreater(score, 0.5)

    def test_two_different_offices_give_a_low_score(self):
        score = dedup.text_similarity(
            'Assistant comptable', 'Mecanicien de maintenance'
        )

        self.assertLess(score, 0.4)

    def test_an_empty_text_gives_no_score(self):
        self.assertEqual(dedup.text_similarity('', 'Assistant comptable'), 0.0)
        self.assertEqual(dedup.text_similarity('Assistant comptable', ''), 0.0)


class DuplicateDetectionTestCase(TestCase):
    """Le rapprochement avec le catalogue deja connu."""

    def setUp(self):
        self.source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois/1',
        )
        self.offer = Offer.objects.create(
            title='Assistant comptable',
            company_name='Societe Exemple',
            location='Ouagadougou',
            description='Tenir la comptabilite generale de l entreprise.',
            deadline='2026-06-30',
            source=self.source,
            application_url='https://exemple.test/emplois/1',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )

        self.extracted = {
            'title': 'Assistant comptable',
            'company_name': 'Societe Exemple',
            'location': 'Ouagadougou',
            'description': 'Tenir la comptabilite generale de l entreprise.',
            'deadline': '2026-06-30',
        }

    def test_the_same_annonce_is_signaled(self):
        matches = dedup.find_duplicates(self.extracted)

        self.assertEqual(len(matches), 1)
        offer, score, reasons = matches[0]
        self.assertEqual(offer, self.offer)
        self.assertGreaterEqual(score, dedup.SEUIL_DOUBLON)
        self.assertTrue(reasons)

    def test_a_different_annonce_is_not_signaled(self):
        matches = dedup.find_duplicates(
            {
                'title': 'Mecanicien de maintenance',
                'company_name': 'Atelier du Faso',
                'location': 'Bobo-Dioulasso',
                'description': 'Entretenir la flotte de vehicules.',
            }
        )

        self.assertEqual(matches, [])

    def test_the_motifs_are_readable(self):
        _offer, _score, reasons = dedup.find_duplicates(self.extracted)[0]
        text = ' '.join(reasons)

        self.assertIn('Intitule', text)
        self.assertIn('entreprise', text)
        self.assertIn('lieu', text)
        self.assertIn('date limite', text)

    def test_the_same_link_alone_is_enough(self):
        """Une annonce reprise du meme lien est un doublon."""
        matches = dedup.find_duplicates(
            {'title': 'Poste entierement different'},
            source_url='https://exemple.test/emplois/1',
        )

        self.assertEqual(len(matches), 1)
        self.assertIn('Meme lien de source', ' '.join(matches[0][2]))

    def test_nothing_is_deleted(self):
        """Un rapprochement ne modifie rien au catalogue."""
        before = Offer.objects.count()

        dedup.find_duplicates(self.extracted)

        self.assertEqual(Offer.objects.count(), before)
        self.assertEqual(self.offer.status, Offer.STATUS_PUBLISHED)

    def test_the_matches_are_sorted_by_score(self):
        Offer.objects.create(
            slug='assistant-comptable-bis',
            title='Assistant comptable',
            company_name='Societe Exemple',
            description='Le poste est identique chez nous aussi.',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )

        matches = dedup.find_duplicates(self.extracted)

        scores = [score for _offer, score, _reasons in matches]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_the_seuil_can_be_stricter(self):
        """Sous un seuil plus strict, les rapprochements faibles disparaissent."""
        Offer.objects.create(
            slug='assistant-comptable-bis',
            title='Assistant comptable',
            company_name='Societe Exemple',
            location='Ouagadougou',
            description='Un poste proche mais formule autrement.',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )

        loose = dedup.find_duplicates(self.extracted)
        strict = dedup.find_duplicates(self.extracted, threshold=0.95)

        self.assertEqual(len(loose), 2)
        self.assertEqual(len(strict), 1)


class AlreadyCollectedTestCase(TestCase):
    """La protection contre la double collecte."""

    def test_an_annonce_never_collected_is_not_found(self):
        self.assertIsNone(dedup.already_collected('a' * 64))

    def test_the_same_annonce_collected_twice_is_found(self):
        first = CollectedAnnouncement.objects.create(
            source_name='Emploi du Faso',
            content_hash='b' * 64,
            raw_content='Nous recrutons un assistant comptable.',
        )
        second = CollectedAnnouncement.objects.create(
            source_name='Emploi du Faso',
            content_hash='b' * 64,
            raw_content='Nous recrutons un assistant comptable.',
        )

        found = dedup.already_collected('b' * 64)

        self.assertEqual(found, first)
        self.assertNotEqual(found, second)

    def test_the_announcement_itself_can_be_excluded(self):
        first = CollectedAnnouncement.objects.create(
            source_name='Emploi du Faso',
            content_hash='c' * 64,
        )
        second = CollectedAnnouncement.objects.create(
            source_name='Emploi du Faso',
            content_hash='c' * 64,
        )

        found = dedup.already_collected('c' * 64, exclude_pk=first.pk)

        self.assertEqual(found, second)

    def test_without_an_empreinte_nothing_is_found(self):
        self.assertIsNone(dedup.already_collected(''))


class SummaryTestCase(TestCase):
    """Le resume lisible des rapprochements."""

    def test_without_duplicate_the_summary_says_so(self):
        self.assertEqual(dedup.summarize([]), 'Aucun doublon potentiel.')

    def test_the_summary_names_the_offer_and_the_score(self):
        offer = Offer.objects.create(
            title='Assistant comptable',
            company_name='Societe Exemple',
            description='Tenir la comptabilite generale de l entreprise.',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )

        text = dedup.summarize([(offer, 0.92, ['Meme entreprise.'])])

        self.assertIn('Assistant comptable', text)
        self.assertIn('92%', text)
        self.assertIn('Meme entreprise', text)
