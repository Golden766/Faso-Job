"""Restauration d une sauvegarde de la base.

La restauration remplace le contenu des tables presentes dans la
sauvegarde. Elle est **toujours simulee par defaut** : il faut passer
`--apply` pour reellement ecrire en base.

Utilisation :

    python manage.py restore_database backups/fasojob-2026-11-12-030000.json
    python manage.py restore_database backups/fasojob-2026-11-12-030000.json --apply

Avertissement : cette commande remplace les donnees actuelles. Une
sauvegarde de la base precede la restauration reste advised.
"""

from django.core.management.base import BaseCommand, CommandError

from offres import backups


class Command(BaseCommand):
    help = 'Restaure une sauvegarde dans la base.'

    def add_arguments(self, parser):
        parser.add_argument('path', help='Chemin du fichier de sauvegarde.')
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Applique reellement la restauration. Sans cette option, rien n est modifie.',
        )

    def handle(self, *args, **options):
        path = options['path']

        try:
            report = backups.restore_from_file(
                path,
                dry_run=not options['apply'],
            )
        except backups.BackupError as error:
            raise CommandError(str(error))

        if not options['apply']:
            self.stdout.write(
                self.style.WARNING(
                    'Simulation : aucune donnee n a ete modifie. '
                    'Ajoutez --apply pour restaurer reellement.'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('Restauration terminee.'))

        self.stdout.write(
            f'Fichier : {report["file"]}'
        )
        self.stdout.write(
            f'{report["rows"]} lignes dans {len(report["tables"])} tables.'
        )
        for table in report['tables']:
            state = 'presente' if table['exists'] else 'absente de la base'
            self.stdout.write(
                f'  - {table["name"]} : {table["rows"]} lignes ({state})'
            )
