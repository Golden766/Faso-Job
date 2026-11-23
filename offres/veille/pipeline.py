"""Le parcours complet d'une annonce collectee.

C'est ici que les etapes s'enchainent dans l'ordre :

1. **collecte** : le texte et l'adresse de l'annonce sont recuperes ;
2. **conservation** : une ligne est ecrite avec la provenance et le
   contenu original ;
3. **extraction** : l'intelligence artificielle propose les informations ;
4. **classement** : l'annonce est classee dans une categorie qui existe
   deja ;
5. **doublons** : le catalogue est passe en revue ;
6. **brouillon** : si l'extraction a reussi, une offre est creee en
   attente de l'equipe ; sinon l'annonce reste detectee avec son erreur.

Deux regles ne bougent pas :

- le brouillon est cree en `draft`, jamais en `published` ;
- rien n'est supprime : un doublon est signale, pas efface.
"""

import logging

from django.utils import timezone
from django.utils.text import slugify

from ..models import (
    Category,
    CollectedAnnouncement,
    Offer,
    VeilleRun,
)
from . import collectors, dedup, ia

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Erreur survenue pendant le traitement d'une annonce."""


def unique_slug(title, fallback='offre'):
    """Construit un identifiant d URL unique.

    L'identifiant d'une offre est unique : deux annonces de meme
    intitule doivent pouvoir coexister. Un suffixe est ajoute au
    besoin, comme le fait deja la creation d offre a partir d une
    proposition.
    """
    base = slugify(title or '') or fallback
    slug = base
    suffix = 1
    while Offer.objects.filter(slug=slug).exists():
        slug = '%s-%s' % (base, suffix)
        suffix += 1
    return slug


def _category_names():
    """Noms des categories deja enregistrees."""
    return list(Category.objects.values_list('name', flat=True))


def _find_category(name):
    """Retrouve une categorie a partir de son nom."""
    if not name:
        return None
    return Category.objects.filter(name__iexact=name).first()


def _parse_date(value):
    """Lit une date au format AAAA-MM-JJ."""
    from datetime import date as date_class

    try:
        return date_class.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def process_item(source, item, adapter=None, category_names=None):
    """Traite une annonce trouvee, du texte brut au brouillon.

    Renvoie la ligne `CollectedAnnouncement` creee. Elle porte la trace
    de tout ce qui a ete fait, y compris les echecs.
    """
    content_hash = collectors.content_hash(item.text)
    provenance_url = item.url or (source.url if source else '')

    # Une annonce deja collectee ne cree pas un second brouillon : la
    # trace suffit, et le catalogue reste propre.
    previous = dedup.already_collected(content_hash)
    if previous is not None:
        return CollectedAnnouncement.objects.create(
            source=source,
            source_name=source.name if source else '',
            source_url=provenance_url,
            collection_method=source.collection_method if source else '',
            collected_at=timezone.now(),
            raw_content=item.text,
            content_hash=content_hash,
            status=CollectedAnnouncement.STATUS_DUPLICATE,
            duplicate_status=CollectedAnnouncement.DUPLICATE_CONFIRMED,
            duplicate_of=previous.offer,
            duplicate_reasons=(
                'Annonce deja collectee le %s.'
                % timezone.localtime(previous.collected_at).strftime('%d/%m/%Y')
            ),
        )

    announcement = CollectedAnnouncement.objects.create(
        source=source,
        source_name=source.name if source else '',
        source_url=provenance_url,
        collection_method=source.collection_method if source else '',
        collected_at=timezone.now(),
        raw_content=item.text,
        content_hash=content_hash,
        status=CollectedAnnouncement.STATUS_DETECTED,
    )

    # --- Extraction ------------------------------------------------------
    extracted = {}
    extraction = ia.extract_announcement(item.text, adapter=adapter)
    announcement.ai_provider = extraction.provider
    announcement.ai_model = extraction.model
    if extraction.raw:
        announcement.extracted_data = {
            'raw': extraction.raw,
            'fields': extraction.data,
        }

    if extraction.is_ok:
        extracted = extraction.data
        announcement.extraction_status = CollectedAnnouncement.EXTRACTION_DONE
        announcement.ai_prompt_version = ia.PROMPT_VERSION
        if extracted.get('published_at'):
            announcement.source_published_at = _parse_date(extracted['published_at'])
    else:
        announcement.extraction_status = CollectedAnnouncement.EXTRACTION_FAILED
        announcement.error_message = extraction.error

    # --- Classement ------------------------------------------------------
    names = category_names if category_names is not None else _category_names()
    category = None
    if extracted and names:
        classification = ia.classify_announcement(extracted, names, adapter=adapter)
        if classification.is_ok:
            category = _find_category(classification.data.get('category'))
            if classification.data.get('category') and category is None:
                announcement.error_message = (
                    announcement.error_message
                    + ' Categorie proposee sans suite : « %s ».'
                    % classification.data.get('category')
                ).strip()

    # --- Doublons --------------------------------------------------------
    matches = dedup.find_duplicates(extracted, source_url=provenance_url)
    if matches:
        best_offer, best_score, _best_reasons = matches[0]
        announcement.duplicate_status = CollectedAnnouncement.DUPLICATE_SUSPECTED
        announcement.duplicate_of = best_offer
        announcement.duplicate_score = best_score
        announcement.duplicate_reasons = dedup.summarize(matches)

    announcement.save()

    # --- Brouillon -------------------------------------------------------
    if not extraction.is_ok:
        return announcement

    offer = _create_draft(source, item, extracted, category)
    announcement.offer = offer
    announcement.status = CollectedAnnouncement.STATUS_DRAFT_CREATED
    announcement.save(update_fields=['offer', 'status'])

    return announcement


def _create_draft(source, item, extracted, category):
    """Cree le brouillon d offre.

    Le brouillon n'est jamais publie : il attend une decision humaine.
    Les deux verifications de publication restent a false : sans coche
    de l equipe, l offre ne peut pas passer en publiee.
    """
    extracted = extracted or {}

    title = (
        extracted.get('title')
        or item.title
        or (source.name if source else '')
        or 'Annonce collectee'
    )

    offer = Offer(
        title=title[:250],
        slug=unique_slug(title),
        company_name=(extracted.get('company_name') or '')[:200],
        location=(extracted.get('location') or '')[:200],
        employment_type=(extracted.get('employment_type') or '')[:100],
        description=extracted.get('description') or '',
        missions=extracted.get('missions') or '',
        required_profile=extracted.get('required_profile') or '',
        required_education=(extracted.get('required_education') or '')[:120],
        experience_required=(extracted.get('experience_required') or '')[:120],
        deadline=_parse_date(extracted.get('deadline')),
        application_method=extracted.get('application_method') or '',
        application_url=extracted.get('application_url') or '',
        application_email=extracted.get('application_email') or '',
        application_phone=extracted.get('application_phone') or '',
        whatsapp_number=extracted.get('whatsapp_number') or '',
        application_instructions=extracted.get('application_instructions') or '',
        category=category,
        source=source,
        status=Offer.STATUS_DRAFT,
        is_published=False,
        is_source_confirmed=False,
        is_employer_verified=False,
    )
    offer.save()
    return offer


def _process_collection(source, collection, adapter=None, category_names=None):
    """Traite les annonces d'un passage de collecte."""
    announcements = []
    for item in collection.items:
        try:
            announcements.append(
                process_item(
                    source,
                    item,
                    adapter=adapter,
                    category_names=category_names,
                )
            )
        except Exception as error:
            # Une annonce qui pose probleme ne doit pas arreter les
            # autres : l erreur est notee, la collecte continue.
            logger.exception('Traitement impossible pour une annonce')
            announcements.append(
                CollectedAnnouncement.objects.create(
                    source=source,
                    source_name=source.name if source else '',
                    source_url=item.url or '',
                    collection_method=source.collection_method if source else '',
                    collected_at=timezone.now(),
                    raw_content=item.text,
                    content_hash=collectors.content_hash(item.text),
                    status=CollectedAnnouncement.STATUS_DETECTED,
                    error_message='Traitement impossible : %s' % error,
                )
            )
    return announcements


def _finish_run(run, collection, announcements):
    """Consigne le resultat d'un passage de collecte."""
    run.found_count = collection.count
    run.created_count = len(
        [
            a
            for a in announcements
            if a.status == CollectedAnnouncement.STATUS_DRAFT_CREATED
        ]
    )
    run.duplicate_count = len(
        [
            a
            for a in announcements
            if a.duplicate_status != CollectedAnnouncement.DUPLICATE_NONE
        ]
    )
    run.error_count = len(collection.errors) + len(
        [
            a
            for a in announcements
            if a.extraction_status == CollectedAnnouncement.EXTRACTION_FAILED
        ]
    )

    finished = timezone.now()
    run.finished_at = finished
    run.duration_seconds = max(0, int((finished - run.started_at).total_seconds()))

    if run.error_count and run.created_count:
        run.status = VeilleRun.STATUS_PARTIAL
    elif run.error_count:
        run.status = VeilleRun.STATUS_FAILURE
    else:
        run.status = VeilleRun.STATUS_SUCCESS

    message = '%d annonce(s) trouvee(s), %d brouillon(s) cree(s)' % (
        run.found_count,
        run.created_count,
    )
    if run.duplicate_count:
        message += ', %d doublon(s) signale(s)' % run.duplicate_count
    if run.error_count:
        message += ', %d erreur(s)' % run.error_count
    run.message = message[:255]

    run.save()
    return run


def collect_and_process(
    source, triggered_by='manual', adapter=None, category_names=None
):
    """Collecte une source et traite les annonces trouvees.

    Renvoie le passage de collecte (`VeilleRun`), avec ses compteurs.
    """
    run = VeilleRun.objects.create(
        source=source,
        triggered_by=triggered_by,
        status=VeilleRun.STATUS_RUNNING,
        started_at=timezone.now(),
    )

    collection = collectors.collect_source(source)
    announcements = _process_collection(
        source, collection, adapter=adapter, category_names=category_names
    )
    _finish_run(run, collection, announcements)

    if source is not None:
        source.last_collected_at = timezone.now()
        source.last_status = run.status
        source.save(update_fields=['last_collected_at', 'last_status'])

    return run


def collect_and_process_text(source, text, adapter=None, category_names=None):
    """Traite un texte d annonce saisi a la main."""
    collection = collectors.collect_text(text)
    return _process_collection(
        source, collection, adapter=adapter, category_names=category_names
    )


def collect_and_process_url(source, url, adapter=None, category_names=None):
    """Traite une page d annonce dont l adresse a ete saisie."""
    collection = collectors.collect_url(url)
    return _process_collection(
        source, collection, adapter=adapter, category_names=category_names
    )
