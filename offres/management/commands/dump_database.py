"""Sauvegarde complète de la base dans un fichier JSON lisible.

La commande est à utiliser avant toute migration appliquée à la base
Supabase de développement, conformément à la règle de travail du projet.

Exemple :

    python manage.py dump_database --output backups/fasojob-avant-migration.json
"""

import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = 'Exporte toutes les tables de la base dans un fichier JSON.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='backups/fasojob-backup.json',
            help='Chemin du fichier JSON à écrire.',
        )

    def handle(self, *args, **options):
        output_path = Path(options['output'])
        tables = {}

        with connection.cursor() as cursor:
            table_names = connection.introspection.table_names(cursor)
            for table_name in sorted(table_names):
                description = connection.introspection.get_table_description(cursor, table_name)
                columns = [column.name for column in description]
                quoted_table = connection.ops.quote_name(table_name)
                cursor.execute(f'SELECT * FROM {quoted_table}')
                rows = [
                    {
                        column: self._serialize(value)
                        for column, value in zip(columns, row)
                    }
                    for row in cursor.fetchall()
                ]
                tables[table_name] = {'columns': columns, 'rows': rows}

        payload = {
            'exported_at': datetime.now().isoformat(),
            'tables': tables,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        total_rows = sum(len(table['rows']) for table in tables.values())
        self.stdout.write(
            self.style.SUCCESS(
                f'Sauvegarde écrite dans {output_path} '
                f'({len(tables)} tables, {total_rows} lignes).'
            )
        )

    @staticmethod
    def _serialize(value):
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        return value
