"""Recette automatique de l'accessibilite et des ressources externes.

Commande de verification, a lancer avant toute livraison :

    python manage.py check_accessibility

Elle sort en code 1 si une verification echoue, ce qui permet de l utiliser
dans une chaine d integration continue.
"""

import os

from django.core.management.base import BaseCommand

from offres import accessibility

# Le fichier est dans offres/management/commands/ : trois remontees
# mene a la racine du projet.
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..')
)

CSS_FILES = [
    os.path.join(BASE_DIR, 'static', 'css', 'refonte', 'tokens.css'),
    os.path.join(BASE_DIR, 'static', 'css', 'refonte', 'base.css'),
    os.path.join(BASE_DIR, 'static', 'css', 'refonte', 'components.css'),
    os.path.join(BASE_DIR, 'static', 'css', 'refonte', 'pages.css'),
    os.path.join(BASE_DIR, 'static', 'css', 'refonte', 'detail.css'),
    os.path.join(BASE_DIR, 'static', 'css', 'refonte', 'submit.css'),
    os.path.join(BASE_DIR, 'static', 'css', 'refonte', 'method.css'),
    os.path.join(BASE_DIR, 'static', 'css', 'refonte', 'report.css'),
    os.path.join(BASE_DIR, 'static', 'css', 'admin.css'),
]

TEMPLATE_FILES = [
    os.path.join(BASE_DIR, 'templates', 'refonte', 'base.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'home.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'catalogue.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'offer_detail.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'offer_closed.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'submit_offer.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'method.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'report_fraud.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'styleguide.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'partials', 'header.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'partials', 'footer.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'partials', 'mobile_nav.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'partials', 'offer_card.html'),
    os.path.join(BASE_DIR, 'templates', 'refonte', 'partials', 'catalogue_filters.html'),
]


class Command(BaseCommand):
    help = 'Verifie contrastes, focus clavier, etiquettes et ressources externes.'

    def handle(self, *args, **options):
        failures = []

        self.stdout.write('=== Contrastes WCAG ===')
        contrast_failures = accessibility.check_contrasts()
        if contrast_failures:
            for failure in contrast_failures:
                self.stdout.write(self.style.ERROR('  ECHEC : %s' % failure))
            failures.extend(contrast_failures)
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    '  Tous les contrastes utilises atteignent le niveau AA.'
                )
            )

        self.stdout.write('=== Ressources externes ===')
        external = accessibility.check_no_external_assets(
            CSS_FILES + TEMPLATE_FILES
        )
        if external:
            for item in external:
                self.stdout.write(self.style.ERROR('  ECHEC : %s' % item))
            failures.extend(external)
        else:
            self.stdout.write(
                self.style.SUCCESS('  Aucune ressource distante.')
            )

        self.stdout.write('=== Focus clavier ===')
        focus_failures = accessibility.check_focus_visible(CSS_FILES)
        if focus_failures:
            for failure in focus_failures:
                self.stdout.write(self.style.ERROR('  ECHEC : %s' % failure))
            failures.extend(focus_failures)
        else:
            self.stdout.write(self.style.SUCCESS('  Un style de focus est declare.'))

        self.stdout.write('=== Etiquettes des formulaires ===')
        label_failures = []
        for template in TEMPLATE_FILES:
            with open(template, encoding='utf-8') as handle:
                html = handle.read()
            label_failures.extend(accessibility.collect_label_problems(html))
            label_failures.extend(accessibility.collect_unlabelled_labels(html))
        if label_failures:
            for failure in label_failures:
                self.stdout.write(self.style.ERROR('  ECHEC : %s' % failure))
            failures.extend(label_failures)
        else:
            self.stdout.write(
                self.style.SUCCESS('  Tous les champs ont une etiquette.')
            )

        self.stdout.write('')
        if failures:
            self.stdout.write(
                self.style.ERROR('%d verification(s) en echec.' % len(failures))
            )
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS('Recette accessibilite : OK.'))
