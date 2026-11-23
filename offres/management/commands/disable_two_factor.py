"""Desactive la double authentification d un compte.

Commande de secours : elle sert uniquement lorsqu un membre de l equipe a
perdu son telephone ET ses codes de secours, et ne peut donc plus se
connecter.

Elle s execute sur le serveur, avec les droits de la base.

Usage :

    python manage.py disable_two_factor --username golden_boy
    python manage.py disable_two_factor --username golden_boy --list
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from offres.models import TwoFactorDevice, TwoFactorRecoveryCode


class Command(BaseCommand):
    help = "Desactive la double authentification d un compte (secours)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument(
            "--list",
            action="store_true",
            help="Affiche l etat de la protection sans rien modifier.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            raise CommandError("Utilisateur %s introuvable." % username)

        device = TwoFactorDevice.objects.filter(user=user).first()
        if device is None:
            self.stdout.write(
                self.style.WARNING(
                    "Aucune double authentification active pour %s." % username
                )
            )
            return

        remaining = device.recovery_codes.filter(is_used=False).count()

        if options["list"]:
            self.stdout.write("Etat de la protection pour %s :" % username)
            self.stdout.write("- active : %s" % device.is_active)
            self.stdout.write(
                "- confirmee le : %s" % (device.confirmed_at or "jamais")
            )
            self.stdout.write("- codes de secours restants : %d" % remaining)
            return

        device.is_active = False
        device.confirmed_at = None
        device.save(update_fields=["is_active", "confirmed_at"])
        TwoFactorRecoveryCode.objects.filter(device=device).delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Double authentification desactivee pour %s. "
                "Les codes de secours ont ete supprimes." % username
            )
        )
