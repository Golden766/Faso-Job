from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from . import moderation
from .models import (
    BlacklistedContact,
    Category,
    CollectedAnnouncement,
    NotificationRecipient,
    Offer,
    OfferReport,
    OfferSubmission,
    OutboundMessage,
    PlatformSettings,
    Source,
    SourceProposal,
    TwoFactorDevice,
    TwoFactorRecoveryCode,
    VeilleRun,
)

admin.site.site_header = 'Faso Job — Administration'
admin.site.site_title = 'Faso Job'
admin.site.index_title = 'Gestion éditoriale des offres'
admin.site.empty_value_display = '—'


def _badge(label, tone, title=''):
    """Petit badge coloré, aligné sur la charte publique."""
    if title:
        return format_html(
            '<span class="fj-admin-badge fj-admin-badge--{}" title="{}">{}</span>',
            tone,
            title,
            label,
        )
    return format_html(
        '<span class="fj-admin-badge fj-admin-badge--{}">{}</span>',
        tone,
        label,
    )


class FasoJobModelAdmin(admin.ModelAdmin):
    """Base commune des pages d'administration de la plateforme.

    Django affiche par defaut « Selectionnez l'objet offre a changer » comme
    titre de liste : le libelle est remplace par un titre editorial, ce qui
    aligne le titre de la page, le fil d'Ariane et le menu lateral.
    """

    changelist_title = ''

    def get_changelist(self, request):
        from django.contrib.admin.views.main import ChangeList

        class FasoJobChangeList(ChangeList):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if self.model_admin.changelist_title:
                    self.title = self.model_admin.changelist_title

        return FasoJobChangeList


OFFER_STATUS_TONES = {
    Offer.STATUS_DRAFT: 'neutral',
    Offer.STATUS_PENDING: 'warning',
    Offer.STATUS_PUBLISHED: 'success',
    Offer.STATUS_REJECTED: 'danger',
    Offer.STATUS_CLOSED: 'neutral',
    Offer.STATUS_ARCHIVED: 'neutral',
}

# Libelles courts utilises dans les listes : la colonne reste lisible et
# toutes les cases du tableau ont la meme hauteur.
OFFER_STATUS_LABELS = {
    Offer.STATUS_DRAFT: 'Brouillon',
    Offer.STATUS_PENDING: 'En validation',
    Offer.STATUS_PUBLISHED: 'Publiée',
    Offer.STATUS_REJECTED: 'Rejetée',
    Offer.STATUS_CLOSED: 'Fermée',
    Offer.STATUS_ARCHIVED: 'Archivée',
}

SUBMISSION_STATUS_TONES = {
    OfferSubmission.STATUS_PENDING: 'warning',
    OfferSubmission.STATUS_ACCEPTED: 'success',
    OfferSubmission.STATUS_REJECTED: 'danger',
}

REPORT_STATUS_TONES = {
    OfferReport.STATUS_OPEN: 'danger',
    OfferReport.STATUS_REVIEWED: 'warning',
    OfferReport.STATUS_RESOLVED: 'success',
    OfferReport.STATUS_IGNORED: 'neutral',
}

BLACKLIST_STATUS_TONES = {
    BlacklistedContact.STATUS_BLOCKED: 'danger',
    BlacklistedContact.STATUS_WATCH: 'warning',
    BlacklistedContact.STATUS_NEUTRALIZED: 'neutral',
}


@admin.action(description='Marquer comme en attente de validation')
def mark_pending_review(modeladmin, request, queryset):
    for offer in queryset:
        offer.status = Offer.STATUS_PENDING
        offer.save()


@admin.action(description='Valider et publier les offres sélectionnées')
def publish_selected(modeladmin, request, queryset):
    offers = list(queryset)
    invalid_offers = []
    for offer in offers:
        offer.status = Offer.STATUS_PUBLISHED
        try:
            offer.full_clean()
        except ValidationError as error:
            invalid_offers.append((offer, error))

    if invalid_offers:
        for offer, error in invalid_offers:
            modeladmin.message_user(
                request,
                f"Publication impossible pour « {offer.title} » : {error}",
                level=messages.ERROR,
            )
        return

    with transaction.atomic():
        for offer in offers:
            offer.save()


@admin.action(description='Rejeter les offres sélectionnées')
def reject_selected(modeladmin, request, queryset):
    for offer in queryset:
        offer.status = Offer.STATUS_REJECTED
        offer.save()


@admin.action(description='Confirmer la disponibilité des offres sélectionnées')
def confirm_availability(modeladmin, request, queryset):
    now = timezone.now()
    queryset.update(is_available=True, availability_confirmed_at=now)


@admin.action(description='Marquer les offres sélectionnées comme indisponibles')
def mark_unavailable(modeladmin, request, queryset):
    queryset.update(is_available=False, availability_confirmed_at=timezone.now())


@admin.action(description='Ajouter les contacts signalés à la liste noire')
def add_to_blacklist(modeladmin, request, queryset):
    """Inscrit les contacts signalés au registre privé.

    Le signalement reste inchangé et le statut d'une offre n'est jamais
    modifié automatiquement : l'équipe décide ensuite du statut du contact.
    """
    created = 0
    already_known = 0
    for report in queryset:
        phone_number = report.suspect_phone.strip()
        if not phone_number:
            continue
        normalized = ''.join(
            character for character in phone_number if character.isdigit()
        )
        exists = BlacklistedContact.objects.filter(
            report=report,
            phone_number=phone_number,
        ).exists()
        if not exists and normalized:
            exists = any(
                entry.normalized_number == normalized
                for entry in BlacklistedContact.objects.all()
            )
        if exists:
            already_known += 1
            continue
        BlacklistedContact.objects.create(
            phone_number=phone_number,
            organization=report.suspect_organization
            or report.suspect_title
            or 'Annonce non précisée',
            reason=report.reason,
            amount_requested=report.amount_requested,
            details=report.details,
            report=report,
            created_by=request.user,
        )
        created += 1

    modeladmin.message_user(
        request,
        f'{created} contact(s) inscrit(s) sur la liste noire.',
        level=messages.SUCCESS if created else messages.WARNING,
    )
    if already_known:
        modeladmin.message_user(
            request,
            f'{already_known} contact(s) déjà présents sur la liste noire.',
            level=messages.INFO,
        )


@admin.action(description='Bloquer définitivement les contacts sélectionnés')
def mark_blacklist_blocked(modeladmin, request, queryset):
    queryset.update(status=BlacklistedContact.STATUS_BLOCKED)


@admin.action(description='Placer les contacts sélectionnés sous surveillance')
def mark_blacklist_watch(modeladmin, request, queryset):
    queryset.update(status=BlacklistedContact.STATUS_WATCH)


@admin.action(description='Recontrôler toutes les offres et propositions')
def rescreen_everything(modeladmin, request, queryset):
    """Relance le croisement sur l'ensemble du catalogue.

    Le contrôle complet leve aussi les quarantarines qui ne correspondent
    plus : c'est la seule voie qui autorise un nettoyage.
    """
    offers = moderation.screen_offers(Offer.objects.all(), clear_when_no_match=True)
    submissions = moderation.screen_submissions(
        OfferSubmission.objects.all(), clear_when_no_match=True
    )
    modeladmin.message_user(
        request,
        f'{offers} offre(s) et {submissions} proposition(s) signalees.',
        level=messages.WARNING if (offers or submissions) else messages.INFO,
    )


@admin.action(description='Relancer le contrôle de quarantaine sur les offres sélectionnées')
def rescreen_offers(modeladmin, request, queryset):
    """Recalcule la quarantaine des offres selectionnees."""
    quarantined = moderation.screen_offers(queryset)
    modeladmin.message_user(
        request,
        f'{quarantined} offre(s) placee(s) en quarantaine.',
        level=messages.WARNING if quarantined else messages.INFO,
    )


@admin.action(description='Enregistrer le contrôle de quarantaine et autoriser la publication')
def mark_quarantine_reviewed(modeladmin, request, queryset):
    """Enregistre un controle humain : la publication redevient possible."""
    now = timezone.now()
    count = 0
    for offer in queryset:
        if not offer.quarantine_reason:
            continue
        offer.quarantine_reviewed_at = now
        offer.quarantine_reviewed_by = request.user
        offer.save(update_fields=[
            'quarantine_reviewed_at',
            'quarantine_reviewed_by',
        ], skip_quarantine_check=True)
        count += 1
    modeladmin.message_user(
        request,
        f'{count} offre(s) marquee(s) comme controlees.',
        level=messages.SUCCESS if count else messages.INFO,
    )


@admin.action(description='Lever la quarantaine sur les offres sélectionnées')
def clear_quarantine(modeladmin, request, queryset):
    """Retire le motif de quarantaine apres verification manuelle."""
    count = 0
    for offer in queryset:
        if not offer.quarantine_reason:
            continue
        offer.quarantine_reason = ''
        offer.quarantined_at = None
        offer.quarantine_reviewed_at = None
        offer.quarantine_reviewed_by = None
        offer.save(update_fields=[
            'quarantine_reason',
            'quarantined_at',
            'quarantine_reviewed_at',
            'quarantine_reviewed_by',
        ], skip_quarantine_check=True)
        count += 1
    modeladmin.message_user(
        request,
        f'{count} offre(s) liberee(s) de la quarantaine.',
        level=messages.SUCCESS if count else messages.INFO,
    )


@admin.action(description='Accepter la soumission et créer une offre en attente de vérification')
def accept_submission(modeladmin, request, queryset):
    for submission in queryset:
        with transaction.atomic():
            submission.status = OfferSubmission.STATUS_ACCEPTED
            submission.reviewed_by = request.user
            submission.save(update_fields=['status', 'reviewed_by'])
            submission.create_offer_from_submission()


@admin.action(description='Rejeter la ou les soumissions sélectionnées')
def reject_submission(modeladmin, request, queryset):
    for submission in queryset:
        submission.status = OfferSubmission.STATUS_REJECTED
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])


@admin.action(description='Marquer le signalement comme en cours de vérification')
def mark_report_in_review(modeladmin, request, queryset):
    for report in queryset:
        report.mark_reviewed(request.user)


@admin.action(description='Résoudre le ou les signalements sélectionnés')
def resolve_report(modeladmin, request, queryset):
    for report in queryset:
        report.mark_resolved(request.user)


@admin.action(description='Ignorer le ou les signalements sélectionnés')
def ignore_report(modeladmin, request, queryset):
    for report in queryset:
        report.status = OfferReport.STATUS_IGNORED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])


@admin.action(description='Préparer un message pour le déclarant des soumissions sélectionnées')
def prepare_submission_message(modeladmin, request, queryset):
    """Prepare un message à destination du déclarant d'une proposition.

    Le message est **préparé et enregistré**, pas envoyé : aucun fournisseur
    WhatsApp ou SMS n'est configure. Le declarant garde la main sur la
    communication, conformement a la regle de gestion qui veut qu'aucune
    notification automatise ne soit promise tant qu'elle n'existe pas.
    """
    from . import channels

    prepared = 0
    skipped = 0
    for submission in queryset:
        recipient = (submission.contact_phone or '').strip()
        if not recipient:
            skipped += 1
            continue

        offer = submission.offer
        body = (
            'Bonjour,\n\n'
            'Votre proposition « %s » a été examinée par l’équipe Faso Job.\n'
            % submission.title
        )
        if offer is not None:
            body += (
                'L’offre correspondante est disponible ici : %s\n'
                % reverse('offer_detail', args=[offer.slug])
            )
        body += (
            '\nUne question ? Répondez directement à ce message.\n\n'
            'L’équipe Faso Job'
        )

        channels.send_message(
            OutboundMessage.CHANNEL_WHATSAPP,
            recipient,
            body,
            offer=offer,
            submission=submission,
        )
        prepared += 1

    modeladmin.message_user(
        request,
        f'{prepared} message(s) préparé(s). Aucun envoi réel : '
        'aucun fournisseur n’est configuré.',
        level=messages.INFO,
    )
    if skipped:
        modeladmin.message_user(
            request,
            f'{skipped} proposition(s) sans téléphone : aucun message préparé.',
            level=messages.WARNING,
        )



@admin.action(description='Collecter la source maintenant')
def collect_source_now(modeladmin, request, queryset):
    """Declenche une collecte immediate des sources selectionnees.

    Seules les sources autorisees et automatisables sont collectees :
    les autres sont signalees, sans etre touchees.
    """
    from .veille import pipeline

    refuses = 0
    for source in queryset:
        if not source.is_watchable:
            refuses += 1
            continue
        run = pipeline.collect_and_process(source)
        modeladmin.message_user(
            request,
            f'{source.name} : {run.message}',
            level=messages.SUCCESS if not run.error_count else messages.WARNING,
        )

    if refuses:
        modeladmin.message_user(
            request,
            f'{refuses} source(s) non collectee(s) : autorisation ou mode de '
            'collecte manquant.',
            level=messages.WARNING,
        )

@admin.register(Source)
class SourceAdmin(FasoJobModelAdmin):
    changelist_title = 'Sources'
    list_display = (
        'name',
        'url',
        'is_verified',
        'watch_badge',
        'collection_method',
        'last_collected_at',
        'created_at',
    )
    list_filter = ('is_verified', 'is_watched', 'collection_method')
    search_fields = ('name', 'url')
    actions = [collect_source_now]
    fieldsets = (
        ('Source', {
            'fields': ('name', 'url', 'description', 'is_verified'),
        }),
        ('Veille', {
            'fields': (
                'collection_method',
                'is_watched',
                'watch_config',
                'authorization_note',
                'last_collected_at',
                'last_status',
            ),
        }),
    )

    @admin.display(description='surveillance', ordering='is_watched')
    def watch_badge(self, obj):
        """Indique si la source est reellement surveillee.

        Une source marquee comme surveillee mais depourvue d autorisation
        n est pas surveillee : la couleur le rappelle a l equipe.
        """
        if obj.is_watchable:
            return _badge('Surveillée', 'success')
        if obj.is_watched and not (obj.authorization_note or '').strip():
            return _badge(
                'Sans autorisation',
                'warning',
                title=(
                    'La surveillance ne demarre pas sans une note '
                    'd autorisation ecrite.'
                ),
            )
        if obj.is_watched:
            return _badge('Mode incompatible', 'warning')
        return _badge('Non surveillée', 'neutral')


@admin.register(Category)
class CategoryAdmin(FasoJobModelAdmin):
    changelist_title = 'Catégories'
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Offer)
class OfferAdmin(FasoJobModelAdmin):
    changelist_title = 'Offres'
    list_display = (
        'title',
        'company_name',
        'location',
        'status_badge',
        'quarantine_badge',
        'verification_badge',
        'availability_badge',
        'view_count',
        'created_at',
    )
    list_filter = (
        'status',
        'is_published',
        'is_available',
        'is_source_confirmed',
        'is_employer_verified',
        'quarantine_reason',
    )
    search_fields = ('title', 'company_name', 'location')
    prepopulated_fields = {'slug': ('title',)}
    actions = [
        mark_pending_review,
        publish_selected,
        reject_selected,
        confirm_availability,
        mark_unavailable,
        rescreen_offers,
        rescreen_everything,
        mark_quarantine_reviewed,
        clear_quarantine,
    ]
    date_hierarchy = 'created_at'
    list_per_page = 30
    save_on_top = True

    @admin.display(description='statut', ordering='status')
    def status_badge(self, obj):
        if obj.status == Offer.STATUS_PUBLISHED and obj.is_expired():
            # Une offre publiee dont la date limite est passee n'est plus
            # visible sur le site public : l'equipe doit le voir ici.
            return _badge(
                'Publiée · expirée',
                'warning',
                title=(
                    'La date limite est dépassée : cette offre n’est plus '
                    'affichée sur le site public.'
                ),
            )
        return _badge(
            OFFER_STATUS_LABELS.get(obj.status, obj.get_status_display()),
            OFFER_STATUS_TONES.get(obj.status, 'neutral'),
        )

    @admin.display(description='vérifications')
    def verification_badge(self, obj):
        if obj.is_source_confirmed and obj.is_employer_verified:
            return _badge('Source + employeur', 'success')
        if obj.is_source_confirmed:
            return _badge('Source vérifiée', 'info')
        if obj.is_employer_verified:
            return _badge('Employeur vérifié', 'success')
        return _badge('Non vérifiée', 'warning')

    @admin.display(description='disponibilité', ordering='is_available')
    def availability_badge(self, obj):
        if obj.is_available and obj.availability_confirmed_at:
            return _badge(
                f'Confirmée {timezone.localtime(obj.availability_confirmed_at):%d/%m/%Y}',
                'success',
            )
        if obj.is_available:
            return _badge('À confirmer', 'warning')
        return _badge('Indisponible', 'danger')

    @admin.display(description='quarantaine', ordering='quarantine_reason')
    def quarantine_badge(self, obj):
        if not obj.quarantine_reason:
            return _badge('Aucune', 'neutral')
        if obj.quarantine_severity == moderation.SEVERITY_BLOCKED:
            return _badge('Bloquée', 'danger')
        if obj.quarantine_reviewed_at:
            return _badge('Contrôlée', 'info')
        return _badge('En quarantaine', 'warning')

    @admin.display(description='panneau de vérification')
    def verification_panel(self, obj):
        """Rappelle les trois contrôles distincts avant publication."""
        if obj is None:
            return 'Enregistrez l’offre pour afficher son panneau de vérification.'

        checks = (
            ('Source vérifiée', obj.is_source_confirmed),
            ('Employeur vérifié', obj.is_employer_verified),
            ('Toujours disponible', obj.is_available),
        )
        rows = []
        for label, is_done in checks:
            badge = _badge('Fait', 'success') if is_done else _badge('À faire', 'warning')
            rows.append(
                format_html(
                    '<div class="fj-admin-check"><span>{}</span>{}</div>',
                    label,
                    badge,
                )
            )

        if obj.status == Offer.STATUS_PUBLISHED:
            published_at = (
                timezone.localtime(obj.published_at).strftime('%d/%m/%Y %H:%M')
                if obj.published_at
                else '—'
            )
            rows.append(
                format_html(
                    '<div class="fj-admin-check"><span>Publiée le</span>{}</div>',
                    published_at,
                )
            )

        missing = []
        if not obj.title.strip():
            missing.append('intitulé')
        if not obj.description.strip():
            missing.append('description')
        if not obj.company_name.strip():
            missing.append('entreprise')
        if not (obj.is_source_confirmed or obj.is_employer_verified):
            missing.append('source ou employeur vérifié')

        if missing:
            rows.append(
                format_html(
                    '<div class="fj-admin-check fj-admin-check--warning">'
                    '<span>Publication impossible — champs manquants</span>{}</div>',
                    ', '.join(missing),
                )
            )

        if obj.quarantine_reason:
            if obj.quarantine_reviewed_at:
                rows.append(
                    format_html(
                        '<div class="fj-admin-check fj-admin-check--warning">'
                        '<span>Quarantaine contrôlée</span>{}</div>',
                        obj.quarantine_reason,
                    )
                )
            else:
                rows.append(
                    format_html(
                        '<div class="fj-admin-check fj-admin-check--danger">'
                        '<span>Quarantaine — publication refusée</span>{}</div>',
                        obj.quarantine_reason,
                    )
                )

        open_reports = obj.reports.filter(
            status__in=(OfferReport.STATUS_OPEN, OfferReport.STATUS_REVIEWED)
        ).count()
        if open_reports:
            rows.append(
                format_html(
                    '<div class="fj-admin-check fj-admin-check--danger">'
                    '<span>Signalements en cours</span>{}</div>',
                    open_reports,
                )
            )

        return mark_safe(
            '<div class="fj-admin-checks">%s</div>' % ''.join(str(row) for row in rows)
        )

    fieldsets = (
        ('Informations principales', {'fields': ('title', 'slug', 'company_name', 'employer_kind', 'category', 'source', 'location', 'employment_type')}),
        ('Description et rémunération', {'fields': ('description', 'salary_min', 'salary_max', 'salary_currency', 'salary_note', 'experience_required', 'deadline', 'deadline_time', 'schedule')}),
        ('Missions et profil recherché', {'fields': ('missions', 'required_profile', 'required_education')}),
        ('Candidature', {'fields': ('application_method', 'application_url', 'application_email', 'whatsapp_number', 'application_phone', 'application_instructions', 'required_documents')}),
        ('Publication et disponibilité', {'fields': ('status', 'is_published', 'is_available', 'published_at', 'availability_confirmed_at')}),
        ('Vérifications', {'fields': ('is_source_confirmed', 'is_employer_verified')}),
        ('Panneau de vérification', {'fields': ('verification_panel',)}),
    )
    readonly_fields = ('availability_confirmed_at', 'verification_panel')


@admin.register(OfferSubmission)
class OfferSubmissionAdmin(FasoJobModelAdmin):
    changelist_title = 'Soumissions'
    list_display = (
        'title',
        'company_name',
        'declarant_role',
        'contact_email',
        'contact_phone',
        'status_badge',
        'reviewed_by',
        'offer',
        'created_at',
    )
    list_filter = ('status', 'declarant_role')
    search_fields = ('title', 'company_name', 'contact_email', 'contact_phone')
    readonly_fields = ('reviewed_by', 'reviewed_at')
    actions = [
        accept_submission,
        reject_submission,
        prepare_submission_message,
        rescreen_everything,
    ]
    date_hierarchy = 'created_at'
    list_per_page = 30
    save_on_top = True

    @admin.display(description='statut', ordering='status')
    def status_badge(self, obj):
        return _badge(
            obj.get_status_display(),
            SUBMISSION_STATUS_TONES.get(obj.status, 'neutral'),
        )
    fieldsets = (
        ('Informations sur le poste', {'fields': ('title', 'company_name', 'employer_kind', 'location', 'employment_type', 'details', 'salary_min', 'salary_max', 'salary_currency', 'salary_note', 'experience_required', 'deadline', 'deadline_time', 'schedule')}),
        ('Source', {'fields': ('source_name', 'source_url')}),
        ('Candidature', {'fields': ('application_method', 'application_url', 'application_email', 'application_phone', 'whatsapp_number', 'application_instructions', 'required_documents')}),
        ('Déclarant et conformité', {'fields': ('declarant_role', 'contact_email', 'contact_phone', 'ethics_commitment')}),
        ('Suivi', {'fields': ('status', 'reviewed_by', 'reviewed_at', 'offer')}),
    )


@admin.register(OfferReport)
class OfferReportAdmin(FasoJobModelAdmin):
    changelist_title = 'Signalements'
    list_display = (
        'id',
        'reason_badge',
        'suspect_title',
        'suspect_organization',
        'status_badge',
        'offer',
        'created_at',
    )
    list_filter = ('status', 'reason', 'suspect_channel', 'created_at')
    date_hierarchy = 'created_at'
    list_per_page = 30
    save_on_top = True
    search_fields = (
        'suspect_title',
        'suspect_organization',
        'suspect_phone',
        'suspect_url',
        'details',
        'reporter_name',
        'reporter_email',
        'offer__title',
    )
    list_select_related = ('offer', 'reviewed_by')
    readonly_fields = ('reviewed_by', 'reviewed_at', 'created_at', 'evidence_download')
    actions = [mark_report_in_review, resolve_report, ignore_report, add_to_blacklist]
    fieldsets = (
        ('Signalement', {'fields': ('offer', 'reason', 'status', 'created_at')}),
        (
            'Annonce ou personne mise en cause',
            {
                'fields': (
                    'suspect_title',
                    'suspect_organization',
                    'suspect_phone',
                    'suspect_channel',
                    'suspect_url',
                    'amount_requested',
                    'location_mentioned',
                    'details',
                )
            },
        ),
        ('Preuve jointe', {'fields': ('evidence_download',)}),
        ('Déclarant', {'fields': ('reporter_name', 'reporter_email', 'reporter_phone')}),
        ('Traitement interne', {'fields': ('admin_note', 'reviewed_by', 'reviewed_at')}),
    )

    @admin.display(description='motif', ordering='reason')
    def reason_badge(self, obj):
        tone = 'danger' if obj.reason in {
            OfferReport.REASON_FEES,
            OfferReport.REASON_FAKE_COMPANY,
            OfferReport.REASON_IMPERSONATION,
            OfferReport.REASON_MLM,
        } else 'warning'
        return _badge(obj.get_reason_display(), tone)

    @admin.display(description='état', ordering='status')
    def status_badge(self, obj):
        return _badge(
            obj.get_status_display(),
            REPORT_STATUS_TONES.get(obj.status, 'neutral'),
        )

    @admin.display(description='preuve jointe')
    def evidence_download(self, obj):
        if not obj.evidence:
            return 'Aucune preuve jointe.'
        return format_html(
            '<a href="{}" rel="noopener">Télécharger la preuve (accès réservé au personnel)</a>',
            reverse('report_evidence', args=[obj.pk]),
        )


@admin.register(BlacklistedContact)
class BlacklistedContactAdmin(FasoJobModelAdmin):
    changelist_title = 'Liste noire'
    list_display = (
        'organization',
        'phone_number',
        'operator',
        'reason_badge',
        'status_badge',
        'alert_badge',
        'report',
        'created_at',
    )
    list_filter = ('status', 'operator', 'reason', 'alert_disseminated', 'created_at')
    search_fields = (
        'phone_number',
        'organization',
        'declared_name',
        'details',
        'report__suspect_title',
    )
    list_select_related = ('report', 'created_by')
    readonly_fields = ('created_by', 'created_at', 'updated_at', 'alert_disseminated_at')
    date_hierarchy = 'created_at'
    list_per_page = 30
    save_on_top = True
    actions = [mark_blacklist_blocked, mark_blacklist_watch]
    fieldsets = (
        ('Contact mis en cause', {
            'fields': ('phone_number', 'operator', 'declared_name', 'organization'),
        }),
        ('Signalement', {
            'fields': ('reason', 'amount_requested', 'details', 'report'),
        }),
        ('Statut', {
            'fields': ('status', 'alert_disseminated', 'alert_disseminated_at'),
        }),
        ('Traçabilité', {
            'fields': ('created_by', 'created_at', 'updated_at'),
        }),
    )

    @admin.display(description='motif', ordering='reason')
    def reason_badge(self, obj):
        tone = 'danger' if obj.reason in {
            OfferReport.REASON_FEES,
            OfferReport.REASON_FAKE_COMPANY,
            OfferReport.REASON_IMPERSONATION,
            OfferReport.REASON_MLM,
        } else 'warning'
        return _badge(obj.get_reason_display(), tone)

    @admin.display(description='statut', ordering='status')
    def status_badge(self, obj):
        return _badge(
            obj.get_status_display(),
            BLACKLIST_STATUS_TONES.get(obj.status, 'neutral'),
        )

    @admin.display(description='alerte')
    def alert_badge(self, obj):
        if obj.alert_disseminated:
            return _badge('Alerte diffusée', 'info')
        return _badge('Alerte non diffusée', 'neutral')


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(FasoJobModelAdmin):
    changelist_title = 'Paramètres de la plateforme'
    """Ligne unique : pas de création ni de suppression depuis l'admin."""

    list_display = (
        'site_name',
        'site_tagline',
        'contact_email',
        'alert_email',
        'auto_archive_days',
        'updated_at',
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Une seule ligne existe : l'écran d'accueil du modèle n'a pas d'intérêt.
        PlatformSettings.load()
        return redirect('admin:offres_platformsettings_change', 1)

    fieldsets = (
        ('Identité', {
            'fields': ('site_name', 'site_tagline'),
        }),
        ('Contacts', {
            'fields': ('contact_email', 'alert_email', 'emergency_phone', 'emergency_whatsapp'),
        }),
        ('Modération', {
            'fields': ('moderation_guideline', 'quarantine_keywords'),
        }),
        ('Automatisation', {
            'fields': ('auto_archive_days', 'view_counter_enabled', 'notifications_enabled'),
        }),
        ('Traçabilité', {
            'fields': ('updated_at',),
        }),
    )


@admin.register(OutboundMessage)
class OutboundMessageAdmin(FasoJobModelAdmin):
    changelist_title = 'Messages envoyés'
    """Journal des messages sortants prepares.

    Aucun fournisseur n'est configure : les messages restent au statut
    « aucun fournisseur configure ». Ce journal montre ce qui aurait ete
    envoye, sans pretendre qu'un envoi a eu lieu.
    """

    list_display = (
        'channel_badge',
        'recipient',
        'status_badge',
        'provider',
        'offer',
        'submission',
        'created_at',
    )
    list_filter = ('channel', 'status', 'created_at')
    search_fields = ('recipient', 'body', 'offer__title', 'submission__title')
    list_select_related = ('offer', 'submission')
    readonly_fields = (
        'channel',
        'recipient',
        'body',
        'status',
        'provider',
        'error',
        'offer',
        'submission',
        'created_at',
        'sent_at',
    )
    date_hierarchy = 'created_at'
    list_per_page = 30
    save_on_top = True

    def has_add_permission(self, request):
        # Les messages sont prepares par le code, pas saisis a la main.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='canal', ordering='channel')
    def channel_badge(self, obj):
        return _badge(obj.get_channel_display(), 'info')

    @admin.display(description='etat', ordering='status')
    def status_badge(self, obj):
        tones = {
            OutboundMessage.STATUS_SENT: 'success',
            OutboundMessage.STATUS_PENDING: 'warning',
            OutboundMessage.STATUS_FAILED: 'danger',
            OutboundMessage.STATUS_NOT_CONFIGURED: 'neutral',
        }
        return _badge(obj.get_status_display(), tones.get(obj.status, 'neutral'))


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(FasoJobModelAdmin):
    changelist_title = 'Destinataires de notification'
    """Adresses qui recoivent les notifications de la plateforme.

    On ajoute une adresse, on la desactive temporairement ou on la
    supprime. L adresse d alerte des parametres reste receveuse meme si
    elle n est pas dans cette liste.
    """

    list_display = ('email', 'label', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('email', 'label')
    list_editable = ('is_active',)
    list_per_page = 30
    save_on_top = True

    fieldsets = (
        ('Destinataire', {
            'fields': ('email', 'label'),
        }),
        ('Actif', {
            'fields': ('is_active',),
        }),
    )


@admin.register(TwoFactorDevice)
class TwoFactorDeviceAdmin(FasoJobModelAdmin):
    changelist_title = 'Appareils 2FA'
    """Appareils d'authentification a deux facteurs.

    Le secret partage n'est jamais affiche en clair ici : il est chiffre
    dans la base. La page de reglages du compte permet a l utilisateur
    d'activer ou de desactiver sa propre protection.
    """

    list_display = (
        'user',
        'is_active',
        'confirmed_at',
        'last_used_at',
        'recovery_codes_remaining',
    )
    list_filter = ('is_active', 'confirmed_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('secret', 'confirmed_at', 'last_used_at', 'created_at')
    list_per_page = 30

    @admin.display(description='codes de secours restants')
    def recovery_codes_remaining(self, obj):
        return obj.recovery_codes.filter(is_used=False).count()

    def has_add_permission(self, request):
        # L appareil se cree depuis la page de reglages du compte.
        return False


@admin.register(TwoFactorRecoveryCode)
class TwoFactorRecoveryCodeAdmin(FasoJobModelAdmin):
    changelist_title = 'Codes de secours'
    """Codes de secours : seules les empreintes sont conservees."""

    list_display = ('device', 'is_used', 'created_at', 'used_at')
    list_filter = ('is_used',)
    readonly_fields = ('code_hash', 'created_at', 'used_at')
    list_select_related = ('device',)

    def has_add_permission(self, request):
        return False


@admin.action(description='Confirmer le doublon signalé')
def confirm_duplicate(modeladmin, request, queryset):
    """Confirme qu'une annonce collectee fait doublon.

    Le catalogue n'est pas modifie : la confirmation dit seulement que
    l'equipe a vu le rapprochement. La suppression, elle, reste une
    decision explicite, dans la liste des offres.
    """
    count = 0
    for announcement in queryset:
        if announcement.duplicate_status == CollectedAnnouncement.DUPLICATE_NONE:
            continue
        announcement.duplicate_status = CollectedAnnouncement.DUPLICATE_CONFIRMED
        announcement.mark_reviewed(request.user)
        announcement.save(
            update_fields=['duplicate_status', 'reviewed_by', 'reviewed_at']
        )
        count += 1
    modeladmin.message_user(
        request,
        f'{count} doublon(s) confirme(s).',
        level=messages.SUCCESS if count else messages.INFO,
    )


@admin.action(description='Écarter le doublon signalé')
def dismiss_duplicate(modeladmin, request, queryset):
    """Ecarte un rapprochement : l annonce reste a verifier."""
    count = 0
    for announcement in queryset:
        if announcement.duplicate_status == CollectedAnnouncement.DUPLICATE_NONE:
            continue
        announcement.duplicate_status = CollectedAnnouncement.DUPLICATE_DISMISSED
        announcement.mark_reviewed(request.user)
        announcement.save(
            update_fields=['duplicate_status', 'reviewed_by', 'reviewed_at']
        )
        count += 1
    modeladmin.message_user(
        request,
        f'{count} doublon(s) ecarte(s).',
        level=messages.SUCCESS if count else messages.INFO,
    )


@admin.action(description='Rejeter les annonces collectées sélectionnées')
def reject_collected(modeladmin, request, queryset):
    """Rejette les annonces collectees signalees par l equipe."""
    count = 0
    for announcement in queryset:
        announcement.status = CollectedAnnouncement.STATUS_REJECTED
        announcement.mark_reviewed(request.user)
        announcement.save(
            update_fields=['status', 'reviewed_by', 'reviewed_at']
        )
        count += 1
    modeladmin.message_user(
        request,
        f'{count} annonce(s) rejetee(s).',
        level=messages.SUCCESS if count else messages.INFO,
    )


@admin.register(SourceProposal)
class SourceProposalAdmin(FasoJobModelAdmin):
    """Sources proposees par l assistant de decouverte.

    L assistant propose, l equipe decide. Cette liste montre ce qui a
    ete constate pour chaque adresse, afin que la decision soit prise
    sur une trace et non sur une impression.
    """

    changelist_title = 'Sources proposées'
    list_display = (
        'id',
        'name',
        'url',
        'kind',
        'verdict_badge',
        'status_badge',
        'score',
        'selector',
        'blocks_count',
        'created_at',
    )
    list_filter = ('status', 'verdict', 'origin', 'kind')
    search_fields = ('url', 'name', 'page_title', 'selector', 'sample')
    list_select_related = ('source', 'reviewed_by')
    readonly_fields = (
        'url',
        'name',
        'page_title',
        'kind',
        'origin',
        'why',
        'verdict',
        'score',
        'selector',
        'blocks_count',
        'sample',
        'reasons',
        'conditions_quote',
        'conditions_found',
        'source',
        'reviewed_by',
        'reviewed_at',
        'created_at',
    )
    date_hierarchy = 'created_at'
    list_per_page = 30
    save_on_top = True
    actions = ['accepter_propositions', 'refuser_propositions']

    @admin.action(description='Accepter les sources proposées sélectionnées')
    def accepter_propositions(modeladmin, request, queryset):
        """Autorise les sources retenues par l equipe.

        La note d autorisation est ecrite par l equipe : elle est
        pre-remplie avec le constat de l assistant, mais c est elle
        qui la signe.
        """
        from .veille import decouverte_admin

        acceptees = 0
        for proposition in queryset:
            if decouverte_admin.accepter(proposition, request.user):
                acceptees += 1
        modeladmin.message_user(
            request,
            f'{acceptees} source(s) autorisee(s) et ajoutee(s) a la veille.',
            level=messages.SUCCESS if acceptees else messages.INFO,
        )

    @admin.action(description='Refuser les sources proposées sélectionnées')
    def refuser_propositions(modeladmin, request, queryset):
        """Refuse les sources proposees.

        Une source refusee reste tracee : on ne peut pas la
        redemander a chaque decouverte.
        """
        refusees = 0
        for proposition in queryset:
            if proposition.status == proposition.STATUS_PENDING:
                proposition.status = proposition.STATUS_REFUSED
                proposition.reviewed_by = request.user
                proposition.reviewed_at = timezone.now()
                proposition.save(
                    update_fields=['status', 'reviewed_by', 'reviewed_at']
                )
                refusees += 1
        modeladmin.message_user(
            request,
            f'{refusees} source(s) refusee(s).',
            level=messages.SUCCESS if refusees else messages.INFO,
        )

    @admin.display(description='verdict', ordering='verdict')
    def verdict_badge(self, obj):
        tones = {
            SourceProposal.VERDICT_SOURCE: 'success',
            SourceProposal.VERDICT_A_VERIFIER: 'warning',
            SourceProposal.VERDICT_ECARTEE: 'danger',
        }
        return _badge(obj.get_verdict_display(), tones.get(obj.verdict, 'neutral'))

    @admin.display(description='decide', ordering='status')
    def status_badge(self, obj):
        tones = {
            SourceProposal.STATUS_PENDING: 'warning',
            SourceProposal.STATUS_ACCEPTED: 'success',
            SourceProposal.STATUS_REFUSED: 'neutral',
            SourceProposal.STATUS_OBSOLETE: 'neutral',
        }
        return _badge(obj.get_status_display(), tones.get(obj.status, 'neutral'))


@admin.register(CollectedAnnouncement)
class CollectedAnnouncementAdmin(FasoJobModelAdmin):
    """Annonces reperees par la veille, avec leur trace de collecte.

    Cette liste est un registre, pas un espace de publication : elle
    montre ce que la veille a trouve et ce que l equipe en a fait. Le
    contenu original reste visible pour que l extraction de l IA puisse
    etre verifiee.
    """

    changelist_title = 'Annonces collectées'
    list_display = (
        'id',
        'source_name',
        'collection_method',
        'status_badge',
        'duplicate_badge',
        'extraction_badge',
        'offer',
        'collected_at',
    )
    list_filter = (
        'status',
        'extraction_status',
        'duplicate_status',
        'collection_method',
    )
    search_fields = ('source_name', 'source_url', 'raw_content')
    list_select_related = ('source', 'offer', 'duplicate_of')
    readonly_fields = (
        'source_name',
        'source_url',
        'collection_method',
        'collected_at',
        'raw_content',
        'content_hash',
        'source_published_at',
        'extraction_status',
        'extracted_data',
        'ai_provider',
        'ai_model',
        'ai_prompt_version',
        'duplicate_status',
        'duplicate_of',
        'duplicate_score',
        'duplicate_reasons',
        'error_message',
        'reviewed_by',
        'reviewed_at',
        'created_at',
    )
    date_hierarchy = 'collected_at'
    list_per_page = 30
    save_on_top = True
    actions = [
        confirm_duplicate,
        dismiss_duplicate,
        reject_collected,
    ]

    @admin.display(description='état', ordering='status')
    def status_badge(self, obj):
        tones = {
            CollectedAnnouncement.STATUS_DETECTED: 'warning',
            CollectedAnnouncement.STATUS_DRAFT_CREATED: 'info',
            CollectedAnnouncement.STATUS_DUPLICATE: 'warning',
            CollectedAnnouncement.STATUS_REJECTED: 'danger',
        }
        return _badge(
            obj.get_status_display(),
            tones.get(obj.status, 'neutral'),
        )

    @admin.display(description='doublon', ordering='duplicate_status')
    def duplicate_badge(self, obj):
        if obj.duplicate_status == CollectedAnnouncement.DUPLICATE_CONFIRMED:
            return _badge('Confirmé', 'danger')
        if obj.duplicate_status == CollectedAnnouncement.DUPLICATE_SUSPECTED:
            return _badge('Potentiel', 'warning')
        if obj.duplicate_status == CollectedAnnouncement.DUPLICATE_DISMISSED:
            return _badge('Écarté', 'neutral')
        return _badge('Aucun', 'neutral')

    @admin.display(description='extraction')
    def extraction_badge(self, obj):
        if obj.extraction_status == CollectedAnnouncement.EXTRACTION_DONE:
            return _badge('Faite', 'success')
        if obj.extraction_status == CollectedAnnouncement.EXTRACTION_FAILED:
            return _badge('Échouée', 'danger')
        return _badge('En attente', 'neutral')


@admin.register(VeilleRun)
class VeilleRunAdmin(FasoJobModelAdmin):
    """Historique des passages de collecte.

    Ces lignes sont ecrites par le code : l administration les consulte,
    elle ne les saisit pas.
    """

    changelist_title = 'Historique des collectes'
    list_display = (
        'id',
        'source',
        'status_badge',
        'found_count',
        'created_count',
        'duplicate_count',
        'error_count',
        'triggered_by',
        'started_at',
    )
    list_filter = ('status', 'triggered_by')
    search_fields = ('source__name', 'message')
    list_select_related = ('source',)
    readonly_fields = (
        'source',
        'triggered_by',
        'status',
        'started_at',
        'finished_at',
        'duration_seconds',
        'found_count',
        'created_count',
        'duplicate_count',
        'error_count',
        'message',
    )
    date_hierarchy = 'started_at'
    list_per_page = 30
    save_on_top = True

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='résultat', ordering='status')
    def status_badge(self, obj):
        tones = {
            VeilleRun.STATUS_RUNNING: 'warning',
            VeilleRun.STATUS_SUCCESS: 'success',
            VeilleRun.STATUS_PARTIAL: 'warning',
            VeilleRun.STATUS_FAILURE: 'danger',
        }
        return _badge(
            obj.get_status_display(),
            tones.get(obj.status, 'neutral'),
        )


# Django enregistre ses propres pages d'utilisateurs et de roles avec le
# titre « Selectionnez l'objet ... a changer ». On les remplace pour que
# le titre, le fil d'Ariane et le menu lateral parlent de la meme chose.
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class FasoJobUserAdmin(FasoJobModelAdmin, UserAdmin):
    """Comptes de l'administration."""

    changelist_title = 'Utilisateurs'


@admin.register(Group)
class FasoJobGroupAdmin(FasoJobModelAdmin, GroupAdmin):
    """Roles et permissions de l'administration."""

    changelist_title = 'Rôles'
