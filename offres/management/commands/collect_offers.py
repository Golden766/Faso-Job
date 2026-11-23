"""Collecte automatique des annonces des sources surveillees.

Cette commande est celle que la tache planifiee appelle. Elle ne
collecte que les sources autorisees par l administration, et elle ne
publie rien : elle prepare des brouillons qui attendent une decision
humaine.

Utilisation manuelle :

    python manage.py collect_offers
    python manage.py collect_offers --source "Emploi du Faso"
    python manage.py collect_offers --dry-run

Utilisation par la tache planifiee :

    python manage.py collect_offers --scheduled

Les instructions d installation de la tache planifiee (cron ou Tache
planifiee Windows) sont affichees dans le Centre de veille.
"""

from django.core.management.base import BaseCommand, CommandError

from offres.models import Source, VeilleRun
from offres.veille import pipeline


class Command(BaseCommand):
    help = 'Collecte les annonces des sources surveillees et prepare les brouillons.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default='',
            help='Nom de la source a collecter (par defaut : toutes les sources surveillees).',
        )
        parser.add_argument(
            '--scheduled',
            action='store_true',
            help='Execution par la tache planifiee.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les sources qui seraient collectees, sans rien faire.',
        )
        parser.add_argument(
            '--ignorer-robots',
            action='store_true',
            help=(
                'Ignore le fichier robots.txt du site. A n utiliser que si '
                'l autorisation de la source l autorise explicitement.'
            ),
        )

    def handle(self, *args, **options):
        sources = self._sources(options)

        if not sources:
            self.stdout.write(
                self.style.WARNING(
                    'Aucune source surveillee a collecter. Ajoutez une source '
                    'dans l administration, avec son mode de collecte et son '
                    'autorisation.'
                )
            )
            return

        if options['dry_run']:
            self.stdout.write('Simulation : %d source(s) seraient collectees.' % len(sources))
            for source in sources:
                self.stdout.write('  - %s (%s)' % (source.name, source.get_collection_method_display()))
            return

        total_found = 0
        total_created = 0
        total_duplicates = 0
        total_errors = 0

        for source in sources:
            run = pipeline.collect_and_process(
                source,
                triggered_by=(
                    VeilleRun.TRIGGER_SCHEDULED
                    if options['scheduled']
                    else VeilleRun.TRIGGER_MANUAL
                ),
            )
            total_found += run.found_count
            total_created += run.created_count
            total_duplicates += run.duplicate_count
            total_errors += run.error_count

            tone = self.style.SUCCESS if run.status == VeilleRun.STATUS_SUCCESS else self.style.WARNING
            self.stdout.write(tone('%s : %s' % (source.name, run.message)))

        self.stdout.write('---')
        self.stdout.write(
            '%d annonce(s) trouvee(s), %d brouillon(s) cree(s), '
            '%d doublon(s) signale(s), %d erreur(s).'
            % (total_found, total_created, total_duplicates, total_errors)
        )
        if total_created:
            self.stdout.write(
                self.style.SUCCESS(
                    'Les brouillons attendent la validation de l equipe dans '
                    'le Centre de veille.'
                )
            )

    def _sources(self, options):
        """Sources a collecter.

        Seules les sources reellement autorisees sont collectees : une
        source surveillee sans autorisation ecrite, ou dont le mode de
        collecte n est pas automatise, est laissee de cote.
        """
        queryset = Source.objects.filter(is_watched=True).order_by('name')

        nom = options.get('source') or ''
        if nom:
            queryset = queryset.filter(name__iexact=nom)
            if not queryset.exists():
                raise CommandError('Aucune source surveillee nommee « %s ».' % nom)

        return [source for source in queryset if source.is_watchable]
