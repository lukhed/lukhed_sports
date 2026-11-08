"""
Offline tests for DkSportsbook. HTTP is mocked with trimmed real DraftKings responses (tests/fixtures/dk), so these
never call DraftKings. The call-count assertions guard the call-reduction work: DraftKings rate limits on the total
number of calls, so a regression that adds calls is a real bug.
"""
import json
import os
import unittest
from unittest import mock

from lukhed_sports.dkWrapper import DkSportsbook
from lukhed_sports.calibrations.dk import loader

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'dk')
CONTENT = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusmi/v1"


def load_fixture(name):
    with open(os.path.join(FIXTURES, f'{name}.json'), encoding='utf-8') as f:
        return json.load(f)


ROUTES = {
    f"{CONTENT}/leagues/88808": 'nfl_league',
    f"{CONTENT}/leagues/88808/categories/492": 'nfl_game_lines',
    f"{CONTENT}/leagues/88808/categories/1003": 'nfl_td_scorers',
    f"{CONTENT}/leagues/92483/categories/487": 'cbb_game_lines',
    f"{CONTENT}/leagues/42133/categories/496": 'nhl_game_lines',
}


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._data = data

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data


class DkTestCase(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.status_override = None
        self.dk = DkSportsbook(api_delay=0, retry_delay=0, use_local_cache=False, calibration_source='local')
        self.dk.session.get = self._fake_get

    def _fake_get(self, url, timeout=None):
        self.calls.append(url)
        if self.status_override is not None:
            return FakeResponse(self.status_override)
        routes = getattr(self, 'routes', ROUTES)
        if url in routes:
            return FakeResponse(200, load_fixture(routes[url]))
        return FakeResponse(404)


class TestCallCounts(DkTestCase):
    def test_init_makes_no_calls(self):
        self.assertEqual(self.calls, [])

    def test_gamelines_for_league_is_one_call(self):
        lines = self.dk.get_gamelines_for_league('nfl')
        self.assertEqual(self.calls, [f"{CONTENT}/leagues/88808/categories/492"])
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0]['event'], 'CLE Browns @ NO Saints')
        self.assertEqual({x['marketType'] for x in lines[0]['selections']}, {'Moneyline', 'Spread', 'Total'})

    def test_gamelines_for_game_is_one_call(self):
        lines = self.dk.get_gamelines_for_game('nfl', 'saints')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(lines), 6)  # 2 moneyline + 2 spread + 2 total

    def test_college_basketball_gamelines_is_one_call(self):
        lines = self.dk.get_gamelines_for_game('college basketball (m)', 'iona')
        self.assertEqual(self.calls, [f"{CONTENT}/leagues/92483/categories/487"])
        self.assertEqual(len(lines), 6)

    def test_nhl_gamelines_is_one_call(self):
        lines = self.dk.get_gamelines_for_game('nhl', 'bruins')
        self.assertEqual(self.calls, [f"{CONTENT}/leagues/42133/categories/496"])
        self.assertEqual(len(lines), 6)

    def test_every_supported_league_has_known_league_id(self):
        for league, sport in self.dk._get_major_league_support_dict().items():
            self.assertIn(league, self.dk._league_ids.get(sport, {}), league)

    def test_repeated_calls_reuse_response(self):
        self.dk.get_spread_for_team('nfl', 'saints')
        self.dk.get_spread_for_team('nfl', 'broncos')
        self.dk.get_gamelines_for_league('nfl')
        self.assertEqual(len(self.calls), 1)

    def test_td_props_with_game_filter_is_one_call(self):
        props = self.dk.get_basic_touchdown_scorer_props('nfl', game_filter='saints')
        self.assertEqual(self.calls, [f"{CONTENT}/leagues/88808/categories/1003"])
        self.assertTrue(len(props) > 0)

    def test_unknown_category_id_reuses_league_json(self):
        # Simulate a league whose category ids are not calibrated: the league json is fetched to find the
        # 'game lines' id, and since it already holds game lines, no second call is made.
        self.dk._category_ids = {}
        lines = self.dk.get_gamelines_for_league('nfl')
        self.assertEqual(self.calls, [f"{CONTENT}/leagues/88808"])
        self.assertEqual(len(lines), 3)

    def test_unknown_category_id_non_default_category_is_two_calls(self):
        self.dk._category_ids = {}
        props = self.dk.get_basic_touchdown_scorer_props('nfl')
        self.assertEqual(self.calls, [f"{CONTENT}/leagues/88808", f"{CONTENT}/leagues/88808/categories/1003"])
        self.assertTrue(len(props) > 0)


class TestFiltering(DkTestCase):
    def test_spread_for_team(self):
        spread = self.dk.get_spread_for_team('nfl', 'saints')
        self.assertIn('spread', spread)
        self.assertIn('american', spread['odds'])

    def test_filter_market_and_team(self):
        lines = self.dk.get_gamelines_for_game('nfl', 'saints', filter_market='moneyline', filter_team=True)
        self.assertEqual(len(lines), 1)
        self.assertIn('Saints', lines[0]['label'])

    def test_td_game_filter_only_returns_that_game(self):
        all_props = self.dk.get_basic_touchdown_scorer_props('nfl')
        saints = self.dk.get_basic_touchdown_scorer_props('nfl', game_filter='saints')
        self.assertTrue(0 < len(saints) < len(all_props))

    def test_td_prop_type_filter(self):
        props = self.dk.get_basic_touchdown_scorer_props('nfl', prop_type_filter='anytime')
        self.assertTrue(len(props) > 0)
        self.assertTrue(all('anytime' in x['outcomeType'].lower() for x in props))

    def test_unknown_team(self):
        self.assertEqual(self.dk.get_gamelines_for_game('nfl', 'not a team'), [])

    def test_category_names_are_stripped(self):
        # DK returns 'Passing Props ' with a trailing space
        self.dk._get_json_for_league('football', 'nfl')
        self.assertIn('passing props', self.dk._discovered_category_ids['88808'])


class TestFailures(DkTestCase):
    def test_403_pauses_all_calls(self):
        self.status_override = 403
        self.assertEqual(self.dk.get_gamelines_for_league('nfl'), [])
        self.assertEqual(len(self.calls), 1)  # not retried

        self.status_override = None
        self.assertEqual(self.dk.get_gamelines_for_league('nfl'), [])
        self.assertEqual(len(self.calls), 1)  # still paused, no call made

    def test_failed_response_is_not_cached(self):
        self.status_override = 500
        self.assertEqual(self.dk.get_gamelines_for_league('nfl'), [])
        failed_calls = len(self.calls)

        self.status_override = None
        self.assertEqual(len(self.dk.get_gamelines_for_league('nfl')), 3)
        self.assertEqual(len(self.calls), failed_calls + 1)

    def test_unsupported_league(self):
        self.assertEqual(self.dk.get_gamelines_for_league('cricket'), [])
        self.assertEqual(self.calls, [])


class TestOdds(DkTestCase):
    def test_american_odds_use_ascii_minus(self):
        lines = self.dk.get_gamelines_for_league('nfl')
        american = [x['displayOdds']['american'] for game in lines for x in game['selections']]
        self.assertTrue(any(a.startswith('-') for a in american))
        self.assertFalse(any('\u2212' in a for a in american))

    def test_parse_odds_selection(self):
        selection = self.dk.get_gamelines_for_game('nfl', 'saints', filter_market='moneyline')[0]
        odds = DkSportsbook.parse_odds(selection)
        self.assertIsInstance(odds['american'], int)
        self.assertAlmostEqual(odds['decimal'], selection['trueOdds'])
        self.assertAlmostEqual(odds['implied_probability'], round(1 / selection['trueOdds'], 4))

    def test_parse_odds_from_odds_dict(self):
        self.assertEqual(DkSportsbook.parse_odds({'american': '\u2212110'}),
                         {'american': -110, 'decimal': 1 + 100 / 110, 'implied_probability': 0.5238})
        self.assertEqual(DkSportsbook.parse_odds({'american': '+150', 'decimal': '2.50'})['decimal'], 2.5)
        self.assertEqual(DkSportsbook.parse_odds({}), {'american': None, 'decimal': None,
                                                       'implied_probability': None})


class TestVersionFallback(DkTestCase):
    def test_404_tries_next_version_and_keeps_it(self):
        self.routes = {url.replace('/dkusmi/v1/', '/dkusmi/v2/'): name for url, name in ROUTES.items()}
        lines = self.dk.get_gamelines_for_league('nfl')
        self.assertEqual(len(lines), 3)
        self.assertEqual(self.dk._api_versions['groupVersion'], 'v2')
        self.assertEqual(self.calls, [f"{CONTENT}/leagues/88808/categories/492",
                                      f"{CONTENT}/leagues/88808/categories/492".replace('/v1/', '/v2/')])

        # Later calls go straight to the new version
        self.dk.get_basic_touchdown_scorer_props('nfl')
        self.assertEqual(self.calls[-1], f"{CONTENT}/leagues/88808/categories/1003".replace('/v1/', '/v2/'))

    def test_404_only_probes_once(self):
        self.routes = {}
        self.dk.get_gamelines_for_league('nfl')
        self.dk.get_basic_touchdown_scorer_props('nfl')
        self.assertEqual(len(self.calls), 3)  # v1 + v2 probe, then v1 only
        self.assertEqual(self.dk._api_versions['groupVersion'], 'v1')


class TestCalibrations(unittest.TestCase):
    def test_bundled_has_required_keys(self):
        cal = loader.load_bundled()
        for key in loader.REQUIRED_KEYS:
            self.assertIn(key, cal)

    def test_remote_overrides_bundled(self):
        bundled = loader.load_bundled()
        remote = {'schema': bundled['schema'], 'api': {'groupVersion': 'v9'}, 'sportIds': {},
                  'leagueIds': {'baseball': {'mlb': '84240'}}, 'categoryIds': {'84240': {'game lines': 999}}}
        with mock.patch.object(loader, 'load_remote', return_value=remote):
            cal = loader.load_calibrations('github')
        self.assertEqual(cal['api']['groupVersion'], 'v9')
        self.assertEqual(cal['api']['navVersion'], bundled['api']['navVersion'])
        self.assertEqual(cal['categoryIds']['84240'], {'champion': 1774, 'game lines': 999})
        self.assertEqual(cal['categoryIds']['88808'], bundled['categoryIds']['88808'])

    def test_unreachable_or_bad_remote_uses_bundled(self):
        bundled = loader.load_bundled()
        with mock.patch.object(loader, 'load_remote', return_value=None):
            self.assertEqual(loader.load_calibrations('github'), bundled)
        with mock.patch.object(loader, 'load_remote', return_value={'schema': 999}):
            self.assertEqual(loader.load_calibrations('github'), bundled)

    def test_local_source_skips_github(self):
        with mock.patch.object(loader, 'load_remote') as remote:
            loader.load_calibrations('local')
        remote.assert_not_called()


if __name__ == '__main__':
    unittest.main()
