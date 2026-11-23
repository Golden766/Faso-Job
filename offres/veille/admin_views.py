"""Le Centre de veille : la page ou l'equipe traite les annonces collectees.

Cette page regroupe les six listes attendues :

- les annonces detectees ;
- les annonces a verifier ;
- les doublons potentiels ;
- les annonces rejetees ;
- les sources surveillees ;
- l'historique des collectes.

Elle permet aussi de declencher une collecte : une source, un lien
colle ou un texte colle.

**Rien n'est publie depuis cette page.** Le Centre de veille prepare des
brouillons ; la publication reste une decision de l'equipe, prise dans
la liste des offres.
"""

from django.contrib import admin, messages
from django.shortcuts import redirect, render

from ..models import (
    CollectedAnnouncement,
    Offer,
    Source,
    SourceProposal,
    VeilleRun,
)
from . import decouverte_admin, decouverte_ia, pipeline
from .ia import get_adapter
from .scheduling import activation_instructions

# Nom de la source qui regroupe les annonces saisies a la main.
SOURCE_MANUELLE_LIEN = 'Saisie manuelle — lien'
SOURCE_MANUELLE_TEXTE = 'Saisie manuelle — texte'


def _manual_source(collection_method, name):
    """Source de saisie manuelle, creee au besoin.

    Les annonces saisies a la main sont rattachees a une source comme
    les autres : la provenance reste lisible.
    """
    source, _created = Source.objects.get_or_create(
        name=name,
        collection_method=collection_method,
        defaults={
            'description': 'Annonces saisies a la main par l equipe de Faso Job.',
        },
    )
    return source


def _chosen_source(request, fallback_method, fallback_name):
    """Source choisie dans le formulaire, ou source de saisie manuelle."""
    source_id = (request.POST.get('source_id') or '').strip()
    if source_id:
        source = Source.objects.filter(pk=source_id).first()
        if source is not None:
            return source
    return _manual_source(fallback_method, fallback_name)


def _announcement(pk):
    """Annonce collectee identifiee."""
    return CollectedAnnouncement.objects.filter(pk=pk).first()


@admin.site.admin_view
def veille_dashboard_view(request):
    """Page unique du Centre de veille."""
    context = admin.site.each_context(request)

    if request.method == 'POST':
        return _handle_action(request)

    adapter = get_adapter()

    contexte = {
        'title': 'Centre de veille',
        'active_section': 'veille',
        'ai_configured': adapter.is_configured(),
        'ai_model': adapter.model if adapter.is_configured() else '',
        'ai_provider': adapter.name if adapter.is_configured() else '',
        'annonces_detectees': CollectedAnnouncement.objects.filter(
            status=CollectedAnnouncement.STATUS_DETECTED
        ).select_related('source')[:20],
        'annonces_a_verifier': CollectedAnnouncement.objects.filter(
            status=CollectedAnnouncement.STATUS_DRAFT_CREATED,
            offer__isnull=False,
            offer__status=Offer.STATUS_DRAFT,
        ).select_related('offer', 'source')[:20],
        'doublons': CollectedAnnouncement.objects.filter(
            duplicate_status__in=[
                CollectedAnnouncement.DUPLICATE_SUSPECTED,
                CollectedAnnouncement.DUPLICATE_CONFIRMED,
            ]
        ).select_related('duplicate_of', 'source')[:20],
        'rejetees': CollectedAnnouncement.objects.filter(
            status=CollectedAnnouncement.STATUS_REJECTED
        ).select_related('source')[:20],
        'sources': Source.objects.all().order_by('name'),
        'sources_surveillees': Source.objects.filter(is_watched=True).order_by('name'),
        'runs': VeilleRun.objects.select_related('source').order_by('-started_at')[:20],
        'propositions': SourceProposal.objects.filter(
            status=SourceProposal.STATUS_PENDING
        ).select_related('reviewed_by')[:20],
        'propositions_refusees': SourceProposal.objects.filter(
            status=SourceProposal.STATUS_REFUSED
        ).count(),
        'moteur_recherche': decouverte_ia.moteur_recherche_disponible(),
        'instructions': activation_instructions(),
        'compteurs': _counters(),
        'offres_liste_url': '/admin/offres/offer/',
    }
    context.update(contexte)
    return render(request, 'admin/veille.html', context)


def _counters():
    """Compteurs affiches en tete de page."""
    return {
        'detectees': CollectedAnnouncement.objects.filter(
            status=CollectedAnnouncement.STATUS_DETECTED
        ).count(),
        'a_verifier': CollectedAnnouncement.objects.filter(
            status=CollectedAnnouncement.STATUS_DRAFT_CREATED,
            offer__isnull=False,
            offer__status=Offer.STATUS_DRAFT,
        ).count(),
        'doublons': CollectedAnnouncement.objects.filter(
            duplicate_status__in=[
                CollectedAnnouncement.DUPLICATE_SUSPECTED,
                CollectedAnnouncement.DUPLICATE_CONFIRMED,
            ]
        ).count(),
        'rejetees': CollectedAnnouncement.objects.filter(
            status=CollectedAnnouncement.STATUS_REJECTED
        ).count(),
        'surveillees': Source.objects.filter(is_watched=True).count(),
        'collectes': VeilleRun.objects.count(),
    }


def _handle_action(request):
    """Traite une action demandee depuis le Centre de veille."""
    action = (request.POST.get('action') or '').strip()

    if action == 'collect_source':
        return _collect_source(request)
    if action == 'collect_url':
        return _collect_url(request)
    if action == 'collect_text':
        return _collect_text(request)
    if action == 'discover_sources':
        return _discover_sources(request)
    if action == 'accept_proposal':
        return _accept_proposal(request)
    if action == 'refuse_proposal':
        return _refuse_proposal(request)
    if action == 'reject_announcement':
        return _reject_announcement(request)
    if action == 'confirm_duplicate':
        return _set_duplicate(request, CollectedAnnouncement.DUPLICATE_CONFIRMED)
    if action == 'dismiss_duplicate':
        return _set_duplicate(request, CollectedAnnouncement.DUPLICATE_DISMISSED)
    if action == 'mark_reviewed':
        return _mark_reviewed(request)

    messages.warning(request, 'Action inconnue.')
    return redirect('admin-veille')


def _collect_source(request):
    """Declenche la collecte d'une source surveillee."""
    source = Source.objects.filter(pk=request.POST.get('source_id')).first()
    if source is None:
        messages.error(request, 'Source introuvable.')
        return redirect('admin-veille')

    if not source.is_watchable:
        messages.error(
            request,
            '« %s » ne peut pas etre collectee : il lui faut un mode de collecte '
            'automatise et une autorisation ecrite.' % source.name,
        )
        return redirect('admin-veille')

    run = pipeline.collect_and_process(source)
    tone = messages.ERROR if run.error_count else messages.SUCCESS
    messages.add_message(request, tone, run.message)
    return redirect('admin-veille')


def _collect_url(request):
    """Traite un lien d annonce colle par l'equipe."""
    url = (request.POST.get('url') or '').strip()
    if not url:
        messages.error(request, 'Indiquez le lien de l annonce.')
        return redirect('admin-veille')

    source = _chosen_source(
        request, Source.COLLECTION_METHOD_MANUAL_URL, SOURCE_MANUELLE_LIEN
    )
    announcements = pipeline.collect_and_process_url(source, url)
    _report(request, announcements, messages)
    return redirect('admin-veille')


def _collect_text(request):
    """Traite un texte d annonce colle par l'equipe."""
    text = (request.POST.get('text') or '').strip()
    if not text:
        messages.error(request, 'Collez le texte de l annonce.')
        return redirect('admin-veille')

    source = _chosen_source(
        request, Source.COLLECTION_METHOD_MANUAL_TEXT, SOURCE_MANUELLE_TEXTE
    )
    announcements = pipeline.collect_and_process_text(source, text)
    _report(request, announcements, messages)
    return redirect('admin-veille')


def _report(request, announcements, messages_module):
    """Rend compte du traitement des annonces saisies."""
    if not announcements:
        messages_module.warning(request, 'Aucune annonce n a pu etre traitee.')
        return

    crees = [
        a for a in announcements
        if a.status == CollectedAnnouncement.STATUS_DRAFT_CREATED
    ]
    doublons = [
        a for a in announcements
        if a.duplicate_status != CollectedAnnouncement.DUPLICATE_NONE
    ]
    echecs = [
        a for a in announcements
        if a.extraction_status == CollectedAnnouncement.EXTRACTION_FAILED
    ]

    if crees:
        messages_module.success(
            request,
            '%d brouillon(s) cree(s) : ils attendent la validation dans la '
            'liste des offres.' % len(crees),
        )
    if doublons:
        messages_module.warning(
            request,
            '%d annonce(s) ressemble(nt) a une offre deja connue.' % len(doublons),
        )
    if echecs:
        messages_module.warning(
            request,
            '%d annonce(s) n ont pas pu etre analysees : aucun brouillon '
            'incomplet n a ete cree. Consultez les annonces detectees et '
            'leur erreur.' % len(echecs),
        )


def _discover_sources(request):
    """Lance la decouverte des sources et enregistre les propositions.

    La demande peut prendre quelques minutes : chaque adresse verifiee
    respecte le delai de dix secondes. Le nombre d adresses verifiees
    est limite pour que la page ne reste pas bloquee trop longtemps.
    """
    demande = (request.POST.get('demande') or '').strip()
    if not demande:
        messages.error(request, "Indiquez ce que l'assistant doit chercher.")
        return redirect('admin-veille')

    try:
        maximum = int(request.POST.get('maximum') or 8)
    except (TypeError, ValueError):
        maximum = 8
    maximum = max(1, min(maximum, decouverte_admin.MAXIMUM_PAR_LANCEMENT))

    propositions, textes = decouverte_admin.lancer_decouverte(
        demande, maximum=maximum
    )

    for texte in textes:
        messages.warning(request, texte)

    if propositions:
        messages.success(
            request,
            '%d source(s) proposee(s) : autorisez ou refusez les ci-dessous.'
            % len(propositions),
        )
    return redirect('admin-veille')


def _accept_proposal(request):
    """Autorise une proposition : la source entre dans la veille."""
    proposition = SourceProposal.objects.filter(
        pk=request.POST.get('proposal_id')
    ).first()
    if proposition is None:
        messages.error(request, 'Proposition introuvable.')
        return redirect('admin-veille')

    note = (request.POST.get('authorization_note') or '').strip()

    if proposition.needs_motivation and not note:
        messages.error(
            request,
            "La reprise n'est pas etablie par le site : indiquez pourquoi vous "
            "autorisez cette source.",
        )
        return redirect('admin-veille')

    accepte, motif = decouverte_admin.accepter(proposition, request.user, note)
    if accepte:
        messages.success(
            request,
            'Source autorisee : elle rejoint la collecte automatique.',
        )
    else:
        messages.warning(request, motif)
    return redirect('admin-veille')


def _refuse_proposal(request):
    """Refuse une proposition."""
    proposition = SourceProposal.objects.filter(
        pk=request.POST.get('proposal_id')
    ).first()
    if proposition is None:
        messages.error(request, 'Proposition introuvable.')
        return redirect('admin-veille')

    if decouverte_admin.refuser(proposition, request.user):
        messages.success(request, 'Source refusee.')
    else:
        messages.warning(request, 'Cette proposition a deja ete traitee.')
    return redirect('admin-veille')


def _reject_announcement(request):
    """Rejette une annonce collectee."""
    announcement = _announcement(request.POST.get('announcement_id'))
    if announcement is None:
        messages.error(request, 'Annonce introuvable.')
        return redirect('admin-veille')

    announcement.status = CollectedAnnouncement.STATUS_REJECTED
    announcement.mark_reviewed(request.user)
    announcement.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    messages.success(request, 'Annonce rejetee.')
    return redirect('admin-veille')


def _set_duplicate(request, status):
    """Confirme ou ecarte un doublon potentiel."""
    announcement = _announcement(request.POST.get('announcement_id'))
    if announcement is None:
        messages.error(request, 'Annonce introuvable.')
        return redirect('admin-veille')

    announcement.duplicate_status = status
    announcement.mark_reviewed(request.user)
    announcement.save(
        update_fields=['duplicate_status', 'reviewed_by', 'reviewed_at']
    )

    if status == CollectedAnnouncement.DUPLICATE_CONFIRMED:
        messages.success(request, 'Doublon confirme.')
    else:
        messages.success(request, 'Doublon ecarte : l annonce reste a verifier.')
    return redirect('admin-veille')


def _mark_reviewed(request):
    """Note qu'une annonce a ete examinee."""
    announcement = _announcement(request.POST.get('announcement_id'))
    if announcement is None:
        messages.error(request, 'Annonce introuvable.')
        return redirect('admin-veille')

    announcement.mark_reviewed(request.user)
    messages.success(request, 'Annonce notee comme examinee.')
    return redirect('admin-veille')
