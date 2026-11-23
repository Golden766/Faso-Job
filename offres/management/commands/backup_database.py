"""Sauvegarde automatique de la base.

Cette commande est celle que la tache planifiee appelle. Elle lit la
configuration definie dans l administration et n executes rien si la
sauvegarde automatique n est pas activee.

Utilisation manuelle, sans activation :

    python manage.py backup_database

Utilisation par la tache planifiee (respecte l'interrupteur de l'admin) :

    python manage.py backup_database --scheduled

Utilisation forcee par la tache planifiee :

    python manage.py backup_database --scheduled --force
"""

from django.core.management.base import BaseCommand

from offres import backups


class Command(BaseCommand):
    help = 'Realise une sauvegarde de la base et applique la retention.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scheduled',
            action='store_true',
            help='Execution par la tache planifiee : respecte l interrupteur.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Execute la sauvegarde meme si la sauvegarde automatique est desactivee.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans ecrire de fichier.',
        )

    def handle(self, *args, **options):
        configuration = backups.get_configuration()

        if options['scheduled'] and not options['force'] and not configuration.enabled:
            self.stdout.write(
                self.style.WARNING(
                    'Sauvegarde automatique desactivee dans l administration : '
                    'rien n est fait.'
                )
            )
            return

        if options['dry_run']:
            rows = backups.count_rows()
            directory = backups.backup_directory(configuration)
            filename = backups.backup_filename(configuration)
            self.stdout.write(
                f'Simulation : {rows} lignes seraient ecrites dans '
                f'{directory / filename}'
            )
            return

        run = backups.perform_backup(
            triggered_by=(
                backups.BackupRun.TRIGGER_SCHEDULED
                if options['scheduled']
                else backups.BackupRun.TRIGGER_MANUAL
            ),
            configuration=configuration,
        )

        if run.status == backups.BackupRun.STATUS_SUCCESS:
            self.stdout.write(self.style.SUCCESS(run.message))
        else:
            self.stdout.write(self.style.ERROR(run.message))
