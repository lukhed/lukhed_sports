from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import stringCommon as sC
from lukhed_basic_utils import listWorkCommon as lC

class DkSportsbook():
    def __init__(self, api_delay=0.75):
        # Set API Information
        self.api_delay = api_delay

        # Set cals
        self._api_versions = None
        self._base_url = None
        self.sportsbook = None
        self._load_calibrations()
        
        # Available Sports
        self.available_sports = None
        self._available_sports = None
        self._check_set_available_sports()

        # Cache
        self._cached_available_leagues_json = {}        # available leagues for a given sport cache
        self._cached_league_json = {}                   # league json for a given league
        self._cached_category = None


    def _load_calibrations(self):
        # Load version cal
        version_cal_loc = osC.create_file_path_string(["lukhed_sports", "calibrations", "dk", "apiVersions.json"])
        self._api_versions = fC.load_json_from_file(version_cal_loc)
        self._base_url = self._api_versions['baseUrl']
        self.sportsbook = self._api_versions['defaultSportsbook']
        
    def _check_set_available_sports(self, force_set=False):
        if self.available_sports is None or force_set:
            api_version = self._api_versions['navVersion']
            url = f"{self._base_url}/sportscontent/navigation/{self.sportsbook}/{api_version}/nav/sports?format=json"
            self._available_sports = self._call_api(url)['sports']
            self.available_sports = [x['name'].lower() for x in self._available_sports]

    def _call_api(self, endpoint):
        if self.api_delay is not None:
            tC.sleep(self.api_delay)
        
        print("called api")
        response = rC.request_json(endpoint, add_user_agent=True)
        return response
    
    ############################
    # Class cache management
    ############################
    def _check_available_league_cache(self, sport_id):
        """
        This function tries to utilize saved available leagues for a sport. Useful for users doing multiple 
        queries against the same sport so as to save api calls.


        Parameters
        ----------
        sport_id : str()
            League being requested

        Returns
        -------
        dict()
            Output from self._get_json_for_league() or blank dict {} if no cache
        """

        try:
            available_leagues_json = self._cached_available_leagues_json[sport_id]
        except KeyError:
            available_leagues_json = None
        
        return available_leagues_json
    
    def _get_league_data_for_sport(self, s_id):
        # check cache for id, get from dk if not in cache
        available_leagues_cache = self._check_available_league_cache(s_id)
        if available_leagues_cache is not None:
            # cache is available
            print("Used available league json cache")
            return available_leagues_cache
        else:
            # obtain league json from dk and add to cache
            api_version = self._api_versions['navVersion']
            url = f"{self._base_url}/sportscontent/navigation/{self.sportsbook}/{api_version}/nav/sports/{s_id}?format=json"
            available_leagues = self._call_api(url)
            self._cached_available_leagues_json[s_id] = available_leagues
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
            print("Used league json cache")
            return league_json_cache
        else:
            # obtain league json from dk and add to cache
            api_version = self._api_versions['groupVersion']
            url = f"{self._base_url}/sportscontent/{self.sportsbook}/{api_version}/leagues/{league_id}"
            league_json = self._call_api(url)
            self._cached_league_json[league_id] = league_json

        return league_json
    
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
    # API Parsing
    ############################   
    def _get_sport_id(self, sport):
        """
        Gets the sport ID for a given sport by parsing the self._available_sports variable which is set upon 
        class instantiation.

        sport
          -> league
            -> category
            -> events
            -> markets

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
        self._check_set_available_sports()
        if sport in self.available_sports:
            index = self.available_sports.index(sport)
            return self._available_sports[index]['id']
        else:
            print(f"ERROR: Could not find {sport} in valid sports. Check api.available_sports for valid input.")
            return None
        
    def _get_league_id(self, sport, league):
        """
        Gets the league ID for a given league by checking cache or collecting league id from dk.

        sport
          -> league
            -> category

        Parameters
        ----------
        league : str()
            A league string available for the given sport

        Returns
        -------
        str()
            A league ID corresponding to the given league which is used in API calls.
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
    
    def get_available_leagues(self, sport):
        sport_id = self._get_sport_id(sport)
        league_data = self._get_league_data_for_sport(sport_id)
        return [x['name'].lower() for x in league_data['leagues']]
    
    def _get_data_from_league_json(self, sport, league, key):
        sport = sport.lower()
        league = league.lower()
        key = key.lower()

        league_json = self._get_json_for_league(sport, league)

        # test the key availability
        try:
            league_json[key]
            data = [x['name'].lower() for x in league_json[key]]
        except KeyError:
            data = []
            
        if len(data) == 0:
            print(f"INFO: There are no '{key}' for {sport} - {league}.")

        return data
    

    ############################
    # Core User Facing
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
