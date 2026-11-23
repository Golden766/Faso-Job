from io import StringIO
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Category, Offer, OfferReport, OfferSubmission, Source


class OfferModelTest(TestCase):
    def setUp(self):
        self.source = Source.objects.create(name='Source fiable', url='https://example.com', is_verified=True)
        self.category = Category.objects.create(name='Data', slug='data')

    def test_published_offer_sets_publication_flags(self):
        offer = Offer.objects.create(
            title='Développeur Python',
            company_name='Acme',
            category=self.category,
            source=self.source,
            description='Description de test.',
            is_source_confirmed=True,
            is_employer_verified=True,
            status=Offer.STATUS_PUBLISHED,
        )

        self.assertTrue(offer.is_published)
        self.assertTrue(offer.is_available)
        self.assertIsNotNone(offer.published_at)

    def test_pending_offer_is_not_public(self):
        offer = Offer.objects.create(
            title='Offre en attente',
            company_name='Acme',
            category=self.category,
            source=self.source,
            description='Description de test.',
            status=Offer.STATUS_PENDING,
        )

        self.assertFalse(offer.is_published)
        self.assertIsNone(offer.published_at)

    def test_returning_offer_to_review_clears_publication_timestamp(self):
        offer = Offer.objects.create(
            title='Offre publiée',
            company_name='Acme',
            source=self.source,
            description='Description de test.',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        offer.status = Offer.STATUS_PENDING
        offer.save()

        self.assertFalse(offer.is_published)
        self.assertIsNone(offer.published_at)

    def test_published_offer_requires_verification_or_source(self):
        offer = Offer(
            title='Offre à vérifier',
            company_name='Acme',
            category=self.category,
            source=self.source,
            description='Description de test.',
            status=Offer.STATUS_PUBLISHED,
        )

        with self.assertRaises(ValidationError):
            offer.full_clean()

    def test_submission_can_be_converted_to_offer(self):
        submission = OfferSubmission.objects.create(
            company_name='Acme',
            title='Offre issue d’une soumission',
            employer_kind=Offer.EMPLOYER_COMPANY,
            source_name='Facebook',
            contact_email='contact@example.com',
            details='Description de la soumission.',
            application_method='physical',
            application_instructions='Déposer le dossier au siège.',
            required_documents='CV\nLettre de motivation',
            deadline='2026-12-01',
            deadline_time='17:30',
            status=OfferSubmission.STATUS_ACCEPTED,
        )

        offer = submission.create_offer_from_submission()

        self.assertEqual(offer.company_name, 'Acme')
        self.assertFalse(offer.is_published)
        self.assertFalse(offer.is_source_confirmed)
        self.assertFalse(offer.is_employer_verified)
        self.assertEqual(offer.status, Offer.STATUS_PENDING)
        self.assertEqual(offer.source.name, 'Facebook')
        self.assertEqual(offer.application_method, 'physical')
        self.assertEqual(offer.application_instructions, 'Déposer le dossier au siège.')
        self.assertEqual(offer.required_documents, 'CV\nLettre de motivation')
        self.assertEqual(offer.deadline_time.strftime('%H:%M'), '17:30')
        self.assertEqual(submission.create_offer_from_submission(), offer)


class OfferViewTest(TestCase):
    def setUp(self):
        self.source = Source.objects.create(name='Source fiable', url='https://example.com', is_verified=True)
        self.category = Category.objects.create(name='Data', slug='data')

    def test_unpublished_offer_is_hidden_from_detail_view(self):
        offer = Offer.objects.create(
            title='Offre cachée',
            company_name='Acme',
            category=self.category,
            source=self.source,
            description='Description de test.',
            is_source_confirmed=True,
            status=Offer.STATUS_DRAFT,
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))
        self.assertEqual(response.status_code, 404)

    def test_published_offer_detail_page_is_accessible(self):
        offer = Offer.objects.create(
            title='Offre publique',
            company_name='Acme',
            category=self.category,
            source=self.source,
            description='Description de test.',
            is_source_confirmed=True,
            is_employer_verified=True,
            is_published=True,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, offer.title)

    def test_detail_page_shows_up_to_three_relevant_similar_offers(self):
        current_offer = Offer.objects.create(
            title='Développeur Python principal',
            company_name='Acme',
            category=self.category,
            employment_type='CDI',
            description='Description de test.',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )
        similar_offers = [
            Offer.objects.create(
                title=f'Développeur Python {index}',
                company_name='Entreprise similaire',
                category=self.category,
                description='Description de test.',
                is_source_confirmed=True,
                status=Offer.STATUS_PUBLISHED,
            )
            for index in range(4)
        ]
        unrelated_offer = Offer.objects.create(
            title='Comptable',
            company_name='Autre entreprise',
            category=Category.objects.create(name='Comptabilité', slug='comptabilite'),
            employment_type='Stage',
            description='Description de test.',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('offer_detail', args=[current_offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['similar_offers']), 3)
        self.assertContains(response, 'Offres similaires')
        self.assertNotIn(current_offer.pk, [offer.pk for offer in response.context['similar_offers']])
        self.assertNotContains(response, unrelated_offer.title)
        shown_titles = {offer.title for offer in response.context['similar_offers']}
        self.assertTrue(shown_titles.issubset({offer.title for offer in similar_offers}))
        for similar_offer in response.context['similar_offers']:
            self.assertContains(response, similar_offer.title)

    def test_detail_page_falls_back_to_three_most_recent_offers_without_matches(self):
        offer = Offer.objects.create(
            title='Offre sans critère de comparaison',
            company_name='Acme',
            description='Description de test.',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )
        recent_offers = [
            Offer.objects.create(
                title=f'Offre récente {index}',
                company_name='Autre entreprise',
                description='Description de test.',
                is_source_confirmed=True,
                status=Offer.STATUS_PUBLISHED,
            )
            for index in range(4)
        ]

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['similar_offers']), 3)
        self.assertContains(response, 'Offres similaires')
        shown_offers = list(response.context['similar_offers'])
        self.assertEqual(shown_offers, list(reversed(recent_offers[-3:])))
        self.assertNotIn(offer.pk, [similar_offer.pk for similar_offer in shown_offers])

    def test_detail_page_keeps_source_and_availability_states_distinct(self):
        offer = Offer.objects.create(
            title='Offre avec modalités',
            company_name='Acme',
            source=self.source,
            description='Description de test.',
            whatsapp_number='+226 70-12-34-56',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Source vérifiée')
        self.assertContains(response, 'Candidature ouverte')
        self.assertContains(response, 'https://wa.me/22670123456')
        self.assertContains(response, 'Entreprise non vérifiée')
        self.assertContains(response, 'fj-detail-apply-bar')
        self.assertContains(response, 'fj-btn--whatsapp')
        self.assertContains(response, 'Postuler sur WhatsApp')

    def test_detail_page_shows_required_documents_deadline_and_publication(self):
        offer = Offer.objects.create(
            title='Assistante administrative',
            company_name='Association Exemple',
            employer_kind=Offer.EMPLOYER_INDIVIDUAL,
            source=self.source,
            description='Description du poste.',
            application_method='physical',
            application_instructions='Déposer le dossier à la réception.',
            required_documents='CV\nCopie du diplôme',
            deadline='2026-12-01',
            deadline_time='16:00',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Employeur non vérifié')
        self.assertContains(response, 'Source vérifiée')
        self.assertContains(response, 'Dossier de candidature à fournir')
        self.assertContains(response, 'CV')
        self.assertContains(response, '01/12/2026 à 16:00')
        self.assertContains(response, 'Dépôt physique')
        self.assertContains(response, 'fj-detail-apply-bar')
        self.assertContains(response, 'Date de publication')
        self.assertContains(response, 'Dépôt physique')

    def test_detail_header_shows_countdown_relative_to_current_date(self):
        offer = Offer.objects.create(
            title='Offre avec clôture à venir',
            company_name='Acme',
            source=self.source,
            description='Description.',
            application_email='candidature@example.com',
            deadline='2026-10-25',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        with patch('offres.views.timezone.localtime', return_value=datetime(2026, 10, 22, 12)):
            response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['days_until_deadline'], 3)
        self.assertContains(response, 'Dépôt de candidature par e-mail')
        self.assertContains(response, '3 jours restants avant la clôture')
        self.assertNotContains(response, 'Ouagadougou')

    def test_detail_header_shows_today_and_expired_deadline_states(self):
        today_offer = Offer.objects.create(
            title='Offre clôturant aujourd’hui',
            company_name='Acme',
            source=self.source,
            description='Description.',
            deadline='2026-10-22',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )
        expired_offer = Offer.objects.create(
            title='Offre dont le délai est dépassé',
            company_name='Acme',
            source=self.source,
            description='Description.',
            deadline='2026-10-20',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        with patch('offres.views.timezone.localtime', return_value=datetime(2026, 10, 22, 12)):
            today_response = self.client.get(reverse('offer_detail', args=[today_offer.slug]))
            expired_response = self.client.get(reverse('offer_detail', args=[expired_offer.slug]))

        self.assertContains(today_response, 'Clôture aujourd’hui')
        self.assertEqual(today_response.context['days_until_deadline'], 0)
        # Une offre dont la date limite est dépassée n'est plus publique.
        self.assertEqual(expired_response.status_code, 404)

    def test_unverified_source_uses_red_status_badge(self):
        offer = Offer.objects.create(
            title='Offre à source non confirmée',
            company_name='Acme',
            source=self.source,
            description='Description.',
            is_source_confirmed=False,
            is_employer_verified=True,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fj-badge--danger')
        self.assertContains(response, 'Source non vérifiée')
        self.assertContains(response, 'fj-badge--success')
        self.assertContains(response, 'Entreprise vérifiée')

    def test_unavailable_published_offer_detail_shows_closed_application_badge(self):
        offer = Offer.objects.create(
            title='Offre terminée',
            company_name='Acme',
            source=self.source,
            description='Description de test.',
            is_source_confirmed=True,
            is_available=False,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Candidature fermée')
        self.assertNotContains(response, 'floating-apply-button')

    def test_offer_with_no_source_does_not_show_source_status_badges(self):
        offer = Offer.objects.create(
            title='Offre sans source',
            company_name='Acme',
            description='Description.',
            is_employer_verified=True,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('offer_detail', args=[offer.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Source vérifiée')
        self.assertNotContains(response, 'Source non vérifiée')

    def test_home_page_offers_search_by_keyword_and_location(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="location"')

    def test_unavailable_offer_is_hidden_from_catalogue(self):
        offer = Offer.objects.create(
            title='Offre fermée',
            company_name='Acme',
            category=self.category,
            source=self.source,
            description='Description de test.',
            is_source_confirmed=True,
            is_available=False,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, offer.title)

    def test_catalogue_uses_french_admin_labels_and_public_copy(self):
        response = self.client.get(reverse('catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rechercher et filtrer')
        self.assertContains(response, 'Résultats')

    def test_catalogue_filters_by_type_source_and_salary_range(self):
        matching_offer = Offer.objects.create(
            title='Développeur confirmé',
            company_name='Acme',
            source=self.source,
            location='Ouagadougou',
            employment_type='CDI',
            description='Description de test.',
            salary_min='400000',
            salary_max='600000',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )
        Offer.objects.create(
            title='Assistant stagiaire',
            company_name='Acme',
            source=self.source,
            location='Ouagadougou',
            employment_type='Stage',
            description='Description de test.',
            salary_min='100000',
            salary_max='200000',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(
            reverse('catalogue'),
            {
                'type': 'CDI',
                'source_verified': '1',
                'salary_min': '350000',
                'salary_max': '650000',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['result_count'], 1)
        self.assertContains(response, matching_offer.title)
        self.assertNotContains(response, 'Assistant stagiaire')

    def test_catalogue_filters_offers_by_closing_date_range(self):
        matching_offer = Offer.objects.create(
            title='Offre clôturant dans la période',
            company_name='Acme',
            source=self.source,
            description='Description de test.',
            deadline='2026-11-10',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )
        Offer.objects.create(
            title='Offre clôturant hors période',
            company_name='Acme',
            source=self.source,
            description='Description de test.',
            deadline='2026-11-20',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )
        Offer.objects.create(
            title='Offre sans date de clôture',
            company_name='Acme',
            source=self.source,
            description='Description de test.',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        with patch('offres.views.timezone.localtime', return_value=datetime(2026, 11, 5, 12)):
            response = self.client.get(
                reverse('catalogue'),
                {'deadline_from': '2026-11-01', 'deadline_to': '2026-11-15'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['result_count'], 1)
        self.assertContains(response, matching_offer.title)
        self.assertNotContains(response, 'Offre clôturant hors période')
        self.assertNotContains(response, 'Offre sans date de clôture')

    def test_catalogue_invalid_closing_date_filter_shows_error(self):
        response = self.client.get(reverse('catalogue'), {'deadline_from': 'invalid'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saisissez une date de clôture valide.')
        self.assertEqual(response.context['result_count'], 0)

    def test_catalogue_card_shows_clickable_offer_and_deadline_urgency(self):
        offer = Offer.objects.create(
            title='Offre urgente',
            company_name='Acme',
            location='Ouagadougou',
            employment_type='CDI',
            salary_min='350000',
            salary_max='500000',
            salary_currency='FCFA',
            source=self.source,
            description='Description de test.',
            deadline=date(2026, 10, 25),
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        with patch(
            'offres.views.timezone.localtime',
            return_value=datetime(2026, 10, 22, 12),
        ):
            response = self.client.get(reverse('catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("offer_detail", args=[offer.slug])}"')
        self.assertContains(response, 'aria-label="Consulter l’offre : Offre urgente"')
        self.assertContains(response, 'Consulter l’offre')
        self.assertContains(response, 'Ouagadougou')
        self.assertContains(response, 'CDI')
        self.assertContains(response, '350000')
        self.assertContains(response, '500000')
        self.assertContains(response, 'FCFA')
        self.assertContains(response, 'Clôture le 25/10/2026')
        self.assertContains(response, 'Reste 3 jours pour postuler')
        self.assertContains(response, 'is-urgent')

    def test_invalid_salary_filter_shows_error_without_crashing(self):
        response = self.client.get(reverse('catalogue'), {'salary_min': 'NaN'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saisissez un montant numérique valide.')
        self.assertEqual(response.context['result_count'], 0)

    def test_catalogue_paginates_results_and_preserves_filters(self):
        for index in range(12):
            Offer.objects.create(
                title=f'Offre {index}',
                company_name='Acme',
                source=self.source,
                location='Ouagadougou',
                description='Description de test.',
                is_source_confirmed=True,
                status=Offer.STATUS_PUBLISHED,
            )

        response = self.client.get(reverse('catalogue'), {'location': 'Ouagadougou', 'page': '2'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertContains(response, 'location=Ouagadougou&page=1')

    def test_public_submission_is_saved_pending_and_not_published(self):
        response = self.client.post(
            reverse('submit_offer'),
            {
                'company_name': 'Entreprise de test',
                'title': 'Chargé de projet',
                'employer_kind': Offer.EMPLOYER_COMPANY,
                'location': 'Ouagadougou',
                'employment_type': 'CDD',
                'contact_email': 'contact@example.com',
                'details': 'Description complète de l’offre.',
                'source_name': 'WhatsApp',
                'application_method': 'whatsapp',
                'whatsapp_number': '+226 70 12 34 56',
                'required_documents': 'CV\nLettre de motivation',
                'deadline': '2026-12-01',
                'deadline_time': '17:00',
                'declarant_role': 'witness',
                'contact_phone': '+226 70 00 00 00',
                'ethics_commitment': 'on',
            },
        )

        self.assertRedirects(response, reverse('submit_offer'))
        submission = OfferSubmission.objects.get(title='Chargé de projet')
        self.assertEqual(submission.status, OfferSubmission.STATUS_PENDING)
        self.assertEqual(submission.source_name, 'WhatsApp')
        self.assertEqual(submission.application_method, 'whatsapp')
        self.assertEqual(submission.required_documents, 'CV\nLettre de motivation')
        self.assertEqual(submission.deadline_time.strftime('%H:%M'), '17:00')
        self.assertEqual(submission.declarant_role, OfferSubmission.DECLARANT_WITNESS)
        self.assertEqual(submission.contact_phone, '+226 70 00 00 00')
        self.assertTrue(submission.ethics_commitment)
        self.assertIsNone(submission.offer)
        self.assertFalse(Offer.objects.filter(title='Chargé de projet').exists())

    def test_public_submission_requires_offer_details(self):
        response = self.client.post(
            reverse('submit_offer'),
            {
                'company_name': 'Entreprise de test',
                'title': 'Chargé de projet',
                'contact_email': '',
                'details': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfferSubmission.objects.exists())
        self.assertContains(response, 'Ce champ est obligatoire')

    def test_submission_form_shows_source_mode_and_documents_sections(self):
        response = self.client.get(reverse('submit_offer'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Source de l’annonce')
        self.assertContains(response, 'Mode principal de candidature')
        self.assertContains(response, 'Dossier à fournir')
        self.assertContains(response, 'Type d’employeur')

    def test_public_report_is_saved_for_the_selected_offer(self):
        offer = Offer.objects.create(
            title='Offre publique',
            company_name='Acme',
            source=self.source,
            description='Description publique.',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.post(
            reverse('report_offer', args=[offer.slug]),
            {
                'reporter_name': 'Visiteur',
                'reporter_email': 'visiteur@example.com',
                'reason': OfferReport.REASON_MISLEADING,
                'suspect_title': offer.title,
                'suspect_organization': offer.company_name,
                'suspect_channel': OfferReport.CHANNEL_FASOJOB,
                'details': 'Le poste a déjà été pourvu et l’annonce reste en ligne.',
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('report_offer', args=[offer.slug])}?recu=1",
        )
        report = OfferReport.objects.get(offer=offer)
        self.assertEqual(report.status, OfferReport.STATUS_OPEN)
        self.assertEqual(report.reason, OfferReport.REASON_MISLEADING)
        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)
        self.assertTrue(offer.is_available)

    def test_public_report_does_not_change_offer_status(self):
        offer = Offer.objects.create(
            title='Offre toujours publiée',
            company_name='Acme',
            source=self.source,
            description='Description publique.',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

        self.client.post(
            reverse('report_offer', args=[offer.slug]),
            {
                'reason': OfferReport.REASON_FEES,
                'suspect_phone': '+226 70 00 00 00',
                'suspect_channel': OfferReport.CHANNEL_WHATSAPP,
                'details': 'Un paiement de 5 000 FCFA a été demandé avant l’entretien.',
            },
        )

        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.STATUS_PUBLISHED)
        self.assertTrue(offer.is_published)
        self.assertTrue(offer.is_available)

    def test_global_report_is_saved_without_an_offer(self):
        response = self.client.post(
            reverse('report_fraud'),
            {
                'reason': OfferReport.REASON_FAKE_COMPANY,
                'suspect_title': 'Assistant logistique',
                'suspect_organization': 'Entreprise fictive',
                'suspect_phone': '+226 70 00 00 00',
                'suspect_channel': OfferReport.CHANNEL_FACEBOOK,
                'details': 'Une page Facebook propose un poste et réclame des frais de dossier.',
            },
        )

        self.assertRedirects(response, f"{reverse('report_fraud')}?recu=1")
        report = OfferReport.objects.get()
        self.assertIsNone(report.offer)
        self.assertEqual(report.reason, OfferReport.REASON_FAKE_COMPANY)
        self.assertEqual(report.status, OfferReport.STATUS_OPEN)

    def test_report_form_is_not_available_for_unavailable_offer(self):
        offer = Offer.objects.create(
            title='Offre indisponible',
            company_name='Acme',
            source=self.source,
            description='Description.',
            is_source_confirmed=True,
            is_available=False,
            status=Offer.STATUS_PUBLISHED,
        )

        response = self.client.get(reverse('report_offer', args=[offer.slug]))

        self.assertEqual(response.status_code, 404)


class AdminInterfaceTest(TestCase):
    def test_admin_home_uses_french_branding_and_model_labels(self):
        user = get_user_model().objects.create_superuser(
            username='administrateur',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:index'), HTTP_ACCEPT_LANGUAGE='en')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Faso Job')
        self.assertContains(response, 'Administration')
        self.assertContains(response, 'Bonjour, administrateur.')
        self.assertContains(response, 'Rapport d’activité')
        self.assertContains(response, 'Actions à traiter')
        self.assertContains(response, 'proposition')
        self.assertContains(response, 'À contrôler')
        self.assertContains(response, 'Signalements')
        self.assertContains(response, 'Offres')
        self.assertContains(response, 'Soumissions')

    def test_admin_offer_and_submission_forms_expose_new_candidature_fields(self):
        user = get_user_model().objects.create_superuser(
            username='gestionnaire',
            email='gestionnaire@example.com',
            password='test-password',
        )
        self.client.force_login(user)

        offer_response = self.client.get(reverse('admin:offres_offer_add'))
        submission_response = self.client.get(reverse('admin:offres_offersubmission_add'))

        self.assertEqual(offer_response.status_code, 200)
        self.assertContains(offer_response, 'Dossier de candidature à fournir')
        self.assertContains(offer_response, 'Heure limite de candidature')
        self.assertContains(offer_response, 'Mode principal de candidature')
        self.assertEqual(submission_response.status_code, 200)
        self.assertContains(submission_response, 'Dossier de candidature à fournir')
        self.assertContains(submission_response, 'Nom de la source')

    def test_moderator_sees_editorial_dashboard_without_team_settings(self):
        user = get_user_model().objects.create_user(username='moderatrice', password='test-password')
        call_command(
            'setup_editorial_roles',
            '--username=moderatrice',
            '--role=moderator',
            stdout=StringIO(),
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Actions à traiter')
        self.assertContains(response, 'proposition')
        self.assertNotContains(response, 'Accès et rôles')
        self.assertNotContains(response, 'Gérer les comptes d’administration')


class EditorialRoleCommandTest(TestCase):
    def test_command_creates_distinct_editorial_roles(self):
        call_command('setup_editorial_roles', stdout=StringIO())

        editor = Group.objects.get(name='Éditeur')
        moderator = Group.objects.get(name='Modérateur')
        editor_codenames = set(editor.permissions.values_list('codename', flat=True))
        moderator_codenames = set(moderator.permissions.values_list('codename', flat=True))

        self.assertIn('add_offer', editor_codenames)
        self.assertNotIn('delete_offer', editor_codenames)
        self.assertIn('change_offerreport', moderator_codenames)
        self.assertNotEqual(editor_codenames, moderator_codenames)

    def test_command_assigns_role_to_existing_staff_user(self):
        user = get_user_model().objects.create_user(username='reviewer', password='test-password')

        call_command(
            'setup_editorial_roles',
            '--username=reviewer',
            '--role=moderator',
            stdout=StringIO(),
        )

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.groups.filter(name='Modérateur').exists())

    def test_moderator_can_review_but_cannot_delete_offers(self):
        user = get_user_model().objects.create_user(username='moderator', password='test-password')
        call_command(
            'setup_editorial_roles',
            '--username=moderator',
            '--role=moderator',
            stdout=StringIO(),
        )
        offer = Offer.objects.create(title='Offre de test', company_name='Acme')
        self.client.force_login(user)

        list_response = self.client.get(reverse('admin:offres_offer_changelist'))
        delete_response = self.client.get(reverse('admin:offres_offer_delete', args=[offer.pk]))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 403)
