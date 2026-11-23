"""Tests du lot 8 (8B) : double authentification et destinataires.

Couvre le module TOTP, l'activation, la verification a la connexion, les
codes de secours et la gestion de la liste des destinataires.
"""

import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import twofactor
from .models import (
    NotificationRecipient,
    OfferSubmission,
    PlatformSettings,
    TwoFactorDevice,
    TwoFactorRecoveryCode,
)


class TwoFactorAlgorithmTest(TestCase):
    def test_secret_is_long_enough(self):
        secret = twofactor.generate_secret()

        self.assertGreaterEqual(len(secret), 32)

    def test_secret_is_different_each_time(self):
        self.assertNotEqual(
            twofactor.generate_secret(),
            twofactor.generate_secret(),
        )

    def test_secret_is_encrypted_and_decryptable(self):
        secret = twofactor.generate_secret()

        encrypted = twofactor.encrypt_secret(secret)

        self.assertNotIn(secret, encrypted)
        self.assertEqual(twofactor.decrypt_secret(encrypted), secret)

    def test_current_code_has_six_digits(self):
        secret = twofactor.generate_secret()

        code = twofactor.current_code(secret)

        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_valid_code_is_accepted(self):
        secret = twofactor.generate_secret()

        self.assertTrue(twofactor.verify_code(secret, twofactor.current_code(secret)))

    def test_wrong_code_is_refused(self):
        secret = twofactor.generate_secret()

        self.assertFalse(twofactor.verify_code(secret, '000000'))

    def test_empty_code_is_refused(self):
        secret = twofactor.generate_secret()

        self.assertFalse(twofactor.verify_code(secret, ''))
        self.assertFalse(twofactor.verify_code(secret, None))
        self.assertFalse(twofactor.verify_code(secret, 'abc'))
        self.assertFalse(twofactor.verify_code(secret, '123'))

    def test_code_from_previous_period_is_accepted(self):
        """Une tolerance d'une periode evite les refus a la frontiere."""
        secret = twofactor.generate_secret()
        previous = twofactor.current_code(secret, at=time.time() - 30)

        self.assertTrue(twofactor.verify_code(secret, previous))

    def test_code_from_two_periods_ago_is_refused(self):
        secret = twofactor.generate_secret()
        old = twofactor.current_code(secret, at=time.time() - 120)

        self.assertFalse(twofactor.verify_code(secret, old))

    def test_provisioning_uri_is_standard(self):
        uri = twofactor.provisioning_uri('ABCDEFGHIJKLMNOP', 'admin@example.bf')

        self.assertTrue(uri.startswith('otpauth://totp/'))
        self.assertIn('secret=ABCDEFGHIJKLMNOP', uri)
        self.assertIn('issuer=Faso%20Job', uri)
        self.assertIn('digits=6', uri)
        self.assertIn('period=30', uri)

    def test_qr_code_is_svg(self):
        uri = twofactor.provisioning_uri('ABCDEFGHIJKLMNOP', 'admin@example.bf')

        svg = twofactor.qr_code_svg(uri)

        self.assertIn('<svg', svg)
        self.assertGreater(len(svg), 100)

    def test_recovery_codes_are_unique(self):
        codes = twofactor.generate_recovery_codes(8)

        self.assertEqual(len(codes), 8)
        self.assertEqual(len(set(codes)), 8)

    def test_recovery_code_hash_ignores_formatting(self):
        first = twofactor.hash_code('ABCDE-FGHIJ')
        second = twofactor.hash_code('abcdefghij')

        self.assertEqual(first, second)


class TwoFactorSetupTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_settings_page_is_reachable(self):
        response = self.client.get(reverse('two_factor_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sécurité du compte')

    def test_settings_page_requires_staff(self):
        self.client.logout()
        visitor = get_user_model().objects.create_user(
            username='visiteur',
            password='test-password',
        )
        self.client.force_login(visitor)

        response = self.client.get(reverse('two_factor_settings'))

        self.assertEqual(response.status_code, 302)

    def test_start_action_shows_the_qr_code(self):
        response = self.client.post(
            reverse('two_factor_settings'),
            {'action': 'start'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<svg')
        self.assertContains(response, 'Scannez ce QR code')
        self.assertTrue(
            TwoFactorDevice.objects.filter(user=self.user).exists()
        )

    def test_device_is_not_active_before_confirmation(self):
        self.client.post(reverse('two_factor_settings'), {'action': 'start'})

        device = TwoFactorDevice.objects.get(user=self.user)

        self.assertFalse(device.is_active)
        self.assertIsNone(device.confirmed_at)

    def test_confirm_with_wrong_code_fails(self):
        self.client.post(reverse('two_factor_settings'), {'action': 'start'})

        response = self.client.post(
            reverse('two_factor_settings'),
            {'action': 'confirm', 'code': '000000'},
        )

        self.assertEqual(response.status_code, 200)
        device = TwoFactorDevice.objects.get(user=self.user)
        self.assertFalse(device.is_active)

    def test_confirm_with_valid_code_activates(self):
        self.client.post(reverse('two_factor_settings'), {'action': 'start'})
        device = TwoFactorDevice.objects.get(user=self.user)
        secret = twofactor.decrypt_secret(device.secret)

        response = self.client.post(
            reverse('two_factor_settings'),
            {'action': 'confirm', 'code': twofactor.current_code(secret)},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertTrue(device.is_active)
        self.assertIsNotNone(device.confirmed_at)
        self.assertContains(response, 'Codes de secours')

    def test_recovery_codes_are_shown_once_after_confirmation(self):
        self.client.post(reverse('two_factor_settings'), {'action': 'start'})
        device = TwoFactorDevice.objects.get(user=self.user)
        secret = twofactor.decrypt_secret(device.secret)

        response = self.client.post(
            reverse('two_factor_settings'),
            {'action': 'confirm', 'code': twofactor.current_code(secret)},
            follow=True,
        )

        self.assertContains(response, 'codes de secours')
        self.assertEqual(
            TwoFactorRecoveryCode.objects.filter(device=device).count(),
            8,
        )

    def test_recovery_codes_are_not_shown_again(self):
        self.client.post(reverse('two_factor_settings'), {'action': 'start'})
        device = TwoFactorDevice.objects.get(user=self.user)
        secret = twofactor.decrypt_secret(device.secret)
        self.client.post(
            reverse('two_factor_settings'),
            {'action': 'confirm', 'code': twofactor.current_code(secret)},
            follow=True,
        )

        response = self.client.get(reverse('two_factor_settings'))

        self.assertNotContains(response, 'ABCDE')

    def test_deactivate_disables_the_protection(self):
        self.client.post(reverse('two_factor_settings'), {'action': 'start'})
        device = TwoFactorDevice.objects.get(user=self.user)
        secret = twofactor.decrypt_secret(device.secret)
        self.client.post(
            reverse('two_factor_settings'),
            {'action': 'confirm', 'code': twofactor.current_code(secret)},
        )

        self.client.post(reverse('two_factor_settings'), {'action': 'deactivate'})

        device.refresh_from_db()
        self.assertFalse(device.is_active)

    def test_stored_secret_is_encrypted_in_database(self):
        """Le secret chiffre ne doit jamais apparaitre tel quel en base."""
        self.client.post(reverse('two_factor_settings'), {'action': 'start'})
        device = TwoFactorDevice.objects.get(user=self.user)
        secret = twofactor.decrypt_secret(device.secret)

        self.assertNotEqual(device.secret, secret)
        self.assertNotIn(secret, device.secret)

    def test_manual_key_is_shown_for_camera_free_setup(self):
        """La cle de saisie manuelle est affichee au moment de l activation."""
        self.client.post(reverse('two_factor_settings'), {'action': 'start'})
        device = TwoFactorDevice.objects.get(user=self.user)
        secret = twofactor.decrypt_secret(device.secret)

        response = self.client.get(reverse('two_factor_settings'))

        self.assertContains(response, secret)
        self.assertContains(response, 'Sans cam')


class TwoFactorLoginTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.device = TwoFactorDevice.objects.create(
            user=self.user,
            secret=twofactor.encrypt_secret(twofactor.generate_secret()),
            is_active=True,
        )
        self.client.force_login(self.user)

    def test_admin_access_is_blocked_without_verification(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('two_factor_verify'), response.url)

    def test_verify_page_is_reachable(self):
        response = self.client.get(reverse('two_factor_verify'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vérification du compte')

    def test_valid_code_unlocks_the_admin(self):
        secret = twofactor.decrypt_secret(self.device.secret)

        response = self.client.post(
            reverse('two_factor_verify'),
            {'code': twofactor.current_code(secret)},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tableau de bord')

    def test_wrong_code_keeps_the_admin_locked(self):
        response = self.client.post(
            reverse('two_factor_verify'),
            {'code': '000000'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Code incorrect')

        follow_up = self.client.get(reverse('admin:index'))
        self.assertEqual(follow_up.status_code, 302)

    def test_recovery_code_unlocks_the_admin(self):
        recovery = TwoFactorRecoveryCode.objects.create(
            device=self.device,
            code_hash=twofactor.hash_code('ABCDE-FGHIJ'),
        )

        response = self.client.post(
            reverse('two_factor_verify'),
            {'code': 'ABCDE-FGHIJ'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        recovery.refresh_from_db()
        self.assertTrue(recovery.is_used)
        self.assertIsNotNone(recovery.used_at)

    def test_recovery_code_cannot_be_used_twice(self):
        TwoFactorRecoveryCode.objects.create(
            device=self.device,
            code_hash=twofactor.hash_code('ABCDE-FGHIJ'),
        )

        self.client.post(reverse('two_factor_verify'), {'code': 'ABCDE-FGHIJ'})

        self.client.logout()
        self.client.force_login(self.user)
        self.client.post(reverse('two_factor_verify'), {'code': 'ABCDE-FGHIJ'})

        follow_up = self.client.get(reverse('admin:index'))
        self.assertEqual(follow_up.status_code, 302)

    def test_account_without_two_factor_is_not_blocked(self):
        self.device.delete()

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)

    def test_public_pages_stay_reachable(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

    def test_verification_survives_within_the_session(self):
        secret = twofactor.decrypt_secret(self.device.secret)
        self.client.post(
            reverse('two_factor_verify'),
            {'code': twofactor.current_code(secret)},
        )

        first = self.client.get(reverse('admin:index'))
        second = self.client.get(reverse('admin:offres_offer_changelist'))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)


class NotificationRecipientTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.bf',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_recipient_can_be_added_from_admin(self):
        response = self.client.post(
            reverse('admin:offres_notificationrecipient_add'),
            {
                'email': 'alerte@example.bf',
                'label': 'Modération',
                'is_active': 'on',
                '_save': 'Enregistrer',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            NotificationRecipient.objects.filter(
                email='alerte@example.bf'
            ).exists()
        )

    def test_recipient_can_be_removed_from_admin(self):
        recipient = NotificationRecipient.objects.create(
            email='alerte@example.bf',
            label='Modération',
        )

        response = self.client.post(
            reverse('admin:offres_notificationrecipient_delete', args=[recipient.pk]),
            {'post': 'yes'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            NotificationRecipient.objects.filter(pk=recipient.pk).exists()
        )

    def test_inactive_recipient_is_not_notified(self):
        from django.core import mail

        settings_row = PlatformSettings.load()
        settings_row.notifications_enabled = True
        settings_row.save()
        NotificationRecipient.objects.create(
            email='inactif@example.bf',
            is_active=False,
        )

        from . import notifications

        result = notifications.notify_new_submission(
            OfferSubmission.objects.create(
                title='Proposition',
                company_name='Entreprise',
            )
        )

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_all_active_recipients_are_notified(self):
        from django.core import mail

        settings_row = PlatformSettings.load()
        settings_row.notifications_enabled = True
        settings_row.save()
        NotificationRecipient.objects.create(
            email='un@example.bf',
            label='Un',
        )
        NotificationRecipient.objects.create(
            email='deux@example.bf',
            label='Deux',
        )

        from . import notifications

        result = notifications.notify_new_submission(
            OfferSubmission.objects.create(
                title='Proposition',
                company_name='Entreprise',
            )
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 2)
        recipients = {message.to[0] for message in mail.outbox}
        self.assertEqual(recipients, {'un@example.bf', 'deux@example.bf'})

    def test_alert_email_from_settings_is_also_notified(self):
        from django.core import mail

        settings_row = PlatformSettings.load()
        settings_row.notifications_enabled = True
        settings_row.alert_email = 'principale@example.bf'
        settings_row.save()
        NotificationRecipient.objects.create(email='secondaire@example.bf')

        from . import notifications

        notifications.notify_new_submission(
            OfferSubmission.objects.create(
                title='Proposition',
                company_name='Entreprise',
            )
        )

        recipients = {message.to[0] for message in mail.outbox}
        self.assertEqual(
            recipients,
            {'principale@example.bf', 'secondaire@example.bf'},
        )

    def test_duplicate_address_is_not_notified_twice(self):
        from django.core import mail

        settings_row = PlatformSettings.load()
        settings_row.notifications_enabled = True
        settings_row.alert_email = 'principale@example.bf'
        settings_row.save()
        NotificationRecipient.objects.create(email='principale@example.bf')

        from . import notifications

        notifications.notify_new_submission(
            OfferSubmission.objects.create(
                title='Proposition',
                company_name='Entreprise',
            )
        )

        self.assertEqual(len(mail.outbox), 1)
