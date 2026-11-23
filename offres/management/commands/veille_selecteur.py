"""Trouver les annonces dans une page d'emplois.

Pour que la veille lise une page de liste, il faut lui dire ou sont
les annonces. Cette commande regarde la page et propose les blocs qui
se repetent : ce sont, en general, les annonces.

Utilisation :

    python manage.py veille_selecteur https://emploi.exemple.bf/offres

Elle affiche les selecteurs possibles, du plus courant au moins
courant, avec le nombre d'elements trouves. Pour verifier un
selecteur precis :

    python manage.py veille_selecteur https://emploi.exemple.bf/offres --exemple "article.offre"

La commande ne modifie rien : elle lit la page et affiche.
"""

from django.core.management.base import BaseCommand, CommandError

from offres.veille import collectors, http


class Command(BaseCommand):
    help = "Propose les selecteurs CSS qui designent les annonces d'une page."

    def add_arguments(self, parser):
        parser.add_argument('url', help='Adresse de la page de liste des annonces.')
        parser.add_argument(
            '--minimum',
            type=int,
            default=2,
            help='Nombre minimal d occurrences pour proposer un selecteur.',
        )
        parser.add_argument(
            '--exemple',
            default='',
            help='Affiche le texte du premier element qui correspond a ce selecteur.',
        )

    def handle(self, *args, **options):
        url = options['url']
        fetch = http.fetch(url)

        if not fetch.is_ok:
            raise CommandError(fetch.error or 'Page illisible.')

        selector = options.get('exemple') or ''
        if selector:
            self._show_example(fetch.text, selector)
            return

        proposals = collectors.candidate_selectors(
            fetch.text, minimum=options['minimum']
        )
        if not proposals:
            self.stdout.write(
                self.style.WARNING(
                    'Aucun bloc repete n a ete trouve. La page utilise peut-etre '
                    'une structure particuliere : utilisez --exemple pour tester '
                    'un selecteur.'
                )
            )
            return

        self.stdout.write('Selecteurs possibles sur %s :' % url)
        for candidate, count, sample in proposals[:15]:
            self.stdout.write('  %3d element(s)  %s' % (count, candidate))
            self.stdout.write('      %s' % _first_line(sample))

    def _show_example(self, html, selector):
        """Affiche le texte du premier element qui correspond."""
        soup = collectors.parse_html(html)
        element = soup.select_one(selector)
        if element is None:
            raise CommandError('Aucun element ne correspond a Â« %s Â».' % selector)
        text = element.get_text('\n', strip=True)
        self.stdout.write('Premier element Â« %s Â» :' % selector)
        self.stdout.write(text[:1500])


def _first_line(text):
    """Premiere ligne non vide d'un texte."""
    for line in (text or '').splitlines():
        if line.strip():
            return line.strip()[:110]
    return ''
