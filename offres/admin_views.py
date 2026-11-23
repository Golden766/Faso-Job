import csv
from datetime import date, datetime, time

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import (
    BackupConfiguration,
    BackupRun,
    BlacklistedContact,
    CollectedAnnouncement,
    Offer,
    OfferClick,
    OfferReport,
    OfferSubmission,
    OfferView,
    PlatformSettings,
)

MOIS_FR = (
    '',
    'janvier',
    'février',
    'mars',
    'avril',
    'mai',
    'juin',
    'juillet',
    'août',
    'septembre',
    'octobre',
    'novembre',
    'décembre',
)


def _percent(part, total):
    if not total:
        return None
    return round(part * 100 / total, 1)


def _expired_offers(now=None):
    now = now or timezone.localtime()
    current_time = now.time().replace(tzinfo=None, microsecond=0)
    return Offer.objects.filter(
        status=Offer.STATUS_PUBLISHED,
        is_published=True,
    ).filter(
        Q(deadline__lt=now.date())
        | Q(deadline=now.date(), deadline_time__lte=current_time)
    )


def _month_buckets(months=6):
    """Six derniers mois, du plus ancien au plus récent."""
    today = timezone.localdate()
    buckets = []
    year, month = today.year, today.month
    for _ in range(months):
        buckets.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(buckets))


def _month_bounds(year, month):
    start = timezone.make_aware(datetime.combine(date(year, month, 1), time.min))
    if month == 12:
        end = timezone.make_aware(datetime.combine(date(year + 1, 1, 1), time.min))
    else:
        end = timezone.make_aware(datetime.combine(date(year, month + 1, 1), time.min))
    return start, end


def _count_by_month(queryset, field_name, buckets):
    """Compte les objets par mois, en une requête et sans trous."""
    start, _ = _month_bounds(*buckets[0])
    _, end = _month_bounds(*buckets[-1])
    counts = {}
    rows = (
        queryset.filter(**{f'{field_name}__gte': start, f'{field_name}__lt': end})
        .annotate(month=TruncMonth(field_name))
        .values('month')
        .annotate(total=Count('id'))
    )
    for row in rows:
        key = (row['month'].year, row['month'].month)
        counts[key] = row['total']
    return counts


def _build_activity_data():
    offer_total = Offer.objects.count()
    submission_total = OfferSubmission.objects.count()
    report_total = OfferReport.objects.count()

    offer_status_counts = {
        row['status']: row['total']
        for row in Offer.objects.values('status').annotate(total=Count('id'))
    }
    submission_status_counts = {
        row['status']: row['total']
        for row in OfferSubmission.objects.values('status').annotate(total=Count('id'))
    }
    report_status_counts = {
        row['status']: row['total']
        for row in OfferReport.objects.values('status').annotate(total=Count('id'))
    }
    report_reason_counts = {
        row['reason']: row['total']
        for row in OfferReport.objects.values('reason').annotate(total=Count('id'))
    }

    published_total = offer_status_counts.get(Offer.STATUS_PUBLISHED, 0)
    active_total = Offer.objects.published().not_expired().count()
    expired_total = _expired_offers().count()
    verified_source_total = Offer.objects.filter(
        status=Offer.STATUS_PUBLISHED,
        is_source_confirmed=True,
    ).count()
    verified_employer_total = Offer.objects.filter(
        status=Offer.STATUS_PUBLISHED,
        is_employer_verified=True,
    ).count()
    availability_total = Offer.objects.filter(
        status=Offer.STATUS_PUBLISHED,
        availability_confirmed_at__isnull=False,
    ).count()

    pending_submissions = submission_status_counts.get(OfferSubmission.STATUS_PENDING, 0)
    accepted_submissions = submission_status_counts.get(OfferSubmission.STATUS_ACCEPTED, 0)
    open_reports = report_status_counts.get(OfferReport.STATUS_OPEN, 0)
    in_review_reports = report_status_counts.get(OfferReport.STATUS_REVIEWED, 0)
    resolved_reports = report_status_counts.get(OfferReport.STATUS_RESOLVED, 0)
    ignored_reports = report_status_counts.get(OfferReport.STATUS_IGNORED, 0)
    handled_reports = resolved_reports + ignored_reports

    buckets = _month_buckets()
    monthly_rows = []
    offers_by_month = _count_by_month(Offer.objects.all(), 'published_at', buckets)
    submissions_by_month = _count_by_month(
        OfferSubmission.objects.all(), 'created_at', buckets
    )
    reports_by_month = _count_by_month(OfferReport.objects.all(), 'created_at', buckets)
    for year, month in buckets:
        key = (year, month)
        monthly_rows.append(
            {
                'label': f'{MOIS_FR[month]} {year}',
                'short_label': f'{month:02d}/{year}',
                'year': year,
                'month': month,
                'offers': offers_by_month.get(key, 0),
                'submissions': submissions_by_month.get(key, 0),
                'reports': reports_by_month.get(key, 0),
                'views': 0,
                'clicks': 0,
            }
        )

    offer_status_rows = [
        {
            'label': label,
            'count': offer_status_counts.get(value, 0),
            'share': _percent(offer_status_counts.get(value, 0), offer_total),
        }
        for value, label in Offer.STATUS_CHOICES
    ]
    submission_status_rows = [
        {
            'label': label,
            'count': submission_status_counts.get(value, 0),
            'share': _percent(submission_status_counts.get(value, 0), submission_total),
        }
        for value, label in OfferSubmission.STATUS_CHOICES
    ]
    report_status_rows = [
        {
            'label': label,
            'count': report_status_counts.get(value, 0),
            'share': _percent(report_status_counts.get(value, 0), report_total),
        }
        for value, label in OfferReport.STATUS_CHOICES
    ]
    report_reason_rows = [
        {
            'label': label,
            'count': report_reason_counts.get(value, 0),
            'share': _percent(report_reason_counts.get(value, 0), report_total),
        }
        for value, label in OfferReport.REASON_CHOICES
    ]

    click_counts = dict(
        OfferClick.objects.values('offer').annotate(total=Count('id'))
    )
    # Le nombre de consultations retenu est celui porte par les offres :
    # il correspond aux fiches reellement vues, meme si la table de
    # journal a ete purgee.
    view_total = sum(offer.view_count for offer in Offer.objects.all())
    click_total = OfferClick.objects.count()

    top_viewed_offers = [
        {
            'title': offer.title,
            'company_name': offer.company_name,
            'location': offer.location,
            'view_count': offer.view_count,
            'click_count': click_counts.get(offer.pk, 0),
        }
        for offer in Offer.objects.filter(view_count__gt=0).order_by(
            '-view_count', '-created_at'
        )[:10]
    ]

    click_channel_counts = {
        row['channel']: row['total']
        for row in OfferClick.objects.values('channel').annotate(total=Count('id'))
    }
    click_channel_rows = [
        {
            'label': label,
            'count': click_channel_counts.get(value, 0),
            'share': _percent(click_channel_counts.get(value, 0), click_total),
        }
        for value, label in OfferClick.CHANNEL_CHOICES
    ]

    views_by_month = _count_by_month(OfferView.objects.all(), 'created_at', buckets)
    clicks_by_month = _count_by_month(OfferClick.objects.all(), 'created_at', buckets)
    for row in monthly_rows:
        key = (row['year'], row['month'])
        row['views'] = views_by_month.get(key, 0)
        row['clicks'] = clicks_by_month.get(key, 0)

    blacklist_total = BlacklistedContact.objects.count()
    blacklist_alerts = BlacklistedContact.objects.filter(
        alert_disseminated=True,
    ).count()
    blacklist_status_counts = {
        row['status']: row['total']
        for row in BlacklistedContact.objects.values('status').annotate(total=Count('id'))
    }
    blacklist_status_rows = [
        {
            'label': label,
            'count': blacklist_status_counts.get(value, 0),
            'share': _percent(blacklist_status_counts.get(value, 0), blacklist_total),
        }
        for value, label in BlacklistedContact.STATUS_CHOICES
    ]

    summary_rows = [
        {'label': 'Offres enregistrées', 'value': offer_total},
        {'label': 'Offres publiées', 'value': published_total},
        {'label': 'Offres actives (publiées et disponibles)', 'value': active_total},
        {'label': 'Offres expirées', 'value': expired_total},
        {'label': 'Offres avec source vérifiée', 'value': verified_source_total},
        {'label': 'Offres avec employeur vérifié', 'value': verified_employer_total},
        {'label': 'Offres avec disponibilité confirmée', 'value': availability_total},
        {'label': 'Propositions reçues', 'value': submission_total},
        {'label': 'Propositions en attente', 'value': pending_submissions},
        {'label': 'Propositions acceptées', 'value': accepted_submissions},
        {'label': 'Signalements reçus', 'value': report_total},
        {'label': 'Signalements ouverts', 'value': open_reports},
        {'label': 'Signalements en vérification', 'value': in_review_reports},
        {'label': 'Signalements résolus', 'value': resolved_reports},
        {'label': 'Signalements ignorés', 'value': ignored_reports},
        {'label': 'Consultations de fiches', 'value': view_total},
        {'label': 'Clics vers un canal de candidature', 'value': click_total},
        {'label': 'Contacts sur liste noire', 'value': blacklist_total},
        {'label': 'Alertes de liste noire diffusées', 'value': blacklist_alerts},
    ]

    verified_published = (
        Offer.objects.filter(status=Offer.STATUS_PUBLISHED)
        .filter(Q(is_source_confirmed=True) | Q(is_employer_verified=True))
        .count()
    )

    return {
        'summary_rows': summary_rows,
        'offer_status_rows': offer_status_rows,
        'submission_status_rows': submission_status_rows,
        'report_status_rows': report_status_rows,
        'report_reason_rows': report_reason_rows,
        'top_viewed_offers': top_viewed_offers,
        'click_channel_rows': click_channel_rows,
        'view_total': view_total,
        'click_total': click_total,
        'blacklist_status_rows': blacklist_status_rows,
        'blacklist_total': blacklist_total,
        'blacklist_alerts': blacklist_alerts,
        'monthly_rows': monthly_rows,
        'offer_total': offer_total,
        'published_total': published_total,
        'active_total': active_total,
        'expired_total': expired_total,
        'submission_total': submission_total,
        'report_total': report_total,
        'open_reports': open_reports,
        'handled_reports': handled_reports,
        'acceptance_rate': _percent(accepted_submissions, submission_total),
        'handling_rate': _percent(handled_reports, report_total),
        'verification_rate': _percent(verified_published, published_total),
        'generated_at': timezone.localtime(),
    }


@admin.site.admin_view
def admin_dashboard_view(request):
    context = admin.site.each_context(request)
    now = timezone.localtime()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    active_offers = Offer.objects.published().not_expired(now)

    context.update(
        {
            'title': 'Tableau de bord éditorial',
            'today': now,
            'pending_submissions_count': OfferSubmission.objects.filter(
                status=OfferSubmission.STATUS_PENDING,
            ).count(),
            'pending_offers_count': Offer.objects.filter(
                status=Offer.STATUS_PENDING,
            ).count(),
            'active_offers_count': active_offers.count(),
            'expired_offers_count': _expired_offers(now).count(),
            'offers_to_refresh_count': active_offers.filter(
                availability_confirmed_at__isnull=True,
            ).count(),
            'open_reports_count': OfferReport.objects.filter(
                status__in=(OfferReport.STATUS_OPEN, OfferReport.STATUS_REVIEWED),
            ).count(),
            'published_offers_count': Offer.objects.filter(
                status=Offer.STATUS_PUBLISHED,
                is_published=True,
            ).count(),
            'published_this_month_count': Offer.objects.filter(
                status=Offer.STATUS_PUBLISHED,
                published_at__gte=month_start,
            ).count(),
            'quarantined_offers_count': Offer.objects.filter(
                quarantine_reason__gt='',
                quarantine_reviewed_at__isnull=True,
            ).count(),
            'blocked_offers_count': Offer.objects.filter(
                quarantine_severity='blocked',
            ).count(),
            'quarantined_submissions_count': OfferSubmission.objects.filter(
                quarantine_reason__gt='',
            ).count(),
            'blacklist_total_count': BlacklistedContact.objects.count(),
            'blacklist_blocked_count': BlacklistedContact.objects.filter(
                status=BlacklistedContact.STATUS_BLOCKED,
            ).count(),
            'blacklist_watch_count': BlacklistedContact.objects.filter(
                status=BlacklistedContact.STATUS_WATCH,
            ).count(),
            'veille_pending_count': CollectedAnnouncement.objects.filter(
                status=CollectedAnnouncement.STATUS_DRAFT_CREATED,
                offer__isnull=False,
                offer__status=Offer.STATUS_DRAFT,
            ).count(),
            'veille_duplicate_count': CollectedAnnouncement.objects.filter(
                duplicate_status__in=[
                    CollectedAnnouncement.DUPLICATE_SUSPECTED,
                    CollectedAnnouncement.DUPLICATE_CONFIRMED,
                ],
            ).count(),
            'platform_settings': PlatformSettings.load(),
            'recent_offers': Offer.objects.select_related('category').order_by(
                '-updated_at'
            )[:5],
            'recent_reports': OfferReport.objects.select_related('offer').filter(
                status__in=(OfferReport.STATUS_OPEN, OfferReport.STATUS_REVIEWED),
            )[:4],
            'recent_submissions': OfferSubmission.objects.filter(
                status=OfferSubmission.STATUS_PENDING,
            )[:4],
            'submission_list_url': reverse('admin:offres_offersubmission_changelist'),
            'offer_list_url': reverse('admin:offres_offer_changelist'),
            'expired_offers_url': reverse('admin-expired-offers'),
            'report_list_url': reverse('admin:offres_offerreport_changelist'),
            'category_list_url': reverse('admin:offres_category_changelist'),
            'source_list_url': reverse('admin:offres_source_changelist'),
            'blacklist_list_url': reverse('admin:offres_blacklistedcontact_changelist'),
            'platform_settings_url': reverse(
                'admin:offres_platformsettings_change', args=[1]
            ),
            'user_list_url': reverse('admin:auth_user_changelist'),
            'group_list_url': reverse('admin:auth_group_changelist'),
            'activity_report_url': reverse('admin-activity-report'),
            'activity_csv_url': reverse('admin-activity-report-csv'),
            'public_site_url': reverse('home'),
            'can_add_offer': request.user.has_perm('offres.add_offer'),
            'can_manage_categories': request.user.has_perm('offres.view_category'),
            'can_manage_sources': request.user.has_perm('offres.view_source'),
            'can_manage_users': request.user.has_perm('auth.view_user'),
            'can_manage_groups': request.user.has_perm('auth.view_group'),
        }
    )
    return render(request, 'admin/dashboard.html', context)


@admin.site.admin_view
def expired_offers_view(request):
    if not request.user.has_perm('offres.view_offer'):
        raise PermissionDenied

    if request.method == 'POST':
        if not request.user.has_perm('offres.change_offer'):
            raise PermissionDenied
        offer = get_object_or_404(
            _expired_offers(),
            pk=request.POST.get('offer_id'),
        )
        offer.status = Offer.STATUS_ARCHIVED
        offer.save()
        messages.success(request, f'« {offer.title} » a été archivée.')
        return redirect('admin-expired-offers')

    context = admin.site.each_context(request)
    context.update(
        {
            'title': 'Offres expirées',
            'active_section': 'expired_offers',
            'expired_offers': _expired_offers().order_by('deadline', 'title'),
            'can_change_offer': request.user.has_perm('offres.change_offer'),
            'offer_list_url': reverse('admin:offres_offer_changelist'),
        }
    )
    return render(request, 'admin/expired_offers.html', context)


@admin.site.admin_view
def activity_report_view(request):
    context = admin.site.each_context(request)
    context.update(_build_activity_data())
    context.update(
        {
            'title': 'Rapport d’activité',
            'active_section': 'activity',
            'csv_url': reverse('admin-activity-report-csv'),
        }
    )
    return render(request, 'admin/activity_report.html', context)


@admin.site.admin_view
def activity_report_export(request):
    data = _build_activity_data()
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f'fasojob-rapport-activite-{timezone.localdate():%Y%m%d}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')

    writer.writerow(['Rapport d’activité Faso Job'])
    writer.writerow(
        ['Généré le', data['generated_at'].strftime('%d/%m/%Y %H:%M')]
    )
    writer.writerow([])

    writer.writerow(['Indicateur', 'Valeur'])
    for row in data['summary_rows']:
        writer.writerow([row['label'], row['value']])
    writer.writerow(
        [
            'Taux d’acceptation des propositions (%)',
            '' if data['acceptance_rate'] is None else data['acceptance_rate'],
        ]
    )
    writer.writerow(
        [
            'Taux de traitement des signalements (%)',
            '' if data['handling_rate'] is None else data['handling_rate'],
        ]
    )
    writer.writerow(
        [
            'Part des offres publiées avec vérification (%)',
            '' if data['verification_rate'] is None else data['verification_rate'],
        ]
    )
    writer.writerow([])

    for section_title, rows in (
        ('Statut des offres', data['offer_status_rows']),
        ('Statut des propositions', data['submission_status_rows']),
        ('Statut des signalements', data['report_status_rows']),
        ('Motifs de signalement', data['report_reason_rows']),
        ('Statut des contacts sur liste noire', data['blacklist_status_rows']),
        ('Clics sortants par canal', data['click_channel_rows']),
    ):
        writer.writerow([section_title, 'Nombre', 'Part (%)'])
        for row in rows:
            writer.writerow(
                [row['label'], row['count'], '' if row['share'] is None else row['share']]
            )
        writer.writerow([])

    writer.writerow([])
    writer.writerow(
        ['Offre', 'Entreprise', 'Consultations', 'Clics sortants']
    )
    for row in data['top_viewed_offers']:
        writer.writerow([
            row['title'],
            row['company_name'],
            row['view_count'],
            row['click_count'],
        ])

    writer.writerow([])
    writer.writerow(
        [
            'Mois',
            'Offres publiées',
            'Propositions reçues',
            'Signalements reçus',
            'Consultations',
            'Clics sortants',
        ]
    )
    for row in data['monthly_rows']:
        writer.writerow([
            row['short_label'],
            row['offers'],
            row['submissions'],
            row['reports'],
            row['views'],
            row['clicks'],
        ])

    return response


@admin.site.admin_view
def backup_settings_view(request):
    """Configuration et historique des sauvegardes.

    L administration configure tout ce qui est possible de configurer :
    destination, retention, frequence, format et fichiers joints. Elle
    peut aussi lancer une sauvegarde immediatement, deposer un fichier de
    sauvegarde et installer une sauvegarde sur le site.

    Ce qu elle ne peut pas faire : se planifier elle-meme. L activation
    automatique demande une tache planifiee sur le serveur ; la commande
    a copier-coller est affichee plus bas.
    """
    from . import backups

    context = admin.site.each_context(request)

    configuration = backups.get_configuration()
    runs = list(
        BackupRun.objects.select_related('configuration').order_by('-started_at')[:20]
    )
    instructions = backups.activation_instructions(configuration)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save':
            configuration.destination = (
                request.POST.get('destination') or 'backups'
            ).strip()
            configuration.filename_prefix = (
                request.POST.get('filename_prefix') or 'fasojob'
            ).strip()
            configuration.retention_count = max(
                0,
                int(request.POST.get('retention_count') or 0),
            )
            configuration.frequency = (
                request.POST.get('frequency') or BackupConfiguration.FREQUENCY_DAILY
            )
            configuration.compress = 'compress' in request.POST
            configuration.include_media = 'include_media' in request.POST
            configuration.enabled = 'enabled' in request.POST
            configuration.save()
            messages.success(request, 'Configuration des sauvegardes enregistree.')
            return redirect('admin-backups')

        if action == 'run':
            rows = backups.count_rows()
            if rows > backups.MANUAL_BACKUP_MAX_ROWS:
                messages.error(
                    request,
                    'La base compte %d lignes : trop pour une sauvegarde depuis '
                    'le navigateur. Utilisez la commande backup_database.' % rows,
                )
                return redirect('admin-backups')

            run = backups.perform_backup(
                triggered_by=BackupRun.TRIGGER_MANUAL,
                configuration=configuration,
                actor=request.user,
            )
            if run.status == BackupRun.STATUS_SUCCESS:
                messages.success(request, run.message)
            else:
                messages.error(request, run.message)
            return redirect('admin-backups')

        if action == 'upload':
            uploaded = request.FILES.get('backup_file')
            try:
                target = backups.store_uploaded_backup(uploaded, configuration)
            except backups.BackupError as error:
                messages.error(request, str(error))
                return redirect('admin-backups')

            messages.success(
                request,
                'Fichier de sauvegarde depose : %s. Verifiez son contenu '
                'avant de l installer.' % target.name,
            )
            return redirect('admin-backup-restore', file_name=target.name)

    # La liste contient le nom et la taille de chaque fichier : un chemin
    # seul ne suffirait pas a afficher une taille lisible.
    backup_files = [
        {
            'name': path.name,
            'size': path.stat().st_size,
            'path': path,
        }
        for path in backups.list_backup_files(configuration)
    ]

    context.update(
        {
            'title': 'Sauvegardes',
            'active_section': 'backups',
            'configuration': configuration,
            'runs': runs,
            'instructions': instructions,
            'backup_files': backup_files,
            'has_files': bool(backup_files),
            'save_url': reverse('admin-backups'),
            'restore_word': backups.RESTORE_CONFIRMATION_WORD,
            'max_upload_mo': backups.MAX_UPLOAD_BYTES // (1024 * 1024),
        }
    )
    return render(request, 'admin/backups.html', context)


@admin.site.admin_view
def backup_restore_view(request, file_name):
    """Apercu puis installation d une sauvegarde sur le site.

    L installation remplace le contenu de la base. Elle est donc protegee
    par deux etapes : l apercu montre ce qui sera ecrit, puis le mot de
    confirmation doit etre recopie. Une sauvegarde de securite est
    produite avant toute ecriture.
    """
    from . import backups

    context = admin.site.each_context(request)
    configuration = backups.get_configuration()

    try:
        path = backups.resolve_backup_file(file_name, configuration)
    except backups.BackupError as error:
        messages.error(request, str(error))
        return redirect('admin-backups')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'apply':
            confirmation = (request.POST.get('confirmation') or '').strip()
            if confirmation != backups.RESTORE_CONFIRMATION_WORD:
                messages.error(
                    request,
                    'Confirmation incorrecte : rien n a ete installe. '
                    'Recopiez le mot demande pour confirmer.',
                )
                return redirect('admin-backup-restore', file_name=path.name)

            try:
                result = backups.install_backup(
                    path,
                    configuration=configuration,
                    actor=request.user,
                )
            except backups.BackupError as error:
                messages.error(request, str(error))
                return redirect('admin-backup-restore', file_name=path.name)
            except Exception as error:
                # La restauration se fait dans une transaction : la base
                # est restee dans son etat d avant.
                messages.error(
                    request,
                    "L'installation a echoue : %s. Aucune donnee n'a ete "
                    'modifiee.' % error,
                )
                return redirect('admin-backup-restore', file_name=path.name)

            messages.success(request, result['message'])
            return redirect('admin-backups')

    try:
        preview = backups.preview_backup(path, configuration)
    except backups.BackupError as error:
        messages.error(request, str(error))
        return redirect('admin-backups')

    context.update(
        {
            'title': 'Installer une sauvegarde',
            'active_section': 'backups',
            'configuration': configuration,
            'preview': preview,
            'restore_word': backups.RESTORE_CONFIRMATION_WORD,
            'install_url': reverse(
                'admin-backup-restore',
                kwargs={'file_name': preview['name']},
            ),
            'backups_url': reverse('admin-backups'),
        }
    )
    return render(request, 'admin/backup_restore.html', context)
