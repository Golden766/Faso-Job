"""Tests du lot 8b : l assistant de decouverte dans le Centre de veille.

Ce qui est verifie :

- la decouverte enregistre les propositions ;
- l'equipe autorise une proposition, et la source est creee ;
- l'equipe refuse une proposition ;
- une proposition dont la reprise n'est pas etablie exige une
  autorisation motivee ;
- une source deja connue n'est pas dupliquee ;
- une adresse ecartee ne peut pas etre autorisee ;
- **rien n'est collecte ni publie** quand on autorise une source.
"""

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CollectedAnnouncement, Offer, Source, SourceProposal, VeilleRun
from .veille import decouverte_admin, http

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
</body>
</html>
"""


def fake_response(text='', status_code=200):
    reponse = mock.Mock()
    reponse.status_code = status_code
    reponse.text = text
    return reponse


class PropositionTestCase(TestCase):
    """Les propositions enregistrees par la decouverte."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.addCleanup(http.reset_delay)
        self.addCleanup(http.clear_robots_cache)
        self.user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.url = reverse('admin-veille')

    def lancer(self, demande='offres emploi Burkina Faso'):
        """Lance une decouverte avec un modele faux et une page fausse."""
        reponse_modele = json.dumps({
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
                return reponse_modele

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_OFFRES)
        ):
            with mock.patch(
                'offres.veille.decouverte_ia.propose_par_modele',
                return_value=[
                    decouverte_admin.decouverte_ia.SourceCandidate(
                        url='https://emploi.exemple.bf/offres',
                        name='Emplois du Faso',
                        origin='modele',
                    )
                ],
            ):
                with mock.patch(
                    'offres.veille.decouverte_ia.propose_par_recherche',
                    return_value=[],
                ):
                    return decouverte_admin.lancer_decouverte(
                        demande, adapter=FauxAdaptateur(), avec_recherche=False
                    )

    def test_la_decouverte_enregistre_une_proposition(self):
        propositions, messages = self.lancer()

        self.assertEqual(len(propositions), 1)
        proposition = propositions[0]
        self.assertEqual(proposition.url, 'https://emploi.exemple.bf/offres')
        self.assertEqual(proposition.selector, 'article.offre')
        self.assertEqual(proposition.blocks_count, 2)
        self.assertEqual(proposition.status, SourceProposal.STATUS_PENDING)

    def test_une_source_deja_connue_est_marquee_obsolete(self):
        Source.objects.create(
            name='Emploi du Faso',
            url='https://emploi.exemple.bf/offres',
        )

        propositions, _messages = self.lancer()

        self.assertEqual(propositions[0].status, SourceProposal.STATUS_OBSOLETE)

    def test_la_page_affiche_les_propositions(self):
        self.lancer()

        reponse = self.client.get(self.url)
        contenu = reponse.content.decode('utf-8')

        self.assertEqual(reponse.status_code, 200)
        self.assertIn('Sources propos', contenu)
        self.assertIn('emploi.exemple.bf/offres', contenu)
        self.assertIn('article.offre', contenu)


class DecisionTestCase(TestCase):
    """La decision de l equipe sur une proposition."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.addCleanup(http.reset_delay)
        self.addCleanup(http.clear_robots_cache)
        self.user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.url = reverse('admin-veille')

        self.proposition = SourceProposal.objects.create(
            url='https://emploi.exemple.bf/offres',
            name='Emplois du Faso',
            kind='Portail d emploi',
            verdict=SourceProposal.VERDICT_SOURCE,
            score=0.9,
            selector='article.offre',
            blocks_count=2,
            sample='Charge de projets ... Postuler',
            reasons='2 annonces detectees.',
        )

    def test_autoriser_une_proposition_cree_la_source(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_OFFRES)
        ):
            reponse = self.client.post(self.url, {
                'action': 'accept_proposal',
                'proposal_id': self.proposition.pk,
                'authorization_note': 'Accord signe avec le site.',
            })

        self.assertEqual(reponse.status_code, 302)
        self.proposition.refresh_from_db()
        self.assertEqual(self.proposition.status, SourceProposal.STATUS_ACCEPTED)
        self.assertIsNotNone(self.proposition.source)
        self.assertEqual(self.proposition.source.authorization_note, 'Accord signe avec le site.')
        self.assertTrue(self.proposition.source.is_watched)
        self.assertEqual(self.proposition.source.collection_method, 'web')
        self.assertTrue(self.proposition.source.is_watchable)

    def test_autoriser_une_source_ne_collecte_rien(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_OFFRES)
        ):
            self.client.post(self.url, {
                'action': 'accept_proposal',
                'proposal_id': self.proposition.pk,
            })

        self.assertEqual(CollectedAnnouncement.objects.count(), 0)
        self.assertEqual(VeilleRun.objects.count(), 0)
        self.assertEqual(Offer.objects.count(), 0)

    def test_refuser_une_proposition_cree_rien(self):
        reponse = self.client.post(self.url, {
            'action': 'refuse_proposal',
            'proposal_id': self.proposition.pk,
        })

        self.assertEqual(reponse.status_code, 302)
        self.proposition.refresh_from_db()
        self.assertEqual(self.proposition.status, SourceProposal.STATUS_REFUSED)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(self.proposition.reviewed_by, self.user)

    def test_une_proposition_non_etablie_exige_une_motivation(self):
        self.proposition.verdict = SourceProposal.VERDICT_A_VERIFIER
        self.proposition.save(update_fields=['verdict'])

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_OFFRES)
        ):
            self.client.post(self.url, {
                'action': 'accept_proposal',
                'proposal_id': self.proposition.pk,
                'authorization_note': '',
            })

        self.proposition.refresh_from_db()
        self.assertEqual(self.proposition.status, SourceProposal.STATUS_PENDING)
        self.assertEqual(Source.objects.count(), 0)

    def test_une_proposition_non_etablie_s_accepte_avec_une_motivation(self):
        self.proposition.verdict = SourceProposal.VERDICT_A_VERIFIER
        self.proposition.save(update_fields=['verdict'])

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_OFFRES)
        ):
            self.client.post(self.url, {
                'action': 'accept_proposal',
                'proposal_id': self.proposition.pk,
                'authorization_note': 'Accord ecrit obtenu de l editoriel.',
            })

        self.proposition.refresh_from_db()
        self.assertEqual(self.proposition.status, SourceProposal.STATUS_ACCEPTED)
        self.assertEqual(Source.objects.count(), 1)

    def test_une_proposition_ecartee_ne_peut_pas_etre_autorisee(self):
        self.proposition.verdict = SourceProposal.VERDICT_ECARTEE
        self.proposition.save(update_fields=['verdict'])

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_OFFRES)
        ):
            self.client.post(self.url, {
                'action': 'accept_proposal',
                'proposal_id': self.proposition.pk,
            })

        self.proposition.refresh_from_db()
        self.assertEqual(self.proposition.status, SourceProposal.STATUS_PENDING)
        self.assertEqual(Source.objects.count(), 0)

    def test_la_source_autorisee_rejoint_la_collecte(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_OFFRES)
        ):
            self.client.post(self.url, {
                'action': 'accept_proposal',
                'proposal_id': self.proposition.pk,
            })

        source = Source.objects.get()
        self.assertTrue(source.is_watchable)
        self.assertEqual(source.watch_config.get('selector'), 'article.offre')


class LancementTestCase(TestCase):
    """Le lancement de la decouverte depuis la page."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.addCleanup(http.reset_delay)
        self.addCleanup(http.clear_robots_cache)
        self.user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.url = reverse('admin-veille')

    def test_le_lancement_depuis_la_page_enregistre_les_propositions(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_OFFRES)
        ):
            with mock.patch(
                'offres.veille.decouverte_ia.propose_par_modele',
                return_value=[
                    decouverte_admin.decouverte_ia.SourceCandidate(
                        url='https://emploi.exemple.bf/offres',
                        name='Emplois du Faso',
                    )
                ],
            ):
                with mock.patch(
                    'offres.veille.decouverte_ia.propose_par_recherche',
                    return_value=[],
                ):
                    reponse = self.client.post(self.url, {
                        'action': 'discover_sources',
                        'demande': 'offres emploi Burkina Faso',
                        'maximum': '4',
                    })

        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(SourceProposal.objects.count(), 1)

    def test_une_demande_vide_est_refusee(self):
        reponse = self.client.post(self.url, {
            'action': 'discover_sources',
            'demande': '   ',
        })

        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(SourceProposal.objects.count(), 0)

    def test_un_nombre_invalide_ne_plante_pas(self):
        with mock.patch(
            'offres.veille.decouverte_ia.proposer', return_value=[]
        ):
            reponse = self.client.post(self.url, {
                'action': 'discover_sources',
                'demande': 'offres emploi',
                'maximum': 'beaucoup',
            })

        self.assertEqual(reponse.status_code, 302)
