from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import listWorkCommon as lC

class DkSportsbook():
    def __init__(self, league, api_delay=0.3):
        # Set API Information
        self.api_delay = api_delay
        self._api = 'v1'
        self._base_url = f'https://sportsbook-nash.draftkings.com/api/sportscontent/dkusmi/{self._api}/'

        # Set League Information
        self.league = league.lower()
        self._league_id = None
        self._league_json = {}
        self.available_betting_categories = []
        self._set_league_data()
    
    def _set_league_data(self):
        self._league_id = self._get_league_id()
        self._league_json = self._get_json_for_league()
        self.available_betting_categories = [x['name'].lower() for x in self._league_json['categories']]
    
    def _call_api(self, endpoint):
        if self.api_delay is not None:
            tC.sleep(self.api_delay)
        
        response = rC.request_json(endpoint, add_user_agent=True)
        return response
    
    def _get_league_id(self):
        """
        :return: the string used in the url for retrieving odds data
        """
        sport_cal = osC.create_file_path_string(['lukhed_sports', 'calibrations', 'dk', 'sports_reference.json'])
        groups = fC.load_json_from_file(sport_cal)['data']
        group_names = [x['eventGroupInfos'][0]['nameIdentifier'].lower() for x in groups]
        
        try:
            index = group_names.index(self.league)
        except ValueError:
            print(f"""ERROR: Could not find DK data for league={self.league}. Use function 
                  'get_supported_leagues()' to get a current list of working leagues. If you still get 
                  an error while using a supported league, make a bug below and paste this error message.\n
                  https://github.com/lukhed/lukhed_sports/issues""")
            quit()

        return groups[index]['eventGroupInfos'][0]['eventGroupId']

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
    
    def change_league(self, league):
        self.league = league.lower()
        self._set_league_data()
