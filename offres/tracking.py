"""Journal des consultations et des clics sortants.

La plateforme compte les consultations d'une fiche d'offre et les clics
vers le canal de candidature. Ces compteurs sont **internes** : ils ne sont
jamais affichés au public et aucune donnée personnelle (adresse IP,
navigateur, identifiant) n'est conservée.

Deux principles tenant :

- une seule consultation est comptée par session et par offre ;
- aucun compteur n'est incrémenté pour le personnel de l'administration.
"""

from django.db.models import F

from .models import Offer, OfferView


def _session_key(request):
    """Clé de session stable, sans donnée personnelle."""
    if not hasattr(request, 'session'):
        return None
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def register_offer_view(request, offer):
    """Enregistre une consultation si elle n'a pas déjà été comptée.

    Renvoie True si un compteur a été incrémenté.
    """
    from .models import PlatformSettings

    settings = PlatformSettings.load()
    if not settings.view_counter_enabled:
        return False

    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.is_staff:
        return False

    session_key = _session_key(request)
    if not session_key:
        return False

    _view, created = OfferView.objects.get_or_create(
        offer=offer,
        session_key=session_key,
    )
    if not created:
        # Cette consultation a deja ete comptee pour cette session.
        return False

    Offer.objects.filter(pk=offer.pk).update(view_count=F('view_count') + 1)
    return True


def register_outbound_click(request, offer, channel):
    """Enregistre un clic vers le canal de candidature d'une offre."""
    if not channel:
        return False

    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.is_staff:
        return False

    session_key = _session_key(request)
    if not session_key:
        return False

    from .models import OfferClick

    OfferClick.objects.create(offer=offer, channel=channel, session_key=session_key)
    return True
