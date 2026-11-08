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
from lukhed_sports.calibrations.dk import known_ids

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
        self.dk = DkSportsbook(api_delay=0, retry_delay=0, use_local_cache=False)
        self.dk.session.get = self._fake_get

    def _fake_get(self, url, timeout=None):
        self.calls.append(url)
        if self.status_override is not None:
            return FakeResponse(self.status_override)
        if url in ROUTES:
            return FakeResponse(200, load_fixture(ROUTES[url]))
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

    def test_every_supported_league_has_known_league_id(self):
        for league, sport in self.dk._get_major_league_support_dict().items():
            self.assertIn((sport, league), known_ids.league_ids, league)

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
        with mock.patch.dict(known_ids.category_ids, {}, clear=True):
            lines = self.dk.get_gamelines_for_league('nfl')
        self.assertEqual(self.calls, [f"{CONTENT}/leagues/88808"])
        self.assertEqual(len(lines), 3)

    def test_unknown_category_id_non_default_category_is_two_calls(self):
        with mock.patch.dict(known_ids.category_ids, {}, clear=True):
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


if __name__ == '__main__':
    unittest.main()
