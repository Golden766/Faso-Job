"""Middleware de double authentification pour l administration.

Tant qu un membre de l equipe n a pas saisi son code TOTP dans la session
courante, l'acces a l'administration est dirige vers l'ecran de
verification. Un mot de passe vole ne suffit donc plus a publier une
annonce ou a modifier la liste noire.

Le middleware laisse passer :

- les ecran de connexion et de deconnexion ;
- l'ecran de verification lui-meme ;
- l'ecran d'activation (pour pouvoir activer sa protection) ;
- les comptes qui n'ont pas active la double authentification.
"""

from django.shortcuts import redirect
from django.urls import reverse

# Chemins exempts de verification. Le middleware s execute avant la
# resolution des URL : on compare donc les chemins, pas les noms de vue.
EXEMPT_PATHS = (
    '/admin/securite/',
    '/admin/securite/verification/',
    '/admin/securite/codes-de-secours/',
    '/admin/login/',
    '/admin/logout/',
)


class TwoFactorRequiredMiddleware:
    """Exige un code TOTP valide pour chaque session d'administration."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._must_verify(request):
            return redirect(
                f'{reverse("two_factor_verify")}?next={request.get_full_path()}'
            )
        return self.get_response(request)

    def _must_verify(self, request):
        from .models import TwoFactorDevice

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or not user.is_staff:
            return False

        # Seule l administration est protegee : le site public reste
        # accessible, la verification n concerne que le personnel.
        if not request.path.startswith('/admin/'):
            return False

        # Les ecrans de connexion, de verification et d'activation restent
        # accessibles : sans cela, impossible de s'authentifier au premier coup.
        if request.path in EXEMPT_PATHS:
            return False

        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return False

        device = TwoFactorDevice.objects.filter(user=user, is_active=True).first()
        if device is None:
            # La protection n'est pas activee pour ce compte.
            return False

        if request.session.get('two_factor_verified_user_id') == user.pk:
            return False

        return True
