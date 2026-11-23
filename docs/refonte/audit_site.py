"""Audit complet du site : toutes les pages, sans laisser d'ecriture.

Le parcours se fait dans une transaction annulee a la fin : les
compteurs de consultation ne sont pas modifies, rien n'est conserve.
"""

import os
import sys

sys.path.insert(0, os.getcwd())

import django  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plateforme_offres.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import transaction  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from django.conf import settings  # noqa: E402
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from offres.models import (  # noqa: E402
    Category,
    CollectedAnnouncement,
    Offer,
    OfferReport,
    OfferSubmission,
    Source,
    VeilleRun,
)

print('=' * 78)
print('1. ETAT DE LA BASE')
print('=' * 78)
for model in (Offer, OfferSubmission, OfferReport, Source, Category,
              CollectedAnnouncement, VeilleRun):
    print('  %-24s %s ligne(s)' % (model.__name__, model.objects.count()))

print()
print('=' * 78)
print('2. INTEGRITE DES DONNEES')
print('=' * 78)
problemes = []

orphelines = Offer.objects.filter(category=None).count()
print('  offres sans categorie      :', orphelines)

sans_titre = Offer.objects.filter(title='').count()
print('  offres sans titre           :', sans_titre)

sans_description = Offer.objects.filter(description='').count()
print('  offres sans description     :', sans_description)

doublons_slug = (
    Offer.objects.values('slug')
    .annotate(n=__import__('django').db.models.Count('slug'))
    .filter(n__gt=1)
)
print('  slugs en double             :', list(doublons_slug))

if not Offer.objects.exists():
    problemes.append('Aucune offre en base : le catalogue serait vide.')

print()
print('=' * 78)
print('3. PAGES PUBLIQUES')
print('=' * 78)

client = Client()

pages_publiques = [
    ('Accueil', reverse('home')),
    ('Catalogue', reverse('catalogue')),
    ('Favoris', reverse('favorites')),
    ('Comment ca marche', reverse('method')),
    ('Proposer une annonce', reverse('submit_offer')),
    ('Signaler une arnaque', reverse('report_fraud')),
    ('Styleguide', reverse('styleguide')),
]

offre = Offer.objects.public().first()
if offre:
    pages_publiques.append(
        ('Fiche offre', reverse('offer_detail', args=[offre.slug]))
    )
    pages_publiques.append(
        ('Signaler cette offre', reverse('report_offer', args=[offre.slug]))
    )

for libelle, url in pages_publiques:
    try:
        with transaction.atomic():
            reponse = client.get(url)
            transaction.set_rollback(True)
        etat = reponse.status_code
        marque = 'ok ' if etat < 400 else 'ECHEC'
        print('  [%s] %-24s HTTP %s  %s' % (marque, libelle, etat, url))
        if etat >= 400:
            problemes.append('%s (%s) repond %s' % (libelle, url, etat))
    except Exception as erreur:
        print('  [EXCEPTION] %-24s %s' % (libelle, erreur))
        problemes.append('%s : %s' % (libelle, erreur))

print()
print('=' * 78)
print('4. PAGES D ADMINISTRATION')
print('=' * 78)

staff = get_user_model().objects.filter(is_staff=True, is_superuser=True).first()
if staff is None:
    staff = get_user_model().objects.filter(is_staff=True).first()
if staff is None:
    print('  Aucun membre du personnel : pages non testees.')
else:
    client.force_login(staff)

    pages_admin = [
        ('Tableau de bord', '/admin/'),
        ('Rapport d activite', reverse('admin-activity-report')),
        ('Export CSV', reverse('admin-activity-report-csv')),
        ('Sauvegardes', reverse('admin-backups')),
        ('Centre de veille', reverse('admin-veille')),
        ('Offres', reverse('admin:offres_offer_changelist')),
        ('Ajouter une offre', reverse('admin:offres_offer_add')),
        ('Soumissions', reverse('admin:offres_offersubmission_changelist')),
        ('Signalements', reverse('admin:offres_offerreport_changelist')),
        ('Liste noire', reverse('admin:offres_blacklistedcontact_changelist')),
        ('Sources', reverse('admin:offres_source_changelist')),
        ('Categories', reverse('admin:offres_category_changelist')),
        ('Annonces collectees', reverse('admin:offres_collectedannouncement_changelist')),
        ('Historique des collectes', reverse('admin:offres_veillerun_changelist')),
        ('Messages envoyes', reverse('admin:offres_outboundmessage_changelist')),
        ('Destinataires', reverse('admin:offres_notificationrecipient_changelist')),
        ('Appareils 2FA', reverse('admin:offres_twofactordevice_changelist')),
        ('Codes de secours', reverse('admin:offres_twofactorrecoverycode_changelist')),
        ('Utilisateurs', reverse('admin:auth_user_changelist')),
        ('Roles', reverse('admin:auth_group_changelist')),
        ('Parametres', reverse('admin:offres_platformsettings_change', args=[1])),
        ('Securite du compte', reverse('two_factor_settings')),
    ]

    if offre:
        pages_admin.append(
            ('Modifier une offre', reverse('admin:offres_offer_change', args=[offre.pk]))
        )

    for libelle, url in pages_admin:
        try:
            with transaction.atomic():
                reponse = client.get(url)
                transaction.set_rollback(True)
            etat = reponse.status_code
            marque = 'ok ' if etat < 400 else 'ECHEC'
            print('  [%s] %-24s HTTP %s  %s' % (marque, libelle, etat, url))
            if etat >= 400:
                problemes.append('%s (%s) repond %s' % (libelle, url, etat))
        except Exception as erreur:
            print('  [EXCEPTION] %-24s %s' % (libelle, erreur))
            problemes.append('%s : %s' % (libelle, erreur))

print()
print('=' * 78)
print('5. BILAN')
print('=' * 78)
if problemes:
    print('  %d probleme(s) :' % len(problemes))
    for probleme in problemes:
        print('   -', probleme)
else:
    print('  Aucune anomalie detectee.')
