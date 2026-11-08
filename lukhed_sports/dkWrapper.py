import time
import requests
from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import listWorkCommon as lC
from lukhed_sports.calibrations.dk import loader as dk_calibrations

# url kind -> calibration key holding that endpoint family's api version
_VERSION_KEYS = {'nav': 'navVersion', 'content': 'groupVersion', 'player': 'playerVersion'}

class DkSportsbook():
    def __init__(self, api_delay=0.5, use_local_cache=True, reset_cache=False, retry_delay=5, timeout=10,
                 response_cache_seconds=60, block_cooldown=300, calibration_source='github'):
        """
        A wrapper class for accessing DraftKings Sportsbook API data.

        This class provides methods to retrieve betting lines, odds, and other sports betting data
        from DraftKings Sportsbook. It supports major sports leagues including NFL, NBA, NHL, MLB,
        and NCAA sports, with functionality to get game lines, player props, and other betting markets.

        DraftKings can block clients (HTTP 403) that make too many calls, so this class tries hard to
        make as few calls as possible: known sport/league/category ids are built in, and responses are re-used
        for a short time within a session.

        Parameters
        ----------
        api_delay : float, optional
            Minimum delay between consecutive API calls in seconds, by default 0.5. Most methods make a single
            call, so this delay rarely comes into play.
        use_local_cache : bool, optional
            Whether to cache reference API responses (sport list, league list, etc.) locally, by default True
            Note: use reset cache if the data is very stale (sports or leagues change over time)
        reset_cache : bool, optional
            Whether to clear existing cache on initialization, by default False
        retry_delay : float, optional
            Delay between retry attempts for failed API calls in seconds, by default 5. Calls that are
            blocked or rate limited (HTTP 403/429) are not retried.
        timeout : float, optional
            Seconds to wait for a DraftKings response before giving up, by default 10
        response_cache_seconds : float, optional
            How long a DraftKings response is re-used within this session before calling again, by default 60.
            Set to 0 to always call the api.
        block_cooldown : float, optional
            After DraftKings blocks a call (HTTP 403/429), no further calls are made for this many seconds,
            by default 300. Calling into a block is unlikely to help and may prolong it.
        calibration_source : str, optional
            Where DraftKings ids and api versions come from, by default 'github': the latest calibration file in
            the lukhed_sports repo (one quick call to GitHub, not DraftKings), falling back to the copy bundled with
            the package. Use 'local' to only use the bundled copy.
        """
        # Set API Information
        self.api_delay = api_delay
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.response_cache_seconds = response_cache_seconds
        self.block_cooldown = block_cooldown
        self.session = self._create_session()
        self._last_call_time = None
        self._last_status = None
        self._blocked_until = None
        self._version_probed = set()

        # Set cals
        self.calibration_source = calibration_source
        self._api_versions = None
        self._base_url = None
        self._player_url = None
        self.sportsbook = None
        self._sport_ids = None
        self._league_ids = None
        self._category_ids = None
        self._load_calibrations()

        # Available Sports (loaded lazily, see the available_sports property)
        self._available_sports = None

        # Cache
        self.use_cache = use_local_cache
        self._local_cache_dir = osC.check_create_dir_structure(['lukhed_sports_local_cache'], return_path=True)
        self._sports_cache_file = osC.append_to_dir(self._local_cache_dir, 'dk_sports_cache.json')
        self._cached_available_leagues_json = {}
        self._leagues_cache_file = osC.append_to_dir(self._local_cache_dir, 'dk_available_leagues_cache.json')
        self._response_cache = {}           # url -> (time fetched, response)
        self._discovered_category_ids = {}  # league id -> {category name: id}, learned from responses
        self._discovered_events = {}        # league id -> events list, learned from responses

        if self.use_cache and reset_cache:
            self._reset_cache()

    def _load_calibrations(self):
        cal = dk_calibrations.load_calibrations(self.calibration_source)
        self._api_versions = cal['api']
        self._sport_ids = cal['sportIds']
        self._league_ids = cal['leagueIds']
        self._category_ids = cal['categoryIds']
        self._base_url = self._api_versions['baseUrl']
        self._player_url = self._api_versions['playerUrl']
        self.sportsbook = self._api_versions['defaultSportsbook']

    @property
    def available_sports(self):
        """
        List of sports available at DraftKings. Retrieved on first use (one api call, then cached locally if
        use_local_cache is True).
        """
        if self._available_sports is None:
            self._set_available_sports()
        return [x['name'].lower() for x in self._available_sports]

    def _set_available_sports(self):
        sports = []
        if self.use_cache and osC.check_if_file_exists(self._sports_cache_file):
            sports = fC.load_json_from_file(self._sports_cache_file) or []

        if not sports:
            sports = self._get('nav', 'nav/sports?format=json', 'retrieve available sports').get('sports', [])
            if self.use_cache and sports:
                fC.dump_json_to_file(self._sports_cache_file, sports)

        self._available_sports = sports

    ############################
    # API calls
    ############################
    def _create_session(self):
        session = requests.Session()
        session.headers.update({
            "User-Agent": rC.get_random_user_agent(),
            "Accept": "application/json",
        })
        return session

    def _wait_for_api_delay(self):
        # Enforce a minimum gap between consecutive calls (time spent parsing between calls counts toward it)
        if self.api_delay is None or self._last_call_time is None:
            return
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < self.api_delay:
            tC.sleep(self.api_delay - elapsed)

    def _call_api(self, endpoint, purpose, max_attempts=3):
        self._last_status = None
        if self._blocked_until is not None:
            remaining = self._blocked_until - time.monotonic()
            if remaining > 0:
                print(f"ERROR: Skipping call to DraftKings ({purpose}). Calls are paused for another "
                      f"{remaining:.0f}s after being blocked.")
                return {}
            self._blocked_until = None

        for attempt in range(1, max_attempts + 1):
            self._wait_for_api_delay()
            print(f"called api: {endpoint}\npurpose: {purpose}\n")
            try:
                response = self.session.get(endpoint, timeout=self.timeout)
            except requests.RequestException as e:
                print(f"ERROR: request failed: {e}")
                response = None
            finally:
                self._last_call_time = time.monotonic()

            self._last_status = None if response is None else response.status_code

            if response is not None:
                if response.status_code in (403, 429):
                    # Blocked or rate limited. Retrying quickly is unlikely to help and may prolong it, so pause all calls.
                    self._blocked_until = time.monotonic() + self.block_cooldown
                    print(f"ERROR: DraftKings returned {response.status_code} (access denied / rate limited). "
                          f"Pausing calls for {self.block_cooldown}s. Increase api_delay or make fewer calls.")
                    return {}
                if response.ok:
                    try:
                        return self._normalize_odds(response.json())
                    except ValueError:
                        print("ERROR: DraftKings response was not valid JSON")
                elif response.status_code == 404:
                    # Not retried: either the resource doesn't exist or the api version changed (see _get)
                    print(f"ERROR: DraftKings returned HTTP 404 for {endpoint}")
                    return {}
                else:
                    print(f"ERROR: DraftKings returned HTTP {response.status_code}")

            if attempt < max_attempts:
                print("Sleeping then retrying api call\n")
                tC.sleep(self.retry_delay)

        return {}

    def _call_api_cached(self, endpoint, purpose):
        """
        Same as _call_api, but re-uses a successful response for self.response_cache_seconds. Failed (empty)
        responses are never cached.
        """
        cached = self._response_cache.get(endpoint)
        if cached is not None:
            fetched_time, data = cached
            if time.monotonic() - fetched_time < self.response_cache_seconds:
                return data

        data = self._call_api(endpoint, purpose)
        if data:
            self._response_cache[endpoint] = (time.monotonic(), data)
        return data

    def _build_url(self, kind, path, version=None):
        version = version or self._api_versions[_VERSION_KEYS[kind]]
        if kind == 'nav':
            return f"{self._base_url}/sportscontent/navigation/{self.sportsbook}/{version}/{path}"
        if kind == 'content':
            return f"{self._base_url}/sportscontent/{self.sportsbook}/{version}/{path}"
        return f"{self._player_url}/{version}/{path}"

    @staticmethod
    def _next_version(version):
        try:
            return f"v{int(version.lstrip('v')) + 1}"
        except ValueError:
            return None

    def _get(self, kind, path, purpose):
        """
        Calls a DraftKings endpoint family ('nav', 'content' or 'player') at its calibrated api version.

        DraftKings doesn't publish versions. If a call returns 404, the next version up is tried once per endpoint
        family per session; if that works, it is used for the rest of the session and a message asks for the
        calibration file to be updated.
        """
        data = self._call_api_cached(self._build_url(kind, path), purpose)
        if data or self._last_status != 404 or kind in self._version_probed:
            return data

        self._version_probed.add(kind)
        key = _VERSION_KEYS[kind]
        current = self._api_versions[key]
        candidate = self._next_version(current)
        if candidate is None:
            return data

        data = self._call_api_cached(self._build_url(kind, path, candidate), f'{purpose} (trying api {candidate})')
        if data:
            self._api_versions[key] = candidate
            print(f"WARNING: DraftKings '{kind}' api moved from {current} to {candidate}. Using {candidate} for this "
                  f"session. Please update '{key}' in lukhed_sports/calibrations/dk/dk_calibrations.json "
                  f"(or open an issue at https://github.com/lukhed/lukhed_sports/issues).")
        return data

    @staticmethod
    def _normalize_odds(data):
        """DK american odds use a unicode minus (U+2212). Replace it with '-' so the values can be parsed."""
        if isinstance(data, dict):
            for selection in data.get('selections') or []:
                odds = selection.get('displayOdds')
                if isinstance(odds, dict) and isinstance(odds.get('american'), str):
                    odds['american'] = odds['american'].replace('\u2212', '-')
        return data

    @staticmethod
    def parse_odds(selection):
        """
        Returns a selection's odds as numbers.

        Parameters
        ----------
        selection : dict()
            A selection returned by any method of this class, or an odds dict like the 'odds' value returned by
            get_spread_for_team() and the player prop methods.

        Returns
        -------
        dict()
            {'american': int, 'decimal': float, 'implied_probability': float}. Values are None if not available.
        """
        display = selection.get('displayOdds', selection.get('odds', selection))
        american = display.get('american') if isinstance(display, dict) else None
        try:
            american = int(str(american).replace('\u2212', '-').replace('+', ''))
        except (TypeError, ValueError):
            american = None

        decimal = selection.get('trueOdds')
        if decimal is None and isinstance(display, dict):
            try:
                decimal = float(display.get('decimal'))
            except (TypeError, ValueError):
                decimal = None
        if decimal is None and american:
            decimal = 1 + (american / 100 if american > 0 else 100 / abs(american))

        return {
            'american': american,
            'decimal': decimal,
            'implied_probability': round(1 / decimal, 4) if decimal else None,
        }

    ############################
    # Class cache management
    ############################
    def _reset_cache(self):
        fC.dump_json_to_file(self._sports_cache_file, [])
        fC.dump_json_to_file(self._leagues_cache_file, {})
        self._available_sports = None
        self._cached_available_leagues_json = {}
        self._response_cache = {}

    def _check_available_league_cache(self, sport_id):
        """
        Checks available league cache on local file system.

        Parameters
        ----------
        sport_id : str()
            Sport being requested

        Returns
        -------
        dict() or None
            Cached nav response for the sport, or None if not cached
        """
        if self._cached_available_leagues_json == {} and self.use_cache:
            # Try to load available leagues cache from file
            if osC.check_if_file_exists(self._leagues_cache_file):
                self._cached_available_leagues_json = fC.load_json_from_file(self._leagues_cache_file) or {}

        cached = self._cached_available_leagues_json.get(sport_id)
        if not cached or 'leagues' not in cached:
            return None
        return cached

    def _get_league_data_for_sport(self, s_id):
        """
        Returns the leagues DraftKings has for a sport. Uses the local file cache (if use_local_cache) or the
        session cache before calling the api.

        Parameters
        ----------
        s_id : str()
            DraftKings sport id

        Returns
        -------
        dict()
            DraftKings nav response with a 'leagues' key, or {'leagues': []} if unavailable.
        """
        available_leagues = self._check_available_league_cache(s_id)
        if available_leagues is not None:
            return available_leagues

        available_leagues = self._get('nav', f'nav/sports/{s_id}?format=json', f'retrieve league data for id={s_id}')
        if 'leagues' not in available_leagues:
            return {'leagues': []}

        self._cached_available_leagues_json[s_id] = available_leagues
        if self.use_cache:
            fC.dump_json_to_file(self._leagues_cache_file, self._cached_available_leagues_json)

        return available_leagues

    def _get_json_for_league(self, sport, league):
        """
        Returns the league 'home page' json (events, categories, subcategories, and the default category's
        markets/selections). Returns {} if the league is not found or the call fails.
        """
        league_id = self._get_league_id(sport, league)
        if league_id is None:
            return {}

        league_json = self._get('content', f'leagues/{league_id}', f'retrieve league json for {league}')
        self._learn_from_response(league_id, league_json)
        return league_json

    def _learn_from_response(self, league_id, data):
        """
        Every league/category response contains the league's category list and the events it covers. Save them
        so later lookups don't need an extra call.
        """
        if not data:
            return
        if data.get('categories'):
            self._discovered_category_ids[league_id] = {
                x['name'].strip().lower(): x['id'] for x in data['categories']
            }
        if data.get('events'):
            known = {x['id']: x for x in self._discovered_events.get(league_id, [])}
            known.update({x['id']: x for x in data['events']})
            self._discovered_events[league_id] = list(known.values())

    def _get_sport_from_id(self, sport_id):
        for x in self._available_sports or []:
            if x['id'] == sport_id:
                return x['name'].lower()
        for name, s_id in self._sport_ids.items():
            if s_id == sport_id:
                return name
        return None

    ############################
    # Input Checks
    ############################
    def _check_valid_sport(self, sport):
        sport = sport.lower()
        if sport in self._sport_ids or sport in self.available_sports:
            return True
        else:
            print(f"ERROR: '{sport}' is not a valid sport. Check api.available_sports for valid input.")
            return False

    ############################
    # Level 2 Parsing Functions
    # Functions that are used by multiple internal class functins
    ############################
    def _get_sport_id(self, sport):
        """
        Returns the DraftKings sport id. Known ids are used without an api call; otherwise available sports are
        looked up (cached across sessions if use_cache = True).

        Parameters
        ----------
        sport : str()
            A sport string available from dk

        Returns
        -------
        str() or None
            A sport ID which is used in API calls.
        """
        sport = sport.lower()
        if sport in self._sport_ids:
            return self._sport_ids[sport]

        if sport in self.available_sports:
            index = self.available_sports.index(sport)
            return self._available_sports[index]['id']

        print(f"ERROR: Could not find {sport} in valid sports. Check api.available_sports for valid input.")
        return None

    def _get_league_id(self, sport, league):
        """
        Returns the DraftKings league id. Known ids are used without an api call; otherwise the leagues for the
        sport are looked up (cached across sessions if use_cache = True).

        Parameters
        ----------
        sport : str()
            Sport associated with the given league. Hiearchy is: sport -> league
        league : str()
            League string in which you want the league id for. Example: 'nfl'

        Returns
        -------
        str() or None
            League ID for a given league.
        """
        sport = sport.lower()
        league = league.lower()
        known = self._league_ids.get(sport, {}).get(league)
        if known is not None:
            return known

        sport_id = self._get_sport_id(sport)
        if sport_id is None:
            return None

        available_leagues = self._get_league_data_for_sport(sport_id)
        for available_league in available_leagues['leagues']:
            if available_league['name'].lower() == league:
                return available_league['id']

        print(f"ERROR: '{league}' was not found for '{sport}'. Use api.get_available_leagues() to check valid input")
        return None

    def _get_category_id(self, sport, league, category):
        """
        Returns the category id for a named category (e.g. 'game lines', 'td scorers'). Checks, in order: known
        ids, ids learned from earlier responses this session, then the league json (one api call).
        """
        category = category.strip().lower()
        league_id = self._get_league_id(sport, league)
        if league_id is None:
            return None

        for source in (self._category_ids, self._discovered_category_ids):
            cat_id = source.get(league_id, {}).get(category)
            if cat_id is not None:
                return cat_id

        self._get_json_for_league(sport, league)
        cat_id = self._discovered_category_ids.get(league_id, {}).get(category)
        if cat_id is None:
            print(f"ERROR: No '{category}' for {league} found at DK. Try api.get_available_betting_categories() "
                  f"to see what is available on dk for {league}")
        return cat_id

    def _get_category_data(self, sport, league, category):
        """
        Returns the DraftKings response for a league category: events, markets and selections for the category
        (plus the league's categories/subcategories). This is normally a single api call.

        If the category id is not known, the league json is fetched to find it. When the league json already
        holds that category's markets (DK's default category, usually game lines), it is returned directly
        instead of making a second call.

        Returns
        -------
        dict()
            DraftKings category response, or {} if unavailable.
        """
        category = category.strip().lower()
        league_id = self._get_league_id(sport, league)
        if league_id is None:
            return {}

        known_before = (
            self._category_ids.get(league_id, {}).get(category) is not None
            or self._discovered_category_ids.get(league_id, {}).get(category) is not None
        )
        cat_id = self._get_category_id(sport, league, category)
        if cat_id is None:
            return {}

        if not known_before:
            # The league json was just fetched to find the category id. Re-use it if it already is the category.
            league_json = self._get_json_for_league(sport, league)
            if self._response_is_category(league_json, cat_id):
                return league_json

        data = self._get('content', f'leagues/{league_id}/categories/{cat_id}', f'retrieve {league} {category}')
        self._learn_from_response(league_id, data)
        return data

    @staticmethod
    def _response_is_category(data, cat_id):
        """True if every market in a league response belongs to the given category."""
        markets = data.get('markets') or []
        if not markets:
            return False
        subcat_to_cat = {x['id']: x['categoryId'] for x in data.get('subcategories', [])}
        return all(subcat_to_cat.get(int(m.get('subcategoryId', -1))) == cat_id for m in markets)

    def _get_events_for_league(self, sport, league):
        """
        Events for a league. Uses events learned from earlier responses this session when available, otherwise
        fetches the league json (one api call).
        """
        league_id = self._get_league_id(sport, league)
        if league_id is None:
            return []
        if not self._discovered_events.get(league_id):
            self._get_json_for_league(sport, league)
        return self._discovered_events.get(league_id, [])

    def _get_data_from_league_json(self, sport, league, key, return_full=False):
        """
        This function is used to parse a league json file. Each league has a default json file with data such
        as 'events' and 'markets'.

        sport -> leagues -> each league has json file

        Parameters
        ----------
        sport : str()
        league : str()
        key : str()
            Each league json file has keys: 'events', 'markets', 'selections', 'categories', 'subcategories'
        return_full : bool, optional
            If true, all the data in the requested key is returned unmodified, by default False. When false,
            the category is parsed for user friendly output.

        Returns
        -------
        list()
            Data from the league json.
        """
        sport = sport.lower()
        league = league.lower()
        key = key.lower()

        league_json = self._get_json_for_league(sport, league)
        raw = league_json.get(key, [])
        if return_full:
            return raw

        data = [x['name'].strip().lower() for x in raw]
        if len(data) == 0:
            print(f"INFO: There are no '{key}' for {sport} - {league}.")

        return data

    @staticmethod
    def _find_game_by_team(events, league, team):
        # DK lists more than one week of games, so a team can match several events. Earliest game first.
        found_game = sorted([x for x in events if team.lower() in x['name'].lower()],
                            key=lambda x: x.get('startEventDate', ''))

        if len(found_game) < 1:
            print(f"ERROR: Could not find '{team}' in available {league} events. Try "
                  f"api.get_available_betting_events() to get valid input")
            return None

        if len(found_game) > 1:
            print(f"WARNING: '{team}' matched multiple {league} events: {[x['name'] for x in found_game]}. "
                  f"Using '{found_game[0]['name']}'.")

        return found_game

    def _find_game_by_team_from_events(self, sport, league, team):
        events = self._get_events_for_league(sport, league)
        return self._find_game_by_team(events, league, team)

    @staticmethod
    def _filter_selections_to_event(data, event_id):
        """Selections in a league/category response that belong to one event (no api call needed)."""
        market_ids = {x['id'] for x in data.get('markets', []) if x['eventId'] == event_id}
        return [x for x in data.get('selections', []) if x['marketId'] in market_ids]

    @staticmethod
    def _parse_gameline_selections_given_filters(event_id, markets, selections, team, filter_market, filter_team):
        """
        Selections retrieved when searching by game lines are categorized by a market id which may
        not give enough information by itself (for example, for totals). Market id needs to be traced back to
        available markets in an event. This function takes care of this while also giving the option to filter by team.

        Parameters
        ----------
        event_id : str()
            Provide the event id you are looking for within the selections data
        markets : list()
            The markets available in the dk data (returned in a dk call)
        selections : list()
            selections available in the dk data (returned in a dk call)
        team : str()
            Provide a team name in conjunction with filter_team to filter by team
        filter_market : str()
            Provide a market type to filter by. If None, market is ignored
        filter_team : bool()
            Instruction to filter team or not
        """
        market_names = {x['id']: x['name'] for x in markets if x['eventId'] == event_id}
        filtered_data = []
        for selection in selections:
            market_name = market_names.get(selection['marketId'])
            if market_name is None:
                continue
            if filter_market is not None and market_name.lower() != filter_market.lower():
                continue
            selection = selection.copy()
            selection['marketType'] = market_name
            filtered_data.append(selection)

        if filter_team:
            filtered_data = [x for x in filtered_data if team.lower() in x['label'].lower()]

        return filtered_data

    def _parse_league_prop_selections_given_filters(self, league, category, prop_type_filter=None, game_filter=None):
        sport = self._major_league_to_sport_mapping(league)
        if sport is None:
            self._print_major_league_not_supported_message(league)
            return []

        data = self._get_category_data(sport, league, category)
        if not data:
            return []

        if game_filter is not None:
            game = self._find_game_by_team(data.get('events', []), league, game_filter)
            if game is None:
                return []
            selections = self._filter_selections_to_event(data, game[0]['id'])
        else:
            selections = data.get('selections', [])

        if prop_type_filter is not None:
            prop_type_filter = prop_type_filter.lower()
            selections = [x for x in selections if prop_type_filter in x.get('outcomeType', '').lower()]

        return selections

    ############################
    # Discovery Methods
    ############################
    def _get_event_market_data(self, event_id):
        data = self._get('content', f'events/{event_id}/categories', f'get markets for {event_id}')
        return data

    def get_available_leagues(self, sport):
        sport_id = self._get_sport_id(sport)
        if sport_id is None:
            return []
        league_data = self._get_league_data_for_sport(sport_id)
        return [x['name'].lower() for x in league_data['leagues']]

    def get_supported_major_sport_leagues(self):
        """
        This method returns a list of the leagues that are considered 'major sport leagues'. Many methods only
        work with these leagues.

        Returns
        -------
        list()
            List of the major sports leagues.
        """
        return list(self._get_major_league_support_dict().keys())

    def get_available_betting_categories(self, sport, league):
        if not self._check_valid_sport(sport):
            return []

        categories = self._get_data_from_league_json(sport, league, 'categories')
        return categories

    def get_available_betting_events(self, sport, league):
        if not self._check_valid_sport(sport):
            return []

        events = self._get_data_from_league_json(sport, league, 'events')
        return events

    def get_available_betting_markets(self, sport, league):
        if not self._check_valid_sport(sport):
            return []
        markets = self._get_data_from_league_json(sport, league, 'markets')
        return lC.return_unique_values(markets)

    def get_betting_selections_by_category(self, sport, league, category):
        data = self._get_category_data(sport, league, category)
        return data.get('selections', [])

    def get_event_data(self, sport, league, event):
        event = event.lower()
        for available in self._get_events_for_league(sport, league):
            if available['name'].lower() == event:
                return available

        print(f"ERROR: '{event}' is not available for '{league}'. Use function "
              f"get_available_betting_events() to get valid input.")
        return {}

    def get_available_markets_by_event(self, sport, league, event):
        event_data = self.get_event_data(sport, league, event)
        if event_data == {}:
            return []

        data = self._get_event_market_data(event_data['id'])
        return [x['name'] for x in data.get('markets', [])]

    def get_betting_selections_by_event_market(self, sport, league, event, event_market):
        event_data = self.get_event_data(sport, league, event)
        if event_data == {}:
            return []

        data = self._get_event_market_data(event_data['id'])
        event_market = event_market.lower()
        matching_markets = [x['id'] for x in data.get('markets', []) if x['name'].lower() == event_market]

        if len(matching_markets) < 1:
            print(f"ERROR: '{event_market}' is not available for '{event}'. Use function "
                  f"get_available_markets_by_event() to get valid input.")
            return []

        market_id = matching_markets[0]
        return [x for x in data.get('selections', []) if x['marketId'] == market_id]

    def get_player_data_by_event(self, sport, league, event):
        event_data = self.get_event_data(sport, league, event)
        if event_data == {}:
            return []

        data = self._get_event_market_data(event_data['id'])

        player_names = []
        player_data = []
        for selection in data.get('selections', []):
            try:
                potential_player = selection['participants'][0]
                if potential_player['type'] == 'Player':
                    if potential_player['name'] not in player_names:
                        player_names.append(potential_player['name'])
                        player_data.append({'name': potential_player['name'], 'id': potential_player['id']})
            except (KeyError, IndexError):
                pass

        return player_data

    def get_player_data_by_id(self, player_id):
        data = self._get('player', f'players/{player_id}', f'get player odds {player_id}')
        return data


    ############################
    # Core Betting Data Methods
    ############################
    def _major_league_to_sport_mapping(self, league):
        mapping = self._get_major_league_support_dict()
        return mapping.get(league.lower())

    @staticmethod
    def _get_major_league_support_dict():
        return {
            "nfl": "football",
            "college football": "football",
            "nba": "basketball",
            "nhl": "hockey",
            "mlb": "baseball",
            "college basketball (m)": "basketball",
            "college basketball (w)": "basketball",
            "wnba": "basketball"
        }

    def _print_major_league_not_supported_message(self, league):
        message = (
            f"ERROR: '{league}' is not supported by this method. "
            f"Supported leagues are: {list(self._get_major_league_support_dict().keys())}"
        )
        print(message)

    def _get_lines_for_game(self, league, team, category, filter_market, filter_team):
        sport = self._major_league_to_sport_mapping(league)
        if sport is None:
            self._print_major_league_not_supported_message(league)
            return []

        data = self._get_category_data(sport, league, category)
        if not data:
            return []

        found_game = self._find_game_by_team(data.get('events', []), league, team)
        if found_game is None:
            return []

        return self._parse_gameline_selections_given_filters(found_game[0]['id'], data['markets'],
                                                             data['selections'], team, filter_market, filter_team)

    def get_gamelines_for_league(self, league, filter_market=None):
        """
        Use this method to retrieve all gamelines (spread, total, and moneyline) for every game in the specified
        league. This method works for all major sport leagues

        Parameters
        ----------
        league : str()
            The major sports league you want lines for. ('nfl', 'college football', 'college basketball (m), etc.).
            Use api.get_supported_major_sport_leagues() for a complete list.
        filter_market : str(), optional
            Use this parameter to return only certain gamelines, by default None. Valid options are: 'spread',
            'total', and 'moneyline'.

        Returns
        -------
        list()
            Game lines separate by event name.
        """
        sport = self._major_league_to_sport_mapping(league)
        if sport is None:
            self._print_major_league_not_supported_message(league)
            return []

        data = self._get_category_data(sport, league, 'game lines')
        if not data:
            return []

        gamelines = []
        for event in data.get('events', []):
            applicable_selections = self._parse_gameline_selections_given_filters(
                event['id'], data['markets'], data['selections'], None, filter_market, False)
            gamelines.append(
                {
                    "event": event['name'],
                    "selections": applicable_selections
                }
            )

        return gamelines

    def get_gamelines_for_game(self, league, team, filter_market=None, filter_team=False):
        """
        Use this method to retrieve all gamelines (spread, total, and moneylines) for a given game.

        Parameters
        ----------
        league : str()
            The major sports league you want lines for. ('nfl', 'college football', 'college basketball (m), etc.).
            Use api.get_supported_major_sport_leagues() for a complete list.

        team : str()
            Use one team name playing in the game. For pro teams, you can use the nickname like "lions" for
            the detroit lions. For college teams, use the team name as displayed on draftkings. For example:
            'notre dame'.
        filter_market : str(), optional
            Use this parameter to return only certain gamelines, by default None. Valid options are: 'spread',
            'total', and 'moneyline'.
        filter_team : bool, optional
            If True, the selections will only be applicable to the team provided, by default False and both team
            spreads and moneylines are returned in the list.

        Returns
        -------
        list()
            Gamelines for the specified game in list format.
        """
        return self._get_lines_for_game(league, team, 'game lines', filter_market, filter_team)

    def get_half_lines_for_game(self, league, team, filter_market=None, filter_team=False):
        """
        Use this method to retrieve all gamelines for halves (spread, total, and moneylines) for a given game.

        Parameters
        ----------
        league : str()
            The major sports league you want lines for. ('nfl', 'college football', 'college basketball (m), etc.).
            Use api.get_supported_major_sport_leagues() for a complete list.
        team : str()
            Use one team name playing in the game. For pro teams, you can use the nickname like "lions" for
            the detroit lions. For college teams, use the team name as displayed on draftkings. For example:
            'notre dame'.
        filter_market : str(), optional
            Use this parameter to return only certain gamelines, by default None. Valid options are: 'spread',
            'total', and 'moneyline'.
        filter_team : bool, optional
            If True, the selections will only be applicable to the team provided, by default False and both team
            spreads and moneylines are returned in the list.

        Returns
        -------
        list()
            Gamelines for halves for the specified game in list format.
        """
        return self._get_lines_for_game(league, team, 'halves', filter_market, filter_team)

    def get_basic_touchdown_scorer_props(self, league, prop_type_filter=None, game_filter=None):
        """
        This method returns basic touchdown scoring props for the given league with optional filtering. Basic props are
        2+ tds, first time scorer, and anytime.

        Parameters
        ----------
        league : str()
            'nfl' or 'college football'
        prop_type_filter : str(), optional
            Use this filter to return only the type of touchdown prop you want, by default None and all available
            selections are returned. Options are '2 or more', 'first', 'anytime'.
        game_filter : str(), optional
            Use this filter to return only touchdown props for a given game, by default None and all available
            selections are returned. Input is one team name, for example: 'redskins'

        Returns
        -------
        list()
            A list of selections available for touchdown scorers and their odds.
        """

        league = league.lower()
        if league != 'nfl' and league != 'college football':
            print("ERROR: league parameter must be 'college football' or 'nfl'")
            return []

        if prop_type_filter is not None:
            prop_type_filter = prop_type_filter.lower()
            if prop_type_filter not in ('2 or more', 'first', 'anytime'):
                print(f"ERROR: {prop_type_filter} is not a valid input. Must be '2 or more', 'first', or 'anytime'")
                return []

        return self._parse_league_prop_selections_given_filters(league, 'td scorers',
                                                                prop_type_filter=prop_type_filter,
                                                                game_filter=game_filter)

    def get_all_touchdown_props_for_game(self, league, team):
        """
        Use this method to get every prop listed under td scorers at draftkings. This includes all of the simple
        selections retrieved by api.get_basic_touchdown_scorer_props() + any additional bets draftking supports.
        Examples are: 'either player to score', 'either player first td', 'player 1 & player 2 4tds', 'either/or', etc.

        Parameters
        ----------
        league : str()
            'nfl' or 'college football'
        team : str()
            Use one team name playing in the game. For pro teams, you can use the nickname like "lions" for
            the detroit lions. For college teams, use the team name as displayed on draftkings. For example:
            'notre dame'.

        Returns
        -------
        list()
            List of td selections dicts with key 'name' and the corresponding available 'selection'.
        """
        league = league.lower()
        if league != 'nfl' and league != 'college football':
            print("ERROR: league parameter must be 'college football' or 'nfl'")
            return []

        game = self._find_game_by_team_from_events('football', league, team)
        if game is None:
            return []
        cat_id = self._get_category_id('football', league, 'td scorers')
        if cat_id is None:
            return []
        data = self._get('content', f"events/{game[0]['id']}/categories/{cat_id}",
                         f"getting td scorers for event: {game[0]['id']}")

        market_names = {x['id']: x['name'] for x in data.get('markets', [])}

        props = []
        for selection in data.get('selections', []):
            props.append({
                "name": market_names.get(selection['marketId']),
                "selection": selection.copy()
            })

        return props

    def get_spread_for_team(self, league, team):
        """
        Use this method to return a simple dict containing the spread and the spread odds.

        Parameters
        ----------
        league : str()
            The major sports league you want lines for. ('nfl', 'college football', 'college basketball (m), etc.).
            Use api.get_supported_major_sport_leagues() for a complete list.
        team : str()
            Use the team you want the spread for. For pro teams, you can use the nickname like "lions" for
            the detroit lions. For college teams, use the team name as displayed on draftkings. For example:
            'notre dame'.

        Returns
        -------
        dict()
            Dict with keys 'spread' and 'odds' for the specied team.
        """
        result = self.get_gamelines_for_game(league, team, filter_market='spread', filter_team=True)
        if len(result) > 0:
            return {
                'spread': result[0]['points'],
                'odds': result[0]['displayOdds']
            }
        else:
            return {}

    def _get_basketball_player_props(self, league, category, game_filter):
        if league.lower() not in ('college basketball (m)', 'nba'):
            print("ERROR: league parameter must be 'college basketball (m)' or 'nba'")
            return []

        filtered_selections = self._parse_league_prop_selections_given_filters(league,
                                                                               category,
                                                                               prop_type_filter=None,
                                                                               game_filter=game_filter)
        final_selections = []
        for prop in filtered_selections:
            final_selections.append(
                {
                    "player": prop['participants'][0]['name'],
                    "line": prop['label'],
                    "odds": prop['displayOdds'].copy()
                }
            )

        return final_selections

    def get_player_three_props(self, league='college basketball (m)', game_filter=None):
        return self._get_basketball_player_props(league, 'player threes', game_filter)

    def get_player_points_props(self, league='college basketball (m)', game_filter=None):
        return self._get_basketball_player_props(league, 'player points', game_filter)

    def get_player_assists_props(self, league='college basketball (m)', game_filter=None):
        return self._get_basketball_player_props(league, 'player assists', game_filter)

    def get_player_rebound_props(self, league='college basketball (m)', game_filter=None):
        return self._get_basketball_player_props(league, 'player rebounds', game_filter)
