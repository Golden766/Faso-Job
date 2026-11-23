"""Audit des parcours qui ecrivent : formulaire public, publication,
signalement, sauvegarde, commandes. Rien n est conserve."""

import os
import sys

sys.path.insert(0, os.getcwd())

import django  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plateforme_offres.settings')
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import transaction  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from offres.models import (  # noqa: E402
    CollectedAnnouncement,
    Offer,
    OfferReport,
    OfferSubmission,
    VeilleRun,
)

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

problemes = []


def verifier(libelle, condition, detail=''):
    marque = 'ok ' if condition else '[X]'
    print('  [%s] %-52s %s' % (marque, libelle, detail))
    if not condition:
        problemes.append(libelle)


print('=' * 78)
print('1. FORMULAIRE PUBLIC : PROPOSER UNE ANNONCE')
print('=' * 78)

client = Client()
avant = OfferSubmission.objects.count()

donnees = {
    'title': 'Assistant de test',
    'company_name': 'Entreprise de test',
    'employer_kind': 'company',
    'location': 'Ouagadougou',
    'employment_type': 'CDI',
    'details': 'Une description de test pour verifier le parcours.',
    'source_name': 'Test',
    'application_method': 'email',
    'application_email': 'recrutement@exemple.bf',
    'contact_email': 'contact@exemple.bf',
    'declarant_role': 'employer',
    'ethics_commitment': 'on',
}

avec_creation = False
with transaction.atomic():
    reponse = client.post(reverse('submit_offer'), donnees)
    avec_creation = OfferSubmission.objects.count() == avant + 1
    transaction.set_rollback(True)

verifier('le formulaire public accepte une annonce', reponse.status_code in (200, 302))
verifier(
    'la soumission est enregistree',
    avec_creation,
    '(%d -> %d)' % (avant, OfferSubmission.objects.count()),
)
derniere = OfferSubmission.objects.order_by('-id').first()
if derniere:
    verifier(
        'la soumission reste en attente de validation',
        derniere.status == OfferSubmission.STATUS_PENDING,
        derniere.status,
    )
    verifier(
        'la soumission cree aucune offre automatiquement',
        derniere.offer_id is None,
    )

print()
print('=' * 78)
print('2. ADMINISTRATION : VALIDER ET PUBLIER UNE OFFRE')
print('=' * 78)

staff = get_user_model().objects.filter(is_staff=True).first()
client.force_login(staff)

offre = Offer(
    title='Offre de controle %s' % os.getpid(),
    company_name='Entreprise de test',
    description='Description de test.',
    status=Offer.STATUS_PENDING,
)
offre.slug = 'offre-de-controle-%s' % os.getpid()
with transaction.atomic():
    offre.save()
    transaction.set_rollback(True)

with transaction.atomic():
    offre.status = Offer.STATUS_PUBLISHED
    offre.is_source_confirmed = True
    offre.save()
    transaction.set_rollback(True)

verifier('une offre peut etre publiee', offre.status == Offer.STATUS_PUBLISHED)
verifier('la publication est horodatee', offre.published_at is not None)

print()
print('=' * 78)
print('3. ADMINISTRATION : REJETER UNE OFFRE')
print('=' * 78)

with transaction.atomic():
    offre.status = Offer.STATUS_REJECTED
    offre.save()
    transaction.set_rollback(True)

verifier('une offre peut etre rejetee', offre.status == Offer.STATUS_REJECTED)
verifier('une offre rejetee n est plus publique', not offre.is_published)

print()
print('=' * 78)
print('4. SIGNALEMENT PUBLIC')
print('=' * 78)

avant = OfferReport.objects.count()
donnees_report = {
    'reason': 'misleading',
    'suspect_title': 'Offre suspecte',
    'suspect_organization': 'Organisation',
    'suspect_channel': 'whatsapp',
    'details': 'Un signalement de controle du parcours de signalement public.',
    'reporter_name': 'Testeur',
}

avec_creation = False
with transaction.atomic():
    reponse = client.post(reverse('report_fraud'), donnees_report)
    avec_creation = OfferReport.objects.count() == avant + 1
    transaction.set_rollback(True)

verifier('le signalement est accepte', reponse.status_code in (200, 302))
verifier(
    'le signalement est enregistre',
    avec_creation,
)

print()
print('=' * 78)
print('5. SAUVEGARDE : LES NOUVELLES TABLES SONT-ELLES INCLUSES ?')
print('=' * 78)

from offres import backups  # noqa: E402

tables = backups.export_tables()
noms = sorted(tables.keys())
for attendue in (
    'offres_collectedannouncement',
    'offres_veillerun',
    'offres_offer',
    'offres_source',
):
    verifier('table %s presente dans la sauvegarde' % attendue, attendue in tables)
verifier('les colonnes de veille sont sauvegardees', 'missions' in tables['offres_offer']['columns'])
verifier(
    'les champs de surveillance sont sauvegardes',
    'authorization_note' in tables['offres_source']['columns'],
)

print()
print('=' * 78)
print('6. COMMANDES DE LA VEILLE')
print('=' * 78)

from io import StringIO  # noqa: E402

sortie = StringIO()
try:
    call_command('collect_offers', '--dry-run', stdout=sortie)
    verifier('collect_offers --dry-run repond', True)
except Exception as erreur:
    verifier('collect_offers --dry-run repond', False, str(erreur))

sortie = StringIO()
try:
    call_command('collect_offers', stdout=sortie)
    verifier('collect_offers sans source autorisee repond', True)
except Exception as erreur:
    verifier('collect_offers sans source autorisee repond', False, str(erreur))

sortie = StringIO()
try:
    call_command('veille_essai', 'Un texte', stdout=sortie)
    verifier('veille_essai repond', True)
except Exception as erreur:
    verifier('veille_essai repond', False, str(erreur))

print()
print('=' * 78)
print('BILAN')
print('=' * 78)
if problemes:
    print('  %d probleme(s) :' % len(problemes))
    for probleme in problemes:
        print('   -', probleme)
else:
    print('  Aucune anomalie detectee.')
