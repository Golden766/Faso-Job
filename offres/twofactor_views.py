"""Vues de double authentification pour l'administration.

Trois ecrans :

- `/admin/securite/` : etat de la protection du compte, activation,
  desactivation, codes de secours ;
- `/admin/securite/verification/` : saisie du code a la connexion ;
- `/admin/securite/recuperation/` : saisie d'un code de secours.

Regle importante : la verification est demandee a chaque nouvelle session
admin. Sans elle, un mot de passe vole suffirait a publier des annonces.
"""

import logging

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import twofactor
from .models import TwoFactorDevice, TwoFactorRecoveryCode

logger = logging.getLogger(__name__)

RECOVERY_CODE_COUNT = 8


@staff_member_required
def two_factor_settings_view(request):
    """Ecran de reglage de la double authentification."""
    user = request.user
    device = TwoFactorDevice.objects.filter(user=user).first()
    recovery_codes = request.session.pop('two_factor_new_codes', [])
    pending_secret = request.session.get('two_factor_pending_secret')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'start':
            secret = twofactor.generate_secret()
            request.session['two_factor_pending_secret'] = secret
            pending_secret = secret
            device = TwoFactorDevice.objects.filter(user=user).first()
            if device is None:
                device = TwoFactorDevice(
                    user=user,
                    secret=twofactor.encrypt_secret(secret),
                )
            device.secret = twofactor.encrypt_secret(secret)
            device.is_active = False
            device.confirmed_at = None
            device.last_used_at = None
            device.save()

        elif action == 'confirm':
            secret = request.session.get('two_factor_pending_secret')
            code = request.POST.get('code', '')
            if not secret:
                messages.error(request, "La configuration a expiré. Recommencez l'activation.")
            elif not twofactor.verify_code(secret, code):
                messages.error(request, "Code incorrect. Vérifiez l’heure de votre téléphone.")
            else:
                device = TwoFactorDevice.objects.filter(user=user).first()
                if device is None:
                    device = TwoFactorDevice(user=user)
                device.secret = twofactor.encrypt_secret(secret)
                device.is_active = True
                device.confirmed_at = timezone.now()
                device.save()
                recovery_codes = _replace_recovery_codes(device)
                request.session['two_factor_new_codes'] = recovery_codes
                request.session.pop('two_factor_pending_secret', None)
                request.session['two_factor_verified_user_id'] = user.pk
                messages.success(
                    request,
                    'Double authentification activée. '
                    'Conservez les codes de secours : ils ne sont affichés qu’une fois.',
                )
                return redirect(reverse('two_factor_settings'))

        elif action == 'deactivate':
            device = TwoFactorDevice.objects.filter(user=user).first()
            if device is not None:
                device.is_active = False
                device.confirmed_at = None
                device.save()
                request.session.pop('two_factor_verified_user_id', None)
                messages.success(request, 'Double authentification désactivée.')

        elif action == 'new_recovery_codes':
            device = TwoFactorDevice.objects.filter(user=user).first()
            if device is not None:
                recovery_codes = _replace_recovery_codes(device)
                messages.success(
                    request,
                    'Nouveaux codes de secours générés. '
                    'Les anciens ne fonctionnent plus.',
                )
                return redirect(reverse('two_factor_settings'))

    # Le contexte de l'administration (menu lateral, fil d'Ariane, rights)
    # est construit a partir de celui du site d'administration : sans lui,
    # la page n'affiche ni la navigation ni le fil d'Ariane.
    context = admin.site.each_context(request)
    context.update({
        'title': 'Sécurité du compte',
        'device': device,
        'is_protected': bool(device and device.is_confirmed),
        'pending_secret': pending_secret,
        'provisioning_uri': (
            twofactor.provisioning_uri(pending_secret, user.get_username())
            if pending_secret
            else ''
        ),
        'qr_code_svg': (
            twofactor.qr_code_svg(
                twofactor.provisioning_uri(pending_secret, user.get_username())
            )
            if pending_secret
            else ''
        ),
        'recovery_codes': recovery_codes,
        'recovery_code_count': (
            TwoFactorRecoveryCode.objects.filter(
                device=device, is_used=False
            ).count() if device else 0
        ),
    })
    return render(request, 'admin/two_factor_settings.html', context)


def _replace_recovery_codes(device):
    """Regenere les codes de secours et renvoie la liste en clair."""
    TwoFactorRecoveryCode.objects.filter(device=device).delete()
    codes = twofactor.generate_recovery_codes(RECOVERY_CODE_COUNT)
    for code in codes:
        TwoFactorRecoveryCode.objects.create(
            device=device,
            code_hash=twofactor.hash_code(code),
        )
    return codes


@login_required
def two_factor_verify_view(request):
    """Ecran de verification du code TOTP lors de la connexion."""
    user = request.user
    device = TwoFactorDevice.objects.filter(user=user, is_active=True).first()

    if device is None:
        # Rien a verifier : on laisse passer.
        return redirect(reverse('admin:index'))

    if request.method == 'POST':
        code = request.POST.get('code', '')
        secret = twofactor.decrypt_secret(device.secret)

        if twofactor.verify_code(secret, code):
            request.session['two_factor_verified_user_id'] = user.pk
            device.last_used_at = timezone.now()
            device.save(update_fields=['last_used_at'])
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url or reverse('admin:index'))

        if code:
            recovery = _consume_recovery_code(device, code)
            if recovery:
                request.session['two_factor_verified_user_id'] = user.pk
                device.last_used_at = timezone.now()
                device.save(update_fields=['last_used_at'])
                messages.success(request, "Code de secours accepté.")
                next_url = request.POST.get('next') or request.GET.get('next')
                return redirect(next_url or reverse('admin:index'))

        messages.error(request, "Code incorrect ou expiré.")

    context = {
        'title': 'Verification du compte',
        'next': request.GET.get('next', ''),
    }
    return render(request, 'admin/two_factor_verify.html', context)


def _consume_recovery_code(device, code):
    """Verifie et consomme un code de secours. Renvoie True si valide."""
    from . import twofactor as module

    code_hash = module.hash_code(code)
    for recovery_code in device.recovery_codes.filter(is_used=False):
        if recovery_code.code_hash == code_hash:
            recovery_code.is_used = True
            recovery_code.used_at = timezone.now()
            recovery_code.save(update_fields=['is_used', 'used_at'])
            return True
    return False


@staff_member_required
@require_POST
def two_factor_regenerate_recovery_codes(request):
    """Regenere les codes de secours depuis l'ecran de reglages."""
    device = TwoFactorDevice.objects.filter(user=request.user).first()
    if device is None:
        raise Http404("Aucune double authentification active sur ce compte.")
    _replace_recovery_codes(device)
    messages.success(request, 'Nouveaux codes de secours générés.')
    return redirect(reverse('two_factor_settings'))
