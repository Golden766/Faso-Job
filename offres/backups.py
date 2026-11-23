"""Service de sauvegarde et de restauration de la plateforme.

Deux principles :

- une sauvegarde doit pouvoir etre **restauree** : la restauration est
  donc traitee au meme niveau que la sauvegarde ;
- une sauvegarde contient des **donnees personnelles** (noms, e-mails et
  numeros des declarants de signalements). Les fichiers restent hors de
  tout repertoire servi par le site et ne sont jamais exposes publiquement.

Le module ne depend d'aucun outil externe : l'export passe par l'introspection
de la base, ce qui fonctionne aussi bien sur SQLite que sur PostgreSQL.

Trois formats de fichier sont acceptes :

- `.json` : la base seule, en clair ;
- `.json.gz` : la base seule, compressee ;
- `.zip` : la base et les fichiers joints, dans une archive unique.

L'installation d'une sauvegarde (c'est-a-dire sa restauration sur le site)
est possible depuis l'administration : `preview_backup` prepare l'apercu
sans rien ecrire, `install_backup` ecrit reellement.
"""

import json
import shutil
import tarfile
import zipfile
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import BackupConfiguration, BackupRun

# Au-dela de ce nombre de lignes, la sauvegarde manuelle depuis l'admin est
# refusee : elle bloquerait la requete web. La commande en ligne reste
# utilisable et c'est elle que la tache planifiee appelle.
MANUAL_BACKUP_MAX_ROWS = 50000

# Extensions acceptees pour un fichier de sauvegarde. L'ordre compte :
# `.json.gz` doit etre teste avant `.json`.
BACKUP_EXTENSIONS = ('.json.gz', '.json', '.zip')

# Taille maximale d'un fichier de sauvegarde depose depuis l'administration.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

# Nom du membre JSON dans une archive ZIP de sauvegarde.
DATABASE_MEMBER = 'database.json'

# Prefixe des fichiers joints dans une archive ZIP.
MEDIA_PREFIX = 'media/'

# Tables que la restauration ne remplace pas.
#
# L historique des migrations decrit l etat du schema du site, pas des
# donnees : le vider ferait croire que le site n a jamais ete migre, et
# les migrations seraient rejouees.
PRESERVED_TABLES = ('django_migrations',)

# Colonnes qui portent une date-heure, selon la base.
DATETIME_TYPE_CODES = {
    'datetime',
    'datetime2',
    'smalldatetime',
    'timestamp',
    'timestamp with time zone',
    'timestamp without time zone',
}

# Colonnes qui portent du JSON.
JSON_TYPE_CODES = {'json', 'jsonb'}

# Mot que l administrateur doit recopier pour confirmer une installation.
RESTORE_CONFIRMATION_WORD = 'RESTAURER'


class BackupError(Exception):
    """Erreur fonctionnelle lors d'une sauvegarde ou d'une restauration."""


def project_root():
    return Path(settings.BASE_DIR)


def backup_directory(configuration=None):
    """Repertoire de destination des sauvegardes.

    Le nom du repertoire est controle : il ne peut pas contenir de
    separation de chemin ni remonter hors du projet.
    """
    configuration = configuration or get_configuration()
    name = (configuration.destination or 'backups').strip()
    if not name:
        name = 'backups'
    if any(separator in name for separator in ('/', '\\', '..')) or name in ('.', '..'):
        raise BackupError(
            'Le dossier de destination ne doit pas contenir de chemin.'
        )
    return project_root() / name


def get_configuration():
    """Renvoie la configuration unique des sauvegardes."""
    configuration, _created = BackupConfiguration.objects.get_or_create(pk=1)
    return configuration


def safe_prefix(configuration=None):
    """Prefixe des fichiers de sauvegarde, nettoye de tout caractere risqué.

    Le prefixe est saisi dans l administration : il ne doit donc jamais
    pouvoir transformer le nom de fichier en chemin.
    """
    configuration = configuration or get_configuration()
    prefix = (configuration.filename_prefix or 'fasojob').strip() or 'fasojob'
    cleaned = ''.join(
        character if (character.isalnum() or character in '._-') else '-'
        for character in prefix
    )
    cleaned = cleaned.strip('-.') or 'fasojob'
    return cleaned[:40]


def split_backup_extension(name):
    """Separe le nom d un fichier de sauvegarde de son extension."""
    for extension in BACKUP_EXTENSIONS:
        if name.endswith(extension):
            return name[:-len(extension)], extension
    return name, ''


def sanitize_backup_name(name):
    """Nettoie le nom d un fichier de sauvegarde depose ou designe.

    Le nom ne doit contenir ni chemin ni caractere indesirable : il est
    utilise dans une URL et ecrit sur le disque.
    """
    name = (name or '').strip().replace('\\', '/')
    name = name.split('/')[-1]
    cleaned = ''.join(
        character if (character.isalnum() or character in '._-') else '_'
        for character in name
    )
    cleaned = cleaned.lstrip('.')
    if not cleaned:
        raise BackupError('Nom de fichier de sauvegarde invalide.')
    if len(cleaned) > 200:
        raise BackupError('Nom de fichier de sauvegarde trop long.')
    if not cleaned.endswith(BACKUP_EXTENSIONS):
        raise BackupError(
            'Le fichier doit se terminer par .json, .json.gz ou .zip.'
        )
    return cleaned


def resolve_backup_file(name, configuration=None):
    """Renvoie le chemin d un fichier de sauvegarde present sur le serveur.

    Le nom est resolu a l interior du dossier de sauvegarde : il ne peut
    pas designer un fichier exterieur (pas de `..`, pas de dossier).
    """
    configuration = configuration or get_configuration()
    raw = (name or '').strip()
    if not raw:
        raise BackupError('Aucun fichier de sauvegarde indique.')

    candidate = sanitize_backup_name(raw)
    if candidate != raw:
        raise BackupError('Nom de fichier de sauvegarde invalide.')

    directory = backup_directory(configuration)
    path = directory / candidate
    if path.parent != directory:
        raise BackupError('Nom de fichier de sauvegarde invalide.')
    if not path.exists() or not path.is_file():
        raise BackupError(
            'Fichier de sauvegarde introuvable : %s' % candidate
        )
    return path


def _serialize(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, memoryview):
        return bytes(value).decode('utf-8', errors='replace')
    return value


def export_tables():
    """Exporte toutes les tables de la base dans un dictionnaire."""
    tables = {}
    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)
        for table_name in sorted(table_names):
            description = connection.introspection.get_table_description(
                cursor, table_name
            )
            columns = [column.name for column in description]
            quoted_table = connection.ops.quote_name(table_name)
            cursor.execute(f'SELECT * FROM {quoted_table}')
            rows = [
                {
                    column: _serialize(value)
                    for column, value in zip(columns, row)
                }
                for row in cursor.fetchall()
            ]
            tables[table_name] = {'columns': columns, 'rows': rows}
    return tables


def count_rows():
    """Compte le total des lignes de la base, sans lire leur contenu."""
    total = 0
    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)
        for table_name in table_names:
            quoted_table = connection.ops.quote_name(table_name)
            cursor.execute(f'SELECT COUNT(*) FROM {quoted_table}')
            row = cursor.fetchone()
            total += row[0] if row else 0
    return total


def backup_filename(configuration=None, moment=None):
    """Nom de fichier horodate, triable par ordre chronologique."""
    configuration = configuration or get_configuration()
    moment = moment or timezone.localtime()
    if configuration.include_media:
        # La base et les fichiers joints tiennent dans une archive unique.
        extension = '.zip'
    elif configuration.compress:
        extension = '.json.gz'
    else:
        extension = '.json'
    prefix = safe_prefix(configuration)
    return f'{prefix}-{moment:%Y-%m-%d-%H%M%S}{extension}'


def list_backup_files(configuration=None):
    """Liste les fichiers de sauvegarde presents, du plus recent au plus ancien."""
    configuration = configuration or get_configuration()
    try:
        directory = backup_directory(configuration)
    except BackupError:
        return []
    if not directory.exists():
        return []
    files = [
        path
        for path in directory.glob('*')
        if path.is_file() and path.name != '.gitkeep'
    ]
    return sorted(files, key=lambda path: path.name, reverse=True)


def prune_old_backups(configuration=None):
    """Supprime les sauvegardes au-dela du nombre conserve.

    Renvoie la liste des fichiers supprimes.
    """
    configuration = configuration or get_configuration()
    retention = configuration.retention_count
    if retention <= 0:
        return []

    files = list_backup_files(configuration)
    removed = []
    for path in files[retention:]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed


def _write_json_archive(path, payload, compress):
    if compress:
        import gzip

        with gzip.open(path, 'wt', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return

    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _write_zip_archive(path, payload, media_root):
    """Ecrit une archive ZIP : la base et les fichiers joints (preuves).

    La base est un membre de l'archive (`database.json`). Les fichiers
    joints sont ranges sous `media/`. Tout tient dans un seul fichier :
    une archive reste lisible et restaurable.
    """
    media_root = Path(media_root)
    count = 0

    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            DATABASE_MEMBER,
            json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'),
        )
        if media_root.exists():
            for file_path in sorted(media_root.rglob('*')):
                if not file_path.is_file():
                    continue
                relative = str(file_path.relative_to(media_root)).replace('\\', '/')
                archive.write(file_path, MEDIA_PREFIX + relative)
                count += 1
    return count


def actor_name(actor):
    """Nom du compte a l origine d une operation.

    L acteur peut etre un utilisateur, une chaine ou absent : seule
    l information utile est conservee.
    """
    if not actor:
        return ''
    if isinstance(actor, str):
        return actor[:150]
    return str(getattr(actor, 'username', '') or actor)[:150]


def unique_path(path):
    """Renvoie un chemin de fichier qui n existe pas encore.

    Deux sauvegardes peuvent etre demandees dans la meme seconde : le
    second fichier ne doit pas ecraser le premier.
    """
    path = Path(path)
    if not path.exists():
        return path

    stem, extension = split_backup_extension(path.name)
    index = 2
    while True:
        candidate = path.with_name(f'{stem}-{index}{extension}')
        if not candidate.exists():
            return candidate
        index += 1


def perform_backup(triggered_by='manual', configuration=None, actor=None):
    """Realise une sauvegarde complete et enregistre son resultat.

    Renvoie l'objet `BackupRun` cree. Ne leve pas d'exception : un echec
    est enregistre dans l'historique pour que l'administration le voie.
    """
    configuration = configuration or get_configuration()
    started_at = timezone.now()

    run = BackupRun.objects.create(
        configuration=configuration,
        triggered_by=triggered_by,
        started_at=started_at,
        status=BackupRun.STATUS_RUNNING,
        actor=actor_name(actor),
    )

    try:
        directory = backup_directory(configuration)
        directory.mkdir(parents=True, exist_ok=True)

        target = unique_path(
            directory / backup_filename(configuration, timezone.localtime())
        )
        payload = {
            'exported_at': timezone.localtime().isoformat(),
            'generator': 'Faso Job',
            'tables': export_tables(),
        }

        media_count = 0
        if configuration.include_media:
            media_count = _write_zip_archive(target, payload, settings.MEDIA_ROOT)
        else:
            _write_json_archive(target, payload, configuration.compress)

        size = target.stat().st_size
        rows = sum(len(table['rows']) for table in payload['tables'].values())
        tables = len(payload['tables'])

        run.finished_at = timezone.now()
        run.duration_seconds = int((run.finished_at - started_at).total_seconds())
        run.status = BackupRun.STATUS_SUCCESS
        run.file_path = str(target.relative_to(project_root()))
        run.file_size = size
        run.tables_count = tables
        run.rows_count = rows
        run.message = (
            f'Sauvegarde reussie : {rows} lignes, {tables} tables, '
            f'{int(size / 1024)} Ko.'
        )
        if media_count:
            run.message += f' {media_count} fichiers joints inclus.'
        run.save()

        configuration.last_run_at = run.finished_at
        configuration.last_status = BackupRun.STATUS_SUCCESS
        configuration.last_message = run.message
        configuration.save(update_fields=[
            'last_run_at',
            'last_status',
            'last_message',
        ])

        prune_old_backups(configuration)

    except Exception as error:
        run.finished_at = timezone.now()
        run.duration_seconds = int((run.finished_at - started_at).total_seconds())
        run.status = BackupRun.STATUS_FAILURE
        run.message = f'Echec de la sauvegarde : {error}'
        run.save()

        configuration.last_run_at = run.finished_at
        configuration.last_status = BackupRun.STATUS_FAILURE
        configuration.last_message = run.message
        configuration.save(update_fields=[
            'last_run_at',
            'last_status',
            'last_message',
        ])

    return run


def read_backup(path):
    """Lit une sauvegarde et renvoie son contenu decode.

    Trois formats sont acceptes : JSON en clair, JSON compresse et
    archive ZIP (base + fichiers joints).
    """
    path = Path(path)
    if not path.exists():
        raise BackupError(f'Fichier de sauvegarde introuvable : {path}')

    if path.name.endswith('.zip'):
        try:
            with zipfile.ZipFile(path, 'r') as archive:
                with archive.open(DATABASE_MEMBER) as handle:
                    return json.loads(handle.read().decode('utf-8'))
        except KeyError:
            raise BackupError(
                "Cette archive ne contient pas de base de donnees."
            )
        except zipfile.BadZipFile:
            raise BackupError("Ce fichier n'est pas une archive valide.")

    if path.name.endswith('.gz'):
        import gzip

        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            return json.load(handle)

    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def store_uploaded_backup(uploaded, configuration=None):
    """Depose un fichier de sauvegarde envoye depuis l'administration.

    Le fichier est ecrit dans le dossier de sauvegardes, apres controle
    de sa taille, de son nom et de son contenu : un fichier qui n'est pas
    une sauvegarde lisible est supprime et refuse.
    """
    configuration = configuration or get_configuration()

    if uploaded is None:
        raise BackupError('Aucun fichier de sauvegarde recu.')

    if uploaded.size > MAX_UPLOAD_BYTES:
        raise BackupError(
            'Fichier trop volumineux : %d Mo maximum.' % (
                MAX_UPLOAD_BYTES // (1024 * 1024)
            )
        )

    name = sanitize_backup_name(uploaded.name)

    directory = backup_directory(configuration)
    directory.mkdir(parents=True, exist_ok=True)

    target = directory / name
    if target.exists():
        stem, extension = split_backup_extension(name)
        stamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')
        target = directory / f'{stem}-{stamp}{extension}'

    temporary = directory / ('.' + target.name + '.depot')
    try:
        with open(temporary, 'wb') as handle:
            for chunk in uploaded.chunks():
                handle.write(chunk)
        temporary.replace(target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise BackupError(f'Le fichier n a pas pu etre enregistre : {error}')

    try:
        payload = read_backup(target)
    except (BackupError, ValueError, OSError) as error:
        target.unlink(missing_ok=True)
        raise BackupError(
            'Ce fichier n est pas une sauvegarde lisible : %s' % error
        )

    if not (payload.get('tables') or {}):
        target.unlink(missing_ok=True)
        raise BackupError('Ce fichier ne contient aucune table.')

    return target


def table_dependency_order(table_names=None):
    """Renvoie les tables dans l ordre de dependance des cles etrangeres.

    Une table est placee apres celles qu elle reference. Sans cet ordre,
    la restauration echoue : vider une table mere avant sa fille viole la
    contrainte de cle etrangere.

    L ordre est deduit des contraintes reelles de la base, et non des
    modeles declares. Il vaut donc aussi pour les tables que Django
    cree automatiquement (les tables de passage des relations
    many-to-many) et pour les tables sans modele declare, comme
    `django_migrations`. Sans cela, les groupes d utilisateurs et les
    droits seraient perdus a la restauration.
    """
    with connection.cursor() as cursor:
        names = list(
            table_names
            if table_names is not None
            else connection.introspection.table_names(cursor)
        )
        relations = {
            name: connection.introspection.get_relations(cursor, name)
            for name in names
        }

    dependencies = {}
    for name in names:
        parents = set()
        # Chaque relation vaut (colonne visee, table visee, regle de
        # suppression).
        for _column, relation in relations.get(name, {}).items():
            other_table = relation[1]
            if other_table != name and other_table in names:
                parents.add(other_table)
        dependencies[name] = parents

    ordered = []
    done = set()
    in_progress = set()

    def visit(name):
        if name in done or name in in_progress:
            return
        in_progress.add(name)
        for parent in sorted(dependencies.get(name, ())):
            visit(parent)
        in_progress.discard(name)
        done.add(name)
        ordered.append(name)

    for name in sorted(names):
        visit(name)

    return ordered


def _reset_sequences(cursor, tables):
    """Remet les compteurs autoincrementes a jour apres restauration.

    Toutes les tables n ont pas une colonne id : la cle de django_session
    est session_key. Ces tables sont ignorees, leur sequence n a pas a
    etre remise a jour.

    Le nom de la sequence est obtenu par pg_get_serial_sequence puis
    recherche dans pg_catalog : le nom qualifie renvoye par PostgreSQL ne
    s applique pas tel quel au schema de recherche courant.
    """
    if connection.vendor != 'postgresql':
        return

    for table_name in tables:
        # 1. La table possede-t-elle une colonne id ?
        cursor.execute(
            'SELECT COUNT(*) FROM information_schema.columns '
            'WHERE table_schema = current_schema() '
            'AND table_name = %s AND column_name = %s',
            [table_name, 'id'],
        )
        if not cursor.fetchone()[0]:
            continue

        # 2. La table a-t-elle une sequence autoincremente ?
        cursor.execute(
            "SELECT pg_get_serial_sequence(%s, 'id')",
            [table_name],
        )
        sequence = cursor.fetchone()
        if not sequence or not sequence[0]:
            continue

        sequence_name = sequence[0].split('.')[-1]

        # 3. Valeur maximale actuelle.
        cursor.execute(
            'SELECT COALESCE(MAX(id), 1) FROM ' + connection.ops.quote_name(table_name)
        )
        max_id = cursor.fetchone()[0] or 1

        cursor.execute(
            'SELECT pg_catalog.setval(pg_catalog.to_regclass(%s), %s)',
            [sequence_name, max(max_id, 1)],
        )


def _table_fields(cursor, table_name):
    """Decrit les colonnes d une table, pour adapter les valeurs ecrites."""
    try:
        description = connection.introspection.get_table_description(
            cursor, table_name
        )
    except Exception:
        return {}
    return {field.name: field for field in description}


def _adapt_datetime_value(value):
    """Convertit une date-heure ISO en date-heure au format de la base.

    La sauvegarde ecrit les dates au format ISO. SQLite les compare
    ensuite comme du texte : sans conversion, une date restauree ne se
    classe plus dans le meme ordre qu une date ecrit par Django.
    """
    parsed = parse_datetime(value)
    if parsed is None:
        return value
    if timezone.is_naive(parsed) and settings.USE_TZ:
        parsed = timezone.make_aware(parsed, timezone.UTC)
    return connection.ops.adapt_datetimefield_value(parsed)


def _adapt_value(field, value):
    """Adapte une valeur restauree au format attendu par la base.

    Deux cas : les dates-heures, ecrites au format ISO par la
    sauvegarde, et les donnees JSON, ecrites sous forme d'objets.
    """
    if field is None or value is None:
        return value

    type_code = getattr(field, 'type_code', '') or ''

    if isinstance(value, str) and type_code in DATETIME_TYPE_CODES:
        return _adapt_datetime_value(value)

    if isinstance(value, (dict, list)) and (
        type_code in JSON_TYPE_CODES or getattr(field, 'is_json', False)
    ):
        return connection.ops.adapt_json_value(value, None)

    return value


def restore_from_payload(payload, dry_run=True, source=''):
    """Restaure une sauvegarde deja lue dans la base.

    En mode `dry_run` (par defaut), rien n'est modifie : la commande
    indique ce qui serait fait. Sinon, les tables sont videes puis
    remplies dans l'ordre de dependance des cles etrangeres.
    """
    tables = payload.get('tables') or {}
    if not tables:
        raise BackupError('Ce fichier ne contient aucune table.')

    report = {
        'file': source,
        'dry_run': dry_run,
        'tables': [],
        'rows': 0,
    }

    with connection.cursor() as cursor:
        existing_tables = set(connection.introspection.table_names(cursor))

        for table_name, table_data in tables.items():
            columns = table_data.get('columns') or []
            rows = table_data.get('rows') or []
            report['tables'].append({
                'name': table_name,
                'rows': len(rows),
                'exists': table_name in existing_tables,
            })
            report['rows'] += len(rows)

        if dry_run:
            return report

        # L ecriture se fait dans une seule transaction : si une ligne
        # refusee, la base reste dans son etat d avant, jamais a moitie
        # restauree.
        with transaction.atomic():
            # 1. Vider les tables en respectant les dependances.
            order = table_dependency_order()
            flush_tables = [
                name
                for name in order
                if name in existing_tables and name not in PRESERVED_TABLES
            ]
            if flush_tables:
                # Django 6.1 : sql_flush produit les instructions,
                # execute_sql_flush les execute. Le TRUNCATE ... CASCADE
                # vide toutes les tables d un coup et respecte les cles
                # etrangeres.
                statements = connection.ops.sql_flush(
                    django_core_style(),
                    flush_tables,
                    reset_sequences=False,
                    allow_cascade=True,
                )
                connection.ops.execute_sql_flush(statements)

            # 2. Reinserer les lignes, parents d'abord.
            inserted = 0
            for table_name in order:
                if table_name in PRESERVED_TABLES:
                    continue
                table_data = tables.get(table_name)
                if table_data is None:
                    continue
                if table_name not in existing_tables:
                    continue
                columns = table_data.get('columns') or []
                rows = table_data.get('rows') or []
                if not columns or not rows:
                    continue

                quoted_table = connection.ops.quote_name(table_name)
                quoted_columns = ', '.join(
                    connection.ops.quote_name(column) for column in columns
                )
                placeholders = ', '.join(['%s'] * len(columns))
                statement = (
                    f'INSERT INTO {quoted_table} ({quoted_columns}) '
                    f'VALUES ({placeholders})'
                )
                fields = _table_fields(cursor, table_name)
                for row in rows:
                    cursor.execute(
                        statement,
                        [
                            _adapt_value(fields.get(column), row.get(column))
                            for column in columns
                        ],
                    )
                    inserted += 1

            _reset_sequences(cursor, [name for name in order if name in tables])

            report['inserted'] = inserted

    return report


def restore_from_file(path, dry_run=True, actor=None):
    """Restaure une sauvegarde depuis un fichier.

    En mode `dry_run` (par defaut), rien n'est modifie : la commande
    indique ce qui serait fait. Sinon, les tables sont videes puis
    remplies dans l'ordre de dependance des cles etrangeres.
    """
    payload = read_backup(path)
    return restore_from_payload(payload, dry_run=dry_run, source=str(path))


def restore_media_from_backup(path):
    """Restaure les fichiers joints d'une archive de sauvegarde.

    Seules les archives ZIP contiennent des fichiers joints. Chaque membre
    `media/...` est recopie dans le dossier des fichiers joints du site.
    """
    path = Path(path)
    if not path.name.endswith('.zip'):
        return 0

    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(parents=True, exist_ok=True)

    count = 0
    with zipfile.ZipFile(path, 'r') as archive:
        for name in archive.namelist():
            if not name.startswith(MEDIA_PREFIX) or name.endswith('/'):
                continue
            relative = name[len(MEDIA_PREFIX):]
            if not relative or '..' in Path(relative).parts:
                continue
            target = media_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, open(target, 'wb') as destination:
                shutil.copyfileobj(source, destination)
            count += 1
    return count


def preview_backup(path, configuration=None):
    """Prepare l'apercu d'une installation, sans rien ecrire.

    Le rapport indique ce que contient la sauvegarde et ce que son
    installation remplacerait sur le site.
    """
    configuration = configuration or get_configuration()
    path = Path(path)

    payload = read_backup(path)
    report = restore_from_payload(payload, dry_run=True, source=path.name)
    tables = payload.get('tables') or {}

    return {
        'path': path,
        'name': path.name,
        'size': path.stat().st_size if path.exists() else 0,
        'exported_at': payload.get('exported_at', ''),
        'tables': report['tables'],
        'rows': report['rows'],
        'missing_tables': [
            table['name'] for table in report['tables'] if not table['exists']
        ],
        'has_media': path.name.endswith('.zip'),
        'table_count': len(tables),
    }


def install_backup(path, configuration=None, actor=None):
    """Installe une sauvegarde sur le site : la restauration a proprement dit.

    Une sauvegarde de securite est produite avant toute ecriture, afin que
    l'etat actuel du site puisse toujours etre retrouve. L'operation est
    ensuite inscrite dans l'historique des sauvegardes.

    Renvoie un dictionnaire : le rapport de restauration, la sauvegarde de
    securite et la ligne d'historique.
    """
    configuration = configuration or get_configuration()
    path = Path(path)
    started_at = timezone.now()

    # La sauvegarde est lue avant tout : son contenu ne peut plus changer
    # entre l'apercu et l'ecriture, meme si le fichier est supprime entre-temps.
    payload = read_backup(path)

    # 1. Sauvegarde de securite de l'etat actuel du site.
    safety = perform_backup(
        triggered_by=BackupRun.TRIGGER_MANUAL,
        configuration=configuration,
        actor=actor,
    )

    # 2. Restauration.
    report = restore_from_payload(payload, dry_run=False, source=path.name)
    media_count = restore_media_from_backup(path)

    # Une sauvegarde encore notee « en cours » a ete interrompue par la
    # restauration : sans cela, l historique la montrerait eternellement en
    # cours.
    BackupRun.objects.filter(
        status=BackupRun.STATUS_RUNNING,
        started_at__lt=started_at,
    ).update(
        status=BackupRun.STATUS_FAILURE,
        message='Sauvegarde interrompue par une installation.',
    )

    finished_at = timezone.now()
    inserted = report.get('inserted', report['rows'])
    message = (
        f'Installation terminee : {inserted} lignes reinstituees depuis '
        f'{path.name}.'
    )
    if safety.status == BackupRun.STATUS_SUCCESS and safety.file_path:
        message += f' Sauvegarde de securite : {safety.file_path}.'
    if media_count:
        message += f' {media_count} fichiers joints restaures.'

    run = BackupRun.objects.create(
        configuration=configuration,
        triggered_by=BackupRun.TRIGGER_RESTORE,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=int((finished_at - started_at).total_seconds()),
        status=BackupRun.STATUS_SUCCESS,
        actor=actor_name(actor),
        file_path=str(path),
        file_size=path.stat().st_size if path.exists() else 0,
        tables_count=len(report['tables']),
        rows_count=inserted,
        message=message[:255],
    )

    return {
        'report': report,
        'safety': safety,
        'run': run,
        'media': media_count,
        'message': message[:255],
    }


def django_core_style():
    """Style SQL sans couleurs, comme utilise par la commande flush."""
    from django.core.management.color import no_style

    return no_style()


def activation_instructions(configuration=None):
    """Explication et commande a utiliser pour activer la planification.

    La commande est fournie prete a copier : il ne reste qu'a la placer
    dans la tache planifiee de la machine qui heberge le site.
    """
    configuration = configuration or get_configuration()
    frequency = configuration.frequency or BackupConfiguration.FREQUENCY_DAILY

    if frequency == BackupConfiguration.FREQUENCY_HOURLY:
        cron_line = '0 * * * *'
        schedule_text = 'toutes les heures'
    elif frequency == BackupConfiguration.FREQUENCY_WEEKLY:
        cron_line = '0 3 * * 0'
        schedule_text = 'chaque dimanche a 03:00'
    else:
        cron_line = '0 3 * * *'
        schedule_text = 'chaque nuit a 03:00'

    python = Path(settings.BASE_DIR) / '.venv' / 'Scripts' / 'python.exe'
    if not python.exists():
        python = Path(settings.BASE_DIR) / '.venv' / 'bin' / 'python'

    cron_command = (
        f'cd {settings.BASE_DIR} && '
        f'{python} manage.py backup_database --scheduled'
    )

    return {
        'frequency': frequency,
        'schedule_text': schedule_text,
        'cron_line': cron_line,
        'cron_command': cron_command,
        'schtasks_command': (
            'schtasks /Create /SC DAILY /ST 03:00 /TN "Faso Job Sauvegarde" '
            f'/TR "{cron_command}" /F'
        ),
        'enabled': configuration.enabled,
    }
