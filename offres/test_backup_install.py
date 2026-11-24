"""Tests de l installation d une sauvegarde depuis l administration.

L installation remplace le contenu de la base : elle est donc protegee
par un apercu et par un mot de confirmation. Ces tests verifient aussi
que le depot d un fichier depuis l administration fonctionne.

Les fichiers de sauvegarde sont ecrits dans un dossier du projet, nettoye
a la fin de chaque test : le dossier des sauvegardes du site n est
jamais touche.
"""

import json
import shutil
import uuid
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import backups
from .models import BackupConfiguration, BackupRun, Offer


class BackupInstallTestCase(TestCase):
    """Base commune : les sauvegardes sont ecrites dans un dossier jetable."""

    def setUp(self):
        self.directory_name = 'fasojob-install-test-%s' % uuid.uuid4().hex[:8]
        self.directory = Path(settings.BASE_DIR) / self.directory_name
        self.addCleanup(shutil.rmtree, self.directory, True)

        self.configuration = backups.get_configuration()
        self.configuration.destination = self.directory_name
        self.configuration.compress = False
        self.configuration.include_media = False
        self.configuration.retention_count = 0
        self.configuration.save()
        # Le dossier reellement utilise peut etre temporaire pendant les
        # tests : c est lui qu il faut nettoyer.
        self.addCleanup(shutil.rmtree, self.backup_dir(), True)

    def backup_dir(self):
        return backups.backup_directory(self.configuration)

    def make_offer(self, title='Offre avant installation'):
        return Offer.objects.create(
            title=title,
            company_name='Entreprise',
            description='Description',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )


class PreviewTest(BackupInstallTestCase):
    """L apercu montre le contenu de la sauvegarde sans rien ecrire."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def create_backup_file(self):
        self.make_offer('Offre sauvegardee')
        backups.perform_backup(configuration=self.configuration)
        path = backups.list_backup_files(self.configuration)[0]
        return path

    def test_preview_page_shows_the_content(self):
        path = self.create_backup_file()

        response = self.client.get(
            reverse('admin-backup-restore', kwargs={'file_name': path.name})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'offres_offer')
        self.assertContains(response, 'Confirmer')

    def test_preview_does_not_change_the_data(self):
        path = self.create_backup_file()
        Offer.objects.all().delete()

        self.client.get(reverse('admin-backup-restore', kwargs={'file_name': path.name}))

        self.assertEqual(Offer.objects.count(), 0)

    def test_preview_page_requires_staff(self):
        path = self.create_backup_file()
        self.client.logout()
        visitor = get_user_model().objects.create_user(
            username='visiteur',
            password='test-password',
        )
        self.client.force_login(visitor)

        response = self.client.get(
            reverse('admin-backup-restore', kwargs={'file_name': path.name})
        )

        self.assertEqual(response.status_code, 302)

    def test_unknown_file_is_refused(self):
        response = self.client.get(
            reverse(
                'admin-backup-restore',
                kwargs={'file_name': 'fichier-inexistant.json'},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin-backups'))

    def test_the_page_shows_the_size_and_the_install_button(self):
        """La liste des fichiers annonce la taille et le bouton d installation."""
        self.create_backup_file()

        response = self.client.get(reverse('admin-backups'))

        self.assertContains(response, 'Installer')
        self.assertNotContains(response, '0 octet')

    def test_path_traversal_is_refused(self):
        response = self.client.get(
            reverse(
                'admin-backup-restore',
                kwargs={'file_name': '..\\..\\db.sqlite3'},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin-backups'))


class UploadTest(BackupInstallTestCase):
    """Depot d un fichier de sauvegarde depuis l administration."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def make_upload(self, name='sauvegarde.json', payload=None):
        if payload is None:
            payload = {
                'exported_at': '2026-11-16T03:00:00',
                'generator': 'Faso Job',
                'tables': {
                    'offres_offer': {
                        'columns': ['id', 'title'],
                        'rows': [],
                    },
                },
            }
        content = json.dumps(payload).encode('utf-8')
        return SimpleUploadedFile(name, content, content_type='application/json')

    def test_upload_stores_the_file_and_opens_the_preview(self):
        upload = self.make_upload()

        response = self.client.post(
            reverse('admin-backups'),
            {'action': 'upload', 'backup_file': upload},
        )

        self.assertEqual(response.status_code, 302)
        stored = list(self.backup_dir().glob('*.json'))
        self.assertEqual(len(stored), 1)
        self.assertRedirects(
            response,
            reverse('admin-backup-restore', kwargs={'file_name': stored[0].name}),
        )

    def test_upload_of_an_unreadable_file_is_refused(self):
        upload = SimpleUploadedFile(
            'sauvegarde.json',
            b'ceci n est pas du json',
            content_type='application/json',
        )

        response = self.client.post(
            reverse('admin-backups'),
            {'action': 'upload', 'backup_file': upload},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'n')
        self.assertEqual(list(self.backup_dir().glob('*')), [])

    def test_upload_with_a_wrong_extension_is_refused(self):
        upload = self.make_upload(name='sauvegarde.txt')

        self.client.post(
            reverse('admin-backups'),
            {'action': 'upload', 'backup_file': upload},
            follow=True,
        )

        self.assertEqual(list(self.backup_dir().glob('*')), [])

    def test_upload_without_file_is_refused(self):
        self.client.post(
            reverse('admin-backups'),
            {'action': 'upload'},
            follow=True,
        )

        self.assertEqual(list(self.backup_dir().glob('*')), [])


class InstallTest(BackupInstallTestCase):
    """L installation ecrit reellement la sauvegarde dans la base."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def create_backup_file(self):
        self.make_offer('Offre a reinstaller')
        backups.perform_backup(configuration=self.configuration)
        path = backups.list_backup_files(self.configuration)[0]
        Offer.objects.all().delete()
        return path

    def test_install_without_the_confirmation_word_does_nothing(self):
        path = self.create_backup_file()

        response = self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {'action': 'apply', 'confirmation': 'oui'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Offer.objects.count(), 0)
        self.assertFalse(
            BackupRun.objects.filter(
                triggered_by=BackupRun.TRIGGER_RESTORE
            ).exists()
        )

    def test_install_with_the_confirmation_word_restores_the_data(self):
        path = self.create_backup_file()

        response = self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Offer.objects.count(), 1)
        self.assertEqual(Offer.objects.first().title, 'Offre a reinstaller')

    def test_install_is_recorded_in_the_history(self):
        path = self.create_backup_file()

        self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        run = BackupRun.objects.filter(
            triggered_by=BackupRun.TRIGGER_RESTORE
        ).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, BackupRun.STATUS_SUCCESS)
        self.assertIn('Installation terminee', run.message)

    def test_install_records_who_did_it(self):
        path = self.create_backup_file()

        self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        run = BackupRun.objects.filter(
            triggered_by=BackupRun.TRIGGER_RESTORE
        ).first()
        self.assertEqual(run.actor, 'admin')

    def test_a_failed_install_leaves_the_data_untouched(self):
        """La restauration est atomique : un echec ne laisse rien a moitie."""
        path = self.create_backup_file()
        Offer.objects.create(
            title='Offre creee apres la sauvegarde',
            company_name='Entreprise',
            description='Description',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )

        # Une sauvegarde abimee : une ligne ne correspond plus aux colonnes.
        payload = backups.read_backup(path)
        payload['tables']['offres_offer']['columns'].append('colonne_en_trop')
        broken = self.directory / 'abimee.json'
        broken.write_text(json.dumps(payload), encoding='utf-8')

        response = self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': broken.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        self.assertEqual(response.status_code, 302)
        # L offre creee apres la sauvegarde est toujours la.
        self.assertTrue(
            Offer.objects.filter(
                title='Offre creee apres la sauvegarde'
            ).exists()
        )
        # L offre de la sauvegarde n a pas ete ecrite : l ecriture
        # commencee a ete annulee.
        self.assertFalse(
            Offer.objects.filter(title='Offre a reininstaller').exists()
        )
        # Les tables ecrites avant l echec ont ete restaurees elles aussi.
        self.assertTrue(
            get_user_model().objects.filter(username='admin').exists()
        )

    def test_install_produces_a_safety_backup_before_writing(self):
        path = self.create_backup_file()
        files_before = len(backups.list_backup_files(self.configuration))

        self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        files_after = backups.list_backup_files(self.configuration)
        self.assertEqual(len(files_after), files_before + 1)

    def test_install_keeps_the_user_accounts(self):
        get_user_model().objects.create_user(
            username='restaure',
            password='test-password',
        )
        path = self.create_backup_file()

        self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        self.assertTrue(
            get_user_model().objects.filter(username='restaure').exists()
        )

    def test_install_keeps_the_groups_of_the_users(self):
        """Les tables de passage doivent etre restaurees.

        Sans elles, un administrateur perd ses groupes : il n a plus
        aucun droit sur l administration.
        """
        group = Group.objects.create(name='Redaction')
        self.user.groups.add(group)
        path = self.create_backup_file()

        self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        self.assertTrue(
            get_user_model().objects.filter(
                username='admin', groups__name='Redaction'
            ).exists()
        )

    def test_install_keeps_the_migration_history(self):
        """L historique des migrations decrit le schema : il est conserve."""
        path = self.create_backup_file()
        before = MigrationRecorder.Migration.objects.count()

        self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        self.assertEqual(MigrationRecorder.Migration.objects.count(), before)

    def test_install_interrupts_the_saved_runs_in_progress(self):
        """Une sauvegarde en cours ne doit pas rester « en cours »."""
        path = self.create_backup_file()
        BackupRun.objects.create(
            configuration=self.configuration,
            triggered_by=BackupRun.TRIGGER_MANUAL,
            started_at=timezone.now() - timezone.timedelta(minutes=5),
            status=BackupRun.STATUS_RUNNING,
        )

        self.client.post(
            reverse('admin-backup-restore', kwargs={'file_name': path.name}),
            {
                'action': 'apply',
                'confirmation': backups.RESTORE_CONFIRMATION_WORD,
            },
        )

        self.assertFalse(
            BackupRun.objects.filter(status=BackupRun.STATUS_RUNNING).exists()
        )


class InstallServiceTest(BackupInstallTestCase):
    """Le service d installation, utilise directement."""

    def test_install_backup_restores_the_offers(self):
        self.make_offer('Offre du service')
        backups.perform_backup(configuration=self.configuration)
        path = backups.list_backup_files(self.configuration)[0]
        Offer.objects.all().delete()

        result = backups.install_backup(
            path, configuration=self.configuration, actor=None
        )

        self.assertEqual(Offer.objects.count(), 1)
        self.assertGreater(result['report']['inserted'], 0)
        self.assertIn('Installation terminee', result['message'])

    def test_preview_does_not_write_anything(self):
        self.make_offer('Offre de l apercu')
        backups.perform_backup(configuration=self.configuration)
        path = backups.list_backup_files(self.configuration)[0]
        Offer.objects.all().delete()

        preview = backups.preview_backup(path, self.configuration)

        self.assertEqual(Offer.objects.count(), 0)
        self.assertGreater(preview['rows'], 0)
        self.assertEqual(preview['missing_tables'], [])

    def test_install_restores_the_media_files(self):
        media_root = Path(settings.MEDIA_ROOT) / 'install-test'
        media_root.mkdir(parents=True, exist_ok=True)
        evidence = media_root / 'preuve.txt'
        evidence.write_text('preuve', encoding='utf-8')
        self.addCleanup(shutil.rmtree, media_root, True)

        self.configuration.include_media = True
        self.configuration.save()
        backups.perform_backup(configuration=self.configuration)
        path = backups.list_backup_files(self.configuration)[0]
        self.assertTrue(path.name.endswith('.zip'))

        evidence.unlink()
        result = backups.install_backup(
            path, configuration=self.configuration, actor=None
        )

        self.assertTrue(evidence.exists())
        self.assertEqual(evidence.read_text(encoding='utf-8'), 'preuve')
        self.assertGreaterEqual(result['media'], 1)

    def test_resolve_backup_file_refuses_a_path(self):
        with self.assertRaises(backups.BackupError):
            backups.resolve_backup_file('../db.sqlite3', self.configuration)

    def test_resolve_backup_file_refuses_an_unknown_file(self):
        with self.assertRaises(backups.BackupError):
            backups.resolve_backup_file('absent.json', self.configuration)

    def test_store_uploaded_backup_refuses_an_unreadable_file(self):
        upload = SimpleUploadedFile(
            'sauvegarde.json',
            b'pas du json',
            content_type='application/json',
        )

        with self.assertRaises(backups.BackupError):
            backups.store_uploaded_backup(upload, self.configuration)

        self.assertEqual(list(self.backup_dir().glob('*')), [])

    def test_backup_with_media_can_be_read_back(self):
        media_root = Path(settings.MEDIA_ROOT) / 'install-test-media'
        media_root.mkdir(parents=True, exist_ok=True)
        (media_root / 'preuve.txt').write_text('preuve', encoding='utf-8')
        self.addCleanup(shutil.rmtree, media_root, True)

        self.configuration.include_media = True
        self.configuration.save()
        backups.perform_backup(configuration=self.configuration)
        path = backups.list_backup_files(self.configuration)[0]

        payload = backups.read_backup(path)

        self.assertIn('tables', payload)
        self.assertIn('offres_offer', payload['tables'])


class BackupCommandCompatibilityTest(TestCase):
    """La commande de restauration continue de fonctionner."""

    def test_restore_command_simulates_by_default(self):
        directory_name = 'fasojob-install-cmd-%s' % uuid.uuid4().hex[:8]
        directory = Path(settings.BASE_DIR) / directory_name
        self.addCleanup(shutil.rmtree, directory, True)

        configuration = backups.get_configuration()
        configuration.destination = directory_name
        configuration.compress = False
        configuration.include_media = False
        configuration.retention_count = 0
        configuration.save()

        Offer.objects.create(
            title='Offre de la commande',
            company_name='Entreprise',
            description='Description',
            status=Offer.STATUS_PUBLISHED,
            is_source_confirmed=True,
        )
        backups.perform_backup(configuration=configuration)
        path = backups.list_backup_files(configuration)[0]
        Offer.objects.all().delete()

        from django.core.management import call_command

        call_command('restore_database', str(path), stdout=StringIO())

        self.assertEqual(Offer.objects.count(), 0)
        self.assertEqual(
            BackupConfiguration.objects.count(),
            1,
        )
