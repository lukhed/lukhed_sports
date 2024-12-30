import math
from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils.githubCommon import GithubHelper
from . import gameAnalysis
import json

"""
Documentation:
    https://sportspagefeeds.com/documentation
"""


# to do:
# more details for final games of sports other than football

class SportsPage(GithubHelper):
    def __init__(self, block_over_limit_calls=True, provide_schedule_json=None, config_file_preference='local', 
                 github_project=None, github_config_dir=None):
        """_summary_

        Args:
            block_over_limit_calls (bool, optional): _description_. Defaults to True. Note, api limits are only 
                tracked if this is set to True. If you pay for a subscription and know you will not go over limits, 
                you should set this to False for best performance.
                performance.
            provide_schedule_json (_type_, optional): _description_. Defaults to None.
            config_file_preference (str, optional): _description_. Defaults to 'local'.
            github_project (_type_, optional): _description_. Defaults to None.
            github_config_dir (_type_, optional): _description_. Defaults to None.
        """
        
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

        self._key = self._config_dict['token']
        self.headers = self._create_headers()
        self.limit_restrict = block_over_limit_calls
        self.tracker_dict = {}
        self.tracker_file_name = "sportsPageTracker.json"
        self.stop_calls = False

        self.today = tC.create_timestamp("%Y-%m-%d")
        self.base_url = "https://sportspage-feeds.p.rapidapi.com/games"
        
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
            return self.today
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
    
    def _check_stop_calls_based_on_limit(self):
        if self.tracker_dict == {}:
            self._load_tracker_json_from_file()

        if self.tracker_dict == {}:
            self.stop_calls = False
        else:
            time_now = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            remaining = self.tracker_dict["remaining"]
            reset_time = self.tracker_dict["resetTime"]

            reset_dict = tC.subtract_time_stamps(reset_time, time_now, time_format='%Y%m%d%H%M%S', detailed=True)

            if reset_dict["seconds"] <= 0:
                self.stop_calls = False
            else:
                if remaining == 0:
                    self.stop_calls = True
                else:
                    self.stop_calls = False

    def _parse_provide_schedule_input(self, provide_schedule_input):
        if provide_schedule_input is None:
            return self.working_schedule
        else:
            return provide_schedule_input

    def get_schedule(self, sport, date_start=None, date_end=None, date_format="%Y-%m-%d"):
        """
        Returns schedule data for given date. Also sets the class working schedule to the data retrieved.

        :param sport:
        :param date_start:
        :param date_end:
        :param date_format:
        :return:
        """
        sport = sport.lower()
        date_input = self._parse_date_input(date_start, date_end, date_format)
        querystring = {"league": sport, "date": date_input}

        if self.limit_restrict:
            self._check_stop_calls_based_on_limit()

        if self.stop_calls:
            print("ERROR: Cannot call API as you have reached your limit. "
                  "Instantiate class with 'block_over_limit_calls' = False to pay for the call")
            return None
        else:
            call_time = tC.create_timestamp(output_format="%Y%m%d%H%M%S")
            rapid_response = rC.make_request(self.base_url, headers=self.headers, params=querystring)
            if self.limit_restrict:
                self._update_limit_tracker(rapid_response, call_time)
            schedule = json.loads(rapid_response.text)
            self.working_schedule = schedule
            return schedule

    def check_if_all_games_complete(self):
        use_schedule = self.working_schedule
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

        game_times = [tC.convert_time_format_by_name(x['schedule']['date'], 'rapid')["%Y%m%d%H%M%S"]
                      for x in use_schedule['results']]

        differences = [tC.subtract_time_stamps_precise(time_now, x) for x in game_times]


        games_meeting_criteria = []
        i = 0
        while i < len(differences):
            if 0 <= differences[i]['minutes'] <= minutes:
                games_meeting_criteria.append(use_schedule['results'][i])
            i = i + 1

        return games_meeting_criteria

    def is_schedule_valid(self, provide_schedule_json=None):
        use_schedule = self._parse_provide_schedule_input(provide_schedule_json)
        if use_schedule is None:
            print("ERROR: No schedule to check if valid")
            return None

        if use_schedule['status'] == 200:
            return True
        else:
            return False

    def get_total_games_in_schedule(self, provide_schedule_json=None):
        use_schedule = self._parse_provide_schedule_input(provide_schedule_json)
        if use_schedule is None:
            print("ERROR: No schedule to check if valid")
            return 0

        return use_schedule['games']

    def get_games_list_from_schedule(self, provide_schedule_json=None):
        use_schedule = self._parse_provide_schedule_input(provide_schedule_json)
        if use_schedule is None:
            print("ERROR: No schedule to check if valid")
            return []

        return use_schedule['results']

    @staticmethod
    def get_team_name_given_game_dict(game_dict, playing, string_type="cityShort"):
        """

        :param game_dict:               dict(), a sports page game dict from results (schedule_dict['results'][#])
        :param playing:                 str(), away or home
        :param string_type:             str(), cityShort or full
        :return:                        str(), team name
        """
        playing = playing.lower()

        if string_type == "cityShort":
            return game_dict['teams'][playing]['abbreviation']
        elif string_type == "full":
            return game_dict['teams'][playing]['team']
        else:
            print("Unsupported string_type argument. Try 'full' or 'abbreviation'")
            return None


class NFLSportsPage(SportsPage):
    """
    NFL specific functions go in this class
    """

    def __init__(self, only_if_under_limit=True, provide_schedule_json=None):
        SportsPage.__init__(self, only_if_under_limit=only_if_under_limit, provide_schedule_json=provide_schedule_json)

    def get_schedule_for_today(self):
        self.working_schedule = self.get_schedule("nfl", date_start=self.today, date_end=self.today)
        return self.working_schedule


def get_schedule_json(sport, date=None):
    # date in format 2020-12-22, if date == '', then use today
    # you can use a date range by comma-separating two dates, such as /games?league=nba&date=2021-07-14,2021-07-17.
    # sport: nfl, nba, cbb

    sport = check_sport_option(sport)

    if date is None:
        dList = timeCommon.get_date_component_list()
        date = str(dList[0]) + '-' + str(dList[1]) + '-' + str(dList[2])

    url = get_base_url()
    key = get_key()
    headers = get_headers(key)

    querystring = {"league": sport, "date": date}

    response = rC.use_requests_return_json(url, headers=headers, params=querystring)

    return response


def get_game_time_given_game_dict(game_dict, sport='nfl'):
    try:
        game_time = game_dict['schedule']['date']
    except KeyError:
        game_time = "n/a"

    return game_time


def create_basic_schedule_dict(schedule_json, sport):
    # supported sports: nfl, nba, ncaab
    # this function parses the standard json for the sportspageFeedsAPI and returns a list of dictionaries
    # if games are not final, basic info comes in
    # if games are final, more details come in

    # output
    op_list = list()  # for nfl, only final games are returned, detailed dict. Other sports, all, basic

    games = get_number_of_games_in_schedule(schedule_json)

    if games > 0:
        op_dict = dict()
        gamesJson = schedule_json['results']

        for gameNum in range(0, games):
            if sport == 'nfl':
                gameDict = parse_game_basics(gamesJson[gameNum])
                if gameDict['status'] == "final":  # game is final, get all details
                    conferenceBool = gamesJson[gameNum]['details']['conferenceGame']
                    divisionBool = gamesJson[gameNum]['details']['divisionGame']
                    awayScore = gamesJson[gameNum]['scoreboard']['score']['away']
                    homeScore = gamesJson[gameNum]['scoreboard']['score']['home']
                    awayQ1 = gamesJson[gameNum]['scoreboard']['score']['awayPeriods'][0]
                    awayQ2 = gamesJson[gameNum]['scoreboard']['score']['awayPeriods'][1]
                    awayQ3 = gamesJson[gameNum]['scoreboard']['score']['awayPeriods'][2]
                    awayQ4 = gamesJson[gameNum]['scoreboard']['score']['awayPeriods'][3]
                    homeQ1 = gamesJson[gameNum]['scoreboard']['score']['homePeriods'][0]
                    homeQ2 = gamesJson[gameNum]['scoreboard']['score']['homePeriods'][1]
                    homeQ3 = gamesJson[gameNum]['scoreboard']['score']['homePeriods'][2]
                    homeQ4 = gamesJson[gameNum]['scoreboard']['score']['homePeriods'][3]
                    awaySpreadOpen = gamesJson[gameNum]['odds'][0]['spread']['open']['away']
                    awaySpreadOpenOdds = gamesJson[gameNum]['odds'][0]['spread']['open']['awayOdds']
                    homeSpreadOpen = gamesJson[gameNum]['odds'][0]['spread']['open']['home']
                    homeSpreadOpenOdds = gamesJson[gameNum]['odds'][0]['spread']['open']['homeOdds']
                    awaySpreadCurrent = gamesJson[gameNum]['odds'][0]['spread']['current']['away']
                    awaySpreadCurrentOdds = gamesJson[gameNum]['odds'][0]['spread']['current']['awayOdds']
                    homeSpreadCurrent = gamesJson[gameNum]['odds'][0]['spread']['current']['home']
                    homeSpreadCurrentOdds = gamesJson[gameNum]['odds'][0]['spread']['current']['homeOdds']
                    awayMoneyLineOpen = gamesJson[gameNum]['odds'][0]['moneyline']['open']['awayOdds']
                    homeMoneyLineOpen = gamesJson[gameNum]['odds'][0]['moneyline']['open']['homeOdds']
                    awayMoneyLineCurrent = gamesJson[gameNum]['odds'][0]['moneyline']['current']['awayOdds']
                    homeMoneyLineCurrent = gamesJson[gameNum]['odds'][0]['moneyline']['current']['homeOdds']
                    totalOpen = gamesJson[gameNum]['odds'][0]['total']['open']['total']
                    totalOpenOverOdds = gamesJson[gameNum]['odds'][0]['total']['open']['overOdds']
                    totalOpenUnderOdds = gamesJson[gameNum]['odds'][0]['total']['open']['underOdds']
                    totalCurrent = gamesJson[gameNum]['odds'][0]['total']['current']['total']
                    totalCurrentOverOdds = gamesJson[gameNum]['odds'][0]['total']['current']['overOdds']
                    totalCurrentUnderOdds = gamesJson[gameNum]['odds'][0]['total']['current']['underOdds']

                    op_dict['awayTeam'] = gameDict['awayteam']
                    op_dict['awayScore'] = awayScore
                    op_dict['homeTeam'] = gameDict['hometeam']
                    op_dict['homeScore'] = homeScore
                    op_dict['hourPlayed'] = gameDict['time']['hour']
                    op_dict['timeStamp'] = gameDict['time']['string']
                    op_dict['conferenceBool'] = conferenceBool
                    op_dict['divisionBool'] = divisionBool
                    op_dict['awayQ1'] = awayQ1
                    op_dict['awayQ2'] = awayQ2
                    op_dict['awayQ3'] = awayQ3
                    op_dict['awayQ4'] = awayQ4
                    op_dict['homeQ1'] = homeQ1
                    op_dict['homeQ2'] = homeQ2
                    op_dict['homeQ3'] = homeQ3
                    op_dict['homeQ4'] = homeQ4
                    op_dict['awaySpreadOpen'] = awaySpreadOpen
                    op_dict['awaySpreadOpenOdds'] = awaySpreadOpenOdds
                    op_dict['homeSpreadOpen'] = homeSpreadOpen
                    op_dict['homeSpreadOpenOdds'] = homeSpreadOpenOdds
                    op_dict['awaySpreadCurrent'] = awaySpreadCurrent
                    op_dict['awaySpreadCurrentOdds'] = awaySpreadCurrentOdds
                    op_dict['homeSpreadCurrent'] = homeSpreadCurrent
                    op_dict['homeSpreadCurrentOdds'] = homeSpreadCurrentOdds
                    op_dict['awayMoneyLineOpen'] = awayMoneyLineOpen
                    op_dict['homeMoneyLineOpen'] = homeMoneyLineOpen
                    op_dict['awayMoneyLineCurrent'] = awayMoneyLineCurrent
                    op_dict['homeMoneyLineCurrent'] = homeMoneyLineCurrent
                    op_dict['totalOpen'] = totalOpen
                    op_dict['totalOpenOverOdds'] = totalOpenOverOdds
                    op_dict['totalOpenUnderOdds'] = totalOpenUnderOdds
                    op_dict['totalCurrent'] = totalCurrent
                    op_dict['totalCurrentOverOdds'] = totalCurrentOverOdds
                    op_dict['totalCurrentUnderOdds'] = totalCurrentUnderOdds

                    dictionary_copy = op_dict.copy()

                    op_list.append(dictionary_copy)
            else:
                gameDict = parse_game_basics(gamesJson[gameNum])
                if gameDict['status'] == "final":
                    test = 1
                    # add more details
                dictionary_copy = gameDict.copy()
                op_list.append(dictionary_copy)

        return op_list
    else:
        return 'error'


def get_number_of_games_in_schedule(schedule_json):
    # returns the # of games in a json file
    games = 0  # default to 0

    try:
        games = int(schedule_json['games'])  # get games from the json
    except:
        return 0

    return games


def parse_game_basics(game_json, sport="nfl", team_name_abbreviation="no"):
    """
    :param game_json: dict(), a single game unit as defined by the api
    :param sport: string(), currently only tested for nfl
    :param team_name_abbreviation: string(), by default, returns the full team name. 'yes' means return abbreviation
    :return: dict(), a simple dictionary with the basic information for a game parsed in good formats
    """

    op_dict = dict()

    game_time = game_json['schedule']['date']
    time_dict = timeCommon.convert_time_formats(game_time, 'ISO 8601')

    op_dict['status'] = game_json['status']
    op_dict['time'] = time_dict

    team_name_abbreviation = team_name_abbreviation.lower()
    if team_name_abbreviation == "no":
        op_dict['awayteam'] = game_json['teams']['away']['team']
        op_dict['hometeam'] = game_json['teams']['home']['team']
    else:
        op_dict['awayteam'] = game_json['teams']['away']['abbreviation']
        op_dict['hometeam'] = game_json['teams']['home']['abbreviation']

    return op_dict


def get_key():
    fName = osC.create_file_path_string(['resources', 'commonSports', 'key', 'key_sportspage.txt'])
    key = fC.read_single_line_from_file(fName)
    return key


def get_base_url():
    url = "https://sportspage-feeds.p.rapidapi.com/games"
    return url


def get_headers(key):
    headers = {
        'x-rapidapi-host': "sportspage-feeds.p.rapidapi.com",
        'x-rapidapi-key': key
    }

    return headers


def check_sport_option(sport):
    sport = sport.lower()
    if sport == 'nfl':
        sport = 'NFL'
    elif sport == 'nba':
        sport = "NBA"
    elif sport == 'cbb':
        sport = "NCAAB"
    elif sport == 'ncaab':
        sport = "NCAAB"
    elif sport == 'ncaaf' or sport == "cfb":
        sport = "NCAAF"

    sport = sport.upper()

    return sport


def parse_json_for_results(fPath, **kwargs):
    # jayson is the file path to the json file to be parsed
    # this function parses the standard json for the sportspageFeedsAPI and returns a list of dictionaries
    # if games are not final, basic info comes in
    # if games are final, more details come in
    sport = 'NFL'
    if 'sport' in kwargs:
        sport = kwargs['sport']
        sport = check_sport_option(sport)

    # output
    op_list = list()  # for nfl, only final games are returned, detailed dict. Other sports, all, basic

    schedJson = fC.load_json_from_file(fPath)
    if 'sport' in kwargs:
        games = parse_json_for_games(schedJson, sport=sport)
    else:
        games = parse_json_for_games(schedJson)

    if games > 0:
        op_dict = dict()
        gamesJson = schedJson['results']

        for gameNum in range(0, games):
            if sport == 'NFL' or sport == 'NBA':
                gameDict = parse_game_basics(gamesJson[gameNum])
                if gameDict['status'] == "final":  # game is final, get all details
                    conferenceBool = gamesJson[gameNum]['details']['conferenceGame']
                    divisionBool = gamesJson[gameNum]['details']['divisionGame']
                    awayScore = gamesJson[gameNum]['scoreboard']['score']['away']
                    homeScore = gamesJson[gameNum]['scoreboard']['score']['home']
                    awayQ1 = gamesJson[gameNum]['scoreboard']['score']['awayPeriods'][0]
                    awayQ2 = gamesJson[gameNum]['scoreboard']['score']['awayPeriods'][1]
                    homeQ1 = gamesJson[gameNum]['scoreboard']['score']['homePeriods'][0]
                    homeQ2 = gamesJson[gameNum]['scoreboard']['score']['homePeriods'][1]
                    try:
                        awaySpreadOpen = gamesJson[gameNum]['odds'][0]['spread']['open']['away']
                    except KeyError:
                        awaySpreadOpen = 'N/A'
                    try:
                        awaySpreadOpenOdds = gamesJson[gameNum]['odds'][0]['spread']['open']['awayOdds']
                    except KeyError:
                        awaySpreadOpenOdds = 'N/A'
                    try:
                        homeSpreadOpen = gamesJson[gameNum]['odds'][0]['spread']['open']['home']
                    except KeyError:
                        homeSpreadOpen = 'N/A'
                    try:
                        homeSpreadOpenOdds = gamesJson[gameNum]['odds'][0]['spread']['open']['homeOdds']
                    except KeyError:
                        homeSpreadOpenOdds = 'N/A'
                    try:
                        awaySpreadCurrent = gamesJson[gameNum]['odds'][0]['spread']['current']['away']
                    except KeyError:
                        awaySpreadCurrent = 'N/A'
                    try:
                        awaySpreadCurrentOdds = gamesJson[gameNum]['odds'][0]['spread']['current']['awayOdds']
                    except KeyError:
                        awaySpreadCurrentOdds = 'N/A'
                    try:
                        homeSpreadCurrent = gamesJson[gameNum]['odds'][0]['spread']['current']['home']
                    except KeyError:
                        homeSpreadCurrent = 'N/A'
                    try:
                        homeSpreadCurrentOdds = gamesJson[gameNum]['odds'][0]['spread']['current']['homeOdds']
                    except KeyError:
                        homeSpreadCurrentOdds = 'N/A'
                    try:
                        awayMoneyLineOpen = gamesJson[gameNum]['odds'][0]['moneyline']['open']['awayOdds']
                    except KeyError:
                        awayMoneyLineOpen = 'N/A'
                    try:
                        homeMoneyLineOpen = gamesJson[gameNum]['odds'][0]['moneyline']['open']['homeOdds']
                    except KeyError:
                        homeMoneyLineOpen = 'N/A'
                    try:
                        awayMoneyLineCurrent = gamesJson[gameNum]['odds'][0]['moneyline']['current']['awayOdds']
                    except KeyError:
                        awayMoneyLineCurrent = 'N/A'
                    try:
                        homeMoneyLineCurrent = gamesJson[gameNum]['odds'][0]['moneyline']['current']['homeOdds']
                    except KeyError:
                        homeMoneyLineCurrent = 'N/A'
                    try:
                        totalOpen = gamesJson[gameNum]['odds'][0]['total']['open']['total']
                    except KeyError:
                        totalOpen = 'N/A'
                    try:
                        totalOpenOverOdds = gamesJson[gameNum]['odds'][0]['total']['open']['overOdds']
                    except KeyError:
                        totalOpenOverOdds = 'N/A'
                    try:
                        totalOpenUnderOdds = gamesJson[gameNum]['odds'][0]['total']['open']['underOdds']
                    except KeyError:
                        totalOpenUnderOdds = 'N/A'
                    try:
                        totalCurrent = gamesJson[gameNum]['odds'][0]['total']['current']['total']
                    except KeyError:
                        totalCurrent = 'N/A'
                    try:
                        totalCurrentOverOdds = gamesJson[gameNum]['odds'][0]['total']['current']['overOdds']
                    except KeyError:
                        totalCurrentOverOdds = 'N/A'
                    try:
                        totalCurrentUnderOdds = gamesJson[gameNum]['odds'][0]['total']['current']['underOdds']
                    except KeyError:
                        totalCurrentUnderOdds = 'N/A'

                    op_dict['awayTeam'] = gameDict['awayteam']
                    op_dict['awayScore'] = awayScore
                    op_dict['homeTeam'] = gameDict['hometeam']
                    op_dict['homeScore'] = homeScore
                    op_dict['hourPlayed'] = gameDict['time']['hour']
                    op_dict['timeStamp'] = gameDict['time']['string']
                    op_dict['conferenceBool'] = conferenceBool
                    op_dict['divisionBool'] = divisionBool
                    op_dict['awayQ1'] = awayQ1
                    op_dict['awayQ2'] = awayQ2
                    op_dict['awayQ3'] = 'N/A'
                    op_dict['awayQ4'] = 'N/A'
                    op_dict['homeQ1'] = homeQ1
                    op_dict['homeQ2'] = homeQ2
                    op_dict['homeQ3'] = 'N/A'
                    op_dict['homeQ4'] = 'N/A'
                    op_dict['awaySpreadOpen'] = awaySpreadOpen
                    op_dict['awaySpreadOpenOdds'] = awaySpreadOpenOdds
                    op_dict['homeSpreadOpen'] = homeSpreadOpen
                    op_dict['homeSpreadOpenOdds'] = homeSpreadOpenOdds
                    op_dict['awaySpreadCurrent'] = awaySpreadCurrent
                    op_dict['awaySpreadCurrentOdds'] = awaySpreadCurrentOdds
                    op_dict['homeSpreadCurrent'] = homeSpreadCurrent
                    op_dict['homeSpreadCurrentOdds'] = homeSpreadCurrentOdds
                    op_dict['awayMoneyLineOpen'] = awayMoneyLineOpen
                    op_dict['homeMoneyLineOpen'] = homeMoneyLineOpen
                    op_dict['awayMoneyLineCurrent'] = awayMoneyLineCurrent
                    op_dict['homeMoneyLineCurrent'] = homeMoneyLineCurrent
                    op_dict['totalOpen'] = totalOpen
                    op_dict['totalOpenOverOdds'] = totalOpenOverOdds
                    op_dict['totalOpenUnderOdds'] = totalOpenUnderOdds
                    op_dict['totalCurrent'] = totalCurrent
                    op_dict['totalCurrentOverOdds'] = totalCurrentOverOdds
                    op_dict['totalCurrentUnderOdds'] = totalCurrentUnderOdds

                    dictionary_copy = op_dict.copy()
                else:
                    gameDict = parse_game_basics(gamesJson[gameNum], sport=sport)
                    dictionary_copy = gameDict.copy()

                op_list.append(dictionary_copy)

            elif sport == 'CBB' or sport == 'NCAAB':
                gameDict = parse_game_basics(gamesJson[gameNum])
                if gameDict['status'] == "final":  # game is final, get all details
                    conferenceBool = gamesJson[gameNum]['details']['conferenceGame']
                    divisionBool = gamesJson[gameNum]['details']['divisionGame']
                    awayScore = gamesJson[gameNum]['scoreboard']['score']['away']
                    homeScore = gamesJson[gameNum]['scoreboard']['score']['home']
                    awayQ1 = gamesJson[gameNum]['scoreboard']['score']['awayPeriods'][0]
                    awayQ2 = gamesJson[gameNum]['scoreboard']['score']['awayPeriods'][1]
                    homeQ1 = gamesJson[gameNum]['scoreboard']['score']['homePeriods'][0]
                    homeQ2 = gamesJson[gameNum]['scoreboard']['score']['homePeriods'][1]
                    awaySpreadOpen = gamesJson[gameNum]['odds'][0]['spread']['open']['away']
                    awaySpreadOpenOdds = gamesJson[gameNum]['odds'][0]['spread']['open']['awayOdds']
                    homeSpreadOpen = gamesJson[gameNum]['odds'][0]['spread']['open']['home']
                    homeSpreadOpenOdds = gamesJson[gameNum]['odds'][0]['spread']['open']['homeOdds']
                    awaySpreadCurrent = gamesJson[gameNum]['odds'][0]['spread']['current']['away']
                    awaySpreadCurrentOdds = gamesJson[gameNum]['odds'][0]['spread']['current']['awayOdds']
                    homeSpreadCurrent = gamesJson[gameNum]['odds'][0]['spread']['current']['home']
                    homeSpreadCurrentOdds = gamesJson[gameNum]['odds'][0]['spread']['current']['homeOdds']
                    try:
                        awayMoneyLineOpen = gamesJson[gameNum]['odds'][0]['moneyline']['open']['awayOdds']
                    except KeyError:
                        awayMoneyLineOpen = 'N/A'
                    try:
                        homeMoneyLineOpen = gamesJson[gameNum]['odds'][0]['moneyline']['open']['homeOdds']
                    except KeyError:
                        homeMoneyLineOpen = 'N/A'
                    try:
                        awayMoneyLineCurrent = gamesJson[gameNum]['odds'][0]['moneyline']['current']['awayOdds']
                    except KeyError:
                        awayMoneyLineCurrent = 'N/A'
                    try:
                        homeMoneyLineCurrent = gamesJson[gameNum]['odds'][0]['moneyline']['current']['homeOdds']
                    except KeyError:
                        homeMoneyLineCurrent = 'N/A'
                    totalOpen = gamesJson[gameNum]['odds'][0]['total']['open']['total']
                    totalOpenOverOdds = gamesJson[gameNum]['odds'][0]['total']['open']['overOdds']
                    totalOpenUnderOdds = gamesJson[gameNum]['odds'][0]['total']['open']['underOdds']
                    totalCurrent = gamesJson[gameNum]['odds'][0]['total']['current']['total']
                    totalCurrentOverOdds = gamesJson[gameNum]['odds'][0]['total']['current']['overOdds']
                    totalCurrentUnderOdds = gamesJson[gameNum]['odds'][0]['total']['current']['underOdds']

                    op_dict['awayTeam'] = gameDict['awayteam']
                    op_dict['awayScore'] = awayScore
                    op_dict['homeTeam'] = gameDict['hometeam']
                    op_dict['homeScore'] = homeScore
                    op_dict['hourPlayed'] = gameDict['time']['hour']
                    op_dict['timeStamp'] = gameDict['time']['string']
                    op_dict['conferenceBool'] = conferenceBool
                    op_dict['divisionBool'] = divisionBool
                    op_dict['awayQ1'] = awayQ1
                    op_dict['awayQ2'] = awayQ2
                    op_dict['awayQ3'] = 'N/A'
                    op_dict['awayQ4'] = 'N/A'
                    op_dict['homeQ1'] = homeQ1
                    op_dict['homeQ2'] = homeQ2
                    op_dict['homeQ3'] = 'N/A'
                    op_dict['homeQ4'] = 'N/A'
                    op_dict['awaySpreadOpen'] = awaySpreadOpen
                    op_dict['awaySpreadOpenOdds'] = awaySpreadOpenOdds
                    op_dict['homeSpreadOpen'] = homeSpreadOpen
                    op_dict['homeSpreadOpenOdds'] = homeSpreadOpenOdds
                    op_dict['awaySpreadCurrent'] = awaySpreadCurrent
                    op_dict['awaySpreadCurrentOdds'] = awaySpreadCurrentOdds
                    op_dict['homeSpreadCurrent'] = homeSpreadCurrent
                    op_dict['homeSpreadCurrentOdds'] = homeSpreadCurrentOdds
                    op_dict['awayMoneyLineOpen'] = awayMoneyLineOpen
                    op_dict['homeMoneyLineOpen'] = homeMoneyLineOpen
                    op_dict['awayMoneyLineCurrent'] = awayMoneyLineCurrent
                    op_dict['homeMoneyLineCurrent'] = homeMoneyLineCurrent
                    op_dict['totalOpen'] = totalOpen
                    op_dict['totalOpenOverOdds'] = totalOpenOverOdds
                    op_dict['totalOpenUnderOdds'] = totalOpenUnderOdds
                    op_dict['totalCurrent'] = totalCurrent
                    op_dict['totalCurrentOverOdds'] = totalCurrentOverOdds
                    op_dict['totalCurrentUnderOdds'] = totalCurrentUnderOdds

                    dictionary_copy = op_dict.copy()
                else:
                    gameDict = parse_game_basics(gamesJson[gameNum], sport=sport)
                    dictionary_copy = gameDict.copy()

                op_list.append(dictionary_copy)
            else:
                gameDict = parse_game_basics(gamesJson[gameNum], sport=sport)

        return op_list
    else:
        return 'error'


def parse_json_for_games(schedJson, **kwargs):
    # returns the # of games in a json file
    games = 0  # default to 0

    if 'sport' in kwargs:
        noPrint = 1
    else:
        noPrint = 0

    try:
        games = int(schedJson['games'])  # get games from the json
        if noPrint == 0:
            print('games in file: ' + str(games))
    except:
        fncMessage = "no games in file"
        return 0

    return games


def full_parse_rapid_schedule_file(schedule_file, sport=None):
    # Takes in a schedule file (see data Harvest)
    # If no sport is passed, basic info is returned

    op_dict_list = list()
    schedule_json = fC.load_json_from_file(schedule_file)
    op_dict = {
        'eventDetails': dict(),
        'matchupDetails': dict(),
        'resultDetails': dict()
    }
    if sport is not None:
        sport = check_sport_option(sport)

    games_int = parse_json_for_games(schedule_json)

    if games_int > 0:
        pull_time = timeCommon.convert_time_formats(schedule_json['time'], 'ISO 8601', to_format='string')
        games_list = schedule_json['results']
        for game in games_list:
            op_dict['eventDetails'] = parse_event_details(game)
            op_dict['matchupDetails'] = parse_matchup_details(game)
            op_dict['resultDetails'] = parse_result_details(game)
            op_dict_list.append(op_dict.copy())
    else:
        return 'No games in file'

    return op_dict_list


def parse_event_details(game_dict):
    # Input is an individual game dict from rapid json
    # Output is a dict shown below

    schedule_dict = game_dict['schedule']
    details_dict = game_dict['details']
    venue_dict = game_dict['venue']

    scheduled_rapid_format = errorHandleCommon.try_except_dictionary_key(schedule_dict, 'date')
    if scheduled_rapid_format != "N/A":
        scheduled = timeCommon.convert_time_formats(scheduled_rapid_format, 'ISO 8601', to_format='string')
    else:
        scheduled = "N/A"

    last_updated = errorHandleCommon.try_except_dictionary_key(game_dict, 'lastUpdated')
    match = errorHandleCommon.try_except_dictionary_key(game_dict, 'summary')
    status = errorHandleCommon.try_except_dictionary_key(game_dict, 'status')
    league = errorHandleCommon.try_except_dictionary_key(details_dict, 'league')
    game_type = errorHandleCommon.try_except_dictionary_key(details_dict, 'seasonType')
    conference_bool = errorHandleCommon.try_except_dictionary_key(details_dict, 'conferenceGame')
    division_bool = errorHandleCommon.try_except_dictionary_key(details_dict, 'divisionGame')
    season = errorHandleCommon.try_except_dictionary_key(details_dict, 'season')
    neutral_site_bool = errorHandleCommon.try_except_dictionary_key(venue_dict, 'neutralSite')

    op_dict = {
        'scheduled': scheduled,
        'scheduledRapidFormat': scheduled_rapid_format,
        'season': season,
        'lastUpdated': last_updated,
        'match': match,
        'status': status,
        'league': league,
        'gameType': game_type,
        'conferenceGame': conference_bool,
        'divisionGame': division_bool,
        'neutralSite': neutral_site_bool
    }

    return op_dict


def parse_matchup_details(game_dict):
    op_dict = dict()

    teams_dict = game_dict['teams']
    odds_dict = errorHandleCommon.try_except_dictionary_key(game_dict, 'odds')

    if odds_dict != "N/A":
        odds_dict = game_dict['odds'][0]
        spread_details = errorHandleCommon.try_except_dictionary_key(odds_dict, 'spread')
        moneyline_details = errorHandleCommon.try_except_dictionary_key(odds_dict, 'moneyline')
        total_details = errorHandleCommon.try_except_dictionary_key(odds_dict, 'total')
        open_date = errorHandleCommon.try_except_dictionary_key(odds_dict, 'openDate')
        last_updated = errorHandleCommon.try_except_dictionary_key(odds_dict, 'lastUpdated')
    else:
        spread_details = {"open": {"away": "N/A", "home": "N/A", "awayOdds": "N/A", "homeOdds": "N/A"},
                          "current": {"away": "N/A", "home": "N/A", "awayOdds": "N/A", "homeOdds": "N/A"}}
        moneyline_details = {"open": {"awayOdds": "N/A", "homeOdds": "N/A"},
                             "current": {"awayOdds": "N/A", "homeOdds": "N/A"}}
        total_details = {"open": {"total": "N/A", "overOdds": "N/A", "underOdds": "N/A"},
                         "current": {"total": "N/A", "overOdds": "N/A", "underOdds": "N/A"}}
        open_date = "N/A"
        last_updated = "N/A"

    away_team_dict = errorHandleCommon.try_except_dictionary_key(teams_dict, 'away')
    home_team_dict = errorHandleCommon.try_except_dictionary_key(teams_dict, 'home')

    if open_date != "N/A":
        open_date = timeCommon.convert_time_formats(open_date, 'ISO 8601', to_format='string')

    if last_updated != "N/A":
        last_updated = timeCommon.convert_time_formats(last_updated, 'ISO 8601', to_format='string')

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
        'openTime': open_date,
        'lastUpdated': last_updated
    }

    return op_dict


def parse_result_details(game_dict):
    op_dict = dict()

    test = 1
    scoreboard_dict = errorHandleCommon.try_except_dictionary_key(game_dict, 'scoreboard')

    if scoreboard_dict != "N/A":
        score_dict = errorHandleCommon.try_except_dictionary_key(scoreboard_dict, 'score')
        current_period = errorHandleCommon.try_except_dictionary_key(scoreboard_dict, 'currentPeriod')
        time_remaining = errorHandleCommon.try_except_dictionary_key(scoreboard_dict, 'periodTimeRemaining')
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


def parse_final_game_dict_for_results(game_dict):
    test = 1


def return_total_final_games_in_schedule_json(schedule_json):
    game_count = 0

    try:
        result_list = schedule_json['results']  # get games from the json
    except KeyError:
        return game_count

    for result in result_list:
        if result["status"] == "final":
            game_count = game_count + 1

    return game_count


def return_games_in_schedule(schedule_json, sport="nfl"):
    sport = sport.lower()

    if sport == 'nfl':
        return schedule_json["results"]
    else:
        print("sport not set up in function yet")


def parse_directory_for_results(dir_full_path):
    files = osC.return_files_in_dir_as_strings(dir_full_path)
    full_results_list = list()
    for f in files:
        if f == "weekCombined.json":
            pass
        else:
            temp_results_list = list()
            temp_json = dict()
            temp_file = osC.append_to_dir(dir_full_path, f)
            try:
                temp_json = fC.load_json_from_file(temp_file)
            except:
                pass

            try:
                temp_results_list = temp_json['results']
            except:
                pass

            for result in temp_results_list:
                full_results_list.append(result)

    return full_results_list


def combine_results_in_directory(dir_full_path):
    full_results_list = parse_directory_for_results(dir_full_path)
    op_file = osC.append_to_dir(dir_full_path, "weekCombined.json")
    op_dict = {
        "fileType": "week combined",
        "results": full_results_list
    }

    fC.dump_json_to_file(op_file, op_dict)


def get_current_spread_given_dict(game_dict, playing):
    """
    :param playing: str(), home or away
    :param game_dict: dict(), rapid game dict
    :return: float(): spread
    """
    playing = playing.lower()
    try:
        return game_dict['odds'][0]['spread']['current'][playing]
    except KeyError:
        return "N/A"


def get_final_score_given_dict(game_dict, playing):
    """
    :param playing: str(), home or away
    :param game_dict: dict(), rapid game dict
    :return: int(): score
    """

    playing = playing.lower()
    return game_dict['scoreboard']['score'][playing]


def get_total_given_dict(game_dict):
    """
    :param game_dict: dict(), rapid game dict()
    :return: float(), total
    """
    try:
        return game_dict['odds'][0]['total']['current']["total"]
    except KeyError:
        return "N/A"


def return_game_final_basics_given_result_dict(game_dict):
    """
    Returns a dict with the game spread
    :param game_dict: dict(), rapid api game dict with final results available
    :return:
    """

    op_dict = dict()
    op_dict['awayTeamFull'] = game_dict['teams']['away']['team']
    op_dict['homeTeamFull'] = game_dict['teams']['home']['team']
    op_dict['awayTeam'] = game_dict['teams']['away']['abbreviation']
    op_dict['homeTeam'] = game_dict['teams']['home']['abbreviation']
    op_dict['awaySpread'] = get_current_spread_given_dict(game_dict, 'away')
    op_dict['homeSpread'] = get_current_spread_given_dict(game_dict, 'home')
    op_dict['awayScore'] = get_final_score_given_dict(game_dict, 'away')
    op_dict['homeScore'] = get_final_score_given_dict(game_dict, 'home')
    op_dict['total'] = get_total_given_dict(game_dict)

    return op_dict


def get_conference_given_game_dict(playing, game_dict):
    """
    Returns the conference of the given team
    :param playing: string(), "away" or "home"
    :param game_dict: rapid game dict
    :return: str(), Rapid conference
    """
    playing = playing.lower()
    try:
        return game_dict['teams'][playing]['conference']
    except KeyError:
        return "N/A"


def get_final_result_basics_dict(game_dict):
    game_details = parse_matchup_details(game_dict)
    game_results = parse_result_details(game_dict)

    if game_dict['status'] == "canceled":
        away_score = "n/a"
        home_score = "n/a"
    else:
        away_score = game_results["score"]["away"]
        home_score = game_results["score"]["home"]
    home_spread = game_details["spreadDetails"]["current"]["home"]
    total = game_details["totalDetails"]["current"]["total"]

    ats_analysis = commonSportsGameAnalysis.calculate_ats_data_for_game(away_score, home_score, home_spread, total)

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


def get_team_name(game_dict, playing, string_type="abbreviation"):
    """

    :param game_dict: dict(), rapid dict of result
    :param playing: str(), away or home
    :param string_type: str(), full or abbreviation
    :return: str(), team name
    """
    playing = playing.lower()

    if string_type == "abbreviation":
        return game_dict['teams'][playing]['abbreviation']
    elif string_type == "full":
        return game_dict['teams'][playing]['team']
    else:
        return "Unsupported string_type argument. Try 'full' or 'abbreviation'"


def test_check_games_within_time():
    test = 1



if __name__ == '__main__':
    # sched_dict = fC.load_json_from_file("schedule_example.json")
    # rapid_obj = RapidSchedule('nfl', sched_dict)
    # game_check = rapid_obj.check_if_all_games_complete(started_before_date_hour=17, date_to_check="20210926")
    nfl = NFLSportsPage()
    nfl.get_schedule_for_today()
    no_games = nfl.get_games_within_specified_minutes(11)
    stop = 1
    sp = SportsPage()
    start_date = "2021-10-19"
    end_date = "2021-10-26"
    sched = sp.get_schedule("nfl", date_start=start_date, date_end=end_date)

    test = 1
