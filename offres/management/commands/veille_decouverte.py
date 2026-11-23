"""L'assistant de decouverte des sources.

Cette commande cherche, verifie et presente les pages qui pourraient
devenir des sources surveillees. Elle ne collecte rien : la decision
d autoriser revient a l equipe, dans le Centre de veille.

Utilisation :

    python manage.py veille_decouverte
    python manage.py veille_decouverte "offres d emploi pour des ONG au Burkina Faso"
    python manage.py veille_decouverte --sans-conditions
    python manage.py veille_decouverte --delai 20

L option --sans-conditions allege la verification : elle n va pas lire
les pages de conditions d utilisation du site.
"""

from django.core.management.base import BaseCommand, CommandError

from offres.veille import decouverte, decouverte_ia


class Command(BaseCommand):
    help = "Cherche et verifie des pages qui pourraient devenir des sources surveillees."

    def add_arguments(self, parser):
        parser.add_argument(
            'demande',
            nargs='?',
            default='offres d emploi au Burkina Faso',
            help='Ce que l assistant doit chercher.',
        )
        parser.add_argument(
            '--delai',
            type=int,
            default=None,
            help='Secondes entre deux requetes (10 par defaut).',
        )
        parser.add_argument(
            '--sans-conditions',
            action='store_true',
            help='Ne va pas lire les pages de conditions du site.',
        )
        parser.add_argument(
            '--sans-recherche',
            action='store_true',
            help='N utilise pas le moteur de recherche, seulement le modele.',
        )
        parser.add_argument(
            '--maximum',
            type=int,
            default=12,
            help='Nombre maximal d adresses verifiees.',
        )

    def handle(self, *args, **options):
        demande = options['demande']
        delai = options.get('delai')
        deep = not options['sans_conditions']

        moteur = decouverte_ia.moteur_recherche_disponible()
        if not options['sans_recherche'] and not moteur:
            self.stdout.write(
                self.style.WARNING(
                    'Aucun moteur de recherche configure : seules les adresses '
                    'proposees par le modele seront verifiees. Pour elargir la '
                    'recherche, renseignez BRAVE_SEARCH_API_KEY ou SEARXNG_URL '
                    'dans le fichier .env.'
                )
            )

        self.stdout.write('Recherche de sources pour : %s' % demande)
        self.stdout.write('---')

        candidates = decouverte_ia.proposer(
            demande, avec_recherche=not options['sans_recherche']
        )

        if not candidates:
            self.stdout.write(
                self.style.WARNING(
                    'Aucune adresse proposee. Verifiez que le service '
                    'd intelligence artificielle est configure.'
                )
            )
            return

        self.stdout.write(
            '%d adresse(s) a verifier (le delai de %s secondes s applique).'
            % (len(candidates), delai if delai else 10)
        )
        self.stdout.write('---')

        rapports = []
        for candidat in candidates[: options['maximum']]:
            self.stdout.write('Verification de %s ...' % candidat.url)
            rapports.append(
                decouverte.verify_candidate(candidat, delay=delai, deep=deep)
            )

        self.stdout.write('')
        self._afficher(rapports)

        sources = [r for r in rapports if r.is_source]
        a_verifier = [
            r for r in rapports if r.verdict == decouverte.VERDICT_A_VERIFIER
        ]
        ecartees = [r for r in rapports if r.is_rejected]

        self.stdout.write('')
        self.stdout.write(
            '%d source(s) proposee(s), %d a verifier, %d ecartee(s).'
            % (len(sources), len(a_verifier), len(ecartees))
        )
        if sources or a_verifier:
            self.stdout.write(
                'Pour autoriser une source : Administration > Sources > '
                'Ajouter une source, puis le Centre de veille pour la '
                'validation.'
            )

    def _afficher(self, rapports):
        """Presente les rapports par verdict."""
        sections = (
            (
                decouverte.VERDICT_SOURCE,
                'SOURCES PROPOSEES',
                'La reprise est explicitement autorisee par le site.',
            ),
            (
                decouverte.VERDICT_A_VERIFIER,
                'SOURCES A VERIFIER',
                'Le site ne dit rien sur la reprise : l autorisation devra '
                'etre motivee.',
            ),
            (
                decouverte.VERDICT_ECARTEE,
                'SOURCES ECARTEES',
                'Ces pages ne sont pas collectables, ou la reprise y est '
                'interdite.',
            ),
        )

        for verdict, titre, explication in sections:
            rapports_du_verdict = [r for r in rapports if r.verdict == verdict]
            if not rapports_du_verdict:
                continue
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_HEADING('%s' % titre))
            self.stdout.write(explication)
            for rapport in rapports_du_verdict:
                self.stdout.write('')
                self.stdout.write('  %s' % rapport.url)
                if rapport.page_title:
                    self.stdout.write('    titre      : %s' % rapport.page_title)
                if rapport.kind:
                    self.stdout.write('    type       : %s' % rapport.kind)
                self.stdout.write('    score      : %d%%' % round(rapport.score * 100))
                if rapport.selector:
                    self.stdout.write(
                        '    selecteur  : %s (%d annonce(s))'
                        % (rapport.selector, rapport.blocks_count)
                    )
                for raison in rapport.reasons:
                    self.stdout.write('    - %s' % raison)
                if rapport.conditions_found:
                    self.stdout.write(
                        '    conditions : %s'
                        % ', '.join(rapport.conditions_found[:3])
                    )
                if rapport.sample:
                    self.stdout.write(
                        '    echantillon : %s' % rapport.sample[:160].replace('\n', ' | ')
                    )
