"""Tests du lot 3 : collecte des annonces.

Aucun test ne sort sur le reseau : les requetes sont simulees. Ce qui
est verifie :

- le delai d'attente entre deux requetes est bien applique ;
- le fichier robots.txt du site est respecte ;
- une panne de reseau ou un refus du site est signale, jamais leve ;
- les quatre methodes de collecte rendent les annonces attendues ;
- une source sans mode automatise n'est pas collectee ;
- deux annonces identiques ont la meme empreinte.
"""

import time
from unittest import mock

from django.test import TestCase

from .models import Source
from .veille import collectors, http


PAGE_LISTE = """
<html>
<head><title>Emplois du Faso</title></head>
<body>
  <article class="offre">
    <h2>Assistant comptable</h2>
    <p>Societe Exemple recherche un assistant comptable.</p>
    <a href="/offre/assistant-comptable">Voir l offre</a>
  </article>
  <article class="offre">
    <h2>Chargé de projets</h2>
    <p>Pilotage de projets au siege d Ouagadougou.</p>
    <a href="https://autre.test/offre/charge-projets">Voir l offre</a>
  </article>
  <div class="pub">Publicite sans rapport</div>
</body>
</html>
"""

PAGE_ANNONCE = """
<html>
<head><title>Offre - Assistant comptable</title></head>
<body>
  <h1>Assistant comptable</h1>
  <p>Nous recrutons un assistant comptable pour notre siege.</p>
  <script>var suivi = 1;</script>
</body>
</html>
"""

FLUX_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Emplois du Faso</title>
    <item>
      <title>Assistant comptable</title>
      <link>https://exemple.test/offre/1</link>
      <description>Nous recrutons un assistant comptable.</description>
      <pubDate>Wed, 02 Jun 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Charge de projets</title>
      <link>https://exemple.test/offre/2</link>
      <description>Pilotage de projets a Ouagadougou.</description>
    </item>
  </channel>
</rss>
"""

FLUX_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Developpeur</title>
    <link href="https://exemple.test/offre/3"/>
    <summary>Developpement d applications web.</summary>
    <published>2026-06-05</published>
  </entry>
</feed>
"""


def fake_response(text='', status_code=200):
    """Reponse simulee de l orienteur de requetes."""
    response = mock.Mock()
    response.status_code = status_code
    response.text = text
    return response


class VeilleTestCase(TestCase):
    """Base commune : le delai de 10 secondes est neutralise.

    Le delai reel est le comportement de production, mais il ne doit
    pas ralentir la suite de tests : il est verifie separement.
    """

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        http._last_request_at = None
        self.addCleanup(http.reset_delay)
        self.addCleanup(http.clear_robots_cache)


class HttpTestCase(VeilleTestCase):
    """La lecture des pages."""

    def test_a_page_is_read(self):
        with mock.patch.object(http.requests, 'get', return_value=fake_response(PAGE_ANNONCE)):
            result = http.fetch('https://exemple.test/offre/1')

        self.assertTrue(result.is_ok)
        self.assertIn('Assistant comptable', result.text)
        self.assertEqual(result.error, '')

    def test_an_http_error_is_rendered(self):
        with mock.patch.object(http.requests, 'get', return_value=fake_response('', 404)):
            result = http.fetch('https://exemple.test/offre/1')

        self.assertFalse(result.is_ok)
        self.assertIn('404', result.error)

    def test_a_network_failure_is_rendered(self):
        import requests

        with mock.patch.object(http.logger, 'warning'):
            with mock.patch.object(
                http.requests,
                'get',
                side_effect=requests.exceptions.ConnectionError('reseau coupe'),
            ):
                result = http.fetch('https://exemple.test/offre/1')

        self.assertFalse(result.is_ok)
        self.assertIn('injoignable', result.error)

    def test_a_timeout_is_rendered(self):
        import requests

        with mock.patch.object(
            http.requests,
            'get',
            side_effect=requests.exceptions.Timeout('trop long'),
        ):
            result = http.fetch('https://exemple.test/offre/1')

        self.assertFalse(result.is_ok)
        self.assertIn('delai', result.error)

    def test_an_address_that_is_not_a_page_is_refused(self):
        result = http.fetch('ftp://exemple.test/offre')

        self.assertFalse(result.is_ok)
        self.assertIn('invalide', result.error)

    def test_the_delay_is_applied_between_two_requests(self):
        """La veille ne martele pas un site."""
        http.set_delay(10)
        http._last_request_at = time.monotonic() - 1

        with mock.patch.object(http.time, 'sleep') as sleep:
            with mock.patch.object(http.requests, 'get', return_value=fake_response(PAGE_ANNONCE)):
                http.fetch('https://exemple.test/offre/1')

        sleep.assert_called_once()
        self.assertGreater(sleep.call_args[0][0], 8)

    def test_the_default_delay_is_ten_seconds(self):
        """Le delai retenu par l equipe est de 10 secondes."""
        http.reset_delay()

        self.assertEqual(http.get_delay(), 10)

    def test_a_page_forbidden_by_robots_is_not_read(self):
        robots = 'User-agent: *\nDisallow: /prive/\n'

        def get(url, **kwargs):
            if url.endswith('/robots.txt'):
                return fake_response(robots)
            return fake_response(PAGE_ANNONCE)

        with mock.patch.object(http.requests, 'get', side_effect=get):
            result = http.fetch('https://exemple.test/prive/offre/1')

        self.assertFalse(result.is_ok)
        self.assertTrue(result.blocked)
        self.assertIn('robots.txt', result.error)

    def test_an_allowed_page_is_read_despite_robots(self):
        robots = 'User-agent: *\nDisallow: /prive/\n'

        def get(url, **kwargs):
            if url.endswith('/robots.txt'):
                return fake_response(robots)
            return fake_response(PAGE_ANNONCE)

        with mock.patch.object(http.requests, 'get', side_effect=get):
            result = http.fetch('https://exemple.test/offre/1')

        self.assertTrue(result.is_ok)


class ManualCollectionTestCase(VeilleTestCase):
    """La saisie a la main : lien ou texte."""

    def test_a_text_becomes_an_item(self):
        result = collectors.collect_text('Nous recrutons un assistant comptable.')

        self.assertEqual(result.count, 1)
        self.assertEqual(result.errors, [])
        self.assertIn('assistant comptable', result.items[0].text)

    def test_an_empty_text_is_refused(self):
        result = collectors.collect_text('   ')

        self.assertEqual(result.count, 0)
        self.assertTrue(result.errors)

    def test_a_link_gives_the_title_and_the_text_of_the_page(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_ANNONCE)
        ):
            result = collectors.collect_url('https://exemple.test/offre/1')

        self.assertEqual(result.count, 1)
        self.assertEqual(result.items[0].title, 'Offre - Assistant comptable')
        self.assertIn('recrutons', result.items[0].text)
        self.assertNotIn('var suivi', result.items[0].text)


class WebListCollectionTestCase(VeilleTestCase):
    """La lecture d'une page de liste d'annonces."""

    def test_the_announcements_of_the_page_are_found(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            result = collectors.collect_web_list(
                'https://exemple.test/emplois', 'article.offre'
            )

        self.assertEqual(result.count, 2)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.items[0].title, 'Assistant comptable')
        self.assertIn('Societe Exemple', result.items[0].text)

    def test_a_relative_link_is_turned_into_an_absolute_address(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            result = collectors.collect_web_list(
                'https://exemple.test/emplois', 'article.offre'
            )

        self.assertEqual(
            result.items[0].url,
            'https://exemple.test/offre/assistant-comptable',
        )
        self.assertEqual(
            result.items[1].url,
            'https://autre.test/offre/charge-projets',
        )

    def test_the_limit_is_respected(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            result = collectors.collect_web_list(
                'https://exemple.test/emplois', 'article.offre', limit=1
            )

        self.assertEqual(result.count, 1)

    def test_a_selector_that_matches_nothing_is_reported(self):
        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            result = collectors.collect_web_list(
                'https://exemple.test/emplois', 'div.inexistant'
            )

        self.assertEqual(result.count, 0)
        self.assertTrue(result.errors)
        self.assertIn('Aucune annonce', result.errors[0])

    def test_a_source_without_selector_is_reported(self):
        result = collectors.collect_web_list('https://exemple.test/emplois', '')

        self.assertEqual(result.count, 0)
        self.assertIn('selecteur', result.errors[0])


class FeedCollectionTestCase(VeilleTestCase):
    """La lecture d'un flux RSS ou Atom."""

    def test_an_rss_feed_gives_its_announcements(self):
        with mock.patch.object(http.requests, 'get', return_value=fake_response(FLUX_RSS)):
            result = collectors.collect_feed('https://exemple.test/flux.xml')

        self.assertEqual(result.count, 2)
        self.assertEqual(result.items[0].title, 'Assistant comptable')
        self.assertEqual(result.items[0].url, 'https://exemple.test/offre/1')
        self.assertIn('assistant comptable', result.items[0].text)

    def test_the_publication_date_of_a_feed_item_is_read(self):
        with mock.patch.object(http.requests, 'get', return_value=fake_response(FLUX_RSS)):
            result = collectors.collect_feed('https://exemple.test/flux.xml')

        self.assertEqual(result.items[0].published_at.isoformat(), '2026-06-02')
        self.assertIsNone(result.items[1].published_at)

    def test_an_atom_feed_gives_its_announcements(self):
        with mock.patch.object(http.requests, 'get', return_value=fake_response(FLUX_ATOM)):
            result = collectors.collect_feed('https://exemple.test/flux.atom')

        self.assertEqual(result.count, 1)
        self.assertEqual(result.items[0].url, 'https://exemple.test/offre/3')
        self.assertEqual(result.items[0].published_at.isoformat(), '2026-06-05')

    def test_a_broken_feed_is_reported(self):
        with mock.patch.object(http.requests, 'get', return_value=fake_response('<pas du xml')):
            result = collectors.collect_feed('https://exemple.test/flux.xml')

        self.assertEqual(result.count, 0)
        self.assertTrue(result.errors)

    def test_an_empty_feed_is_reported(self):
        with mock.patch.object(
            http.requests,
            'get',
            return_value=fake_response('<rss version="2.0"><channel></channel></rss>'),
        ):
            result = collectors.collect_feed('https://exemple.test/flux.xml')

        self.assertEqual(result.count, 0)
        self.assertIn('aucune annonce', result.errors[0])


class ContentHashTestCase(VeilleTestCase):
    """L'empreinte qui evite de collecter deux fois la meme annonce."""

    def test_the_same_text_gives_the_same_empreinte(self):
        first = collectors.content_hash('Nous recrutons un assistant comptable.')
        second = collectors.content_hash('nous recrutons un ASSISTANT comptable')

        self.assertEqual(first, second)

    def test_two_different_annonces_give_two_empreintes(self):
        first = collectors.content_hash('Nous recrutons un assistant comptable.')
        second = collectors.content_hash('Nous recrutons un charge de projets.')

        self.assertNotEqual(first, second)

    def test_the_empreinte_of_an_item_is_computed(self):
        item = collectors.CollectedItem(text='Nous recrutons un assistant comptable.')

        self.assertEqual(len(item.content_hash), 64)


class CandidateSelectorTestCase(VeilleTestCase):
    """L'aide a la recherche du selecteur d'une page."""

    def test_the_repeated_blocks_are_proposed(self):
        proposals = collectors.candidate_selectors(PAGE_LISTE)

        selectors = [selector for selector, _count, _sample in proposals]
        self.assertIn('article.offre', selectors)

    def test_the_number_of_occurrences_is_given(self):
        proposals = collectors.candidate_selectors(PAGE_LISTE)

        counts = {selector: count for selector, count, _sample in proposals}
        self.assertEqual(counts.get('article.offre'), 2)

    def test_a_block_that_appears_once_is_not_proposed(self):
        proposals = collectors.candidate_selectors(PAGE_LISTE, minimum=3)

        selectors = [selector for selector, _count, _sample in proposals]
        self.assertNotIn('article.offre', selectors)

    def test_a_sample_of_text_is_given(self):
        proposals = collectors.candidate_selectors(PAGE_LISTE)

        samples = {selector: sample for selector, _count, sample in proposals}
        self.assertIn('Assistant comptable', samples.get('article.offre', ''))


class CollectSourceTestCase(VeilleTestCase):
    """La collecte d'une source, selon son mode."""

    def setUp(self):
        http.set_delay(0)
        http.clear_robots_cache()
        http._last_request_at = None

    def test_a_web_source_is_collected(self):
        source = Source.objects.create(
            name='Emplois du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            watch_config={'selector': 'article.offre', 'limit': 5},
        )

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            result = collectors.collect_source(source)

        self.assertEqual(result.count, 2)
        self.assertEqual(result.errors, [])

    def test_a_feed_source_is_collected(self):
        source = Source.objects.create(
            name='Emplois du Faso',
            url='https://exemple.test/flux.xml',
            collection_method=Source.COLLECTION_METHOD_RSS,
        )

        with mock.patch.object(http.requests, 'get', return_value=fake_response(FLUX_RSS)):
            result = collectors.collect_source(source)

        self.assertEqual(result.count, 2)

    def test_a_manual_source_is_not_collected_automatically(self):
        """Facebook et WhatsApp restent saisis a la main."""
        source = Source.objects.create(
            name='Groupe WhatsApp',
            collection_method=Source.COLLECTION_METHOD_WHATSAPP,
            is_watched=True,
            authorization_note='Saisie manuelle uniquement.',
        )

        result = collectors.collect_source(source)

        self.assertEqual(result.count, 0)
        self.assertIn('saisie', result.errors[0])

    def test_a_source_with_an_unreadable_configuration_does_not_crash(self):
        """La configuration est saisie a la main : elle peut etre invalide.

        Une configuration illisible ne doit jamais provoquer une erreur
        technique : la collecte est simplement refusee, avec une
        explication.
        """
        source = Source.objects.create(
            name='Emploi du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            is_watched=True,
            authorization_note='Autorisation accordee.',
            watch_config=['ceci', 'n est', 'pas', 'un', 'objet'],
        )

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            result = collectors.collect_source(source)

        self.assertEqual(result.count, 0)
        self.assertEqual(len(result.errors), 1)
        self.assertIn('selecteur', result.errors[0])

    def test_a_source_with_a_wrong_setting_still_works(self):
        """Une source configuree de travers ne doit pas arreter la collecte."""
        source = Source.objects.create(
            name='Emplois du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            watch_config={
                'selector': 'article.offre',
                'limit': 'beaucoup',
                'delay_seconds': 'vite',
            },
        )

        with mock.patch.object(
            http.requests, 'get', return_value=fake_response(PAGE_LISTE)
        ):
            result = collectors.collect_source(source)

        self.assertEqual(result.count, 2)
        self.assertEqual(result.errors, [])

    def test_the_delay_of_the_source_is_used(self):
        source = Source.objects.create(
            name='Emplois du Faso',
            url='https://exemple.test/emplois',
            collection_method=Source.COLLECTION_METHOD_WEB,
            watch_config={'selector': 'article.offre', 'delay_seconds': 10},
        )

        with mock.patch.object(http.time, 'sleep') as sleep:
            with mock.patch.object(
                http.requests, 'get', return_value=fake_response(PAGE_LISTE)
            ):
                http._last_request_at = time.monotonic() - 1
                collectors.collect_source(source)

        sleep.assert_called()
