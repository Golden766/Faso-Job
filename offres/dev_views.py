from django.conf import settings
from django.http import Http404
from django.shortcuts import render


def styleguide_view(request):
    """Page interne de référence visuelle, accessible uniquement en DEBUG."""
    if not settings.DEBUG:
        raise Http404
    return render(request, "refonte/styleguide.html")
