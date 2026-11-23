"""Tests du lot 6 : le Centre de veille.

Couvre la page unique du Centre de veille, les actions qu'elle
propose (collecter une source, coller un lien, coller un texte,
confirmer ou ecarter un doublon, rejeter une annonce) et le menu qui
mene a la page.

Regle verifiee dans chaque cas : **rien n'est publie depuis cette
page**.
"""

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CollectedAnnouncement, Offer, Source, VeilleRun
from .veille import http

ANNONCE = """
La Societe Burkina Faso Telecom recherche un CHARGE DE PROJETS pour son
siege a Ouagadougou. Bac+5 en gestion de projet.
Date limite de candidature : 15 juillet 2026. Candidature par e-mail :
rh@bft.bf ou WhatsApp 70 55 44 33.
"""

RETOUR_IA = {
    'title': 'Charge de projets',
    'company_name': 'Societe Burkina Faso Telecom',
    'description': 'Pilotage de projets au siege.',
    'missions': 'Piloter les projets.',
    'required_profile': 'Bac+5 en gestion de projet',
    'required_education': 'Bac+5',
    'experience_required': '3 ans',
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
    """Faux adaptateur d'intelligence artificielle."""

    def __init__(self, answer=None):
        self.name = 'faux-adaptateur'
        self.model = 'modele-de-test'
        self.answer = json.dumps(answer if answer is not None else RETOUR_IA)
        self.configured = True

    def is_configured(self):
        return self.configured

    def complete(self, prompt, system=''):
        if 'categorie' in prompt.lower():
            return ''
        return self.answer


def fake_response(text='', status_code=200):
    response = mock.Mock()
    response.status_code = status_code
    response.text = text
    return response


class VeillePageAccessTest(TestCase):
    """Qui peut ouvrir le Centre de veille."""

    def setUp(self):
        self.url = reverse('admin-veille')
        self.user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
            is_staff=True,
        )

    def test_an_anonymous_visitor_is_sent_to_the_login_page(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/', response['Location'])

    def test_a_visitor_without_permission_cannot_open_the_page(self):
        simple = get_user_model().objects.create_user(
            username='lecteur',
            password='motdepasse-test-1',
        )
        self.client.force_login(simple)

        response = self.client.get(self.url)

        self.assertIn(response.status_code, (302, 403))

    def test_a_staff_member_can_open_the_page(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)


class VeillePageContentTest(TestCase):
    """Ce que la page montre."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.url = reverse('admin-veille')

    def test_the_six_sections_are_present(self):
        response = self.client.get(self.url)
        content = response.content.decode('utf-8')

        self.assertIn('Annonces d&eacute;tect&eacute;es'.replace('&eacute;', 'é'), content)
        self.assertIn('Centre de veille', content)
        self.assertIn('Doublons potentiels', content)
        self.assertIn('Annonces rejetées', content)
        self.assertIn('Sources surveillées', content)
        self.assertIn('Historique des collectes', content)

    def test_the_service_state_is_shown(self):
        response = self.client.get(self.url)
        content = response.content.decode('utf-8')

        self.assertIn('Aucun service d’intelligence artificielle configuré', content)

    def test_the_secret_key_is_never_shown(self):
        """La cle du service ne doit jamais apparaitre dans la page."""
        with self.settings(AI_API_KEY='une-cle-secrete-de-test'):
            response = self.client.get(self.url)

        content = response.content.decode('utf-8')

        self.assertNotIn('une-cle-secrete-de-test', content)

    def test_the_menu_leads_to_the_page(self):
        response = self.client.get(reverse('admin:index'))
        content = response.content.decode('utf-8')

        self.assertIn('Centre de veille', content)

    def test_the_breadcrumb_section_is_declared(self):
        from .templatetags.admin_ui import SECTIONS

        labels = [section[1] for section in SECTIONS]

        self.assertIn('Centre de veille', labels)


class VeilleCollectionTest(TestCase):
    """Les actions de collecte du Centre de veille."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        self.user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.url = reverse('admin-veille')

    def test_a_pasted_text_creates_a_draft(self):
        with mock.patch(
            'offres.veille.pipeline.ia.extract_announcement'
        ) as extraction:
            extraction.return_value = mock.Mock(
                is_ok=True,
                data=RETOUR_IA,
                raw='{}',
                provider='faux',
                model='modele-de-test',
                error='',
            )
            with mock.patch(
                'offres.veille.pipeline.ia.classify_announcement'
            ) as classification:
                classification.return_value = mock.Mock(
                    is_ok=True, data={'category': ''}, error=''
                )
                response = self.client.post(self.url, {
                    'action': 'collect_text',
                    'text': ANNONCE,
                })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(CollectedAnnouncement.objects.count(), 1)
        self.assertEqual(Offer.objects.count(), 1)

        offer = Offer.objects.get()
        self.assertEqual(offer.status, Offer.STATUS_DRAFT)
        self.assertFalse(offer.is_published)
        self.assertFalse(offer.is_source_confirmed)

    def test_a_pasted_text_is_attached_to_a_manual_source(self):
        with mock.patch(
            'offres.veille.pipeline.ia.extract_announcement'
        ) as extraction:
            extraction.return_value = mock.Mock(
                is_ok=True, data=RETOUR_IA, raw='{}', provider='faux',
                model='modele-de-test', error='',
            )
            with mock.patch(
                'offres.veille.pipeline.ia.classify_announcement'
            ) as classification:
                classification.return_value = mock.Mock(
                    is_ok=True, data={'category': ''}, error=''
                )
                self.client.post(self.url, {'action': 'collect_text', 'text': ANNONCE})

        announcement = CollectedAnnouncement.objects.get()
        self.assertIsNotNone(announcement.source)
        self.assertEqual(announcement.source.collection_method, 'manual_text')

    def test_an_empty_text_is_refused(self):
        response = self.client.post(self.url, {'action': 'collect_text', 'text': '  '})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(CollectedAnnouncement.objects.count(), 0)

    def test_a_pasted_link_is_read(self):
        with mock.patch.object(
            http.requests,
            'get',
            return_value=fake_response('<html><body><h1>Offre</h1><p>Bonjour</p></body></html>'),
        ):
            with mock.patch(
                'offres.veille.pipeline.ia.extract_announcement'
            ) as extraction:
                extraction.return_value = mock.Mock(
                    is_ok=True, data=RETOUR_IA, raw='{}', provider='faux',
                    model='modele-de-test', error='',
                )
                with mock.patch(
                    'offres.veille.pipeline.ia.classify_announcement'
                ) as classification:
                    classification.return_value = mock.Mock(
                        is_ok=True, data={'category': ''}, error=''
                    )
                    self.client.post(self.url, {
                        'action': 'collect_url',
                        'url': 'https://exemple.test/offre/1',
                    })

        self.assertEqual(CollectedAnnouncement.objects.count(), 1)
        self.assertEqual(
            CollectedAnnouncement.objects.get().source_url,
            'https://exemple.test/offre/1',
        )

    def test_a_source_without_authorization_is_not_collected(self):
        source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            watch_config={'selector': 'article.offre'},
        )

        response = self.client.post(
            self.url, {'action': 'collect_source', 'source_id': source.pk}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(VeilleRun.objects.count(), 0)
        self.assertEqual(CollectedAnnouncement.objects.count(), 0)

    def test_an_authorized_source_is_collected(self):
        source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='Accord de republication signe.',
            watch_config={'selector': 'article.offre'},
        )

        page = """
        <html><body>
          <article class="offre"><h2>Charge de projets</h2>
          <p>Nous recrutons.</p><a href="/offre/1">Voir</a></article>
        </body></html>
        """

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(page)
        ):
            with mock.patch(
                'offres.veille.pipeline.ia.extract_announcement'
            ) as extraction:
                extraction.return_value = mock.Mock(
                    is_ok=True, data=RETOUR_IA, raw='{}', provider='faux',
                    model='modele-de-test', error='',
                )
                with mock.patch(
                    'offres.veille.pipeline.ia.classify_announcement'
                ) as classification:
                    classification.return_value = mock.Mock(
                        is_ok=True, data={'category': ''}, error=''
                    )
                    self.client.post(
                        self.url,
                        {'action': 'collect_source', 'source_id': source.pk},
                    )

        self.assertEqual(VeilleRun.objects.count(), 1)
        self.assertEqual(CollectedAnnouncement.objects.count(), 1)
        self.assertEqual(Offer.objects.count(), 1)

    def test_nothing_is_published_by_a_collection(self):
        source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='Accord signe.',
            watch_config={'selector': 'article.offre'},
        )

        page = """
        <html><body>
          <article class="offre"><h2>Charge de projets</h2>
          <p>Nous recrutons.</p><a href="/offre/1">Voir</a></article>
        </body></html>
        """

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(page)
        ):
            with mock.patch(
                'offres.veille.pipeline.ia.extract_announcement'
            ) as extraction:
                extraction.return_value = mock.Mock(
                    is_ok=True, data=RETOUR_IA, raw='{}', provider='faux',
                    model='modele-de-test', error='',
                )
                with mock.patch(
                    'offres.veille.pipeline.ia.classify_announcement'
                ) as classification:
                    classification.return_value = mock.Mock(
                        is_ok=True, data={'category': ''}, error=''
                    )
                    self.client.post(
                        self.url,
                        {'action': 'collect_source', 'source_id': source.pk},
                    )

        offer = Offer.objects.get()
        self.assertEqual(offer.status, Offer.STATUS_DRAFT)
        self.assertFalse(offer.is_published)


class VeilleSourceListTest(TestCase):
    """La liste des sources reste affichee, quelles que soient les valeurs."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_a_source_without_authorization_is_listed(self):
        Source.objects.create(
            name='Groupe WhatsApp',
            collection_method=Source.COLLECTION_METHOD_WHATSAPP,
            is_watched=True,
        )

        response = self.client.get(reverse('admin:offres_source_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Groupe WhatsApp')

    def test_a_source_with_an_empty_authorization_is_listed(self):
        Source.objects.create(
            name='Source sans note',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='   ',
        )

        response = self.client.get(reverse('admin:offres_source_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Source sans note')


class VeilleReviewTest(TestCase):
    """Les actions de traitement des annonces."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='veilleur',
            password='motdepasse-test-1',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.url = reverse('admin-veille')

        self.offer = Offer.objects.create(
            title='Charge de projets',
            company_name='Societe Burkina Faso Telecom',
            description='Pilotage de projets.',
            status=Offer.STATUS_DRAFT,
        )
        self.announcement = CollectedAnnouncement.objects.create(
            offer=self.offer,
            source_name='Emploi du Faso',
            raw_content=ANNONCE,
            status=CollectedAnnouncement.STATUS_DRAFT_CREATED,
        )

    def test_an_annonce_can_be_rejected(self):
        response = self.client.post(self.url, {
            'action': 'reject_announcement',
            'announcement_id': self.announcement.pk,
        })

        self.assertEqual(response.status_code, 302)
        self.announcement.refresh_from_db()
        self.assertEqual(
            self.announcement.status, CollectedAnnouncement.STATUS_REJECTED
        )
        self.assertEqual(self.announcement.reviewed_by, self.user)

    def test_a_duplicate_can_be_confirmed(self):
        self.announcement.duplicate_status = CollectedAnnouncement.DUPLICATE_SUSPECTED

        self.client.post(self.url, {
            'action': 'confirm_duplicate',
            'announcement_id': self.announcement.pk,
        })

        self.announcement.refresh_from_db()
        self.assertEqual(
            self.announcement.duplicate_status,
            CollectedAnnouncement.DUPLICATE_CONFIRMED,
        )

    def test_a_duplicate_can_be_dismissed(self):
        self.announcement.duplicate_status = CollectedAnnouncement.DUPLICATE_SUSPECTED

        self.client.post(self.url, {
            'action': 'dismiss_duplicate',
            'announcement_id': self.announcement.pk,
        })

        self.announcement.refresh_from_db()
        self.assertEqual(
            self.announcement.duplicate_status,
            CollectedAnnouncement.DUPLICATE_DISMISSED,
        )

    def test_rejecting_an_annonce_does_not_delete_the_offer(self):
        self.client.post(self.url, {
            'action': 'reject_announcement',
            'announcement_id': self.announcement.pk,
        })

        self.assertTrue(Offer.objects.filter(pk=self.offer.pk).exists())
        self.assertEqual(self.offer.status, Offer.STATUS_DRAFT)

    def test_an_unknown_annonce_is_handled(self):
        response = self.client.post(self.url, {
            'action': 'reject_announcement',
            'announcement_id': 99999,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(CollectedAnnouncement.objects.count(), 1)
