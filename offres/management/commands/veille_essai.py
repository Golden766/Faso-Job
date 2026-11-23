"""Essai du service d intelligence artificielle de la veille.

Cette commande sert a verifier que la configuration fonctionne : elle
envoie un texte d annonce au service et affiche ce qui revient. Elle
ne touche a aucun enregistrement.

Utilisation :

    python manage.py veille_essai "Nous recrutons un assistant comptable a Ouagadougou."
    python manage.py veille_essai --fichier chemin/vers/annonce.txt
    python manage.py veille_essai --fichier annonce.txt --classer

Sans cle configuree, la commande le dit clairement : elle ne simule
aucune reponse.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from offres.veille import ia
from offres.veille.schema import EXTRACT_FIELDS


class Command(BaseCommand):
    help = "Essaye le service d intelligence artificielle de la veille sur un texte d annonce."

    def add_arguments(self, parser):
        parser.add_argument(
            'texte',
            nargs='?',
            default='',
            help='Texte de l annonce a analyser.',
        )
        parser.add_argument(
            '--fichier',
            default='',
            help='Fichier contenant le texte de l annonce.',
        )
        parser.add_argument(
            '--classer',
            action='store_true',
            help='Demande aussi le classement dans les categories existantes.',
        )

    def handle(self, *args, **options):
        content = self._read_content(options)
        if not content:
            raise CommandError(
                'Indiquez un texte d annonce ou un fichier (--fichier).'
            )

        adapter = ia.get_adapter()
        if not adapter.is_configured():
            self.stdout.write(
                self.style.WARNING(
                    'Aucun service configure : renseignez AI_BASE_URL, AI_API_KEY '
                    'et AI_MODEL dans le fichier .env.'
                )
            )
            raise CommandError('Le service d intelligence artificielle n est pas configure.')

        self.stdout.write('Service : %s' % adapter.name)
        self.stdout.write('Modele  : %s' % adapter.model)
        self.stdout.write('---')

        result = ia.extract_announcement(content, adapter=adapter)

        if not result.is_ok:
            self.stderr.write(self.style.ERROR('Echec : %s' % result.error))
            raise CommandError('Extraction impossible.')

        for key, label in EXTRACT_FIELDS:
            value = result.data.get(key) or '(non precise)'
            self.stdout.write('%-24s %s' % (key + ' :', value))

        if options['classer']:
            from offres.models import Category

            categories = list(Category.objects.values_list('name', flat=True))
            classification = ia.classify_announcement(
                result.data, categories, adapter=adapter
            )
            if classification.is_ok:
                self.stdout.write('---')
                self.stdout.write(
                    'categorie             %s'
                    % (classification.data.get('category') or '(aucune)')
                )
            else:
                self.stderr.write(self.style.ERROR('Echec : %s' % classification.error))

        self.stdout.write('---')
        self.stdout.write('Reponse brute conservee pour audit (%d caracteres).' % len(result.raw))

    def _read_content(self, options):
        """Lit le texte a analyser, depuis l argument ou le fichier."""
        fichier = options.get('fichier') or ''
        if fichier:
            path = Path(fichier)
            if not path.exists():
                raise CommandError('Fichier introuvable : %s' % fichier)
            return path.read_text(encoding='utf-8', errors='replace')
        return options.get('texte') or ''
