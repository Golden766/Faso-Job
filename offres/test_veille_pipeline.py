"""Tests du lot 5 : le parcours complet de la veille.

Ce qui est verifie :

- une annonce collectee produit un **brouillon**, jamais une publication ;
- la trace de collecte est conservee ;
- le classement utilise une categorie qui existe deja ;
- un doublon est signale, jamais supprime ;
- une annonce collectee deux fois ne cree pas un second brouillon ;
- deux offres de meme intitule peuvent coexister ;
- la commande ne collecte que les sources autorisees.
"""

import json
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import Category, CollectedAnnouncement, Offer, Source, VeilleRun
from .veille import collectors, http, pipeline


ANNONCE = """
La Societe Burkina Faso Telecom recherche un CHARGE DE PROJETS pour son
siege a Ouagadougou. Bac+5 en gestion de projet, 3 ans d experience.
Date limite de candidature : 15 juillet 2026. Candidature par e-mail :
rh@bft.bf ou WhatsApp 70 55 44 33.
"""

RETOUR_IA = {
    'title': 'Charge de projets',
    'company_name': 'Societe Burkina Faso Telecom',
    'description': 'Pilotage de projets au siege.',
    'missions': 'Piloter les projets et suivre les budgets.',
    'required_profile': 'Bac+5 en gestion de projet',
    'required_education': 'Bac+5',
    'experience_required': '3 ans d experience',
    'location': 'Ouagadougou',
    'employment_type': 'CDI',
    'published_at': '2026-06-02',
    'deadline': '2026-07-15',
    'application_email': 'rh@bft.bf',
    'application_phone': '70 55 44 33',
    'whatsapp_number': '70 55 44 33',
    'application_method': 'email',
    'application_url': '',
    'application_instructions': 'Envoyer un CV.',
}


class FakeAdapter:
    """Faux adaptateur : repond avec des informations preparees."""

    def __init__(self, answer=None, category=''):
        self.name = 'faux-adaptateur'
        self.model = 'modele-de-test'
        self.answer = json.dumps(answer if answer is not None else RETOUR_IA)
        self.category = category
        self.configured = True

    def is_configured(self):
        return self.configured

    def complete(self, prompt, system=''):
        if 'categorie' in prompt.lower() or 'Choisis la categorie' in prompt:
            return self.category
        return self.answer


def fake_response(text='', status_code=200):
    response = mock.Mock()
    response.status_code = status_code
    response.text = text
    return response


PAGE_LISTE = """
<html><head><title>Emplois</title></head><body>
  <article class="offre">
    <h2>Charge de projets</h2>
    <p>Nous recrutons un charge de projets.</p>
    <a href="/offre/1">Voir</a>
  </article>
</body></html>
"""


class DraftCreationTestCase(TestCase):
    """Le brouillon produit par la veille."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='Accord de republication signe.',
            watch_config={'selector': 'article.offre'},
        )
        self.item = collectors.CollectedItem(
            url='https://exemple.test/offre/1',
            title='Charge de projets',
            text=ANNONCE,
        )

    def test_a_draft_is_created(self):
        announcement = pipeline.process_item(
            self.source, self.item, adapter=FakeAdapter()
        )

        offer = announcement.offer
        self.assertIsNotNone(offer)
        self.assertEqual(offer.status, Offer.STATUS_DRAFT)
        self.assertFalse(offer.is_published)
        self.assertFalse(offer.is_source_confirmed)
        self.assertFalse(offer.is_employer_verified)

    def test_the_draft_is_not_visible_on_the_public_site(self):
        announcement = pipeline.process_item(
            self.source, self.item, adapter=FakeAdapter()
        )

        self.assertNotIn(announcement.offer, Offer.objects.public(timezone.localtime()))

    def test_the_extracted_information_lands_in_the_offer(self):
        announcement = pipeline.process_item(
            self.source, self.item, adapter=FakeAdapter()
        )
        offer = announcement.offer

        self.assertEqual(offer.title, 'Charge de projets')
        self.assertEqual(offer.company_name, 'Societe Burkina Faso Telecom')
        self.assertEqual(offer.location, 'Ouagadougou')
        self.assertEqual(offer.employment_type, 'CDI')
        self.assertEqual(offer.description, 'Pilotage de projets au siege.')
        self.assertEqual(offer.missions, 'Piloter les projets et suivre les budgets.')
        self.assertEqual(offer.required_profile, 'Bac+5 en gestion de projet')
        self.assertEqual(offer.required_education, 'Bac+5')
        self.assertEqual(offer.experience_required, '3 ans d experience')
        self.assertEqual(offer.deadline.isoformat(), '2026-07-15')
        self.assertEqual(offer.application_method, 'email')
        self.assertEqual(offer.application_email, 'rh@bft.bf')
        self.assertEqual(offer.application_phone, '70 55 44 33')
        self.assertEqual(offer.whatsapp_number, '70 55 44 33')
        self.assertEqual(offer.application_instructions, 'Envoyer un CV.')
        self.assertEqual(offer.source, self.source)

    def test_the_trace_of_the_collection_is_kept(self):
        announcement = pipeline.process_item(
            self.source, self.item, adapter=FakeAdapter()
        )

        self.assertEqual(announcement.source_name, 'Emploi du Faso')
        self.assertEqual(announcement.source_url, 'https://exemple.test/offre/1')
        self.assertEqual(announcement.collection_method, 'web')
        self.assertEqual(announcement.raw_content, ANNONCE)
        self.assertTrue(announcement.content_hash)
        self.assertEqual(
            announcement.extraction_status,
            CollectedAnnouncement.EXTRACTION_DONE,
        )
        self.assertEqual(announcement.ai_model, 'modele-de-test')
        self.assertEqual(announcement.ai_prompt_version, 'v1')
        self.assertIn('raw', announcement.extracted_data)
        self.assertEqual(
            announcement.status, CollectedAnnouncement.STATUS_DRAFT_CREATED
        )

    def test_the_publication_date_of_the_source_is_kept(self):
        announcement = pipeline.process_item(
            self.source, self.item, adapter=FakeAdapter()
        )

        self.assertEqual(announcement.source_published_at.isoformat(), '2026-06-02')

    def test_the_category_is_one_that_already_exists(self):
        Category.objects.create(name='Informatique et telecom')

        announcement = pipeline.process_item(
            self.source, self.item, adapter=FakeAdapter(category='Informatique et telecom')
        )

        self.assertEqual(announcement.offer.category.name, 'Informatique et telecom')

    def test_an_unknown_category_leaves_the_offer_without_category(self):
        Category.objects.create(name='Informatique et telecom')

        announcement = pipeline.process_item(
            self.source, self.item, adapter=FakeAdapter(category='Metiers du bâtiment')
        )

        self.assertIsNone(announcement.offer.category)

    def test_without_service_the_announcement_is_kept_without_a_draft(self):
        """Une panne de l IA ne doit pas creer une offre mal renseignee."""
        adapter = FakeAdapter()
        adapter.configured = False

        announcement = pipeline.process_item(self.source, self.item, adapter=adapter)

        self.assertIsNone(announcement.offer)
        self.assertEqual(
            announcement.extraction_status,
            CollectedAnnouncement.EXTRACTION_FAILED,
        )
        self.assertTrue(announcement.error_message)
        self.assertEqual(announcement.status, CollectedAnnouncement.STATUS_DETECTED)

    def test_a_failed_extraction_keeps_provider_and_raw_answer_for_diagnosis(self):
        adapter = FakeAdapter(answer={'title': 'Charge de projets'})

        announcement = pipeline.process_item(self.source, self.item, adapter=adapter)

        self.assertIsNone(announcement.offer)
        self.assertEqual(announcement.ai_provider, 'faux-adaptateur')
        self.assertEqual(announcement.ai_model, 'modele-de-test')
        self.assertEqual(announcement.extracted_data['fields']['title'], 'Charge de projets')

    def test_two_offers_with_the_same_title_can_coexist(self):
        """Les identifiants d URL restent uniques."""
        first = pipeline.process_item(self.source, self.item, adapter=FakeAdapter())
        second = pipeline.process_item(
            self.source,
            collectors.CollectedItem(
                url='https://exemple.test/offre/2',
                title='Charge de projets',
                text=ANNONCE + ' Suite du poste.',
            ),
            adapter=FakeAdapter(),
        )

        self.assertEqual(Offer.objects.count(), 2)
        self.assertNotEqual(first.offer.slug, second.offer.slug)


class DuplicateHandlingTestCase(TestCase):
    """Les doublons sont signales, jamais supprimes."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='Accord signe.',
        )
        self.item = collectors.CollectedItem(
            url='https://exemple.test/offre/1',
            title='Charge de projets',
            text=ANNONCE,
        )

    def test_a_known_offer_is_signaled_as_a_duplicate(self):
        Offer.objects.create(
            slug='charge-de-projets',
            title='Charge de projets',
            company_name='Societe Burkina Faso Telecom',
            location='Ouagadougou',
            description='Pilotage de projets au siege.',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )

        announcement = pipeline.process_item(
            self.source, self.item, adapter=FakeAdapter()
        )

        self.assertEqual(
            announcement.duplicate_status,
            CollectedAnnouncement.DUPLICATE_SUSPECTED,
        )
        self.assertIsNotNone(announcement.duplicate_of)
        self.assertTrue(announcement.duplicate_reasons)

    def test_the_known_offer_is_not_deleted(self):
        known = Offer.objects.create(
            slug='charge-de-projets',
            title='Charge de projets',
            company_name='Societe Burkina Faso Telecom',
            location='Ouagadougou',
            description='Pilotage de projets au siege.',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )

        pipeline.process_item(self.source, self.item, adapter=FakeAdapter())

        self.assertTrue(Offer.objects.filter(pk=known.pk).exists())
        self.assertEqual(known.status, Offer.STATUS_PUBLISHED)

    def test_the_same_annonce_collected_twice_creates_one_offer_only(self):
        pipeline.process_item(self.source, self.item, adapter=FakeAdapter())
        second = pipeline.process_item(self.source, self.item, adapter=FakeAdapter())

        self.assertEqual(Offer.objects.count(), 1)
        self.assertEqual(second.status, CollectedAnnouncement.STATUS_DUPLICATE)
        self.assertEqual(
            second.duplicate_status,
            CollectedAnnouncement.DUPLICATE_CONFIRMED,
        )
        self.assertIsNotNone(second.duplicate_of)


class CollectionRunTestCase(TestCase):
    """Le passage de collecte et son historique."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='Accord signe.',
            watch_config={'selector': 'article.offre'},
        )

    def test_a_pass_creates_a_run_with_its_counters(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            run = pipeline.collect_and_process(self.source, adapter=FakeAdapter())

        self.assertEqual(run.source, self.source)
        self.assertEqual(run.status, VeilleRun.STATUS_SUCCESS)
        self.assertEqual(run.found_count, 1)
        self.assertEqual(run.created_count, 1)
        self.assertEqual(run.duplicate_count, 0)
        self.assertEqual(run.error_count, 0)
        self.assertIsNotNone(run.finished_at)
        self.assertIn('brouillon', run.message)

    def test_the_source_remembers_its_last_collection(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            pipeline.collect_and_process(self.source, adapter=FakeAdapter())

        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.last_collected_at)
        self.assertEqual(self.source.last_status, VeilleRun.STATUS_SUCCESS)

    def test_a_source_in_panne_is_reported_without_raising(self):
        import requests

        with mock.patch.object(http.logger, 'warning'):
            with mock.patch.object(
                http.requests,
                'get',
                side_effect=requests.exceptions.ConnectionError('reseau coupe'),
            ):
                run = pipeline.collect_and_process(self.source, adapter=FakeAdapter())

        self.assertEqual(run.status, VeilleRun.STATUS_FAILURE)
        self.assertEqual(run.created_count, 0)
        self.assertGreater(run.error_count, 0)


class CollectCommandTestCase(TestCase):
    """La commande de collecte."""

    def test_without_watched_source_it_says_so(self):
        output = StringIO()

        call_command('collect_offers', stdout=output)

        self.assertIn('Aucune source surveillee', output.getvalue())

    def test_a_source_without_authorization_is_not_collected(self):
        Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            watch_config={'selector': 'article.offre'},
        )

        output = StringIO()
        call_command('collect_offers', '--dry-run', stdout=output)

        self.assertIn('Aucune source surveillee', output.getvalue())

    def test_the_authorized_sources_are_listed_in_the_simulation(self):
        Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='Accord signe.',
            watch_config={'selector': 'article.offre'},
        )

        output = StringIO()
        call_command('collect_offers', '--dry-run', stdout=output)

        self.assertIn('Emploi du Faso', output.getvalue())
        self.assertIn('1 source(s)', output.getvalue())

    def test_an_unknown_source_name_is_refused(self):
        with self.assertRaises(Exception):
            call_command('collect_offers', '--source', 'Inexistante')
