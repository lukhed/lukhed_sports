"""
Live check of DkSportsbook against the real DraftKings API.

Run this from your own terminal:

    python tests/dk_live_check.py
    python tests/dk_live_check.py --save-responses     # also save raw responses for new test fixtures

It runs each main method once, counts the DraftKings calls each one makes, and checks the result looks right.
DraftKings blocks scripted clients (HTTP 403) from time to time, especially after bursts of calls. If a call is
blocked, the remaining checks are skipped; wait a while before running again.
About 12 DraftKings calls in total, spaced out by --pause seconds. A summary is printed and the full report is written
to reference/dk_live_check.json (gitignored) so it can be reviewed later.

Not part of the unit test suite (the file name doesn't start with 'test').
"""
import argparse
import contextlib
import datetime
import io
import json
import os
import sys
import time
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from lukhed_sports import DkSportsbook  # noqa: E402

REPORT_FILE = os.path.join(REPO_ROOT, 'reference', 'dk_live_check.json')
RESPONSES_DIR = os.path.join(REPO_ROOT, 'reference', 'dk responses', 'live_check')


class Skip(Exception):
    """Raised by a check that can't run (e.g. an earlier check it depends on didn't get data)."""


class CallRecorder:
    """Wraps the wrapper's session.get to record every DraftKings call and its status."""

    def __init__(self, dk, save_dir=None):
        self.calls = []
        self.save_dir = save_dir
        self._get = dk.session.get
        dk.session.get = self

    def __call__(self, url, **kwargs):
        response = self._get(url, **kwargs)
        self.calls.append({'url': url, 'status': response.status_code})
        if self.save_dir and response.ok:
            os.makedirs(self.save_dir, exist_ok=True)
            name = url.split('.com/')[-1].replace('/', '_').replace('?', '_')[:150] + '.json'
            with open(os.path.join(self.save_dir, name), 'w', encoding='utf-8') as f:
                f.write(response.text)
        return response


def first_team(event_name):
    # 'CIN Bengals @ ATL Falcons' -> 'falcons'
    return event_name.split('@')[-1].strip().split()[-1].lower()


def american_ok(selections):
    values = [x['displayOdds']['american'] for x in selections if 'displayOdds' in x]
    return bool(values) and all('−' not in v for v in values)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pause', type=float, default=2, help='seconds to wait between checks (default 2)')
    parser.add_argument('--save-responses', action='store_true',
                        help=f'save raw responses to {os.path.relpath(RESPONSES_DIR, REPO_ROOT)}')
    parser.add_argument('--calibration-source', default='github', choices=['github', 'local'])
    args = parser.parse_args()

    dk = DkSportsbook(calibration_source=args.calibration_source)
    recorder = CallRecorder(dk, RESPONSES_DIR if args.save_responses else None)
    results = []
    state = {}

    def check(name, expected_calls, fn):
        """expected_calls: int, or (min, max). fn returns (ok, summary)."""
        lo, hi = expected_calls if isinstance(expected_calls, tuple) else (expected_calls, expected_calls)
        if dk._blocked_until is not None and time.monotonic() < dk._blocked_until:
            results.append({'check': name, 'status': 'SKIPPED', 'summary': 'DraftKings blocked an earlier call',
                            'expected_calls': [lo, hi]})
            print(f"[SKIPPED] {name:55} (DraftKings blocked an earlier call)")
            return

        before = len(recorder.calls)
        log = io.StringIO()
        skipped = None
        try:
            with contextlib.redirect_stdout(log):  # keep the wrapper's own prints out of the summary
                ok, summary = fn()
            error = None
        except Skip as e:
            ok, summary, error, skipped = False, None, None, str(e)
        except Exception:
            ok, summary, error = False, None, traceback.format_exc()
        calls = recorder.calls[before:]
        if skipped:
            results.append({'check': name, 'status': 'SKIPPED', 'summary': skipped, 'expected_calls': [lo, hi]})
            print(f"[SKIPPED] {name:55} ({skipped})")
            return
        calls_ok = lo <= len(calls) <= hi
        blocked = any(c['status'] in (403, 429) for c in calls)
        http_ok = all(c['status'] == 200 for c in calls)
        status = 'BLOCKED' if blocked else ('PASS' if ok and calls_ok and http_ok else 'FAIL')
        results.append({'check': name, 'status': status, 'result_ok': ok, 'calls': len(calls),
                        'expected_calls': [lo, hi], 'summary': summary, 'error': error, 'requests': calls,
                        'log': log.getvalue().strip().splitlines()})
        print(f"[{status:7}] {name:55} calls={len(calls)} (expected {lo if lo == hi else f'{lo}-{hi}'})"
              f"{'' if summary is None else '  ' + str(summary)}")
        if error:
            print('          ' + error.strip().splitlines()[-1])
        for line in log.getvalue().splitlines():
            if line.startswith(('ERROR', 'WARNING')):
                print('          ' + line)
        if calls:
            time.sleep(args.pause)

    print(f"DkSportsbook live check {datetime.datetime.now():%Y-%m-%d %H:%M}  "
          f"(api versions nav={dk._api_versions['navVersion']} content={dk._api_versions['groupVersion']})\n")

    check('init makes no DraftKings calls', 0, lambda: (True, None))

    # --- NFL: the league call should serve every gameline method afterwards ---
    def nfl_lines():
        lines = dk.get_gamelines_for_league('nfl')
        state['nfl_events'] = [x['event'] for x in lines]
        selections = [s for x in lines for s in x['selections']]
        return bool(lines) and american_ok(selections), f"{len(lines)} games"
    check('nfl get_gamelines_for_league', 1, nfl_lines)

    def need_nfl_games():
        if not state.get('nfl_events'):
            raise Skip('no NFL games from the first check')

    def nfl_spread():
        need_nfl_games()
        team = first_team(state['nfl_events'][0])
        spread = dk.get_spread_for_team('nfl', team)
        state['nfl_team'] = team
        return 'spread' in spread, f"{team}: {spread.get('spread')} {DkSportsbook.parse_odds(spread.get('odds', {}))}"
    check('nfl get_spread_for_team (re-uses league response)', 0, nfl_spread)

    def nfl_game():
        need_nfl_games()
        lines = dk.get_gamelines_for_game('nfl', state['nfl_team'], filter_market='moneyline', filter_team=True)
        return len(lines) == 1, [x['label'] for x in lines]
    check('nfl get_gamelines_for_game (re-uses league response)', 0, nfl_game)

    def nfl_halves():
        need_nfl_games()
        lines = dk.get_half_lines_for_game('nfl', state['nfl_team'])
        return True, f"{len(lines)} selections (0 is ok if DK has no half lines yet)"
    check('nfl get_half_lines_for_game', 1, nfl_halves)

    def nfl_td():
        need_nfl_games()
        props = dk.get_basic_touchdown_scorer_props('nfl', prop_type_filter='anytime', game_filter=state['nfl_team'])
        return True, f"{len(props)} anytime td props (0 is ok if the game has started or props aren't posted)"
    check('nfl get_basic_touchdown_scorer_props (game filter)', 1, nfl_td)

    def nfl_all_td():
        need_nfl_games()
        props = dk.get_all_touchdown_props_for_game('nfl', state['nfl_team'])
        return True, f"{len(props)} td props"
    check('nfl get_all_touchdown_props_for_game', 1, nfl_all_td)

    # --- Other leagues: one call each for gamelines (MLB may need a lookup call, see issue #73) ---
    for league, expected in [('college football', 1), ('nba', 1), ('college basketball (m)', 1), ('nhl', 1),
                             ('mlb', (1, 2))]:
        def other_lines(league=league):
            lines = dk.get_gamelines_for_league(league)
            selections = [s for x in lines for s in x['selections']]
            ok = american_ok(selections) if selections else True
            return ok, f"{len(lines)} games (0 is ok in the offseason)"
        check(f'{league} get_gamelines_for_league', expected, other_lines)

    def nba_points():
        props = dk.get_player_points_props('nba')
        return True, f"{len(props)} player points props" + (f", e.g. {props[0]}" if props else '')
    check('nba get_player_points_props', 1, nba_points)

    # --- Report ---
    counts = {s: sum(1 for r in results if r['status'] == s) for s in ('PASS', 'FAIL', 'BLOCKED', 'SKIPPED')}
    report = {
        'run_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'api_versions': dk._api_versions,
        'calibration_source': args.calibration_source,
        'total_calls': len(recorder.calls),
        'counts': counts,
        'results': results,
    }
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"\n{counts['PASS']} passed, {counts['FAIL']} failed, {counts['BLOCKED']} blocked, "
          f"{counts['SKIPPED']} skipped. "
          f"{len(recorder.calls)} DraftKings calls total.")
    print(f"Report: {os.path.relpath(REPORT_FILE, REPO_ROOT)}")
    if counts['BLOCKED']:
        print("DraftKings blocked this client (HTTP 403). Wait a while (at least an hour) before running again; "
              "re-running sooner tends to extend the block.")
    return 0 if counts['FAIL'] == 0 and counts['BLOCKED'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
