from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import stringCommon as sC
from lukhed_basic_utils import listWorkCommon as lC

class DkSportsbook():
    def __init__(self, api_delay=1.5, use_local_cache=True, reset_cache=False, retry_delay=2):
        # Set API Information
        self.api_delay = api_delay
        self.retry_delay = retry_delay

        # Set cals
        self._api_versions = None
        self._base_url = None
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
        version_cal_loc = osC.create_file_path_string(["lukhed_sports", "calibrations", "dk", "apiVersions.json"])
        self._api_versions = fC.load_json_from_file(version_cal_loc)
        self._base_url = self._api_versions['baseUrl']
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
            self._available_sports = self._call_api(url)['sports']
            if self.use_cache:
                fC.dump_json_to_file(self._sports_cache_file, self._available_sports)

        self.available_sports = [x['name'].lower() for x in self._available_sports]
            
    def _call_api(self, endpoint):
        retry_count = 3
        if self.api_delay is not None:
            tC.sleep(self.api_delay)

        while retry_count > 0:
            print(f"called api: {endpoint}")
            response = rC.request_json(endpoint, add_user_agent=True, timeout=1)
            if response == {}:
                print("Sleeping then retrying api call")
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
            available_leagues = self._call_api(url)
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
            league_json = self._call_api(url)
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
            _description_
        markets : _type_
            _description_
        selections : _type_
            _description_
        team : _type_
            _description_
        filter_market : _type_
            _description_
        filter_team : _type_
            _description_
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
    
    def _build_url_for_category(self, sport, league, category_string):
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
    def get_available_leagues(self, sport):
        sport_id = self._get_sport_id(sport)
        league_data = self._get_league_data_for_sport(sport_id)
        return [x['name'].lower() for x in league_data['leagues']]

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
        selections = self._call_api(url)['selections']
        
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
    

    ############################
    # Core Betting Data Methods
    ############################
    @staticmethod
    def _major_league_to_sport_mapping(league):
        mapping = {
            "nfl": "football",
            "college football": "football",
            "nba": "basketball",
            "nhl": "hockey",
            "mlb": "baseball"
        }
        league = league.lower()
        try:
            return mapping[league]
        except KeyError:
            return None
        
    def get_gamelines_for_game(self, league, team, filter_market=None, filter_team=False):
        team = team.lower()
        
        sport = self._major_league_to_sport_mapping(league)
        if sport is None:
            print(f"ERROR: '{league}' is not supported by this method. (supported: nfl, nhl, mlb, nba)")
            return []
        
        # parse team
        found_game = self._find_game_by_team_from_events(sport, league, team)
        if found_game is None:
            return []

        # call the api
        url = self._build_url_for_category(sport, league, 'game lines')
        game_lines = self._call_api(url)

        # parse the result
        event_id = found_game[0]['id']
        gameline_data = self._parse_gameline_selections_given_filters(event_id, game_lines['markets'], 
                                                                      game_lines['selections'], 
                                                                      team, filter_market, filter_team)

        return gameline_data
    
    def get_half_lines_for_game(self, league, team, filter_market=None, filter_team=False):
        sport = self._major_league_to_sport_mapping(league)
        if sport is None or sport == 'nhl' or sport == 'mlb':
            print(f"ERROR: '{league}' is not supported by this method. (supported: nfl, nba)")
            return []
        
        # parse team
        found_game = self._find_game_by_team_from_events(sport, league, team)
        if found_game is None:
            return []
        
        # call the api
        url = self._build_url_for_category(sport, league, 'halves')
        half_lines = self._call_api(url)
        
        # parse the result
        event_id = found_game[0]['id']
        half_line_data = self._parse_gameline_selections_given_filters(event_id, half_lines['markets'], 
                                                                       half_lines['selections'], 
                                                                       team, filter_market, filter_team)

        return half_line_data
    
    def get_touchdown_scorer_props(self):
        selections = self.get_betting_selections_by_category('football', 'nfl', 'td scorers')
        return selections
    
