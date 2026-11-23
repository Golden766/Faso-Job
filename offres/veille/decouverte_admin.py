"""Le lien entre l assistant de decouverte et l administration.

Ce module fait deux choses :

1. **lancer la decouverte** et enregistrer ce que l assistant a
   constate ;
2. **appliquer la decision de l equipe** : autoriser une proposition
   cree la source, refuser une proposition la trace.

Une autorisation cree une source avec sa note d autorisation. La source
rejoint alors la collecte automatique, avec les memes regles que les
autres : delai, robots.txt, et rien de publie automatiquement.
"""

import logging

from django.db import transaction
from django.utils import timezone

from ..models import Source, SourceProposal
from . import decouverte, decouverte_ia

logger = logging.getLogger(__name__)

# Nombre maximal d adresses verifiees lors d un lancement. Chaque
# verification respecte le delai de dix secondes : la limite evite
# qu un lancement prenne un quart d'heure.
MAXIMUM_PAR_LANCEMENT = 8


def _source_existante(url):
    """Source deja connue pour cette adresse."""
    for source in Source.objects.filter(url=url):
        return source
    return None


def enregistrer_rapport(rapport, candidat=None, demandeur=None):
    """Enregistre une proposition a partir d un rapport de verification."""
    if _source_existante(rapport.url):
        # La source existe deja : la proposition n apporte rien.
        return SourceProposal.objects.create(
            url=rapport.url,
            name=(candidat.name if candidat else '')[:200],
            page_title=rapport.page_title[:250],
            kind=rapport.kind[:80],
            origin=(candidat.origin if candidat else '')[:20],
            why=(candidat.why if candidat else '')[:500],
            verdict=rapport.verdict,
            score=rapport.score,
            selector=rapport.selector[:300],
            blocks_count=rapport.blocks_count,
            sample=rapport.sample[:2000],
            reasons='\n'.join(rapport.reasons)[:2000],
            conditions_quote=rapport.conditions_quote[:1000],
            conditions_found=list(rapport.conditions_found)[:10],
            status=SourceProposal.STATUS_OBSOLETE,
        )

    return SourceProposal.objects.create(
        url=rapport.url,
        name=(candidat.name if candidat else '')[:200],
        page_title=rapport.page_title[:250],
        kind=rapport.kind[:80],
        origin=(candidat.origin if candidat else '')[:20],
        why=(candidat.why if candidat else '')[:500],
        verdict=rapport.verdict,
        score=rapport.score,
        selector=rapport.selector[:300],
        blocks_count=rapport.blocks_count,
        sample=rapport.sample[:2000],
        reasons='\n'.join(rapport.reasons)[:2000],
        conditions_quote=rapport.conditions_quote[:1000],
        conditions_found=list(rapport.conditions_found)[:10],
        status=SourceProposal.STATUS_PENDING,
    )


def lancer_decouverte(
    demande,
    maximum=MAXIMUM_PAR_LANCEMENT,
    adapter=None,
    avec_recherche=True,
):
    """Cherche, verifie et enregistre des propositions de sources.

    Renvoie le couple (propositions, messages). Les messages
    expliquent a l equipe ce qui s est passe, y compris quand rien
    n a ete trouve.
    """
    messages = []

    candidats = decouverte_ia.proposer(
        demande, adapter=adapter, avec_recherche=avec_recherche
    )

    if not candidats:
        messages.append(
            "Aucune adresse proposee. Verifiez que le service d'intelligence "
            "artificielle est configure, ou configurez un moteur de "
            "recherche (BRAVE_SEARCH_API_KEY ou SEARXNG_URL)."
        )
        return [], messages

    maximum = max(1, min(int(maximum), len(candidats)))
    if len(candidats) > maximum:
        messages.append(
            '%d adresses proposees sur %d : seules les %d premieres ont ete '
            'verifiees (le delai de dix secondes s applique).'
            % (len(candidats), len(candidats), maximum)
        )

    propositions = []
    for candidat in candidats[:maximum]:
        try:
            rapport = decouverte.verify_candidate(candidat)
        except Exception as erreur:
            logger.exception('Verification impossible pour %s', candidat.url)
            messages.append('%s : verification impossible (%s).' % (candidat.url, erreur))
            continue
        propositions.append(enregistrer_rapport(rapport, candidat))

    ecartees = [p for p in propositions if p.verdict == SourceProposal.VERDICT_ECARTEE]
    if ecartees:
        messages.append(
            '%d adresse(s) ecartee(s) : le site interdit la reprise, la page '
            'est protegee, ou elle ne contient pas d offres.'
            % len(ecartees)
        )

    return propositions, messages


def accepter(proposition, user, note='', verifier=True):
    """Autorise une proposition : la source entre dans la veille.

    La page est reverifiee avant d etre ajoutee : une proposition peut
    avoir ete faite il y a plusieurs jours, et le site a pu changer.

    Renvoie (True, '') ou (False, motif du refus).
    """
    if proposition.status != SourceProposal.STATUS_PENDING:
        return False, 'Cette proposition a deja ete traitee.'

    if proposition.verdict == SourceProposal.VERDICT_ECARTEE:
        return False, (
            'Cette adresse a ete ecartee : le site interdit la reprise, ou la '
            'page ne peut pas etre lue.'
        )

    existante = _source_existante(proposition.url)
    if existante is not None:
        proposition.status = SourceProposal.STATUS_OBSOLETE
        proposition.source = existante
        proposition.reviewed_by = user
        proposition.reviewed_at = timezone.now()
        proposition.save(
            update_fields=['status', 'source', 'reviewed_by', 'reviewed_at']
        )
        return False, 'Cette source est deja connue : elle a ete reliee.'

    if verifier:
        # La page est reverifiee : une proposition peut avoir ete faite
        # il y a plusieurs jours, et le site a pu changer.
        rapport = decouverte.verify_candidate(
            decouverte.SourceCandidate(url=proposition.url),
            deep=False,
        )
        if not rapport.selector:
            motif = rapport.error or (
                rapport.reasons[0] if rapport.reasons else 'raison inconnue'
            )
            return False, (
                'La page n est plus lisible telle quelle (%s). La source n est '
                'pas ajoutee : redemandez une decouverte.' % motif
            )

    with transaction.atomic():
        source = Source.objects.create(
            name=(proposition.name or proposition.url)[:200],
            url=proposition.url,
            description=proposition.reasons[:1000],
            collection_method=(
                Source.COLLECTION_METHOD_WEB
                if proposition.selector
                else Source.COLLECTION_METHOD_MANUAL_URL
            ),
            is_watched=bool(proposition.selector),
            watch_config=(
                {'selector': proposition.selector, 'limit': 20}
                if proposition.selector
                else {}
            ),
            authorization_note=(
                (note or '').strip() or proposition.default_authorization_note()
            ),
            is_verified=False,
        )

        proposition.status = SourceProposal.STATUS_ACCEPTED
        proposition.source = source
        proposition.reviewed_by = user
        proposition.reviewed_at = timezone.now()
        if (note or '').strip():
            proposition.conditions_quote = (
                (note or '').strip()[:1000]
            )
        proposition.save(
            update_fields=[
                'status',
                'source',
                'reviewed_by',
                'reviewed_at',
                'conditions_quote',
            ]
        )

    return True, ''


def refuser(proposition, user):
    """Refuse une proposition."""
    if proposition.status != SourceProposal.STATUS_PENDING:
        return False
    proposition.status = SourceProposal.STATUS_REFUSED
    proposition.reviewed_by = user
    proposition.reviewed_at = timezone.now()
    proposition.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    return True
