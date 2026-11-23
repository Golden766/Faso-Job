"""Veille automatisee de Faso Job.

Ce paquet regroupe les outils de la veille : ce qui va chercher les
annonces, ce qui les analyse, ce qui repere les doublons et ce qui
prepare les brouillons.

Deux regles'y applique du bout en bout :

1. **Aucune annonce collectee n est publiee automatiquement.** La veille
   produit un brouillon, l'equipe decide.
2. **Aucune information n est inventee.** Ce que le service d
   intelligence artificielle propose est verifie avant d etre enregistre ;
   ce qui n est pas clair reste vide.
"""

from .collectors import (
    CollectedItem,
    CollectionResult,
    collect_feed,
    collect_source,
    collect_text,
    collect_url,
    collect_web_list,
    content_hash,
)
from .dedup import (
    SEUIL_DOUBLON,
    already_collected,
    compare,
    find_duplicates,
    text_similarity,
)
from .ia import (
    AiRequestError,
    ExtractionResult,
    classify_announcement,
    extract_announcement,
    get_adapter,
)

__all__ = [
    'AiRequestError',
    'CollectedItem',
    'CollectionResult',
    'ExtractionResult',
    'SEUIL_DOUBLON',
    'already_collected',
    'classify_announcement',
    'collect_feed',
    'collect_source',
    'collect_text',
    'collect_url',
    'collect_web_list',
    'compare',
    'content_hash',
    'extract_announcement',
    'find_duplicates',
    'get_adapter',
    'text_similarity',
]
