"""Archivage automatique des offres publiees et expirees.

La commande archive les offres publiees dont la date limite est depassee
depuis plus de N jours, N etant fixe dans les parametres de la plateforme
(`auto_archive_days`). Une valeur de 0 desactive l'archivage automatique.

L'archivage retire l'offre du catalogue actif sans la supprimer : elle reste
consultable par l'administration pour l'historique.

Usage :

    python manage.py archive_expired_offers [--dry-run]
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from offres.models import Offer, PlatformSettings


class Command(BaseCommand):
    help = "Archive les offres publiees dont la date limite est depassee."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les offres concernees sans les archiver.',
        )

    def handle(self, *args, **options):
        settings = PlatformSettings.load()
        days = settings.auto_archive_days
        dry_run = options['dry_run']

        if days <= 0:
            self.stdout.write(
                self.style.WARNING(
                    'Archivage automatique desactive : '
                    'le parametre « archivage automatique apres (jours) » est a 0.'
                )
            )
            return

        today = timezone.localdate()
        expired_offers = (
            Offer.objects.filter(
                status=Offer.STATUS_PUBLISHED,
                is_published=True,
                deadline__isnull=False,
                deadline__lt=today,
            )
            .order_by('deadline')
        )

        to_archive = []
        for offer in expired_offers:
            days_since_deadline = (today - offer.deadline).days
            if days_since_deadline >= days:
                to_archive.append(offer)

        if not to_archive:
            self.stdout.write(
                self.style.SUCCESS('Aucune offre a archiver.')
            )
            return

        for offer in to_archive:
            self.stdout.write(
                f'- {offer.title} (limite : {offer.deadline:%d/%m/%Y})'
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'{len(to_archive)} offre(s) seraient archivees '
                    '(simulation, aucune modification).'
                )
            )
            return

        archived = 0
        for offer in to_archive:
            offer.status = Offer.STATUS_ARCHIVED
            offer.save()
            archived += 1

        self.stdout.write(
            self.style.SUCCESS(f'{archived} offre(s) archivee(s).')
        )
