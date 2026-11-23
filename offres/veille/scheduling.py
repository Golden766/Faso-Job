"""Instructions d'activation de la collecte automatique.

La veille ne se planifie pas toute seule : comme les sauvegardes, elle
repose sur une tache planifiee installee sur la machine qui heberge le
site. Ce module fournit la commande prete a copier.

Rien n'est declenche ici : le Centre de veille montre les instructions,
l'equipe decide quand les installer.
"""

from pathlib import Path

from django.conf import settings

# Frequence retenue : la veille est lente et les pages d'emplois
# changent peu souvent. Une fois toutes les six heures suffit.
CRON_LINE = '0 */6 * * *'
SCHEDULE_TEXT = 'toutes les six heures'


def _python_command():
    """Chemin de l interpreteur Python du projet."""
    python = Path(settings.BASE_DIR) / '.venv' / 'Scripts' / 'python.exe'
    if not python.exists():
        python = Path(settings.BASE_DIR) / '.venv' / 'bin' / 'python'
    return python


def activation_instructions():
    """Explication et commande a utiliser pour activer la planification.

    La commande est fournie prete a copier : il ne reste qu'a la placer
    dans la tache planifiee de la machine qui heberge le site.
    """
    cron_command = (
        f'cd {settings.BASE_DIR} && '
        f'{_python_command()} manage.py collect_offers --scheduled'
    )

    return {
        'schedule_text': SCHEDULE_TEXT,
        'cron_line': CRON_LINE,
        'cron_command': cron_command,
        'schtasks_command': (
            'schtasks /Create /SC HOURLY /MO 6 /TN "Faso Job Veille" '
            f'/TR "{cron_command}" /F'
        ),
    }
