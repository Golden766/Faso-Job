"""Aides d'interface pour l'administration éditoriale.

L'administration Django construit son fil d'Ariane a partir de l'index
d'application (`/admin/offres/`), qui n'existe pas chez nous et ne
correspond pas au menu lateral. Ces aides reconstruisent un fil unique et
coherent pour toutes les pages de l'administration.
"""

from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


# (prefixe d'URL, libelle, nom d'URL de la section, arguments)
SECTIONS = (
    (
        '/admin/offres-expirees/',
        'Offres expirées',
        'admin-expired-offers',
        (),
    ),
    (
        '/admin/offres/offerreport/',
        'Signalements',
        'admin:offres_offerreport_changelist',
        (),
    ),
    (
        '/admin/offres/offersubmission/',
        'Soumissions',
        'admin:offres_offersubmission_changelist',
        (),
    ),
    (
        '/admin/offres/blacklistedcontact/',
        'Liste noire',
        'admin:offres_blacklistedcontact_changelist',
        (),
    ),
    (
        '/admin/offres/outboundmessage/',
        'Messages envoyés',
        'admin:offres_outboundmessage_changelist',
        (),
    ),
    (
        '/admin/offres/notificationrecipient/',
        'Notifications',
        'admin:offres_notificationrecipient_changelist',
        (),
    ),
    (
        '/admin/offres/twofactordevice/',
        'Appareils 2FA',
        'admin:offres_twofactordevice_changelist',
        (),
    ),
    (
        '/admin/offres/platformsettings/',
        'Paramètres',
        'admin:offres_platformsettings_change',
        (1,),
    ),
    (
        '/admin/offres/source/',
        'Sources',
        'admin:offres_source_changelist',
        (),
    ),
    (
        '/admin/offres/category/',
        'Catégories',
        'admin:offres_category_changelist',
        (),
    ),
    (
        '/admin/offres/offer/',
        'Offres',
        'admin:offres_offer_changelist',
        (),
    ),
    (
        '/admin/rapport-activite/',
        'Rapport d’activité',
        'admin-activity-report',
        (),
    ),
    (
        '/admin/veille/',
        'Centre de veille',
        'admin-veille',
        (),
    ),
    (
        '/admin/sauvegardes/',
        'Sauvegardes',
        'admin-backups',
        (),
    ),
    (
        '/admin/securite/',
        'Sécurité du compte',
        'two_factor_settings',
        (),
    ),
    (
        '/admin/auth/user/',
        'Utilisateurs',
        'admin:auth_user_changelist',
        (),
    ),
    (
        '/admin/auth/group/',
        'Rôles',
        'admin:auth_group_changelist',
        (),
    ),
)

# Le tableau de bord n'a pas de prefixe : son URL est exacte.
DASHBOARD = ('Tableau de bord', 'admin:index', ())


def _section_url(url_name, args):
    try:
        return reverse(url_name, args=args)
    except Exception:
        return ''


def _match_section(path):
    """Retourne (libelle, url) de la section correspondant a l'URL."""
    if path.rstrip('/') in ('', '/admin'):
        return (DASHBOARD[0], _section_url(DASHBOARD[1], DASHBOARD[2]))
    for prefix, label, url_name, args in SECTIONS:
        if path.startswith(prefix):
            return (label, _section_url(url_name, args))
    return None


@register.simple_tag(takes_context=True)
def admin_section(context, section):
    """Marque le lien du menu lateral correspondant a la page courante."""
    request = context.get('request')
    path = request.path if request else ''
    matched = _match_section(path)
    if not matched:
        return ''
    label, _ = matched
    return ' sidebar-link-active' if label == section else ''


@register.simple_tag(takes_context=True)
def admin_breadcrumbs(context):
    """Construit le fil d'Ariane de l'administration.

    Le fil est toujours le meme : Administration, puis la section, puis
    l'objet en cours de modification. Chaque cran pointe vers la page que le
    menu lateral propose.
    """
    request = context.get('request')
    path = request.path if request else ''
    opts = context.get('opts')
    original = context.get('original')

    matched = _match_section(path)
    crumbs = []

    if matched:
        label, url = matched
        if original is not None and opts is not None:
            # Page de modification d'un objet : la section reste un lien.
            crumbs.append((url, label))
            try:
                object_url = reverse(
                    'admin:%s_%s_change' % (opts.app_label, opts.model_name),
                    args=[original.pk],
                )
            except Exception:
                object_url = ''
            crumbs.append((object_url, str(original)))
        else:
            # La section est la page courante.
            crumbs.append(('', label))
    else:
        crumbs.append(('', 'Administration'))

    items = []
    for index, (url, label) in enumerate(crumbs):
        is_last = index == len(crumbs) - 1
        label = escape(label)
        if is_last:
            items.append('<li aria-current="page">%s</li>' % label)
        elif url:
            items.append('<li><a href="%s">%s</a></li>' % (url, label))
        else:
            items.append('<li>%s</li>' % label)

    home = reverse('admin:index')
    return mark_safe(
        (
            '<ol class="breadcrumbs">'
            '<li><a href="%s">Administration</a></li>%s</ol>'
        )
        % (home, ''.join(items))
    )
