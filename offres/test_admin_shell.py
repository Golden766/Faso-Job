"""Tests de la coque de l'administration.

La coque (menu lateral unique, barre superieure groupee, fil d'Ariane) doit
etre presente et coherente sur toutes les pages : celles de l'administration
Django comme celles de la plateforme.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Offer


class AdminShellTest(TestCase):
    """Navigation, fil d'Ariane et titres des pages d'administration."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='superadmin-shell',
            email='shell@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.offer = Offer.objects.create(
            title='Offre de test',
            company_name='Employeur de test',
            description='Description de test.',
            is_source_confirmed=True,
            status=Offer.STATUS_PUBLISHED,
        )

    def test_sidebar_is_present_on_every_admin_page(self):
        """Le menu lateral ne doit plus disparaitre selon la page visitee."""
        pages = [
            reverse('admin:index'),
            reverse('admin-expired-offers'),
            reverse('admin:offres_offer_changelist'),
            reverse('admin:offres_offersubmission_changelist'),
            reverse('admin:offres_offerreport_changelist'),
            reverse('admin-activity-report'),
            reverse('admin-backups'),
            reverse('two_factor_settings'),
            reverse(
                'admin:offres_offer_change',
                args=[self.offer.pk],
            ),
        ]

        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'fj-admin-sidebar')

    def test_sidebar_marks_the_current_section(self):
        response = self.client.get(reverse('admin:offres_offer_changelist'))

        self.assertContains(response, 'sidebar-link-active')

    def test_breadcrumb_points_to_the_section_list_and_not_to_the_app_index(self):
        """Le fil doit mener a la meme page que le menu lateral."""
        response = self.client.get(reverse('admin:offres_offer_changelist'))

        self.assertContains(
            response,
            reverse('admin:offres_offer_changelist'),
            status_code=200,
        )
        # L'index d'application de Django ne correspond a aucune page du site.
        self.assertNotContains(response, 'href="/admin/offres/"')
        self.assertNotContains(response, '&lt;ol')

    def test_breadcrumb_lists_the_object_on_a_change_form(self):
        response = self.client.get(
            reverse('admin:offres_offer_change', args=[self.offer.pk])
        )

        self.assertContains(response, 'Offre de test')
        self.assertContains(response, reverse('admin:offres_offer_changelist'))

    def test_changelist_title_is_an_editorial_label(self):
        """Django affiche par defaut « Selectionnez l'objet ... a changer »."""
        response = self.client.get(reverse('admin:offres_offer_changelist'))

        self.assertContains(response, '<h1>Offres</h1>', status_code=200)
        self.assertNotContains(response, 'Sélectionnez l&#x27;objet')

    def test_top_navigation_is_grouped_in_four_menus(self):
        response = self.client.get(reverse('admin:index'))

        for label in ('Offres', 'Référentiel', 'Pilotage', 'Réglages'):
            with self.subTest(menu=label):
                self.assertContains(response, '>%s</summary>' % label)

    def test_admin_navigation_has_no_useless_django_sidebar(self):
        """Django affiche sa propre barre laterale : elle fait doublon."""
        response = self.client.get(reverse('admin:offres_offer_changelist'))

        self.assertNotContains(response, 'id="nav-sidebar"')
