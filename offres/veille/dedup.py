"""Rapprochement des annonces collectees avec le catalogue deja connu.

Avant de creer un brouillon, la veille regarde si l offre n existe
pas deja. Elle compare :

- l'intitule du poste ;
- l'entreprise ;
- le lieu ;
- la date limite de candidature ;
- le lien de la source ;
- le contenu de l'annonce.

**Rien n'est supprime.** Un rapprochement est un signalement : c'est
l'equipe qui decide si l annonce est la meme offre, si elle est
reprise d'une autre source, ou si c'est une offre differente qui se
ressemble. La veille se contente de dire « celles-ci se ressemblent,
et voici pourquoi ».
"""

import difflib

from .schema import normalize

# Similarite au-dela de laquelle deux annonces sont considerees comme
# un meme poste. En dessous, la veille ne dit rien : trop de
# rapprochements rendraient le signalement inutile.
SEUIL_DOUBLON = 0.6

# Similarite des intitules a partir de laquelle deux offres sont
# vues comme le meme poste.
SEUIL_TITRE_FORT = 0.85
SEUIL_TITRE_FAIBLE = 0.6

# Similarite des descriptions a partir de laquelle le contenu est
# juge identique.
SEUIL_DESCRIPTION = 0.8

# Similarite des entreprises et des lieux.
SEUIL_IDENTIQUE = 0.9


def _tokens(value):
    """Mots significatifs d'un texte."""
    return set(normalize(value).split())


def _jaccard(first, second):
    """Proportion de mots communs entre deux textes."""
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def text_similarity(first, second):
    """Similarite entre deux textes, entre 0 et 1.

    Deux mesures sont croisees : la ressemblance de la suite de
    caracteres et la proportion de mots communs. Une annonce reformulee
    garde ainsi un score eleve, alors que deux intitules sans rapport
    restent a zero.
    """
    left = normalize(first)
    right = normalize(second)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    ratio = difflib.SequenceMatcher(None, left, right).ratio()
    tokens = _jaccard(_tokens(left), _tokens(right))
    return round((ratio * 0.5) + (tokens * 0.5), 4)


def compare(offer, extracted, source_url=''):
    """Compare une offre deja connue et une annonce collectee.

    Renvoie le couple (score, motifs). Le score va de 0 a 1 : plus il
    est haut, plus les deux annonces se ressemblent.
    """
    extracted = extracted or {}
    reasons = []
    score = 0.0

    if source_url:
        known_links = {offer.application_url or ''}
        if offer.source_id and offer.source:
            known_links.add(offer.source.url or '')
        if source_url in known_links:
            score += 0.6
            reasons.append('Meme lien de source.')

    title_score = text_similarity(offer.title, extracted.get('title', ''))
    if title_score >= SEUIL_TITRE_FORT:
        score += 0.35
        reasons.append('Intitule tres proche (%d%%).' % round(title_score * 100))
    elif title_score >= SEUIL_TITRE_FAIBLE:
        score += 0.15
        reasons.append('Intitule partiellement proche (%d%%).' % round(title_score * 100))

    if text_similarity(offer.company_name, extracted.get('company_name', '')) >= SEUIL_IDENTIQUE:
        score += 0.2
        reasons.append('Meme entreprise.')

    if offer.location and text_similarity(
        offer.location, extracted.get('location', '')
    ) >= SEUIL_IDENTIQUE:
        score += 0.15
        reasons.append('Meme lieu.')

    deadline = extracted.get('deadline') or ''
    if offer.deadline and deadline and offer.deadline.isoformat() == deadline:
        score += 0.1
        reasons.append('Meme date limite de candidature.')

    description_score = text_similarity(
        offer.description, extracted.get('description', '')
    )
    if description_score >= SEUIL_DESCRIPTION:
        score += 0.25
        reasons.append('Description tres proche (%d%%).' % round(description_score * 100))

    return round(min(score, 1.0), 4), reasons


def find_duplicates(extracted, source_url='', offers=None, threshold=SEUIL_DOUBLON):
    """Cherche les offres deja connues qui ressemblent a l annonce.

    Renvoie la liste des couples (offre, score, motifs), de la plus
    proche a la moins proche. Seuil en dessous, rien n est signale :
    un signalement trop nombreux ne serait lu par personne.
    """
    from ..models import Offer

    if offers is None:
        offers = Offer.objects.select_related('source').all()

    matches = []
    for offer in offers:
        score, reasons = compare(offer, extracted, source_url)
        if score >= threshold and reasons:
            matches.append((offer, score, reasons))

    matches.sort(key=lambda item: (-item[1], item[0].pk))
    return matches


def already_collected(content_hash, exclude_pk=None):
    """Indique si cette annonce a deja ete collectee.

    Renvoie l annonce precedente ou None. C'est la maniere la plus
    simple d' eviter de collecter deux fois la meme annonce : son
    empreinte suffit.
    """
    from ..models import CollectedAnnouncement

    if not content_hash:
        return None

    queryset = CollectedAnnouncement.objects.filter(content_hash=content_hash)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.order_by('collected_at').first()


def summarize(matches):
    """Resume lisible d'une liste de rapprochements."""
    if not matches:
        return 'Aucun doublon potentiel.'

    lines = []
    for offer, score, reasons in matches[:3]:
        lines.append(
            '%s (%s) - %d%% : %s'
            % (
                offer.title,
                offer.company_name or 'entreprise non precisee',
                round(score * 100),
                ' '.join(reasons),
            )
        )
    if len(matches) > 3:
        lines.append('... et %d autre(s).' % (len(matches) - 3))
    return ' '.join(lines)
