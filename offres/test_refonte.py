import tempfile

from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
import re

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Offer, OfferReport, OfferSubmission, Source


def make_published_offer(title='Assistante comptable', **overrides):
    data = {
        'title': title,
        'company_name': 'Employeur de test',
        'description': 'Description de test.',
        'is_source_confirmed': True,
        'status': Offer.STATUS_PUBLISHED,
    }
    data.update(overrides)
    return Offer.objects.create(**data)


class HomeViewTest(TestCase):
    def test_home_is_a_distinct_landing_page(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Les opportunités professionnelles, au même endroit.')
        self.assertContains(response, f'action="{reverse("catalogue")}"')
        self.assertNotContains(response, 'Rechercher et filtrer')
        self.assertNotContains(response, 'href="#"')

    def test_home_only_shows_published_offers(self):
        published = make_published_offer('Offre visible sur l’accueil')
        draft = Offer.objects.create(
            title='Brouillon invisible',
            company_name='Employeur de test',
            description='Description de test.',
        )

        response = self.client.get(reverse('home'))

        self.assertContains(response, published.title)
        self.assertNotContains(response, draft.title)

    def test_home_offer_count_is_computed_from_database(self):
        make_published_offer('Première offre')
        make_published_offer('Deuxième offre')

        response = self.client.get(reverse('home'))

        self.assertContains(response, '2 annonces publiées.')

    def test_home_search_sends_keyword_and_location_to_catalogue(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="location"')

    def test_home_has_empty_state_without_published_offers(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Aucune offre n’est publiée pour le moment')

    def test_home_hides_expired_offers_and_ignores_them_in_the_count(self):
        make_published_offer('Offre encore ouverte')
        make_published_offer('Offre déjà expirée', deadline='2026-10-01')

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Offre encore ouverte')
        self.assertNotContains(response, 'Offre déjà expirée')
        self.assertContains(response, '1 annonce publiée.')

    def test_home_offer_cards_expose_favorite_controls(self):
        offer = make_published_offer('Offre à enregistrer')

        response = self.client.get(reverse('home'))

        self.assertContains(response, f'data-favorite-id="{offer.pk}"')
        self.assertContains(response, 'data-favorite-toggle')


class FavoritesViewTest(TestCase):
    def test_favorites_page_uses_the_main_site_shell(self):
        response = self.client.get(reverse('favorites'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mes favoris')
        self.assertContains(response, 'stockage de ce navigateur')
        self.assertContains(response, 'data-favorites-list')


class CatalogueViewTest(TestCase):
    def test_catalogue_uses_new_shell_and_real_headings(self):
        response = self.client.get(reverse('catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toutes les opportunités')
        self.assertContains(response, 'Rechercher et filtrer')
        self.assertContains(response, 'Résultats')
        self.assertContains(response, 'Fil d’Ariane')
        self.assertNotContains(response, 'href="#"')

    def test_catalogue_type_tabs_are_computed_from_database(self):
        make_published_offer('Offre CDI', employment_type='CDI')
        make_published_offer('Offre stage', employment_type='Stage')

        response = self.client.get(reverse('catalogue'))

        self.assertContains(response, f'{reverse("catalogue")}?type=CDI')
        self.assertContains(response, f'{reverse("catalogue")}?type=Stage')
        self.assertContains(response, 'CDI')

    def test_catalogue_active_filters_expose_removal_links(self):
        make_published_offer(
            'Offre à Ouagadougou',
            location='Ouagadougou',
            employment_type='CDI',
        )

        response = self.client.get(
            reverse('catalogue'),
            {'location': 'Ouagadougou', 'type': 'CDI'},
        )

        self.assertContains(response, 'Filtres actifs')
        self.assertContains(response, f'{reverse("catalogue")}?type=CDI')
        self.assertContains(response, f'{reverse("catalogue")}?location=Ouagadougou')

    def test_catalogue_can_sort_by_closest_deadline(self):
        today = timezone.localdate()
        later = make_published_offer(
            'Offre plus tardive', deadline=today + timedelta(days=45)
        )
        sooner = make_published_offer(
            'Offre la plus proche', deadline=today + timedelta(days=5)
        )

        response = self.client.get(reverse('catalogue'), {'sort': 'deadline'})

        titles = [offer.title for offer in response.context['offers']]
        self.assertLess(titles.index(sooner.title), titles.index(later.title))

    def test_catalogue_exposes_mobile_filters_dialog(self):
        response = self.client.get(reverse('catalogue'))

        self.assertContains(response, 'id="catalogue-filters"')
        self.assertContains(response, 'aria-controls="catalogue-filters"')
        self.assertContains(response, 'Fermer les filtres')

    def test_catalogue_hides_expired_offers(self):
        make_published_offer('Offre encore ouverte', deadline='2026-12-31')
        make_published_offer('Offre déjà expirée', deadline='2026-10-01')

        response = self.client.get(reverse('catalogue'))

        self.assertContains(response, 'Offre encore ouverte')
        self.assertNotContains(response, 'Offre déjà expirée')
        self.assertEqual(response.context['result_count'], 1)

    def test_catalogue_keeps_offer_closing_today_until_its_hour_has_passed(self):
        with patch(
            'offres.views.timezone.localtime',
            return_value=datetime(2026, 11, 20, 12),
        ):
            make_published_offer(
                'Offre clôturée ce matin',
                deadline='2026-11-20',
                deadline_time='09:00',
            )
            make_published_offer(
                'Offre encore ouverte ce jour',
                deadline='2026-11-20',
                deadline_time='17:00',
            )

            response = self.client.get(reverse('catalogue'))

        self.assertNotContains(response, 'Offre clôturée ce matin')
        self.assertContains(response, 'Offre encore ouverte ce jour')
        self.assertEqual(response.context['result_count'], 1)

    def test_catalogue_keeps_offers_without_a_deadline(self):
        make_published_offer('Offre sans date de clôture', deadline=None)

        response = self.client.get(reverse('catalogue'))

        self.assertContains(response, 'Offre sans date de clôture')
        self.assertEqual(response.context['result_count'], 1)


class OfferDetailViewTest(TestCase):
    def test_detail_uses_new_shell_and_real_sections(self):
        offer = make_published_offer(
            'Comptable confirmé',
            company_name='Cabinet Faso',
            location='Ouagadougou',
            employment_type='CDI',
            deadline='2026-12-31',
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Comptable confirmé')
        self.assertContains(response, 'Informations essentielles')
        self.assertContains(response, 'À propos du poste')
        self.assertContains(response, 'Traçabilité et contrôle')
        self.assertContains(response, 'Comment postuler ?')
        self.assertContains(response, 'Fil d’Ariane')
        self.assertContains(response, 'has-detail-apply')
        self.assertNotContains(response, 'href="#"')

    def test_detail_shows_missions_profile_and_education(self):
        """Les informations extraites par la veille sont visibles du public."""
        offer = make_published_offer(
            'Charge de projets',
            company_name='Telecom Faso',
            location='Ouagadougou',
            missions='Piloter les projets et suivre les budgets.',
            required_profile='Trois ans d experience en gestion de projet.',
            required_education='Bac+5',
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Missions du poste')
        self.assertContains(response, 'Piloter les projets et suivre les budgets.')
        self.assertContains(response, 'Profil recherché')
        self.assertContains(response, 'Trois ans d experience en gestion de projet.')
        self.assertContains(response, 'Niveau d’études')
        self.assertContains(response, 'Bac+5')

    def test_detail_hides_the_empty_new_sections(self):
        """Une offre sans ces informations ne montre pas de bloc vide."""
        offer = make_published_offer('Offre simple', company_name='Entreprise')

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Missions du poste')
        self.assertNotContains(response, 'Profil recherché')

    def test_detail_meta_description_is_built_from_offer_data(self):
        offer = make_published_offer(
            'Chauffeur livreur',
            company_name='Transports Sahel',
            location='Bobo-Dioulasso',
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertContains(response, 'Chauffeur livreur chez Transports Sahel à Bobo-Dioulasso.')
        self.assertContains(response, 'Consultez les modalités de candidature sur Faso Job.')

    def test_detail_shows_whatsapp_cta_and_channel(self):
        offer = make_published_offer(
            whatsapp_number='+226 70-12-34-56',
            application_method='whatsapp',
            deadline='2026-12-31',
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertContains(response, 'https://wa.me/22670123456')
        self.assertContains(response, 'Postuler sur WhatsApp')
        self.assertContains(response, 'fj-btn--whatsapp')
        self.assertContains(response, 'fj-detail-apply-bar')
        self.assertContains(response, 'data-copy-link')
        self.assertContains(response, 'data-share-status')

    def test_detail_expired_offer_is_not_public(self):
        offer = make_published_offer(
            'Offre expirée',
            deadline='2026-10-01',
            application_email='rh@example.com',
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 404)
        # Le visiteur est informé et renvoyé vers les offres ouvertes.
        self.assertContains(
            response,
            'Cette offre n’est plus disponible',
            status_code=404,
        )
        self.assertContains(response, reverse('catalogue'), status_code=404)
        # Le contenu de l'annonce n'est plus affiché.
        self.assertNotContains(response, 'Offre expirée', status_code=404)
        self.assertNotContains(response, 'rh@example.com', status_code=404)

    def test_detail_has_traceability_badges_and_fraud_warning(self):
        source = Source.objects.create(name='Source de test')
        offer = make_published_offer(
            source=source,
            is_source_confirmed=True,
            is_employer_verified=False,
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertContains(response, 'Source vérifiée')
        self.assertContains(response, 'Entreprise non vérifiée')
        self.assertContains(response, 'Rappel de vigilance')
        self.assertContains(response, 'Aucun recruteur sérieux ne demande d’argent')
        self.assertContains(response, 'Signaler cette offre')

    def test_detail_similar_offers_exclude_current_offer(self):
        current = make_published_offer('Offre courante')
        other = make_published_offer('Offre voisine')

        response = self.client.get(reverse('offer_detail', args=[current.slug]))

        similar_ids = [offer.pk for offer in response.context['similar_offers']]
        self.assertIn(other.pk, similar_ids)
        self.assertNotIn(current.pk, similar_ids)
        self.assertContains(response, 'Offres similaires')

    def test_detail_similar_offers_exclude_expired_offers(self):
        current = make_published_offer('Offre courante')
        make_published_offer('Offre voisine expirée', deadline='2026-10-01')

        response = self.client.get(reverse('offer_detail', args=[current.slug]))

        similar_ids = [offer.pk for offer in response.context['similar_offers']]
        self.assertNotIn(
            'Offre voisine expirée',
            [offer.title for offer in response.context['similar_offers']],
        )
        self.assertNotContains(response, 'Offre voisine expirée')
        self.assertEqual(similar_ids, [])


class SubmitOfferViewTest(TestCase):
    def valid_payload(self, **overrides):
        payload = {
            'title': 'Assistant comptable',
            'company_name': 'Cabinet Faso',
            'employer_kind': Offer.EMPLOYER_COMPANY,
            'location': 'Ouagadougou',
            'employment_type': 'CDI',
            'details': 'Missions et profil détaillés dans l’annonce.',
            'source_name': 'Site de l’entreprise',
            'application_method': 'email',
            'application_email': 'recrutement@example.bf',
            'contact_email': 'contact@example.bf',
            'declarant_role': OfferSubmission.DECLARANT_EMPLOYER,
            'ethics_commitment': 'on',
        }
        payload.update(overrides)
        return payload

    def test_submit_page_uses_new_shell_and_numbered_sections(self):
        response = self.client.get(reverse('submit_offer'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Proposer une annonce ou une opportunité')
        self.assertContains(response, 'Comment nous vérifions')
        self.assertContains(response, 'Charte éthique')
        self.assertContains(response, 'id="section-title-1"')
        self.assertContains(response, 'id="section-title-5"')
        self.assertContains(response, 'data-step-navigation')
        self.assertContains(response, 'data-multistep-form')
        self.assertContains(response, 'data-form-step="0"')
        self.assertContains(response, 'data-step-next')
        self.assertContains(response, 'name="declarant_role"')
        self.assertContains(response, 'name="contact_phone"')
        self.assertContains(response, 'name="ethics_commitment"')
        self.assertNotContains(response, 'href="#"')

    def test_legacy_submit_url_redirects_permanently(self):
        response = self.client.get('/proposer-une-offre/')

        self.assertRedirects(
            response,
            reverse('submit_offer'),
            status_code=301,
        )

    def test_submit_page_shows_verification_and_anti_fraud_warnings(self):
        response = self.client.get(reverse('submit_offer'))

        self.assertContains(response, 'Rappel anti-fraude')
        self.assertContains(response, 'Aucune annonce n’est mise en ligne avant cet examen')
        self.assertContains(response, 'Vos coordonnées restent privées')
        self.assertNotContains(response, '4h à 24h')
        self.assertNotContains(response, '92,4')

    def test_valid_submission_is_pending_and_never_published(self):
        response = self.client.post(
            reverse('submit_offer'),
            self.valid_payload(
                declarant_role=OfferSubmission.DECLARANT_WITNESS,
                contact_phone='+226 70 00 00 00',
            ),
        )

        self.assertRedirects(response, reverse('submit_offer'))
        submission = OfferSubmission.objects.get(title='Assistant comptable')
        self.assertEqual(submission.status, OfferSubmission.STATUS_PENDING)
        self.assertEqual(submission.declarant_role, OfferSubmission.DECLARANT_WITNESS)
        self.assertEqual(submission.contact_phone, '+226 70 00 00 00')
        self.assertTrue(submission.ethics_commitment)
        self.assertIsNone(submission.offer)
        self.assertFalse(Offer.objects.filter(title='Assistant comptable').exists())

    def test_success_message_confirms_pending_review(self):
        response = self.client.post(
            reverse('submit_offer'),
            self.valid_payload(),
            follow=True,
        )

        self.assertContains(response, 'Votre proposition a bien été reçue')
        self.assertContains(
            response,
            'Elle est en attente de vérification et ne sera pas publiée automatiquement.',
        )

    def test_ethics_commitment_is_required(self):
        payload = self.valid_payload()
        payload.pop('ethics_commitment')

        response = self.client.post(reverse('submit_offer'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferSubmission.objects.exists())
        self.assertContains(response, 'Vous devez accepter la charte éthique')
        self.assertContains(response, 'data-error-target="ethics_commitment"')

    def test_submission_requires_a_contact_channel(self):
        response = self.client.post(
            reverse('submit_offer'),
            self.valid_payload(contact_email='', contact_phone=''),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferSubmission.objects.exists())
        self.assertContains(response, 'Indiquez un e-mail ou un téléphone')

    def test_submission_requires_channel_details_matching_method(self):
        response = self.client.post(
            reverse('submit_offer'),
            self.valid_payload(application_email=''),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferSubmission.objects.exists())
        self.assertContains(response, 'Indiquez l’adresse e-mail de candidature')

    def test_submission_validates_salary_range(self):
        response = self.client.post(
            reverse('submit_offer'),
            self.valid_payload(salary_min='500000', salary_max='300000'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferSubmission.objects.exists())
        self.assertContains(
            response,
            'La rémunération maximale doit être supérieure ou égale au minimum',
        )


class ReportFraudViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.TemporaryDirectory()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir.name)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        cls._media_dir.cleanup()
        super().tearDownClass()

    def valid_payload(self, **overrides):
        payload = {
            'reason': OfferReport.REASON_FEES,
            'suspect_title': 'Assistant logistique',
            'suspect_organization': 'Entreprise fictive',
            'suspect_phone': '+226 70 00 00 00',
            'suspect_channel': OfferReport.CHANNEL_WHATSAPP,
            'details': (
                'Un recruteur demande 5 000 FCFA de frais de dossier avant '
                'de transmettre une prétendue promesse d’embauche.'
            ),
        }
        payload.update(overrides)
        return payload

    def test_global_report_page_is_available_and_explains_the_process(self):
        response = self.client.get(reverse('report_fraud'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Signalez une arnaque ou une offre frauduleuse')
        self.assertContains(response, 'Règle cardinale')
        self.assertContains(response, 'Ce qui se passe ensuite')
        self.assertContains(response, 'Vos coordonnées restent privées')
        self.assertContains(response, 'Aucun statut ne change automatiquement')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'id="report-section-1"')
        self.assertContains(response, 'id="report-section-3"')
        self.assertNotContains(response, 'href="#"')
        self.assertNotContains(response, '142 arnaques')
        self.assertNotContains(response, '100% des dossiers')
        self.assertNotContains(response, 'Délai moyen')
        self.assertNotContains(response, 'Traitement prioritaire')
        self.assertNotContains(response, '+226 25 39 58 42')

    def test_offer_report_page_prefills_the_offer_details(self):
        offer = make_published_offer(
            'Comptable senior',
            company_name='Cabinet Exemple',
            location='Ouagadougou',
            application_method='whatsapp',
            whatsapp_number='+226 70 12 34 56',
        )

        response = self.client.get(reverse('report_offer', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Signalement lié à cette offre')
        self.assertContains(response, 'Comptable senior')
        self.assertContains(response, 'Cabinet Exemple')
        self.assertContains(response, 'value="+226 70 12 34 56"')
        self.assertEqual(response.context['form']['suspect_channel'].value(), 'whatsapp')

    def test_offer_detail_links_to_the_prefilled_report_page(self):
        offer = make_published_offer('Offre à signaler')

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertContains(response, reverse('report_offer', args=[offer.slug]))

    def test_expired_offer_cannot_be_reported_from_the_public_site(self):
        offer = make_published_offer('Offre expirée', deadline='2026-10-01')

        response = self.client.get(reverse('report_offer', args=[offer.slug]))

        self.assertEqual(response.status_code, 404)

    def test_report_requires_an_identifier_for_a_global_report(self):
        payload = self.valid_payload(
            suspect_title='',
            suspect_organization='',
            suspect_phone='',
        )

        response = self.client.post(reverse('report_fraud'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferReport.objects.exists())
        self.assertContains(
            response,
            'Indiquez au moins un élément permettant d’identifier l’annonce',
        )

    def test_report_requires_a_detailed_description(self):
        response = self.client.post(
            reverse('report_fraud'),
            self.valid_payload(details='Trop court.'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferReport.objects.exists())
        self.assertContains(response, '30 caractères minimum')

    def test_report_requires_a_main_reason(self):
        payload = self.valid_payload()
        payload.pop('reason')

        response = self.client.post(reverse('report_fraud'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferReport.objects.exists())
        self.assertContains(response, 'Choisissez le motif principal')

    def test_report_accepts_a_valid_evidence_file(self):
        upload = SimpleUploadedFile(
            'capture.png',
            b'\x89PNG\r\n\x1a\n' + b'0' * 64,
            content_type='image/png',
        )

        response = self.client.post(
            reverse('report_fraud'),
            self.valid_payload(evidence=upload),
        )

        self.assertRedirects(response, f"{reverse('report_fraud')}?recu=1")
        report = OfferReport.objects.get()
        self.assertIn('signalements/', report.evidence.name)

    def test_report_rejects_an_unsupported_evidence_extension(self):
        upload = SimpleUploadedFile(
            'preuve.exe',
            b'MZ' + b'0' * 64,
            content_type='application/octet-stream',
        )

        response = self.client.post(
            reverse('report_fraud'),
            self.valid_payload(evidence=upload),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferReport.objects.exists())
        self.assertContains(response, 'n’est pas autorisée')

    def test_report_rejects_an_oversized_evidence_file(self):
        upload = SimpleUploadedFile(
            'capture.pdf',
            b'%PDF-1.4' + b'0' * (5 * 1024 * 1024),
            content_type='application/pdf',
        )

        response = self.client.post(
            reverse('report_fraud'),
            self.valid_payload(evidence=upload),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferReport.objects.exists())
        self.assertContains(response, 'ne doit pas dépasser 5 Mo')

    def test_evidence_is_only_downloadable_by_staff(self):
        upload = SimpleUploadedFile(
            'capture.png',
            b'\x89PNG\r\n\x1a\n' + b'0' * 64,
            content_type='image/png',
        )
        self.client.post(reverse('report_fraud'), self.valid_payload(evidence=upload))
        report = OfferReport.objects.get()
        url = reverse('report_evidence', args=[report.pk])

        anonymous_response = self.client.get(url)
        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn('/admin/login/', anonymous_response.url)

        user_model = get_user_model()
        visitor = user_model.objects.create_user(
            username='visiteur',
            password='mot-de-passe-test',
        )
        self.client.force_login(visitor)
        visitor_response = self.client.get(url)
        self.assertEqual(visitor_response.status_code, 302)
        self.assertIn('/admin/login/', visitor_response.url)

        staff = user_model.objects.create_user(
            username='moderateur',
            password='mot-de-passe-test',
            is_staff=True,
        )
        self.client.force_login(staff)
        staff_response = self.client.get(url)
        self.assertEqual(staff_response.status_code, 200)
        self.assertIn('attachment', staff_response['Content-Disposition'])

    def test_evidence_download_returns_404_without_a_file(self):
        user_model = get_user_model()
        staff = user_model.objects.create_user(
            username='moderateur-sans-preuve',
            password='mot-de-passe-test',
            is_staff=True,
        )
        report = OfferReport.objects.create(
            reason=OfferReport.REASON_OTHER,
            suspect_title='Annonce sans preuve',
            details='Signalement sans pièce jointe.',
        )

        self.client.force_login(staff)
        response = self.client.get(reverse('report_evidence', args=[report.pk]))

        self.assertEqual(response.status_code, 404)

    def test_success_state_confirms_human_review(self):
        response = self.client.get(f"{reverse('report_fraud')}?recu=1")

        self.assertContains(response, 'Votre signalement a bien été enregistré')
        self.assertContains(response, 'Aucun changement de statut n’est appliqué automatiquement')
        self.assertNotContains(response, 'id="report-section-1"')


class MethodViewTest(TestCase):
    def test_method_page_explains_the_verification_path(self):
        response = self.client.get(reverse('method'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Comment Faso Job vérifie les annonces')
        self.assertContains(response, 'Le parcours d’une annonce, de la collecte à la publication')
        self.assertContains(response, 'Collecte des annonces')
        self.assertContains(response, 'Source et employeur')
        self.assertContains(response, 'Conditions de candidature')
        self.assertContains(response, 'Publication et suivi')

    def test_method_page_lists_the_five_badges(self):
        response = self.client.get(reverse('method'))

        self.assertContains(response, 'Comprendre les 5 badges d’état')
        for label in (
            'Source vérifiée',
            'Employeur vérifié',
            'Disponibilité confirmée',
            'Source non vérifiée',
            'Candidature fermée',
        ):
            self.assertContains(response, label)

    def test_method_page_lists_the_four_red_lines(self):
        response = self.client.get(reverse('method'))

        self.assertContains(response, '4 motifs d’exclusion immédiate')
        self.assertContains(response, 'Frais de dossier ou de badge exigés')
        self.assertContains(response, 'Dépôt obligatoire par Mobile Money')
        self.assertContains(response, 'Entité fictive ou identité intraçable')
        self.assertContains(response, 'Réseaux MLM et vente pyramidale')

    def test_method_page_provides_an_accessible_faq(self):
        """La FAQ doit rester utilisable, independamment de son habillage.

        On verifie le comportement attendu : quatre questions repondables
        au clavier, chacune signalee par un element details et un resume.
        On ne verifie pas les noms de classes CSS : ce sont des choix de
        presentation, pas une promesse faite a l utilisateur.
        """
        response = self.client.get(reverse('method'))

        self.assertContains(response, 'Questions fréquentes sur notre méthode')

        page = response.content.decode()

        # Les questions de la FAQ sont les resumes qui Biblio graphiques
        # d un chevron : c est le contenu qui les identifie, pas une
        # classe CSS.
        summaries = re.findall(r'<summary[^>]*>(.*?)</summary>', page, re.DOTALL)
        questions = [s for s in summaries if 'chevron-down' in s]
        self.assertEqual(len(questions), 4)

        # Chaque question est un texte lisible, pas une image seule.
        for question in questions:
            self.assertNotEqual(
                re.sub(r'<[^>]+>', '', question).strip(),
                '',
            )

        # La page reste utilisable au clavier : le detail et son resume
        # sont associes et le detail est refermable nativement.
        self.assertEqual(page.count('<details'), page.count('</details>'))
        self.assertEqual(page.count('<summary'), len(summaries))

    def test_method_page_links_to_submission_and_reporting(self):
        response = self.client.get(reverse('method'))

        self.assertContains(response, reverse('submit_offer'))
        self.assertContains(response, reverse('report_fraud'))
        self.assertNotContains(response, 'href="#"')

    def test_method_page_avoids_invented_statistics_and_delays(self):
        response = self.client.get(reverse('method'))

        self.assertNotContains(response, '4h à 24h')
        self.assertNotContains(response, '100%')
        self.assertNotContains(response, '0 FCFA')
        self.assertNotContains(response, '142 arnaques')
        self.assertNotContains(response, '+226 25 39 58 42')

    def test_navigation_points_to_the_method_page(self):
        home_response = self.client.get(reverse('home'))
        method_url = reverse('method')

        self.assertContains(home_response, f'href="{method_url}"')
        self.assertContains(home_response, f'href="{method_url}#controle-des-annonces"')
        self.assertNotContains(home_response, f'href="{reverse("home")}#parcours"')

    def test_offer_detail_links_to_the_method_page(self):
        offer = make_published_offer('Offre avec méthode de contrôle')

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertContains(
            response,
            f'href="{reverse("method")}#controle-des-annonces"',
        )


class StyleguideViewTest(TestCase):
    @override_settings(DEBUG=True)
    def test_styleguide_is_available_in_debug(self):
        response = self.client.get(reverse('styleguide'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Charte visuelle Faso Job')
        self.assertContains(response, 'Faso Job')

    @override_settings(DEBUG=False)
    def test_styleguide_is_hidden_outside_debug(self):
        response = self.client.get(reverse('styleguide'))

        self.assertEqual(response.status_code, 404)
