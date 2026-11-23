"""Tests de l assistant de decouverte des sources.

Ce qui est verifie :

- une page de listes d'offres est reconnue et son selecteur trouve ;
- une page qui interdit la reprise est ecartee ;
- une page qui l autorise est proposee ;
- une page qui ne parle pas d'offres, ou qui est rendue en JavaScript,
  est ecartee ;
- les reseaux sociaux ne sont jamais proposes ;
- le moteur de recherche est facultatif ;
- la commande s'execute et rend un rapport.
"""

import json
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from .veille import decouverte, decouverte_ia
from .veille import http

PAGE_OFFRES = """
<html>
<head><title>Emplois du Faso</title></head>
<body>
  <article class="offre">
    <h2>Charge de projets</h2>
    <p>Societe Exemple recherche un charge de projets a Ouagadougou.</p>
    <span>Date limite : 30 juin 2026</span>
    <a href="/offre/1">Postuler</a>
  </article>
  <article class="offre">
    <h2>Assistant comptable</h2>
    <p>Cabinet comptable recherche un assistant a Ouagadougou, CDI.</p>
    <span>Date limite : 15 juillet 2026</span>
    <a href="/offre/2">Postuler</a>
  </article>
  <div class="pub"><a href="/pub">Publicite</a></div>
</body>
</html>
"""

CONDITIONS_AUTORISEES = """
<html><body>
<p>Mentions legales de l association.</p>
<p>La reproduction de nos offres est autorisee, a la condition de mentionner
la source et de ne pas modifier le contenu. Toute autre utilisation est
interdite. Ce texte est assez long pour que la page soit lue comme telle
par l assistant de decouverte des sources.</p>
</body></html>
"""

CONDITIONS_INTERDITES = """
<html><body>
<p>Mentions legales de la societe.</p>
<p>La reproduction de nos annonces est interdite sans autorisation prealable
de notre part. Toute reprise integrale est constitutive de contrefacon.
Ce texte est assez long pour que la page soit lue comme telle par l
assistant de decouverte des sources d emploi.</p>
</body></html>
"""

PAGE_SANS_OFFRES = """
<html><head><title>Notre association</title></head>
<body>
<p>Nousaptor la protection de l enfant et l eau potable au Burkina Faso.
Ce texte ne parle d aucun emploi et d aucune candidature.</p>
</body></html>
"""

PAGE_JAVASCRIPT = """
<html><head><title>Emplois</title></head>
<body>
<div id="root"></div>
<script>var app = 1;</script>
<script>var data = 2;</script>
<script>var render = 3;</script>
<script>var mount = 4;</script>
</body></html>
"""


def fake_response(text='', status_code=200):
    reponse = mock.Mock()
    reponse.status_code = status_code
    reponse.text = text
    return reponse


class VerificationTestCase(TestCase):
    """La verification d une adresse proposee."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.addCleanup(http.reset_delay)
        self.addCleanup(http.clear_robots_cache)

    def verifier(self, page, conditions=None, url='https://emploi.exemple.bf/offres'):
        """Verifie une adresse avec une page et des conditions donnees."""

        def get(adresse, **kwargs):
            if '/mentions-legales' in adresse:
                if conditions is None:
                    return fake_response('', 404)
                return fake_response(conditions)
            return fake_response(page)

        candidat = decouverte.SourceCandidate(url=url, name='Emplois du Faso')
        with mock.patch.object(http.requests, 'get', side_effect=get):
            return decouverte.verify_candidate(candidat)

    def test_une_page_d_offres_est_reconnue(self):
        rapport = self.verifier(PAGE_OFFRES)

        self.assertEqual(rapport.verdict, decouverte.VERDICT_A_VERIFIER)
        self.assertEqual(rapport.selector, 'article.offre')
        self.assertEqual(rapport.blocks_count, 2)
        self.assertTrue(rapport.sample)

    def test_une_page_qui_autorise_la_reprise_est_proposee(self):
        rapport = self.verifier(PAGE_OFFRES, conditions=CONDITIONS_AUTORISEES)

        self.assertEqual(rapport.verdict, decouverte.VERDICT_SOURCE)
        self.assertIn('autorise', rapport.conditions_quote.lower())

    def test_une_page_qui_interdit_la_reprise_est_ecartee(self):
        rapport = self.verifier(PAGE_OFFRES, conditions=CONDITIONS_INTERDITES)

        self.assertEqual(rapport.verdict, decouverte.VERDICT_ECARTEE)
        self.assertTrue(
            any('interdit' in raison.lower() for raison in rapport.reasons)
        )

    def test_une_page_sans_offres_est_ecartee(self):
        rapport = self.verifier(PAGE_SANS_OFFRES)

        self.assertEqual(rapport.verdict, decouverte.VERDICT_ECARTEE)

    def test_une_page_en_javascript_est_ecartee(self):
        rapport = self.verifier(PAGE_JAVASCRIPT)

        self.assertEqual(rapport.verdict, decouverte.VERDICT_ECARTEE)
        self.assertTrue(
            any('javascript' in raison.lower() for raison in rapport.reasons)
        )

    def test_une_page_inaccessible_est_ecartee(self):
        rapport = self.verifier(PAGE_OFFRES, url='https://emploi.exemple.bf/offres')

        def get(adresse, **kwargs):
            return fake_response('', 404)

        candidat = decouverte.SourceCandidate(url='https://emploi.exemple.bf/offres')
        with mock.patch.object(http.requests, 'get', side_effect=get):
            rapport = decouverte.verify_candidate(candidat)

        self.assertEqual(rapport.verdict, decouverte.VERDICT_ECARTEE)
        self.assertTrue(rapport.error)

    def test_un_reseau_social_jamais_propose(self):
        for adresse in (
            'https://www.facebook.com/emploi.bf',
            'https://linkedin.com/jobs/burkina',
            'https://wa.me/recrutement',
        ):
            with self.subTest(adresse=adresse):
                candidat = decouverte.SourceCandidate(url=adresse)
                rapport = decouverte.verify_candidate(candidat)

                self.assertEqual(
                    rapport.verdict, decouverte.VERDICT_ECARTEE
                )
                self.assertTrue(
                    any('reseaux sociaux' in r.lower() for r in rapport.reasons)
                )

    def test_le_type_de_site_est_devine(self):
        rapport = self.verifier(PAGE_OFFRES)

        self.assertIn(rapport.kind, (
            'Portail d emploi',
            'Carriere d entreprise ou d institution',
            'Site institutionnel',
            'Organisation ou projet',
            'Autre',
        ))


class PropositionTestCase(TestCase):
    """Les adresses que le modele propose."""

    def test_la_reponse_du_modele_est_lue(self):
        reponse = json.dumps({
            'sources': [
                {
                    'url': 'https://emploi.exemple.bf/offres',
                    'name': 'Emplois du Faso',
                    'type': 'Portail d emploi',
                    'why': 'Page de listes.',
                },
                {
                    'url': 'https://facebook.com/emploi.bf',
                    'name': 'Facebook',
                    'type': 'Autre',
                    'why': 'A ecarter.',
                },
                {
                    'url': 'pas-une-adresse',
                    'name': 'Faux',
                    'type': 'Autre',
                    'why': 'A ecarter.',
                },
            ]
        })

        candidats = decouverte_ia._parse_candidates(reponse)

        self.assertEqual(len(candidats), 1)
        self.assertEqual(candidats[0].url, 'https://emploi.exemple.bf/offres')
        self.assertEqual(candidats[0].origin, 'modele')

    def test_une_reponse_illisible_ne_plante_pas(self):
        with mock.patch.object(decouverte_ia.logger, 'warning'):
            self.assertEqual(decouverte_ia._parse_candidates('pas du json'), [])
            self.assertEqual(decouverte_ia._parse_candidates(''), [])

    def test_des_champs_mal_types_ne_font_pas_echouer_la_decouverte(self):
        raw = json.dumps({
            'sources': [
                {
                    'url': 'https://emploi.exemple.bf/offres',
                    'name': 123,
                    'type': 1,
                    'kind': 'Portail emploi',
                    'why': ['liste des offres'],
                },
                {
                    'url': 456,
                    'name': 'Adresse invalide',
                },
                {
                    'url': 'https://jobs.exemple.bf/',
                    'name': 'Emploi Faso',
                    'type': 'Portail emploi',
                    'why': 'Liste des postes ouverts.',
                },
            ]
        })

        candidates = decouverte_ia._parse_candidates(raw)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].name, '')
        self.assertEqual(candidates[0].kind, 'Portail emploi')
        self.assertEqual(candidates[0].why, '')
        self.assertEqual(candidates[1].url, 'https://jobs.exemple.bf/')

    def test_le_modele_recoit_la_consigne_de_decouverte(self):
        class FauxAdaptateur:
            name = 'faux'

            def is_configured(self):
                return True

            def complete(self, prompt, system=''):
                self.system = system
                return '{"sources": []}'

        adapter = FauxAdaptateur()

        decouverte_ia.propose_par_modele('offres emploi', adapter=adapter)

        self.assertEqual(adapter.system, decouverte_ia.SYSTEM_PROMPT)

    def test_sans_moteur_de_recherche_la_recherche_ne_renvoie_rien(self):
        from django.test import override_settings

        with override_settings(BRAVE_SEARCH_API_KEY='', SEARXNG_URL=''):
            self.assertEqual(decouverte_ia.moteur_recherche_disponible(), '')
            resultats = decouverte_ia.propose_par_recherche('offres emploi')

        self.assertEqual(resultats, [])

    def test_avec_une_cle_le_moteur_est_detecte(self):
        from django.test import override_settings

        with override_settings(
            BRAVE_SEARCH_API_KEY='une-cle', SEARXNG_URL=''
        ):
            self.assertEqual(decouverte_ia.moteur_recherche_disponible(), 'brave')

        with override_settings(BRAVE_SEARCH_API_KEY='', SEARXNG_URL='https://s.exemple'):
            self.assertEqual(decouverte_ia.moteur_recherche_disponible(), 'searxng')

    def test_les_adresses_en_double_ne_sont_gardees_une_fois(self):
        reponse = json.dumps({
            'sources': [
                {'url': 'https://emploi.exemple.bf/offres', 'name': 'A'},
                {'url': 'https://emploi.exemple.bf/offres/', 'name': 'B'},
            ]
        })

        class FauxAdaptateur:
            name = 'faux'
            model = 'test'
            configured = True

            def is_configured(self):
                return True

            def complete(self, prompt, system=''):
                return reponse

        candidats = decouverte_ia.proposer(
            'offres', adapter=FauxAdaptateur(), avec_recherche=False
        )

        self.assertEqual(len(candidats), 1)


class CommandeTestCase(TestCase):
    """La commande en ligne."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.addCleanup(http.reset_delay)
        self.addCleanup(http.clear_robots_cache)

    def test_la_commande_sans_service_d_ia_le_dit(self):
        from io import StringIO

        sortie = StringIO()
        call_command('veille_decouverte', stdout=sortie)

        self.assertIn('Aucune adresse', sortie.getvalue())

    def test_la_commande_rend_un_rapport(self):
        from io import StringIO

        reponse = json.dumps({
            'sources': [
                {
                    'url': 'https://emploi.exemple.bf/offres',
                    'name': 'Emplois du Faso',
                    'type': 'Portail d emploi',
                    'why': 'Page de listes.',
                }
            ]
        })

        class FauxAdaptateur:
            name = 'faux'
            model = 'test'
            configured = True

            def is_configured(self):
                return True

            def complete(self, prompt, system=''):
                return reponse

        def get(adresse, **kwargs):
            return fake_response(PAGE_OFFRES)

        sortie = StringIO()
        with mock.patch.object(http.requests, 'get', side_effect=get):
            with mock.patch.object(
                decouverte_ia, 'proposer', return_value=[
                    decouverte.SourceCandidate(
                        url='https://emploi.exemple.bf/offres', name='Emplois'
                    )
                ]
            ):
                call_command('veille_decouverte', stdout=sortie)

        contenu = sortie.getvalue()
        self.assertIn('SOURCES A VERIFIER', contenu)
        self.assertIn('article.offre', contenu)
