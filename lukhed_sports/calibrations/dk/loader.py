"""
Loads DraftKings calibrations (api versions and known sport/league/category ids).

The calibration file is bundled with the package, and the latest copy is also fetched from the GitHub repo at runtime.
That way, when DraftKings changes an id or api version, updating dk_calibrations.json on main fixes every installed
version without a new release. If GitHub can't be reached, or the remote file has an unexpected schema, the bundled
copy is used.
"""
import copy
import json
import os

import requests

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), 'dk_calibrations.json')
REMOTE_URL = ("https://raw.githubusercontent.com/lukhed/lukhed_sports/main/"
              "lukhed_sports/calibrations/dk/dk_calibrations.json")
REQUIRED_KEYS = ('schema', 'api', 'sportIds', 'leagueIds', 'categoryIds')


def load_bundled():
    with open(CALIBRATION_FILE, encoding='utf-8') as f:
        return json.load(f)


def _deep_merge(base, override):
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_remote(timeout=3):
    """Returns the calibration file from GitHub main, or None if it can't be retrieved."""
    try:
        response = requests.get(REMOTE_URL, timeout=timeout)
        if response.ok:
            return response.json()
    except (requests.RequestException, ValueError):
        pass
    return None


def load_calibrations(source='github', timeout=3):
    """
    Parameters
    ----------
    source : str, optional
        'github' (default) to use the latest calibrations from the repo, merged over the bundled copy. 'local' to
        use only the bundled copy.
    timeout : float, optional
        Seconds to wait for GitHub, by default 3

    Returns
    -------
    dict()
        Calibrations with keys 'api', 'sportIds', 'leagueIds', 'categoryIds'.
    """
    bundled = load_bundled()
    if source != 'github':
        return bundled

    remote = load_remote(timeout)
    if remote is None:
        return bundled

    if not all(k in remote for k in REQUIRED_KEYS) or remote['schema'] != bundled['schema']:
        print("INFO: Remote DraftKings calibrations have an unexpected format. Using bundled calibrations. "
              "Upgrading lukhed_sports may fix this.")
        return bundled

    return _deep_merge(bundled, remote)
