"""Tests du lot 2 : extraction et classement par intelligence artificielle.

Ces tests n'appellent jamais le service : un faux adaptateur remplace
le client HTTP. Ce qui est verifie ici, c'est la regle de la veille :

- **le service propose, le code valide** ;
- une information absente reste vide ;
- une information mal formee est ecartee, jamais completee ;
- une panne du service est rendue dans le resultat, jamais levee.
"""

import io
import json
import urllib.error
from unittest import mock

from django.test import TestCase, override_settings

from .models import CollectedAnnouncement
from .veille import ia
from .veille.schema import (
    build_extraction_prompt,
    clean_classification,
    clean_date,
    clean_email,
    clean_extraction,
    clean_phone,
    clean_url,
    parse_json_answer,
)


class FakeAdapter:
    """Faux adaptateur : renvoie une reponse preparee a l avance."""

    def __init__(self, answer='', configured=True, error=None):
        self.name = 'faux-adaptateur'
        self.model = 'modele-de-test'
        self.answer = answer
        self.configured = configured
        self.error = error
        self.prompts = []

    def is_configured(self):
        return self.configured

    def complete(self, prompt, system=''):
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.answer


class FakeResponse:
    """Reponse HTTP minimale, utilisable dans un `with`."""

    def __init__(self, payload=None, raw=None):
        if raw is not None:
            self.payload = raw.encode('utf-8')
        else:
            self.payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


ANNONCE = """
Recherche d'un assistant comptable pour notre Direction generale a Ouagadougou.
Contrat a duree indefinite. Bac+2 minimum en comptabilite, 2 ans d'experience.
Date limite de candidature : 30 juin 2026. Postuler par e-mail a
recrutement@exemple.bf ou au telephone 70 12 34 56.
"""


class CleaningTestCase(TestCase):
    """Les regles de validation, une par une."""

    def test_a_missing_value_stays_empty(self):
        cleaned = clean_extraction({'title': 'Poste', 'company_name': None})

        self.assertEqual(cleaned['title'], 'Poste')
        self.assertEqual(cleaned['company_name'], '')
        self.assertEqual(cleaned['description'], '')

    def test_a_value_of_the_wrong_type_is_discarded(self):
        cleaned = clean_extraction({'title': 12345, 'company_name': ['a']})

        self.assertEqual(cleaned['title'], '')
        self.assertEqual(cleaned['company_name'], '')

    def test_dates_are_read_in_the_usual_writings(self):
        self.assertEqual(clean_date('2026-06-30'), '2026-06-30')
        self.assertEqual(clean_date('30/06/2026'), '2026-06-30')
        self.assertEqual(clean_date('30-06-2026'), '2026-06-30')
        self.assertEqual(clean_date('30.06.2026'), '2026-06-30')
        self.assertEqual(clean_date('30 juin 2026'), '2026-06-30')
        self.assertEqual(clean_date('2026-06-30T08:00:00'), '2026-06-30')

    def test_an_ambiguous_date_is_discarded(self):
        """Une date inventee ferait expirer l offre au mauvais moment."""
        self.assertEqual(clean_date('juin 2026'), '')
        self.assertEqual(clean_date('demain'), '')
        self.assertEqual(clean_date('32/13/2026'), '')
        self.assertEqual(clean_date(''), '')

    def test_an_invalid_email_is_discarded(self):
        self.assertEqual(clean_email('recrutement@exemple.bf'), 'recrutement@exemple.bf')
        self.assertEqual(clean_email('recrutement@exemple'), '')
        self.assertEqual(clean_email('pas une adresse'), '')
        self.assertEqual(clean_email('a@b.co'), 'a@b.co')

    def test_only_http_links_are_kept(self):
        self.assertEqual(clean_url('https://exemple.bf/offre'), 'https://exemple.bf/offre')
        self.assertEqual(clean_url('http://exemple.bf'), 'http://exemple.bf')
        self.assertEqual(clean_url('javascript:alert(1)'), '')
        self.assertEqual(clean_url('exemple.bf'), '')
        self.assertEqual(clean_url(''), '')

    def test_an_implausible_phone_number_is_discarded(self):
        self.assertEqual(clean_phone('+226 70 12 34 56'), '+226 70 12 34 56')
        self.assertEqual(clean_phone('123'), '')
        self.assertEqual(clean_phone('appeler 70 12 34 56'), '')

    def test_the_application_method_is_reduced_to_a_known_value(self):
        cleaned = clean_extraction({'application_method': 'En ligne'})

        self.assertEqual(cleaned['application_method'], 'online')

    def test_an_unknown_application_method_is_discarded(self):
        cleaned = clean_extraction({'application_method': 'par pigeon'})

        self.assertEqual(cleaned['application_method'], '')

    def test_a_too_long_value_is_shortened_not_lost(self):
        cleaned = clean_extraction({'title': 'a' * 400})

        self.assertEqual(len(cleaned['title']), 250)


class JsonAnswerTestCase(TestCase):
    """La lecture des reponses du service."""

    def test_a_plain_json_object_is_read(self):
        payload = parse_json_answer('{"title": "Poste"}')

        self.assertEqual(payload['title'], 'Poste')

    def test_a_code_fence_around_the_json_is_accepted(self):
        payload = parse_json_answer('```json\n{"title": "Poste"}\n```')

        self.assertEqual(payload['title'], 'Poste')

    def test_a_comment_around_the_json_is_accepted(self):
        payload = parse_json_answer('Voici le resultat :\n{"title": "Poste"}\nMerci.')

        self.assertEqual(payload['title'], 'Poste')

    def test_an_empty_answer_is_refused(self):
        with self.assertRaises(ValueError):
            parse_json_answer('')

    def test_a_broken_answer_is_refused(self):
        with self.assertRaises(ValueError):
            parse_json_answer('ceci n est pas du json')

    def test_a_list_is_refused(self):
        with self.assertRaises(ValueError):
            parse_json_answer('[1, 2, 3]')


class ExtractionTestCase(TestCase):
    """La demande d'extraction complete."""

    def test_the_fields_are_extracted(self):
        adapter = FakeAdapter(
            answer=json.dumps(
                {
                    'title': 'Assistant comptable',
                    'company_name': 'Entreprise Exemple',
                    'description': 'Tenir la comptabilite generale.',
                    'missions': 'Saisir les ecritures.',
                    'required_profile': 'Comptable avere',
                    'required_education': 'Bac+2',
                    'location': 'Ouagadougou',
                    'employment_type': 'CDI',
                    'published_at': '2026-05-02',
                    'deadline': '2026-06-30',
                    'application_email': 'recrutement@exemple.bf',
                    'application_phone': '+226 70 12 34 56',
                    'whatsapp_number': '',
                    'application_method': 'email',
                    'application_url': '',
                    'application_instructions': 'Envoyer un CV.',
                }
            )
        )

        result = ia.extract_announcement(ANNONCE, adapter=adapter)

        self.assertEqual(result.status, CollectedAnnouncement.EXTRACTION_DONE)
        self.assertTrue(result.is_ok)
        self.assertEqual(result.data['title'], 'Assistant comptable')
        self.assertEqual(result.data['company_name'], 'Entreprise Exemple')
        self.assertEqual(result.data['location'], 'Ouagadougou')
        self.assertEqual(result.data['deadline'], '2026-06-30')
        self.assertEqual(result.data['application_email'], 'recrutement@exemple.bf')
        self.assertEqual(result.data['application_method'], 'email')

    def test_a_field_the_service_omitted_stays_empty(self):
        adapter = FakeAdapter(answer=json.dumps({'title': 'Assistant comptable'}))

        result = ia.extract_announcement(ANNONCE, adapter=adapter)

        self.assertEqual(result.data['title'], 'Assistant comptable')
        self.assertEqual(result.data['company_name'], '')
        self.assertEqual(result.data['deadline'], '')
        self.assertEqual(result.data['application_method'], '')
        self.assertEqual(result.status, CollectedAnnouncement.EXTRACTION_FAILED)
        self.assertIn("que l'intitule", result.error)

    def test_an_extraction_without_a_title_is_rejected(self):
        adapter = FakeAdapter(
            answer=json.dumps({'description': 'Tenir la comptabilite generale.'})
        )

        result = ia.extract_announcement(ANNONCE, adapter=adapter)

        self.assertEqual(result.status, CollectedAnnouncement.EXTRACTION_FAILED)
        self.assertIn('intitule', result.error)

    def test_the_raw_answer_is_kept_for_audit(self):
        raw = json.dumps({'title': 'Assistant comptable'})
        adapter = FakeAdapter(answer=raw)

        result = ia.extract_announcement(ANNONCE, adapter=adapter)

        self.assertEqual(result.raw, raw)

    def test_a_broken_answer_is_reported_and_not_raised(self):
        adapter = FakeAdapter(answer='le modele a refuse de repondre en JSON')

        result = ia.extract_announcement(ANNONCE, adapter=adapter)

        self.assertEqual(result.status, CollectedAnnouncement.EXTRACTION_FAILED)
        self.assertFalse(result.is_ok)
        self.assertEqual(result.data, {})
        self.assertIn('illisible', result.error)

    def test_a_service_failure_is_reported_and_not_raised(self):
        adapter = FakeAdapter(error=ia.AiRequestError('Le service est injoignable.'))

        result = ia.extract_announcement(ANNONCE, adapter=adapter)

        self.assertEqual(result.status, CollectedAnnouncement.EXTRACTION_FAILED)
        self.assertIn('injoignable', result.error)

    def test_an_unconfigured_service_is_reported_clearly(self):
        adapter = FakeAdapter(configured=False)

        result = ia.extract_announcement(ANNONCE, adapter=adapter)

        self.assertEqual(result.status, CollectedAnnouncement.EXTRACTION_FAILED)
        self.assertIn('AI_BASE_URL', result.error)
        self.assertEqual(adapter.prompts, [])

    def test_the_prompt_lists_the_allowed_fields(self):
        prompt = build_extraction_prompt(ANNONCE)

        for key in ('title', 'company_name', 'description', 'deadline'):
            self.assertIn('"%s"' % key, prompt)

    def test_the_prompt_asks_for_null_when_information_is_missing(self):
        prompt = build_extraction_prompt(ANNONCE)

        self.assertIn('null', prompt)
        self.assertIn('Ne complete jamais', prompt)

    def test_the_prompt_lists_the_allowed_application_methods(self):
        prompt = build_extraction_prompt(ANNONCE)

        self.assertIn('online', prompt)
        self.assertIn('whatsapp', prompt)


class ClassificationTestCase(TestCase):
    """Le classement dans les categories existantes."""

    def test_an_existing_category_is_kept(self):
        adapter = FakeAdapter(answer='Comptabilite et finance')

        result = ia.classify_announcement(
            {'title': 'Assistant comptable'},
            ['Comptabilite et finance', 'Informatique'],
            adapter=adapter,
        )

        self.assertEqual(result.status, CollectedAnnouncement.EXTRACTION_DONE)
        self.assertEqual(result.data['category'], 'Comptabilite et finance')

    def test_an_unknown_category_is_discarded(self):
        """La veille ne cree jamais une categorie."""
        adapter = FakeAdapter(answer='Metiers de la restauration')

        result = ia.classify_announcement(
            {'title': 'Assistant comptable'},
            ['Comptabilite et finance', 'Informatique'],
            adapter=adapter,
        )

        self.assertEqual(result.data['category'], '')

    def test_the_answer_may_be_a_json_object(self):
        adapter = FakeAdapter(answer=json.dumps({'category': 'Informatique'}))

        result = ia.classify_announcement(
            {'title': 'Developpeur'},
            ['Informatique'],
            adapter=adapter,
        )

        self.assertEqual(result.data['category'], 'Informatique')

    def test_without_category_the_service_is_not_called(self):
        adapter = FakeAdapter(answer='Informatique')

        result = ia.classify_announcement({'title': 'Developpeur'}, [], adapter=adapter)

        self.assertEqual(result.data['category'], '')
        self.assertEqual(adapter.prompts, [])

    def test_an_unconfigured_service_does_not_classify(self):
        adapter = FakeAdapter(configured=False)

        result = ia.classify_announcement(
            {'title': 'Developpeur'},
            ['Informatique'],
            adapter=adapter,
        )

        self.assertEqual(result.status, CollectedAnnouncement.EXTRACTION_FAILED)

    def test_the_category_is_matched_without_regard_to_the_case(self):
        self.assertEqual(clean_classification('comptabilite', ['Comptabilite']), 'Comptabilite')
        self.assertEqual(clean_classification('  Comptabilite  ', ['Comptabilite']), 'Comptabilite')
        self.assertEqual(clean_classification('Inconnu', ['Comptabilite']), '')


class AdapterTestCase(TestCase):
    """Le transport vers le service, sans jamais sortir de la machine."""

    def test_the_adapter_reads_the_settings(self):
        """Changer de modele se fait dans le .env, pas dans le code."""
        with override_settings(
            AI_BASE_URL='https://openrouter.ai/api/v1',
            AI_API_KEY='une-cle',
            AI_MODEL='un-modele-gratuit',
        ):
            adapter = ia.get_adapter()

            self.assertTrue(adapter.is_configured())
            self.assertEqual(adapter.endpoint, 'https://openrouter.ai/api/v1/chat/completions')
            self.assertEqual(adapter.model, 'un-modele-gratuit')

    def test_the_google_openai_compatible_endpoint_is_supported(self):
        with override_settings(
            AI_BASE_URL='https://generativelanguage.googleapis.com/v1beta/openai/',
            AI_API_KEY='une-cle',
            AI_MODEL='gemini-3.8-flash',
        ):
            adapter = ia.get_adapter()

        self.assertTrue(adapter.is_configured())
        self.assertEqual(
            adapter.endpoint,
            'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        )
        self.assertEqual(adapter.model, 'gemini-3.8-flash')

    def test_without_settings_the_service_is_not_configured(self):
        with override_settings(AI_BASE_URL='', AI_API_KEY='', AI_MODEL=''):
            self.assertFalse(ia.get_adapter().is_configured())

    def test_the_adapter_is_not_configured_without_a_key(self):
        adapter = ia.OpenAICompatibleAdapter(base_url='', api_key='', model='')

        self.assertFalse(adapter.is_configured())

    def test_the_adapter_is_configured_with_the_three_settings(self):
        adapter = ia.OpenAICompatibleAdapter(
            base_url='https://exemple.test/v1',
            api_key='une-cle',
            model='un-modele',
        )

        self.assertTrue(adapter.is_configured())
        self.assertEqual(adapter.endpoint, 'https://exemple.test/v1/chat/completions')

    def test_the_request_carries_the_key_the_model_and_the_prompt(self):
        adapter = ia.OpenAICompatibleAdapter(
            base_url='https://exemple.test/v1',
            api_key='une-cle',
            model='un-modele',
        )
        response = FakeResponse({'choices': [{'message': {'content': '{"title": "Poste"}'}}]})

        with mock.patch.object(ia.urllib.request, 'urlopen', return_value=response) as urlopen:
            answer = adapter.complete('Ma demande', 'Consigne')

        request = urlopen.call_args[0][0]
        body = json.loads(request.data.decode('utf-8'))

        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.full_url, 'https://exemple.test/v1/chat/completions')
        self.assertEqual(request.headers['Authorization'], 'Bearer une-cle')
        self.assertEqual(body['model'], 'un-modele')
        self.assertEqual(body['temperature'], 0)
        self.assertEqual(body['messages'][1]['content'], 'Ma demande')
        self.assertEqual(answer, '{"title": "Poste"}')

    def test_the_strict_json_mode_is_optional(self):
        adapter = ia.OpenAICompatibleAdapter(
            base_url='https://exemple.test/v1',
            api_key='une-cle',
            model='un-modele',
            json_mode=True,
        )

        payload = adapter.build_payload('Ma demande')

        self.assertEqual(payload['response_format'], {'type': 'json_object'})

    def test_the_answer_is_read_from_the_choices(self):
        response = FakeResponse({'choices': [{'message': {'content': 'du texte'}}]})

        with mock.patch.object(ia.urllib.request, 'urlopen', return_value=response):
            answer = ia.OpenAICompatibleAdapter(
                base_url='https://exemple.test/v1',
                api_key='une-cle',
                model='un-modele',
            ).complete('demande')

        self.assertEqual(answer, 'du texte')

    def test_an_answer_given_in_pieces_is_reassembled(self):
        response = FakeResponse({
            'choices': [{'message': {'content': [{'text': 'une '}, {'text': 'phrase'}]}}]
        })

        with mock.patch.object(ia.urllib.request, 'urlopen', return_value=response):
            answer = ia.OpenAICompatibleAdapter(
                base_url='https://exemple.test/v1',
                api_key='une-cle',
                model='un-modele',
            ).complete('demande')

        self.assertEqual(answer, 'une phrase')

    def test_a_refused_request_becomes_a_readable_error(self):
        error = urllib.error.HTTPError(
            'https://exemple.test/v1/chat/completions',
            429,
            'Trop de requetes',
            {},
            io.BytesIO(b'{"error": "quota"}'),
        )

        with mock.patch.object(ia.logger, 'warning'):
            with mock.patch.object(ia.urllib.request, 'urlopen', side_effect=error):
                with self.assertRaises(ia.AiRequestError) as caught:
                    ia.OpenAICompatibleAdapter(
                        base_url='https://exemple.test/v1',
                        api_key='une-cle',
                        model='un-modele',
                    ).complete('demande')

        self.assertIn('429', str(caught.exception))

    def test_an_unreachable_service_becomes_a_readable_error(self):
        with mock.patch.object(ia.logger, 'warning'):
            with mock.patch.object(
                ia.urllib.request,
                'urlopen',
                side_effect=urllib.error.URLError('reseau indisponible'),
            ):
                with self.assertRaises(ia.AiRequestError) as caught:
                    ia.OpenAICompatibleAdapter(
                        base_url='https://exemple.test/v1',
                        api_key='une-cle',
                        model='un-modele',
                    ).complete('demande')

        self.assertIn('injoignable', str(caught.exception))

    def test_an_illisible_answer_becomes_a_readable_error(self):
        with mock.patch.object(
            ia.urllib.request,
            'urlopen',
            return_value=FakeResponse(raw='pas du json du tout'),
        ):
            adapter = ia.OpenAICompatibleAdapter(
                base_url='https://exemple.test/v1',
                api_key='une-cle',
                model='un-modele',
            )
            with self.assertRaises(ia.AiRequestError):
                adapter.complete('demande')
