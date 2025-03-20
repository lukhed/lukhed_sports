from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import stringCommon as sC
from lukhed_basic_utils import listWorkCommon as lC
from lukhed_sports.calibrations.dk import api_versions

class DkSportsbook():
    def __init__(self, api_delay=0.5, use_local_cache=True, reset_cache=False, retry_delay=1.5):
        """
        A wrapper class for accessing DraftKings Sportsbook API data.

        This class provides methods to retrieve betting lines, odds, and other sports betting data
        from DraftKings Sportsbook. It supports major sports leagues including NFL, NBA, NHL, MLB,
        and NCAA sports, with functionality to get game lines, player props, and other betting markets.

        Parameters
        ----------
        api_delay : float, optional
            Delay between API calls in seconds, by default 0.5
        use_local_cache : bool, optional
            Whether to cache reference API responses (sport list, league list, etc.) locally, by default True
            Note: use reset cache if the data is very stale (sports or leagues change over time)
        reset_cache : bool, optional
            Whether to clear existing cache on initialization, by default False
        retry_delay : float, optional
            Delay between retry attempts for failed API calls in seconds, by default 1.5
        """
        # Set API Information
        self.api_delay = api_delay
        self.retry_delay = retry_delay

        # Set cals
        self._api_versions = None
        self._base_url = None
        self._player_url = None
        self.sportsbook = None
        self._load_calibrations()
        
        # Available Sports
        self.available_sports = None
        self._available_sports = None
        
        # Cache
        self.use_cache = use_local_cache
        self._local_cache_dir = osC.check_create_dir_structure(['lukhed_sports', 'local_cache'], return_path=True)
        self. _sports_cache_file = osC.append_to_dir(self._local_cache_dir, 'dk_sports_cache.json')
        self._cached_available_leagues_json = {}
        self._leagues_cache_file = osC.append_to_dir(self._local_cache_dir, 'dk_available_leagues_cache.json')
        self._cached_league_json = {}
        self._cached_category = None

        if self.use_cache and reset_cache:
            self._reset_cache()

        self._set_available_sports()

    def _load_calibrations(self):
        # Load version cal
        self._api_versions = api_versions.api_versions
        self._base_url = self._api_versions['baseUrl']
        self._player_url = self._api_versions['playerUrl']
        self.sportsbook = self._api_versions['defaultSportsbook']
        
    def _set_available_sports(self):
        if self.use_cache:
            if osC.check_if_file_exists(self._sports_cache_file):
                self._available_sports = fC.load_json_from_file(self._sports_cache_file)
            else:
                self._available_sports = {}

        if self._available_sports == {}:
            # Call the api
            api_version = self._api_versions['navVersion']
            url = f"{self._base_url}/sportscontent/navigation/{self.sportsbook}/{api_version}/nav/sports?format=json"
            self._available_sports = self._call_api(url, 'retrieve available sports')['sports']
            if self.use_cache:
                fC.dump_json_to_file(self._sports_cache_file, self._available_sports)

        self.available_sports = [x['name'].lower() for x in self._available_sports]
            
    def _call_api(self, endpoint, purpose):
        retry_count = 3
        if self.api_delay is not None:
            tC.sleep(self.api_delay)

        while retry_count > 0:
            print(f"called api: {endpoint}\npurpose: {purpose}\n")
            response = rC.request_json(endpoint, add_user_agent=True, timeout=2)
            if response == {}:
                print("Sleeping then retrying api call\n")
                tC.sleep(self.retry_delay)
            else:
                break

            retry_count = retry_count - 1

        return response
    
    ############################
    # Class cache management
    ############################
    def _reset_cache(self):
        fC.dump_json_to_file(self._sports_cache_file, {})
        fC.dump_json_to_file(self._leagues_cache_file, {})
    
    def _check_available_league_cache(self, sport_id):
        """
        Checks available league cache on local file system.

        Parameters
        ----------
        sport_id : str()
            League being requested

        Returns
        -------
        dict()
            Output from self._get_json_for_league() or blank dict {} if no cache
        """
        if self._cached_available_leagues_json == {} and self.use_cache:
            # Try to load available leagues cache from file
            if osC.check_if_file_exists(self._leagues_cache_file):
                self._cached_available_leagues_json = fC.load_json_from_file(self._leagues_cache_file)
        
        # See if leagues available for sport are in cache
        try:
            available_leagues_json = self._cached_available_leagues_json[sport_id]
        except KeyError:
            available_leagues_json = None
        
        return available_leagues_json
    
    def _get_league_data_for_sport(self, s_id):
        """
        This function tries to utilize saved available leagues for a sport. Useful for users doing multiple 
        queries against the same sport so as to save api calls.

        There are two types of cache for available leagues: local file storage and RAM (local class variable).

        The RAM cache is on by default, as the leagues associated with a sport should not change during an 
        active session.

        The local file storage option is linked to user instantiation method (use_local_cache). 

        Parameters
        ----------
        s_id : str()
            _description_

        Returns
        -------
        _type_
            _description_
        """
        # check cache for id, get from dk if not in cache
        available_leagues_cache = self._check_available_league_cache(s_id)
        if available_leagues_cache is not None:
            # cache is available
            available_leagues = available_leagues_cache
        else:
            # obtain league json from dk and add to cache
            api_version = self._api_versions['navVersion']
            url = f"{self._base_url}/sportscontent/navigation/{self.sportsbook}/{api_version}/nav/sports/{s_id}?format=json"
            available_leagues = self._call_api(url, 'retrieve league data for id={s_id}')
            self._cached_available_leagues_json[s_id] = available_leagues
            if self.use_cache:
                fC.dump_json_to_file(self._leagues_cache_file, self._cached_available_leagues_json)

        return available_leagues
    
    def _check_league_json_cache(self, league_id):
        """
        This function tries to utilize saved league json if available. Useful for users doing multiple queries against 
        the same leagues so as to save api calls.

        When a user makes a call for data from dk with a league input parameter, the self._get_json_for_league() 
        function checks the cache and sets the cache when applicable.

        Parameters
        ----------
        league_json : str()
            League being requested

        Returns
        -------
        dict()
            Output from self._get_league_data_for_sport() or blank dict {} if no cache
        """

        try:
            league_json = self._cached_league_json[league_id]
        except KeyError:
            league_json = None
        
        return league_json
    
    def _get_json_for_league(self, sport, league):
        sport = sport.lower()
        league = league.lower()
        'https://sportsbook-nash.draftkings.com/api/sportscontent/dkusmi/v1/leagues/88808'

        league_id = self._get_league_id(sport, league)

        # check cache for id, get from dk if not in cache
        league_json_cache = self._check_league_json_cache(league_id)
        if league_json_cache is not None:
            # cache is available
            return league_json_cache
        else:
            # obtain league json from dk and add to cache
            api_version = self._api_versions['groupVersion']
            url = f"{self._base_url}/sportscontent/{self.sportsbook}/{api_version}/leagues/{league_id}"
            league_json = self._call_api(url, f'retrieve league json for {league}')
            self._cached_league_json[league_id] = league_json

        return league_json
    
    def _check_category_cache(league):
        stop = 1
    
    def _get_sport_from_id(self, sport_id):
        sport_ids = [x['id'] for x in self._available_sports]
        sport = self.available_sports[sport_ids.index(sport_id)]
        return sport
    
    ############################
    # Input Checks
    ############################
    def _check_valid_sport(self, sport):
        sport = sport.lower()
        if sport in self.available_sports:
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
        This function parses available sports for sport id. Available sports are made available upon class 
        instantiation and cached across sessions if use_cache = True.

        Parameters
        ----------
        league : str()
            A sport string available from dk

        Returns
        -------
        str()
            A sport ID which is used in API calls.
        """
        sport = sport.lower()
        if sport in self.available_sports:
            index = self.available_sports.index(sport)
            return self._available_sports[index]['id']
        else:
            print(f"ERROR: Could not find {sport} in valid sports. Check api.available_sports for valid input.")
            return None
        
    def _get_league_id(self, sport, league):
        """
        This function parses the available league data for a given sport for the league id. Available leagues 
        for a sport are only made available once a user needs data for a sport then are cached across sessions. 

        Parameters
        ----------
        sport : str()
            Sport associated with the given league. Hiearchy is: sport -> league
        league : str()
            League string in which you want the league id for. Example: 'nfl'

        Returns
        -------
        str()
            League ID for a given league.
        """


        sport_id = self._get_sport_id(sport)
        available_leagues = self._get_league_data_for_sport(sport_id)
        league = league.lower()

        for available_league in available_leagues['leagues']:
            league_name = available_league['name'].lower()
            if league_name == league:
                return available_league['id']
            
        print(f"ERROR: '{league}' was not found for '{sport}'. Use api.get_available_leagues() to check valid input")
        return None
    
    def _get_data_from_league_json(self, sport, league, key, return_full=False):
        """
        This function is used to parse a league json file. A league json file is cached within a session and stored in 
        self._cached_league_json. Each league has a default json file if queried with data such as 'events' and 
        'markets'.

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

        # test the key availability
        try:
            league_json[key]
            if not return_full:
                data = [x['name'].lower() for x in league_json[key]]
            else:
                return league_json[key]
        except KeyError:
            data = []
            
        if len(data) == 0:
            print(f"INFO: There are no '{key}' for {sport} - {league}.")

        return data
    
    def _find_game_by_team_from_events(self, sport, league, team):
        events = self._get_data_from_league_json(sport, league, 'events', return_full=True)
        found_game = [x for x in events if team.lower() in x['name'].lower()]

        if len(found_game) < 1:
            print(f"""ERROR: Could not find '{team}' in available {league} events. Try api.get_available_betting_events() 
                      to get valid input""")
            return None
        
        return found_game
    
    def _get_category_id_for_named_category(self, sport, league, named_category):
        categories = self._get_data_from_league_json(sport, league, 'categories', return_full=True)
        cat_id = self._get_category_id(categories, named_category)
        if cat_id is None:
            print(f"""ERROR: No {named_category} for {league} found at DK. Try api.get_available_betting_categories() 
                  to see what is available on dk for {league}""")
            return None
        
        return cat_id
    
    def _parse_gameline_selections_given_filters(self, event_id, markets, selections, team, filter_market, filter_team):
        """
        Selections retrieved when searching by game lines are categorized by a market id which may 
        not give enough information by itself (for example, for totals). Market id needs to be traced back to 
        available markets in an event. This function takes care of this while also giving the option to filter by team.

        Parameters
        ----------
        event_id : _type_
            Provide the event id you are looking for within the selections data
        markets : _type_
            The markets available in the dk data (returned in a dk call)
        selections : _type_
            selections available in the dk data (returned in a dk call)
        team : _type_
            Provide a team name in conjunction with filter_team to filter by team
        filter_market : _type_
            Provide a market type to filter by. If None, market is ignored
        filter_team : bool()
            Instruction to filter team or not
        """
        filtered_data = []
        applicable_market_ids = [x['id'] for x in markets if x['eventId'] == event_id]
        applicable_market_types = [x['name'] for x in markets if x['eventId'] == event_id]
        for selection in selections:
            if selection['marketId'] in applicable_market_ids:
                selection['marketType'] = applicable_market_types[applicable_market_ids.index(selection['marketId'])]
                if filter_market is not None:
                    if selection['marketType'].lower() == filter_market.lower():
                        filtered_data.append(selection.copy())
                else:
                    filtered_data.append(selection.copy())

        if filter_team:
            filtered_data = [x for x in filtered_data if team.lower() in x['label'].lower()]

        return filtered_data
    
    def _parse_league_prop_selections_given_filters(self, league, category, prop_type_filter=None, game_filter=None):
        selections = self.get_betting_selections_by_category('basketball', league, category)

        game_filtered_selections = []
        if game_filter is not None:
            game = self._find_game_by_team_from_events('basketball', league, game_filter)
            if game is None:
                return []
            
            event_name = game[0]['name']
            players = self.get_player_data_by_event('basketball', league, event_name)
            player_ids = [x['id'] for x in players]
            for selection in selections:
                try:
                    test_id = selection['participants'][0]['id']
                    if test_id in player_ids:
                        game_filtered_selections.append(selection.copy())
                        
                except KeyError:
                    pass
        else:
            game_filtered_selections = selections

        if prop_type_filter is not None:
            prop_type_filter = prop_type_filter.lower()
            final_selections = [x for x in game_filtered_selections if prop_type_filter.lower() in 
                                x['outcomeType'].lower()]
        else:
            final_selections = game_filtered_selections
            
        return final_selections
    
    def _build_league_url_for_category(self, sport, league, category_string):
        # stuff for url
        cat_id = self._get_category_id_for_named_category(sport, league, category_string)
        league_id = self._get_league_id(sport, league)

        # call the api
        api_version = self._api_versions['groupVersion']
        url = f"{self._base_url}/sportscontent/{self.sportsbook}/{api_version}/leagues/{league_id}/categories/{cat_id}"
        
        return url
    
    @staticmethod
    def _get_category_id(categories_json, category):
        try:
            return [x['id'] for x in categories_json if category.lower() == x['name'].lower()][0]
        except IndexError:
            return None

    ############################
    # Discovery Methods
    ############################
    def _get_event_market_data(self, event_id):
        api_version = self._api_versions['groupVersion']
        url = f"{self._base_url}/sportscontent/{self.sportsbook}/{api_version}/events/{event_id}/categories"
        data = self._call_api(url, f'get markets for {event_id}')
        return data
    
    def get_available_leagues(self, sport):
        sport_id = self._get_sport_id(sport)
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
        category = category.lower()
        league_json = self._get_json_for_league(sport, league)
        available = self.get_available_betting_categories(sport, league)
        if category not in available:
            print(f"""ERROR: '{category}' is not available for '{league}'. Use function 
                  get_available_betting_categories() to get valid input.""")
            return []
        
        market_index = available.index(category)
        league_id = self._get_league_id(sport, league)
        cat_id = league_json['categories'][market_index]['id']
        api_version = self._api_versions['groupVersion']
        url = f"{self._base_url}/sportscontent/{self.sportsbook}/{api_version}/leagues/{league_id}/categories/{cat_id}"
        selections = self._call_api(url, f'retrieve selections for {league} {category}')['selections']
        
        return selections
    
    def get_event_data(self, sport, league, event):
        event = event.lower()
        league_json = self._get_json_for_league(sport, league)
        events = league_json['events']
        for available in events:
            if available['name'].lower() == event:
                return available

        print(f"""ERROR: '{event}' is not available for '{league}'. Use function 
                  get_available_betting_events() to get valid input.""")
        return {}
    
    def get_available_markets_by_event(self, sport, league, event):
        event_data = self.get_event_data(sport, league, event)
        if event_data == {}:
            return {}
        
        event_id = event_data['id']
        data = self._get_event_market_data(event_id)
        return [x['name'] for x in data['markets']]
    
    def get_betting_selections_by_event_market(self, sport, league, event, event_market):
        event_data = self.get_event_data(sport, league, event)
        if event_data == {}:
            return {}
        
        event_id = event_data['id']
        data = self._get_event_market_data(event_id)
        matching_markets = [x['id'] for x in data['markets'] if x['name'].lower() == event_market]

        if len(matching_markets) < 1:
            print(f"""ERROR: '{event_market}' is not available for '{event}'. Use function 
                  get_available_markets_by_event() to get valid input.""")
        
        market_id = matching_markets[0]

        selections = [x for x in data['selections'] if x['marketId'] == market_id]
        return selections
    
    def get_player_data_by_event(self, sport, league, event):
        event_data = self.get_event_data(sport, league, event)
        if event_data == {}:
            return {}
        
        event_id = event_data['id']
        data = self._get_event_market_data(event_id)

        player_names = []
        player_data = []
        for selection in data['selections']:
            try:
                potential_player = selection['participants'][0]
                if potential_player['type'] == 'Player':
                    if potential_player['name'] not in player_names:
                        player_names.append(potential_player['name'])
                        player_data.append({'name': potential_player['name'], 'id': potential_player['id']})
            except KeyError:
                pass

        return player_data

    def get_player_data_by_id(self, player_id):
        api_version = self._api_versions['playerVersion']
        url = f"{self._player_url}/{api_version}/players/{player_id}"
        data = self._call_api(url, f'get player odds {player_id}')
        return data
    

    ############################
    # Core Betting Data Methods
    ############################
    def _major_league_to_sport_mapping(self, league):
        mapping = self._get_major_league_support_dict()
        league = league.lower()
        try:
            return mapping[league]
        except KeyError:
            return None
    
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
        
    def _build_sub_category_event_url(self, event_id, sub_cat):
        api_version = self._api_versions['groupVersion']
        url = f"{self._base_url}/sportscontent/{self.sportsbook}/{api_version}/events/{event_id}/categories/{sub_cat}"
        return url
        
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
        
        url = self._build_league_url_for_category(sport, league, 'game lines')
        data = self._call_api(url, f'get game lines for {league}')

        event_data = self._get_data_from_league_json(sport, league, 'events', return_full=True)
        event_names = [x['name'] for x in event_data]
        event_ids = [x['id'] for x in event_data]

        gamelines = []
        for index, event_id in enumerate(event_ids):
            event_name = event_names[index]
            applicable_selections = self._parse_gameline_selections_given_filters(
                event_id, data['markets'], data['selections'], None, filter_market, None)
            gamelines.append(
                {
                    "event": event_name,
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
        team = team.lower()
        
        sport = self._major_league_to_sport_mapping(league)
        if sport is None:
            self._print_major_league_not_supported_message(league)
            return []
        
        # parse team
        found_game = self._find_game_by_team_from_events(sport, league, team)
        if found_game is None:
            return []

        # call the api
        url = self._build_league_url_for_category(sport, league, 'game lines')
        game_lines = self._call_api(url, f'retrieve {league} game lines')

        # parse the result
        event_id = found_game[0]['id']
        gameline_data = self._parse_gameline_selections_given_filters(event_id, game_lines['markets'], 
                                                                      game_lines['selections'], 
                                                                      team, filter_market, filter_team)

        return gameline_data
    
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

        sport = self._major_league_to_sport_mapping(league)
        if sport is None:
            self._print_major_league_not_supported_message(league)
            return []
        
        # parse team
        found_game = self._find_game_by_team_from_events(sport, league, team)
        if found_game is None:
            return []
        
        # call the api
        url = self._build_league_url_for_category(sport, league, 'halves')
        half_lines = self._call_api(url, f'retrieve {league} half lines')
        
        # parse the result
        event_id = found_game[0]['id']
        half_line_data = self._parse_gameline_selections_given_filters(event_id, half_lines['markets'], 
                                                                       half_lines['selections'], 
                                                                       team, filter_market, filter_team)

        return half_line_data

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
            if prop_type_filter != '2 or more' and prop_type_filter != 'first' and prop_type_filter != 'anytime':
                print(f"ERROR: {prop_type_filter} is not a valid input. Must be '2 or more', 'first', or 'anytime'")
                return []
        
        selections = self.get_betting_selections_by_category('football', league, 'td scorers')

        game_filtered_selections = []
        if game_filter is not None:
            game = self._find_game_by_team_from_events('football', league, game_filter)
            if game is None:
                return []
            event_name = game[0]['name']
            players = self.get_player_data_by_event('football', league, event_name)
            player_ids = [x['id'] for x in players]
            
            for selection in selections:
                try:
                    test_id = selection['participants'][0]['id']
                    if test_id in player_ids:
                        game_filtered_selections.append(selection.copy())
                except KeyError:
                    pass
        else:
            game_filtered_selections = selections
        
        if prop_type_filter is not None:
            final_selections = [x for x in game_filtered_selections if prop_type_filter.lower() in 
                                x['outcomeType'].lower()]
        else:
            final_selections = game_filtered_selections
        
        return final_selections
    
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
        cat_id = self._get_category_id_for_named_category('football', league, 'td scorers')
        url = self._build_sub_category_event_url(game[0]['id'], cat_id)
        data = self._call_api(url, f"getting td scorers for event: {game[0]['id']}")

        market_ids = [x['id'] for x in data['markets']]
        market_names = [x['name'] for x in data['markets']]
        
        props = []
        for selection in data['selections']:
            market_index = market_ids.index(selection['marketId'])
            market_name = market_names[market_index]
            props.append({
                "name": market_name,
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
        sport = self._major_league_to_sport_mapping(league)
        if sport is None:
            self._print_major_league_not_supported_message(league)
            return []
        
        result = self.get_gamelines_for_game(league, team, filter_market='spread', filter_team=team)
        if len(result) > 0:
            spread = result[0]['points']
            odds = result[0]['displayOdds']
            return {
                'spread': spread,
                'odds': odds
            }
        else:
            return {}

    def get_player_three_props(self, league='college basketball (m)', game_filter=None):
        if league.lower() != 'college basketball (m)' and league != "nba":
            print("ERROR: league parameter must be 'college basketball (m)', NBA not supported yet")
            return []
        
        filtered_selections = self._parse_league_prop_selections_given_filters(league, 
                                                                               'player threes', 
                                                                               prop_type_filter=None, 
                                                                               game_filter=game_filter)
        final_selections = []
        for prop in filtered_selections:
            player = prop['participants'][0]['name']
            threes = prop['label']
            odds = prop['displayOdds'].copy()
            final_selections.append(
                {
                    "player": player,
                    "line": threes,
                    "odds": odds
                }
            )
        
        return final_selections
    
    def get_player_points_props(self, league='college basketball (m)', game_filter=None):
        if league.lower() != 'college basketball (m)' and league != "nba":
            print("ERROR: league parameter must be 'college basketball (m)', NBA not supported yet")
            return []
        
        filtered_selections = self._parse_league_prop_selections_given_filters(league, 
                                                                               'player points', 
                                                                               prop_type_filter=None, 
                                                                               game_filter=game_filter)
        final_selections = []
        for prop in filtered_selections:
            player = prop['participants'][0]['name']
            threes = prop['label']
            odds = prop['displayOdds'].copy()
            final_selections.append(
                {
                    "player": player,
                    "line": threes,
                    "odds": odds
                }
            )
        
        return final_selections

    def get_player_assists_props(self, league='college basketball (m)', game_filter=None):
        if league.lower() != 'college basketball (m)' and league != "nba":
            print("ERROR: league parameter must be 'college basketball (m)', NBA not supported yet")
            return []
        
        filtered_selections = self._parse_league_prop_selections_given_filters(league, 
                                                                               'player assists', 
                                                                               prop_type_filter=None, 
                                                                               game_filter=game_filter)
        final_selections = []
        for prop in filtered_selections:
            player = prop['participants'][0]['name']
            threes = prop['label']
            odds = prop['displayOdds'].copy()
            final_selections.append(
                {
                    "player": player,
                    "line": threes,
                    "odds": odds
                }
            )
        
        return final_selections
    
    def get_player_rebound_props(self, league='college basketball (m)', game_filter=None):
        if league.lower() != 'college basketball (m)' and league != "nba":
            print("ERROR: league parameter must be 'college basketball (m)', NBA not supported yet")
            return []
        
        filtered_selections = self._parse_league_prop_selections_given_filters(league, 
                                                                               'player rebounds', 
                                                                               prop_type_filter=None, 
                                                                               game_filter=game_filter)
        final_selections = []
        for prop in filtered_selections:
            player = prop['participants'][0]['name']
            threes = prop['label']
            odds = prop['displayOdds'].copy()
            final_selections.append(
                {
                    "player": player,
                    "line": threes,
                    "odds": odds
                }
            )
        
        return final_selections