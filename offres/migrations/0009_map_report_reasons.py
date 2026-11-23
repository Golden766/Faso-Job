from django.db import migrations


LEGACY_REASONS = {
    'Offre déjà pourvue': 'misleading',
    'Informations inexactes': 'misleading',
    'Lien de candidature invalide': 'invalid_link',
    'Suspicion de fraude': 'fees',
    'Autre': 'other',
}

KNOWN_REASONS = [
    'fees',
    'fake_company',
    'impersonation',
    'mlm',
    'dangerous_meeting',
    'misleading',
    'invalid_link',
    'other',
]


def map_legacy_reasons(apps, schema_editor):
    OfferReport = apps.get_model('offres', 'OfferReport')
    for legacy_label, code in LEGACY_REASONS.items():
        OfferReport.objects.filter(reason=legacy_label).update(reason=code)
    OfferReport.objects.exclude(reason__in=KNOWN_REASONS).update(reason='other')


class Migration(migrations.Migration):

    dependencies = [
        ('offres', '0008_offerreport_admin_note_offerreport_amount_requested_and_more'),
    ]

    operations = [
        migrations.RunPython(map_legacy_reasons, migrations.RunPython.noop),
    ]
