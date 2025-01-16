from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import stringCommon as sC
from lukhed_basic_utils import listWorkCommon as lC

class DkSportsbook():
    def __init__(self, sport=None, api_delay=0.3):
        # Set API Information
        self.api_delay = api_delay

        'https://sportsbook-nash.draftkings.com/api/sportscontent/dkusmi/v1/leagues/42133'
        'https://sportsbook-nash.draftkings.com/api/sportscontent/navigation/dkusmi/v2/nav/sports?format=json'
        
        # Set cals
        self._api_versions = None
        self._base_url = None
        self.sportsbook = None
        self._load_calibrations()
        
        # Available data
        self.available_sports = None
        self._available_sports = None

        self.sport = sport.lower() if type(sport) is str else None
        self._sport_id = self._get_sport_id(self.sport) if sport is not None else None

        self.available_leagues = None
        self._available_leagues = None
        if self._sport_id is not None:
            self._set_available_leagues()


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

    def _get_json_for_league(self):
        add_url = f'leagues/{self._league_id}'
        url = self._base_url + add_url
        response = self._call_api(url)

        return response
    
    def _get_category_id(self, category):
        category = category.lower()
        for cat in self._league_json['categories']:
            if cat['name'].lower() == category:
                return cat['id']

        print(f"""ERROR: _get_category_id() could not match category Id for {self._league_id}, 
              {category}. You can raise a bug below by copy and pasting this error message.\n\n
                  https://github.com/lukhed/lukhed_sports/issues""")
        
        return None
    
    def _get_sport_id(self, sport):
        sport = sport.lower()
        self._check_set_available_sports()
        if sport in self.available_sports:
            index = self.available_sports.index(sport)
            return self._available_sports[index]['id']
        else:
            print(f"ERROR: Could not find {sport} in valid sports. Try 'get_available_sports()' to see valid sports")
            return None

    def _get_league_data_for_sport(self, s_id):
        api_version = self._api_versions['navVersion']
        url = f"{self._base_url}/sportscontent/navigation/{self.sportsbook}/{api_version}/nav/sports/{s_id}?format=json"
        league_data = self._call_api(url)
        return league_data

    def _set_available_leagues(self):
        league_data = self._get_league_data_for_sport(self._sport_id)
        self.available_leagues = [x['name'] for x in league_data['leagues']]
        self._available_leagues = league_data['leagues']
        
    def set_sport(self, sport):
        self._sport_id = self._get_sport_id(sport)
        if self._sport_id is None:
            self.sport = None
        else:
            self.sport = sport.lower()
            self._set_available_leagues()
            
    def get_available_sports(self):
        self._check_set_available_sports()
        return self.available_sports
    
    def get_available_leagues_for_sport(self, sport):
        """
        Provide a valid sport to check the available leagues available for lines. Use get_available_sports() to 
        get a list of valid sports.

        Parameters
        ----------
        sport : str()
            A valid draftkings sport
        """

        'https://sportsbook-nash.draftkings.com/api/sportscontent/navigation/dkusmi/v2/nav/sports?format=json'

        sport = sport.lower()
        self._check_set_available_sports()
        if sport in self.available_sports:
            s_id = self._get_sport_id(sport)
            league_data = self._get_league_data_for_sport(s_id)
            return [x['name'] for x in league_data['leagues']]
        else:
            print(f"ERROR: Could not find {sport} in valid sports. Try 'get_available_sports()' to see valid sports")
            return []
    
    def get_available_betting_categories(self):
        return self.available_betting_categories

    def get_market_by_category(self, category):
        if category.lower() not in self.available_betting_categories:
            print(f"""ERROR: No betting category {category} available. Use function 
                  get_available_betting_categories() to get a list of available categories. If you are using a 
                  supported category and still getting this error, raise an issue below and paste this error 
                  message.\n\n
                  https://github.com/lukhed/lukhed_sports/issues""")
            return {}

        cat_id = self._get_category_id(category)
        url = f'{self._base_url}leagues/{self._league_id}/categories/{cat_id}'
        response = rC.request_json(url, add_user_agent=True)

        return response['selections']
    
    def set_league(self, league):
        self.league = league.lower()
        self._set_league_data()

    def get_available_leagues(self, match_fuzzy_search_term=None):
        """
        Returns a list of all available leagues. Optionally complete a fuzzy search to 
        narrow down results.

        Parameters
        ----------
        match_fuzzy_search_term : str(), optional
            The term you want to use to search all available leagues. Only leagues that are 
            close to the string provided will be returned. By default None
        """

        stop = 1
