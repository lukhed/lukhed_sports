from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import timeCommon as tC
from lukhed_sports.calibrations import endpoint_valid_inputs
from lukhed_sports import gameAnalysis
from lukhed_basic_utils.githubCommon import GithubHelper
import json

"""
Documentation:
    https://sportspagefeeds.com/documentation
"""

class SportsPage(GithubHelper):
    def __init__(self, block_over_limit_calls=True, provide_schedule_json=None, config_file_preference='local', 
                 github_project=None, github_config_dir=None, timezone="US/Eastern", block_invalid_requests=True):
        """
        This class is a custom wrapper for the sportspagefeeds API (https://sportspagefeeds.com/documentation). 

        It provides:
        - Management of api key -> You can store api key locally (by default) or with a private github repo 
          so you can use the api efficiently across different hardware.
        - Optionally manage api limits (on by default) 
        - Methods to utilize each endpoint
        - Optionally validate input (on by default), to ensure you do not waste API calls
        - Methods to get valid inputs for each endpoint, as documentation is sparse
        - Methods to parse data returned by basic (non-paid) endpoints 
        

        Parameters:
            block_over_limit_calls (bool, optional): Defaults to True. Note, api limits are only 
                tracked if this is set to True. If you pay for a subscription and know you will not go over limits, 
                you should set this to False for best performance.
            provide_schedule_json (dict, optional): Provide the class the result of the get_games method to utilize 
                the classes parsing functions without needing to call the API. For example: result = get_games() -> 
                store result for later use, then instantiate the class with the result dict to use parsing. 
                Defaults to None.
            config_file_preference (str): 'local' to store your api key in your working directory. 'github' to store 
                your api key in a private github repository. Defaults to 'local'.
            github_project (str, optional): The Github project you setup as a means to store your Github token. 
                Defaults to None, in which case you will be prompted to setup a project.
            github_config_dir (str, optional): Full path to a local directory that contains your local GithubHelper 
                config file (token file). Default is None and the GithubHelper class looks in your working directory 
                for 'lukhedConfig' to get/store the GithubHelper config file.
            block_invalid_requests (bool): If True, input validation features of the class are turned on and the class 
                will only attempt to call the API if you provide valid inputs. If you provide invalid inputs, you 
                will get an error message. Defaults to True.
            timezone (str): str, a valid timezone string. See Python's zoneinfo documentation for valid timezone 
                identifiers: https://docs.python.org/3/library/zoneinfo.html Common examples: 'US/Eastern', 
                'US/Pacific', 'UTC', 'Europe/London'
        """
        self.timezone = timezone
        self._config_dict = {}
        self._config_type = config_file_preference
        if config_file_preference == 'github':
            if github_project is None:
                github_project = 'default'
            super().__init__(project=github_project, repo_name='lukhedConfig', set_config_directory=github_config_dir)
            if not self._check_load_config_from_github():
                self._guided_setup()
        else:
            if not self._check_load_config_from_local():
                self._guided_setup()

        # Authorizatoin
        self.base_url = "https://sportspage-feeds.p.rapidapi.com/"
        self._key = self._config_dict['token']
        self.headers = self._create_headers()

        # API limit tracking
        self.limit_restrict = block_over_limit_calls
        self.stop_calls = False
        self.tracker_file_name = "sportsPageTracker.json"
        self.tracker_dict = {}
        if self.limit_restrict:
            self._load_tracker_json_from_file()
        
        # Various configs
        self.block_invalid_requests = block_invalid_requests
        self.valid_leagues = endpoint_valid_inputs.leagues
        self.valid_game_statuses = endpoint_valid_inputs.game_status
        self.working_schedule = provide_schedule_json

    def _check_load_config_from_github(self):
        if self.file_exists("sportsPageConfig.json"):
            self._config_dict = self.retrieve_file_content("sportsPageConfig.json")
            return True
        else:
            return False
            
    def _check_load_config_from_local(self):
        config_path = osC.check_create_dir_structure(['lukhedConfig'], return_path=True)
        config_file = osC.append_to_dir(config_path, "sportsPageConfig.json")
        if osC.check_if_file_exists(config_file):
            self._config_dict = fC.load_json_from_file(config_file)
            return True
        else:
            return False
        
    def _guided_setup(self):
        confirm = input((f"You do not have an API key stored. Do you want to go through setup? (y/n)"))
        if confirm != 'y':
            print("OK, Exiting...")

        if self._config_type == 'github':
            input(("\n1. Starting setup\n"
                "The sportspage key you provide in this setup will be stored on a private github repo: "
                "'lukhedConfig/sportsPageConfig.json. "
                "\nPress enter to continue"))
        else:
            input(("\n1. Starting setup\n"
                "The sportspage key you provide in this setup will be stored locally at: "
                "'lukhedConfig/sportsPageConfig.json. "
                "\nPress enter to continue"))
            
        token = input("\n2. Copy and paste your sports page token below. You can obtain a free token here: "
                      "https://rapidapi.com/SportspageFeeds/api/sportspage-feeds/pricing :\n")
        token = token.replace(" ", "")
        token_dict = {"token": token}

        if self._config_type == 'github':
            self.create_update_file("sportsPageConfig.json", token_dict, message='created config file for SportsPage')
            self._config_dict = token_dict
            return True
        else:
            fC.dump_json_to_file(osC.create_file_path_string(['lukhedConfig', 'sportsPageConfig.json']), token_dict)
            self._config_dict = token_dict
            return True
        
    def _parse_date_input(self, date_start, date_end, date_format="%Y-%m-%d"):
        if date_start is None and date_end is None:
            return None
        elif date_start is not None and date_end is None:
            return tC.convert_date_format(date_start, from_format=date_format, to_format="%Y-%m-%d")
        elif date_start is not None and date_end is not None:
            ds = tC.convert_date_format(date_start, from_format=date_format, to_format="%Y-%m-%d")
            de = tC.convert_date_format(date_end, from_format=date_format, to_format="%Y-%m-%d")
            return ds + "," + de

    def _create_headers(self):
        headers = {
            'x-rapidapi-host': "sportspage-feeds.p.rapidapi.com",
            'x-rapidapi-key': self._key
        }

        return headers

    def _update_tracker_json_file(self):
        if self._config_type == 'github':
            self.create_update_file(self.tracker_file_name, self.tracker_dict, message='Updating api usage')
        else:
            fC.dump_json_to_file(osC.create_file_path_string(['lukhedConfig', self.tracker_file_name]), 
                                 self.tracker_dict)
    
    def _update_limit_tracker(self, response, call_time):
        sports_page_limit = int(response.headers["X-RateLimit-Sportspage-Limit"])
        sports_page_remaining = int(response.headers["x-rateLimit-sportspage-remaining"])
        sports_page_reset_in_seconds = int(response.headers["x-ratelimit-sportspage-reset"])
        reset_stamp = tC.add_seconds_to_time_stamp(call_time, sports_page_reset_in_seconds)
        self.tracker_dict = {
            "limit": sports_page_limit,
            "remaining": sports_page_remaining,
            "resetTime": reset_stamp,
            "lastCall": call_time
        }

        self._update_tracker_json_file()

    def _load_tracker_json_from_file(self):
        if self._config_type == 'github':
            if self.file_exists(self.tracker_file_name):
                self.tracker_dict = self.retrieve_file_content(self.tracker_file_name)
            else:
                self.tracker_dict = {}
        else:
            local_path = osC.create_file_path_string(['lukhedConfig', self.tracker_file_name])
            if osC.check_if_file_exists(local_path):
                self.tracker_dict = fC.load_json_from_file(local_path)
            else:
                self.tracker_dict = {}

        self._check_reset_current_limit()
    
    def _check_reset_current_limit(self):
        """
        This function checks the current limit and reset time to see if the limit should be reset based on the 
        last logged reset time.

        Returns the reamining limit for the user.
        """

        if self.tracker_dict == {}:
            return None
        else:
            # check if limit was reset since last use
            time_now = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            reset_time = self.tracker_dict["resetTime"]
            reset_seconds = tC.subtract_time_stamps(reset_time, time_now, time_format='%Y%m%d%H%M%S')

            if reset_seconds < 0:
                # reset the limit
                self.tracker_dict["reamining"] = self.tracker_dict["limit"]

            return self.tracker_dict["remaining"]
 
    def _parse_provide_schedule_input(self, provide_schedule_input):
        if provide_schedule_input is None:
            return self.working_schedule
        else:
            return provide_schedule_input

    
    #####################
    # Endpoints
    #####################
    def _valid_request_check(self, league=None, odds_type_filter=None, status_filter=None, conference=None, 
                             division=None):
        error_dict = {"validInputs": True}

        # League input check
        error_dict.update(self._valid_league_input(league))
        if error_dict['leagueError']:
            error_dict['validInputs'] = False

        # Status filter check
        error_dict.update(self._valid_status_filter(status_filter))
        if error_dict['statusFilterError']:
            error_dict['validInputs'] = False

        # Conference check
        error_dict.update(self._valid_conference(league, conference))
        if error_dict['conferenceError']:
            error_dict['validInputs'] = False

        return error_dict
    
    def _valid_league_input(self, league_input):
        if league_input is None:
            return {"leagueError": False}
        else:
            if league_input.lower() in self.valid_leagues:
                return {"leagueError": False}
            else:
                self._add_print_bar()
                print(f"ERROR: '{league_input}' is not a valid league. Not calling the API. Valid league codes are:\n"
                      f"{self.valid_leagues}\n")
                self._add_valid_input_error_message()
                self._add_print_bar()
                return {"leagueError": True}
    
    def _valid_status_filter(self, status_filter):
        if status_filter is None:
            return {"statusFilterError": False}
        else:
            if status_filter.lower() in self.valid_game_statuses:
                return {"statusFilterError": False}
            else:
                self._add_print_bar()
                print(f"ERROR: '{status_filter}' is not a valid game status. Not calling the API. Valid statuses are:\n"
                      f"{self.valid_game_statuses}\n")
                self._add_valid_input_error_message()
                self._add_print_bar()
                return {"statusFilterError": True}
            
    def _valid_conference(self, league, conference):
        if conference is None:
            return {"conferenceError": False}
        elif league is None and conference is not None:
            self._add_print_bar()
            print(f"ERROR: '{conference}' is not a valid conference for league 'None'. Not calling the API. "
                  "You need to specify a league to utilize the conference filter "
                  "Instantiate class with 'block_invalid_requests' = False to ignore this error and call API.")
            self._add_print_bar()
            return {"conferenceError": True}
        elif league is None and conference is None:
            return {"conferenceError": False}
        else:
            valid_conferences = endpoint_valid_inputs.conferences[league.lower()]
            if conference.lower() in valid_conferences:
                return {"conferenceError": False}
            else:
                self._add_print_bar()
                print(f"ERROR: '{conference}' is not a valid conference in league '{league}'. Not calling the API. "
                      f"Valid conferences in '{league}' are:\n"
                      f"{valid_conferences}\n")
                self._add_valid_input_error_message()
                self._add_print_bar()
                      
                return {"conferenceError": True}
    
    @staticmethod
    def _add_print_bar():
        print("*****************************")
    
    def _add_valid_input_error_message(self):
        print(f"Valid inputs were last updated on {endpoint_valid_inputs.valid_input_last_update}. If you " 
              f"are getting this message in error, instantiate class with block_invalid_requests=False to "
              "ignore this error and call API. Open an issue here:\n"
              "https://github.com/lukhed/lukhed_sports/issues.")
        
    def _check_stop_calls_based_on_limit(self):
        if not self.limit_restrict:
            # User does not want to check limits
            self.stop_calls = False
            return False
        
        if self.tracker_dict == {}:
            # No API calls yet while using class tracking, so we do not know limit.
            self.stop_calls = False
            return False
        else:
            # Get last logged api limits
            remaining_calls = self._check_reset_current_limit()

            if remaining_calls > 0:
                # Still have calls left in limit, don't block
                self.stop_calls = False
                return False

            else:
                # No more calls left with current plan
                self.stop_calls = True
                print("ERROR: Cannot call API as you have reached your limit. "
                        "Instantiate class with 'block_over_limit_calls' = False to pay for the call")
                return True
    
    def get_games(self, league=None, date_start=None, date_end=None, date_format="%Y-%m-%d", odds_type_filter=None, 
                  status_filter=None, skip=None, conference=None, division=None, team=None):
        """
        Wrapper for 'Games' endpoint. https://sportspagefeeds.com/documentation#games. Returns schedule data for 
        given date and sets the class working schedule to the data retrieved for further parsing.

        Parameters
        ----------
        league : _type_, optional
            _description_, by default None
        date_start : _type_, optional
            _description_, by default None
        date_end : _type_, optional
            _description_, by default None
        date_format : str, optional
            _description_, by default "%Y-%m-%d"
        odds_type_filter : _type_, optional
            _description_, by default None
        status_filter : _type_, optional
            _description_, by default None
        skip : _type_, optional
            _description_, by default None
        conference : _type_, optional
            _description_, by default None
        division : _type_, optional
            _description_, by default None
        team : _type_, optional
            _description_, by default None

        Returns
        -------
        _type_
            _description_
        """        
       
        # Input Check
        error_check = self._valid_request_check(league=league, odds_type_filter=odds_type_filter, 
                                                status_filter=status_filter, conference=conference, division=division)
        if self.block_invalid_requests and not error_check['validInputs']:
            return error_check
        
        # Build Request
        endpoint_url = self.base_url + "games"
        date_input = self._parse_date_input(date_start, date_end, date_format)
        querystring = {"league": league, "date": date_input, "skip": skip, "conference": conference, "team": team, 
                       "division": division, "type": odds_type_filter}

        # Call API
        if self._check_stop_calls_based_on_limit():
            return None
        else:
            call_time = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            rapid_response = rC.make_request(endpoint_url, headers=self.headers, params=querystring)
            if self.limit_restrict:
                self._update_limit_tracker(rapid_response, call_time)
            schedule = json.loads(rapid_response.text)
            self.working_schedule = schedule
            return schedule

    def get_rankings(self, league):
        """
        Wrapper for 'Rankings' endpoint. https://sportspagefeeds.com/documentation#rankings
        
        Gets rankings data for the specified league.

        Parameters
        ----------
        league : str
            The league code to get rankings for. Use info_get_valid_league_codes() to see valid options.

        Returns
        -------
        dict
            A dictionary containing the rankings data for the specified league, or error dict if invalid input.
        """
        
        # Input check
        error_check = self._valid_request_check(league=league)
        if self.block_invalid_requests and not error_check['validInputs']:
            return error_check
        
        # Build request
        endpoint_url = self.base_url + "rankings"
        querystring = {"league": league}

        if self._check_stop_calls_based_on_limit():
            return None
        else:
            call_time = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            rapid_response = rC.make_request(endpoint_url, headers=self.headers, params=querystring)
            if self.limit_restrict:
                self._update_limit_tracker(rapid_response, call_time)
            result = json.loads(rapid_response.text)
            return result

    def get_teams(self, league, division=None, conference=None):
        """
        Wrapper for 'Teams' endpoint. https://sportspagefeeds.com/documentation#teams
        
        Gets team data for the specified league with optional division and conference filters.

        Parameters
        ----------
        league : str
            The league code to get teams for. Use info_get_valid_league_codes() to see valid options.
        division : str, optional
            Filter teams by division, by default None
        conference : str, optional
            Filter teams by conference, by default None

        Returns
        -------
        dict
            A dictionary containing the team data for the specified league, or error dict if invalid input.
        """
        
        # Input check
        error_check = self._valid_request_check(league=league, conference=conference, division=division)
        if self.block_invalid_requests and not error_check['validInputs']:
            return error_check
        
        # Build request
        endpoint_url = self.base_url + "teams"
        querystring = {"league": league, "division": division, "conference": conference}

        if self._check_stop_calls_based_on_limit():
            return None
        else:
            call_time = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            rapid_response = rC.make_request(endpoint_url, headers=self.headers, params=querystring)
            if self.limit_restrict:
                self._update_limit_tracker(rapid_response, call_time)
            result = json.loads(rapid_response.text)
            return result
    
    def get_conferences(self, league):
        """
        Wrapper for 'Conferences' endpoint. https://sportspagefeeds.com/documentation#conferences
        
        Gets conference data for the specified league.

        Parameters
        ----------
        league : str
            The league code to get conferences for. Use info_get_valid_league_codes() to see valid options.

        Returns
        -------
        dict
            A dictionary containing the conference data for the specified league, or error dict if invalid input.
        """
        
        endpoint_url = self.base_url + "conferences"

        # Input check
        error_check = self._valid_request_check(league=league)
        if self.block_invalid_requests and not error_check['validInputs']:
            return error_check
        
        querystring = {"league": league}

        if self._check_stop_calls_based_on_limit():
            return None
        else:
            call_time = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            rapid_response = rC.make_request(endpoint_url, headers=self.headers, params=querystring)
            if self.limit_restrict:
                self._update_limit_tracker(rapid_response, call_time)
            result = json.loads(rapid_response.text)
            return result
        
    def get_game_by_id(self, game_id):
        """
        Wrapper for 'Game by ID' endpoint. https://sportspagefeeds.com/documentation#game-by-id
        
        Gets detailed game data for a specific game ID.

        Parameters
        ----------
        game_id : str or int
            The unique game identifier to retrieve data for.

        Returns
        -------
        dict
            A dictionary containing detailed game data for the specified game ID.
        """
        
        endpoint_url = self.base_url + "gameById"
        querystring = {"gameId": game_id}
        if self._check_stop_calls_based_on_limit():
            return None
        else:
            call_time = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            rapid_response = rC.make_request(endpoint_url, headers=self.headers, params=querystring)
            if self.limit_restrict:
                self._update_limit_tracker(rapid_response, call_time)
            result = json.loads(rapid_response.text)
            return result
    
    def get_odds(self, game_id, odds_type_filter=None):
        """
        Wrapper for 'Odds' endpoint. https://sportspagefeeds.com/documentation#odds
        
        Gets odds data for a specific game. Note: This endpoint requires a paid subscription.

        Parameters
        ----------
        game_id : str or int
            The unique game identifier to retrieve odds for.
        odds_type_filter : str, optional
            Filter for specific odds type, by default None

        Returns
        -------
        dict
            A dictionary containing odds data for the specified game, or error message for free tier users.
        """
        
        endpoint_url = self.base_url + "odds"
        querystring = {"gameId": game_id, "type": odds_type_filter}

        if self._check_stop_calls_based_on_limit():
            return None
        else:
            call_time = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            rapid_response = rC.make_request(endpoint_url, headers=self.headers, params=querystring)
            if self.limit_restrict:
                self._update_limit_tracker(rapid_response, call_time)
            result = json.loads(rapid_response.text)
            return result
        
    
    #####################
    # API Info
    #####################
    def info_get_valid_league_codes(self):
        """
        Display and return valid league codes that can be used with API endpoints.

        Returns
        -------
        list
            A list of valid league codes.
        """
        print(f"Valid league codes are:\n{self.valid_leagues}")
        return self.valid_leagues
    
    def info_get_valid_status_filters(self):
        """
        Display and return valid game status filters that can be used with API endpoints.

        Returns
        -------
        list
            A list of valid game status filters.
        """
        print(f"Valid status filters are:\n{self.valid_game_statuses}")
        return self.valid_game_statuses


    #####################
    # Schedule Parsing
    #####################
    def is_schedule_valid(self, provide_schedule_json=None):
        """
        Check if the provided or working schedule data is valid based on API response status.

        Parameters
        ----------
        provide_schedule_json : dict, optional
            Schedule data to validate. If None, uses the class working schedule, by default None

        Returns
        -------
        bool or None
            True if schedule is valid (status 200), False if invalid, None if no schedule available.
        """        
        use_schedule = self._parse_provide_schedule_input(provide_schedule_json)
        if use_schedule is None:
            print("ERROR: No schedule to check if valid")
            return None

        if use_schedule['status'] == 200:
            return True
        else:
            return False
    
    def get_games_within_specified_minutes(self, minutes, provide_schedule_json=None):
        """
        If a game is to start within the specified minutes, it will be returned in a list. For example, if a game
        starts in 10 minutes and the minutes parameter is 10, then it is considered within the specified time and so
        it will be returned.

        :param minutes:
        :param provide_schedule_json:
        :return:                                list(),
        """
        use_schedule = self._parse_provide_schedule_input(provide_schedule_json)
        if use_schedule is None:
            print("ERROR: No schedule to filter")
            return None

        time_now = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
        game_times = [tC.convert_non_python_format(x['schedule']['date'], time_zone=self.timezone, 
                                                   single_output_format="%Y%m%d%H%M%S") for x 
                                                   in use_schedule['results']]

        differences = [tC.subtract_time_stamps(x, time_now, time_format="%Y%m%d%H%M%S", detailed=False) // 60 
                       for x in game_times]

        games_meeting_criteria = []
        i = 0
        
        while i < len(differences):
            if 0 <= differences[i] <= minutes:
                games_meeting_criteria.append(use_schedule['results'][i])

            i = i + 1

        return games_meeting_criteria

    def get_total_games_in_schedule(self, provide_schedule_json=None):
        """
        Get the total number of games in the provided or working schedule.

        Parameters
        ----------
        provide_schedule_json : dict, optional
            Schedule data to count games from. If None, uses the class working schedule, by default None

        Returns
        -------
        int
            The total number of games in the schedule, or 0 if no schedule available.
        """
        use_schedule = self._parse_provide_schedule_input(provide_schedule_json)
        if use_schedule is None:
            print("ERROR: No schedule to check if valid")
            return 0

        return use_schedule['games']

    def get_games_list_from_schedule(self, provide_schedule_json=None):
        """
        Extract the games list from the provided or working schedule data.

        Parameters
        ----------
        provide_schedule_json : dict, optional
            Schedule data to extract games from. If None, uses the class working schedule, by default None

        Returns
        -------
        list
            A list of game dictionaries from the schedule, or empty list if no schedule available.
        """
        use_schedule = self._parse_provide_schedule_input(provide_schedule_json)
        if use_schedule is None:
            print("ERROR: No schedule to check if valid")
            return []

        return use_schedule['results']
    
    def get_times_until_game_starts(self, provide_schedule_json=None):
        """
        Goes through each game in the schedule and provides the amount of time until the game starts.

        Parameters
        ----------
        provide_schedule_json : dict, optional
            Provide the function the result of the get_games method to utilize the classes parsing functions 
            without needing to call the API. For example: result = get_games() -> store result for later use, 
            then pass the result dict to use this parsing. Defaults to None.

        Returns
        -------
        dict
            A dictionary containing the time until each game starts.
        """
        use_schedule = self._parse_provide_schedule_input(provide_schedule_json)
        if use_schedule is None:
            print("ERROR: No schedule to filter")
            return None

        time_now = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
        game_times = [tC.convert_non_python_format(x['schedule']['date'], time_zone=self.timezone, 
                                                   single_output_format="%Y%m%d%H%M%S") for x 
                                                   in use_schedule['results']]

        differences = [tC.subtract_time_stamps(x, time_now, time_format="%Y%m%d%H%M%S", detailed=True) 
                       for x in game_times]
        
        output = []
        i = 0
        while i < len(differences):
            full_dict = differences[i].copy()
            full_dict['game'] = use_schedule['results'][i]['summary']
            full_dict['gameData'] = use_schedule['results'][i].copy()
            output.append(full_dict)
            i = i + 1

        return output

    #####################
    # Game Dict Parsing
    #####################
    @staticmethod
    def parse_matchup_details(game_dict):
        """
        Parses a single game's dictionary data to extract core matchup details including teams, odds, and timestamps.

        Parameters
        ----------
        game_dict : dict
            The dictionary containing game details.

        Returns
        -------
        dict
            A dictionary containing the parsed matchup details.
        """
        op_dict = dict()

        teams_dict = game_dict['teams']
        odds_dict = game_dict.get('odds', "N/A")

        op_dict = dict()

        teams_dict = game_dict['teams']
        odds_dict = game_dict.get('odds', "N/A")

        if odds_dict != "N/A":
            odds_dict = game_dict['odds'][0]
            spread_details = odds_dict.get('spread', "N/A")
            moneyline_details = odds_dict.get('moneyline', "N/A")
            total_details = odds_dict.get('total', "N/A")
            open_date = odds_dict.get('openDate', "N/A")
            last_updated = odds_dict.get('lastUpdated', "N/A")
        else:
            spread_details = {"open": {"away": "N/A", "home": "N/A", "awayOdds": "N/A", "homeOdds": "N/A"},
                            "current": {"away": "N/A", "home": "N/A", "awayOdds": "N/A", "homeOdds": "N/A"}}
            moneyline_details = {"open": {"awayOdds": "N/A", "homeOdds": "N/A"},
                                "current": {"awayOdds": "N/A", "homeOdds": "N/A"}}
            total_details = {"open": {"total": "N/A", "overOdds": "N/A", "underOdds": "N/A"},
                            "current": {"total": "N/A", "overOdds": "N/A", "underOdds": "N/A"}}
            open_date = "N/A"
            last_updated = "N/A"

        away_team_dict = teams_dict.get('away', "N/A")
        home_team_dict = teams_dict.get('home', "N/A")

        if open_date != "N/A":
            open_date = tC.convert_non_python_format(open_date, time_zone="US/Eastern", single_output_format=None)

        if last_updated != "N/A":
            last_updated = tC.convert_non_python_format(last_updated, time_zone="US/Eastern", single_output_format=None)

        if type(spread_details) == str:
            spread_details = {"open": {"away": "N/A", "home": "N/A", "awayOdds": "N/A", "homeOdds": "N/A"},
                            "current": {"away": "N/A", "home": "N/A", "awayOdds": "N/A", "homeOdds": "N/A"}}

        if type(moneyline_details) == str:
            moneyline_details = {"open": {"awayOdds": "N/A", "homeOdds": "N/A"},
                                "current": {"awayOdds": "N/A", "homeOdds": "N/A"}}

        if type(total_details) == str:
            total_details = {"open": {"total": "N/A", "overOdds": "N/A", "underOdds": "N/A"},
                            "current": {"total": "N/A", "overOdds": "N/A", "underOdds": "N/A"}}

        op_dict = {
            'awayTeam': away_team_dict,
            'homeTeam': home_team_dict,
            'spreadDetails': spread_details,
            'moneylineDetails': moneyline_details,
            'totalDetails': total_details,
            'openTime': open_date['datetime_object'],
            'lastUpdated': last_updated['datetime_object']
        }

        return op_dict

    @staticmethod
    def parse_result_details(game_dict):
        op_dict = dict()

        scoreboard_dict = game_dict.get('scoreboard', "N/A")

        if scoreboard_dict != "N/A":
            score_dict = scoreboard_dict.get('score', "N/A")
            current_period = scoreboard_dict.get('currentPeriod', "N/A")
            time_remaining = scoreboard_dict.get('periodTimeRemaining', "N/A")
        else:
            score_dict = "N/A"
            current_period = "N/A"
            time_remaining = "N/A"

        op_dict = {
            'score': score_dict,
            'currentPeriod': current_period,
            'periodTimeRemaining': time_remaining
        }

        return op_dict
    
    @staticmethod
    def get_conference_given_game_dict(playing, game_dict):
        """
        Returns the conference of the away or home team specified in playing parameter.

        Parameters
        ----------
        playing : str
            "away" or "home" to specify which team's conference to return.
        game_dict : dict
            A single game's dictionary data from the schedule.

        Returns
        -------
        str
            The conference of the given team
        """
        playing = playing.lower()
        try:
            return game_dict['teams'][playing]['conference']
        except KeyError:
            return "N/A"

    def get_final_result_basics_dict(self, game_dict):
        """
        Parses a single game's dictionary data to extract final result basics including scores, spreads, totals, 
        and ATS analysis.

        Parameters
        ----------
        game_dict : dict
            A single game's dictionary data from the schedule.

        Returns
        -------
        dict
            A dictionary containing the final result basics.
        """

        game_details = self.parse_matchup_details(game_dict)
        game_results = self.parse_result_details(game_dict)

        if game_dict['status'] == "canceled":
            away_score = "n/a"
            home_score = "n/a"
        else:
            away_score = game_results["score"]["away"]
            home_score = game_results["score"]["home"]
        home_spread = game_details["spreadDetails"]["current"]["home"]
        total = game_details["totalDetails"]["current"]["total"]

        ats_analysis = gameAnalysis.calculate_ats_data_for_game(away_score, home_score, home_spread, total)

        try:
            score_diff = abs(away_score - home_score)
        except TypeError:
            score_diff = "n/a"

        try:
            cov_by_abs = abs(ats_analysis["awayCoverBy"])
        except TypeError:
            cov_by_abs = "n/a"

        try:
            tot_by_abs = abs(ats_analysis["underCoverBy"])
        except TypeError:
            tot_by_abs = "n/a"

        try:
            away_moneyline = game_details["moneylineDetails"]["current"]["awayOdds"]
        except KeyError:
            away_moneyline = "n/a"

        try:
            home_moneyline = game_details["moneylineDetails"]["current"]["homeOdds"]
        except KeyError:
            home_moneyline = "n/a"

        op_game_dict = {
            "awayTeam": game_details["awayTeam"]["abbreviation"],
            "homeTeam": game_details["homeTeam"]["abbreviation"],
            "awayTeamFull": game_dict['teams']['away']['team'],
            "homeTeamFull": game_dict['teams']['home']['team'],
            "awaySpread": game_details["spreadDetails"]["current"]["away"],
            "awayOdds": game_details["spreadDetails"]["current"]["awayOdds"],
            "homeSpread": home_spread,
            "homeOdds": game_details["spreadDetails"]["current"]["homeOdds"],
            "total": total,
            "totalPointsScored": home_score + away_score,
            "overOdds": game_details["totalDetails"]["current"]["overOdds"],
            "underOdds": game_details["totalDetails"]["current"]["underOdds"],
            "awayScore": away_score,
            "homeScore": home_score,
            "gameWinner": ats_analysis["winner"],
            "atsWinner": ats_analysis["atsWinner"],
            "awayAtsResult": ats_analysis["awayAtsGrade"],
            "homeAtsResult": ats_analysis["homeAtsGrade"],
            "awayTeamCoverBy": ats_analysis["awayCoverBy"],
            "homeTeamCoverBy": ats_analysis["homeCoverBy"],
            "totalWinner": ats_analysis["totalGrade"],
            "underCoverBy": ats_analysis["underCoverBy"],
            "overCoverBy": ats_analysis["overCoverBy"],
            "scoreDifferenceAbsoluteValue": score_diff,
            "atsCoverByAbsoluteValue": cov_by_abs,
            "totalCoverByAbsoluteValue": tot_by_abs,
            "awayMoneyline": away_moneyline,
            "homeMoneyline": home_moneyline
        }

        return op_game_dict

    
    #####################
    # API Settings
    #####################
    def check_api_limit(self):
        """
        Check and display current API usage statistics including remaining calls, reset time, and limit.
        
        Only available when block_over_limit_calls is True during class instantiation.

        Returns
        -------
        None
            Prints API limit information to console.
        """
        if self.limit_restrict:
            if self.tracker_dict == {}:
                print("INFO: No api limit data available. Have you made a call to the api yet with this class?")
            else:
                print((f"You have {self.tracker_dict['remaining']} api calls remaining\n"
                       f"Your reset time is set for {self.tracker_dict['resetTime']} {self.timezone}\n"
                       f"Your limit is {self.tracker_dict['limit']}"))
        
            self.tracker_dict
        else:
            print("Feature only available if 'block_over_limit_calls' is set to True when instantiating the class")

    def change_timezone(self, new_timezone):
        """
        Change the timezone used by the class for any functions that utilize timezone.

        :param new_timezone:         str, a valid timezone string. See Python's zoneinfo documentation for valid 
                                     timezone identifiers: https://docs.python.org/3/library/zoneinfo.html
                                     Common examples: 'US/Eastern', 'US/Pacific', 'UTC', 'Europe/London'
        :return:                     None
        """
        self.timezone = new_timezone