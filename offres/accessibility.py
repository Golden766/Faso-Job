"""Recette automatisée de l'accessibilité (lot 9).

Ce module verifie, de façon reproductible, les points qui ne dependent pas
du navigateur :

- le contraste des paires de couleurs reellement utilisees ;
- la presence de focus clavier visible ;
- l'association des etiquettes aux champs de formulaire ;
- l'absence de ressource externe ;
- la presence des attributs d'accessibilite attendus.

Il ne remplace pas la verification visuelle dans un vrai navigateur : il
detecte les regressions objectives.
"""

import re

# Jetons de couleur du site public.
COLOR_TOKENS = {
    'fj-primary': '#176391',
    'fj-primary-strong': '#0f4c73',
    'fj-primary-soft': '#6cabdd',
    'fj-primary-pale': '#eaf4fb',
    'fj-secondary': '#16845f',
    'fj-secondary-strong': '#0f6b4c',
    'fj-secondary-pale': '#e6f7f0',
    'fj-whatsapp': '#25d366',
    'fj-whatsapp-strong': '#1eaa51',
    'fj-ink': '#0f172a',
    'fj-text': '#334155',
    'fj-muted': '#64748b',
    'fj-surface': '#ffffff',
    'fj-canvas': '#f8fafc',
    'fj-subtle': '#f1f5f9',
    'fj-border': '#e2e8f0',
    'fj-border-strong': '#cbd5e1',
    'fj-success-text': '#0f6b4c',
    'fj-success-bg': '#e8f5e9',
    'fj-info-text': '#2a6496',
    'fj-info-bg': '#f0f7fd',
    'fj-warning-text': '#b45309',
    'fj-warning-bg': '#fef3c7',
    'fj-danger-text': '#b91c1c',
    'fj-danger-bg': '#fee2e2',
    'fj-neutral-text': '#475569',
    'fj-neutral-bg': '#f1f5f9',
}

# Paires texte sur fond, avec le ratio minimal attendu (WCAG AA).
TEXT_PAIRS = [
    ('fj-ink', 'fj-surface', 4.5),
    ('fj-text', 'fj-surface', 4.5),
    ('fj-text', 'fj-canvas', 4.5),
    ('fj-text', 'fj-subtle', 4.5),
    ('fj-muted', 'fj-surface', 4.5),
    ('fj-muted', 'fj-canvas', 4.5),
    ('fj-primary', 'fj-surface', 4.5),
    ('fj-primary', 'fj-canvas', 4.5),
    ('fj-primary-strong', 'fj-surface', 4.5),
    ('fj-primary-strong', 'fj-primary-pale', 4.5),
    ('fj-primary', 'fj-primary-pale', 4.5),
    ('fj-secondary', 'fj-surface', 4.5),
    ('fj-secondary-strong', 'fj-surface', 4.5),
    ('fj-secondary-strong', 'fj-secondary-pale', 4.5),
    ('fj-success-text', 'fj-success-bg', 4.5),
    ('fj-info-text', 'fj-info-bg', 4.5),
    ('fj-warning-text', 'fj-warning-bg', 4.5),
    ('fj-danger-text', 'fj-danger-bg', 4.5),
    ('fj-neutral-text', 'fj-neutral-bg', 4.5),
    ('fj-ink', 'fj-subtle', 4.5),
    ('fj-text', 'fj-primary-pale', 4.5),
    ('fj-text', 'fj-success-bg', 4.5),
    ('fj-text', 'fj-warning-bg', 4.5),
    ('fj-text', 'fj-danger-bg', 4.5),
    ('fj-ink', 'fj-whatsapp', 4.5),
    ('fj-ink', 'fj-whatsapp-strong', 4.5),
]

# Paires de texte blanc sur fond de bouton.
WHITE_ON = [
    ('#ffffff', 'fj-primary', 4.5),
    ('#ffffff', 'fj-primary-strong', 4.5),
    ('#ffffff', 'fj-danger-text', 4.5),
    ('#ffffff', 'fj-ink', 4.5),
]

# Bordures d'elements interactifs : 3:1 (WCAG 1.4.11).
BORDER_PAIRS = [
    ('fj-muted', 'fj-surface', 3.0),
    ('fj-primary', 'fj-surface', 3.0),
    ('fj-muted', 'fj-canvas', 3.0),
]


def _hex_to_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _relative_luminance(rgb):
    channels = []
    for channel in rgb:
        ratio = channel / 255
        if ratio <= 0.03928:
            channels.append(ratio / 12.92)
        else:
            channels.append(((ratio + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground, background):
    """Rapport de contraste WCAG entre deux couleurs hexadecimales."""
    lum_a = _relative_luminance(_hex_to_rgb(foreground))
    lum_b = _relative_luminance(_hex_to_rgb(background))
    return (max(lum_a, lum_b) + 0.05) / (min(lum_a, lum_b) + 0.05)


def check_contrasts():
    """Verifie tous les contrastes attendus.

    Renvoie la liste des manquements sous forme de textes.
    """
    failures = []

    for foreground, background, minimum in TEXT_PAIRS:
        ratio = contrast_ratio(COLOR_TOKENS[foreground], COLOR_TOKENS[background])
        if ratio < minimum:
            failures.append(
                'Texte %s sur %s : %.2f:1 (minimum %.1f)'
                % (foreground, background, ratio, minimum)
            )

    for foreground, background, minimum in WHITE_ON:
        ratio = contrast_ratio(foreground, COLOR_TOKENS[background])
        if ratio < minimum:
            failures.append(
                'Texte %s sur %s : %.2f:1 (minimum %.1f)'
                % (foreground, background, ratio, minimum)
            )

    for foreground, background, minimum in BORDER_PAIRS:
        ratio = contrast_ratio(COLOR_TOKENS[foreground], COLOR_TOKENS[background])
        if ratio < minimum:
            failures.append(
                'Bordure %s sur %s : %.2f:1 (minimum %.1f)'
                % (foreground, background, ratio, minimum)
            )

    return failures


def check_no_external_assets(paths):
    """Detecte les ressources chargees depuis un autre domaine.

    Renvoie la liste des occurrences trouvees.
    """
    found = []
    pattern = re.compile(r'(?:src|href)\s*=\s*["\'](https?:)?//[^"\']+', re.IGNORECASE)

    for path in paths:
        with open(path, encoding='utf-8') as handle:
            content = handle.read()
        for match in pattern.finditer(content):
            found.append('%s : %s' % (path, match.group(0)[:120]))

    return found


def check_focus_visible(css_paths):
    """Verifie qu un style de focus visible est declare dans la feuille.

    La presence dans une seule feuille suffit : les styles sont globaux.
    Renvoie la liste des manquements.
    """
    failures = []
    found = False
    for css_path in css_paths:
        with open(css_path, encoding="utf-8") as handle:
            content = handle.read()
        if ":focus-visible" in content or ":focus" in content:
            found = True
    if not found:
        failures.append(
            "Aucun style de focus declare dans les feuilles de style"
        )
    return failures


def _fields_without_label(html):
    """Champs de formulaire visibles, avec leurs attributs.

    Renvoie une liste de dictionnaires decrivant chaque champ.
    """
    fields = []
    pattern = re.compile(
        r'<(input|select|textarea)\b([^>]*)>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        tag = match.group(1).lower()
        attributes = match.group(2)
        lowered = attributes.lower()

        if 'type="hidden"' in lowered:
            continue
        fields.append({
            'tag': tag,
            'attributes': attributes,
            'start': match.start(),
            'end': match.end(),
        })
    return fields


def _is_inside_label(html, position):
    """Indique si la position donnee se trouve a l interieur d un label.

    Un label qui englobe son champ est une association valide : c est
    la technique employee par le site pour les filtres du catalogue.
    """
    open_labels = 0
    for match in re.finditer(r'<(/?)label\b[^>]*>', html, re.IGNORECASE):
        if match.start() >= position:
            break
        if match.group(1) == '/':
            open_labels = max(0, open_labels - 1)
        else:
            open_labels += 1
    return open_labels > 0


def collect_label_problems(html):
    """Detecte les champs de formulaire sans etiquette associee.

    Un champ est correctement etiquete si :

    - il porte un aria-label ou un aria-labelledby ;
    - il est englobe par un label ;
    - il possede un id reference par un label for ;
    - il est cache.

    Renvoie la liste des problemes trouves.
    """
    problems = []

    labelled_ids = set()
    for match in re.finditer(
        r'<label\b[^>]*for="([^"]+)"[^>]*>', html, re.IGNORECASE
    ):
        labelled_ids.add(match.group(1))

    for field in _fields_without_label(html):
        attributes = field['attributes']
        lowered = attributes.lower()

        if 'aria-label' in lowered or 'aria-labelledby' in lowered:
            continue

        identifier = re.search(r'id="([^"]+)"', attributes)
        if identifier and identifier.group(1) in labelled_ids:
            continue

        if _is_inside_label(html, field['start']):
            continue

        problems.append(
            '<%s> sans etiquette : %s'
            % (field['tag'], ' '.join(attributes.split())[:100])
        )

    return problems


def collect_unlabelled_labels(html):
    """Detecte les etiquettes <label> qui ne sont associees a aucun champ.

    Une etiquette qui englobe son champ est valide : elle est passeee
    dans ce cas. Ne sont signalees que les etiquettes orphelines, dont le
    attribut for pointe vers un identifiant inexistant.

    Renvoie la liste des problemes trouves.
    """
    problems = []

    for match in re.finditer(
        r'<label\b([^>]*)>(.*?)</label>', html, re.IGNORECASE | re.DOTALL
    ):
        attributes = match.group(1)
        inner = match.group(2)

        if 'aria-label' in attributes.lower():
            continue
        if 'aria-labelledby' in attributes.lower():
            continue

        target = re.search(r'for="([^"]+)"', attributes)
        if target:
            identifier = target.group(1)
            # Django genere les identifiants au rendu : ils ne sont pas
            # dans le source du template, on ne peut pas les verifier ici.
            if "{{" in identifier:
                continue
            if ('id="%s"' % identifier) not in html:
                problems.append(
                    'label for="%s" ne correspond a aucun id' % target.group(1)
                )
            continue

        # Sans attribut for : l etiquette doit englober un champ.
        if re.search(
            r'<(input|select|textarea)\b', inner, re.IGNORECASE
        ):
            continue

        problems.append(
            'label sans champ associe : %s' % ' '.join(inner.split())[:80]
        )

    return problems
