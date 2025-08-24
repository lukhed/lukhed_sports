from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import listWorkCommon as lC
from lukhed_sports.leagueData import TeamConversion
from typing import Optional


class NextGenStatsSchedule:

    def __init__(self, season='current'):
        """
        This class utilizes Next Gen Stats public APIs to get the NFL schedule.

        season: str, optional
            The season for which to retrieve the schedule. By default, it is set to 'current'.

            In the post and off-season, the 'current' schedule may not be what you expect, and you may have to 
            input the season in the season parameter.
        """
        self.team_converter: Optional[TeamConversion] = None
        self.team_format = {"provider": "ngs", "teamType": "cityShort"}

        self.ngs_header = {'Referer': 'https://nextgenstats.nfl.com/stats/game-center/2023100200'}

        self.ngs_schedule_data = {}
        self.ngs_game_ids = {}
        self.season = "current" if type(season) == str and season.lower() == 'current' else int(season)

        self._check_get_ngs_schedule_data()

    def _check_get_ngs_schedule_data(self, force_season_overwrite=None):
        """
        Gets the scheduled based on the current season. Param force_overwrite is used by change_season function.

        :param force_overwrite:         bool(), will get the schedule again (to be used when user wants to change
                                        season.
        :return:
        """

        self.season = force_season_overwrite if force_season_overwrite is not None else self.season

        if self.ngs_schedule_data == {} or force_season_overwrite:
            if self.season == 'current':
                url = 'https://nextgenstats.nfl.com/api/league/schedule/current'
            else:
                url = f'https://nextgenstats.nfl.com/api/league/schedule?season={self.season}'
            self.ngs_schedule_data = self._call_api(url)

            if type(self.ngs_schedule_data) == list:
                pass
            else:
                try:
                    # If current schedule is post season data, it will be in a different format
                    self.ngs_schedule_data = self.ngs_schedule_data['games']
                except KeyError:
                    pass

    def _check_create_team_conversion_object(self):
        if self.team_converter is None:
            self.team_converter = TeamConversion('nfl', reset_cache=False)

    def _call_api(self, url):
        return rC.request_json(url, add_user_agent=True, headers=self.ngs_header)
    
    def _get_game_id(self, team, week):
        """
        Gets the game ID for a specific team and week from the Next Gen Stats schedule.

        Parameters
        ----------
        team : str
            The abbreviation of the team for which to retrieve the game ID (e.g., 'DET' for Detroit Lions).
            You can check the appropriate team abbreviations by visting NGS game center page:
            https://nextgenstats.nfl.com/stats/game-center-index

        week : str or int
            For regular season, this should be an integer from 1 to 18.
            For post-season, this can be 'WC' for wildcard, 'DIV' for division, 'CONF' for conference, or 'SB' 
            for Super Bowl.

        Returns
        -------
        str
            The game ID for the specified team and week. This ID can be used to retrieve more detailed game data
        """
        return self.get_game_data(team, week)['gameId']
    
    def _get_team_id(self, team):
        self._check_get_ngs_schedule_data()
        team = team.lower()
        team_id = None
        for game in self.ngs_schedule_data:
            if game['visitorTeamAbbr'].lower() == team or game['homeTeamAbbr'].lower() == team:
                team_id = game['homeTeamId'] if game['homeTeamAbbr'].lower() == team else game['visitorTeamId']
                break

        return team_id

    def change_season(self, season):
        """
        Changes the season for which the Next Gen Stats schedule is retrieved.

        Parameters
        ----------
        season : str or int
            The season for which to retrieve the schedule. It can be 'current' or an integer representing a 
            specific season.
        """
        self._check_get_ngs_schedule_data(force_overwrite=season)

    def get_regular_season_games(self, team=None):
        """
        Returns the regular season games from the Next Gen Stats schedule.

        Returns
        -------
        list
            A list of dictionaries containing the regular season games.
        """
        self._check_get_ngs_schedule_data()
        all_games = [x for x in self.ngs_schedule_data if x['seasonType'] == 'REG']
        if team:
            team = team.lower()
            all_games = [x for x in all_games if
                         (x['visitorTeamAbbr'].lower() == team or x['homeTeamAbbr'].lower() == team)]
        return all_games
    
    def get_game_data(self, team, week):
            """
            Gets the game data for a specific team and week from the Next Gen Stats schedule.

            Parameters
            ----------
            team : str
                The abbreviation of the team for which to retrieve the game data (e.g., 'DET' for Detroit Lions).
                You can check the appropriate team abbreviations by visting NGS game center page:
                https://nextgenstats.nfl.com/stats/game-center-index

            week : int::
                For regular season, this should be an integer from 1 to 18.
                For post-season, this can be 'WC' for wildcard, 'DIV' for division, 'CONF' for conference, or 'SB' 
                for Super Bowl.
                For pre-season, this should be 'P#' where # is the pre-season week number (1-4).

            Returns
            -------
            dict
                A dictionary containing the game data for the specified team and week. The dictionary includes various
            """
            self._check_get_ngs_schedule_data()
            team = team.lower()
            
            if type(week) == int:
                week = "week " + str(week)
            else:
                week = week.lower()

            team_data = [x for x in self.ngs_schedule_data if
                        (x['visitorTeamAbbr'].lower() == team or x['homeTeamAbbr'].lower() == team) and
                        x['weekNameAbbr'].lower() == week][0]


            return team_data

    def get_game_overview_for_team(self, team, week):
        game_id = self._get_game_id(team, week)
        url = f'https://nextgenstats.nfl.com/api/gamecenter/overview?gameId={game_id}'
        game_overview = self._call_api(url)
        return game_overview

    def get_schedule(self, force_season_overwrite=None):
        """
        Gets the NFL schedule data from Next Gen Stats.

        Parameters
        ----------
        force_season_overwrite : str or int, optional
            If provided, forces the retrieval of the schedule for the specified season, overriding the current season.
            If None, uses the current season set in the instance.

        Returns
        -------
        list
        A list of dictionaries containing the NFL schedule data for the specified season.
        """
        self._check_get_ngs_schedule_data(force_season_overwrite=force_season_overwrite)
        return self.ngs_schedule_data
    
    def get_all_teams(self):
        """
        Gets a list of all teams in the NFL schedule.

        Returns
        -------
        list
            A list of dicts containing team information, including nickname, abbreviation, and full name.
        """
        self._check_get_ngs_schedule_data()
        teams = []
        no_dupes = []

        for game in self.ngs_schedule_data:
            try:
                ta = game['homeTeamAbbr']
                if ta not in no_dupes:
                    no_dupes.append(ta)
                    teams.append({
                        'nickname': game['homeNickname'], 
                        'abbreviation': ta,
                        'displayName': game['homeDisplayName']
                    })
            except KeyError:
                pass
            
            try:
                ta = game['visitorTeamAbbr']
                if ta not in no_dupes:
                    no_dupes.append(ta)
                    teams.append({
                        'nickname': game['visitorNickname'], 
                        'abbreviation': ta,
                        'displayName': game['visitorDisplayName']
                    })

            except KeyError:
                pass
                
        return teams
    
    def get_current_week(self):
        """
        Gets the current week of the NFL season based on the schedule data.

        Returns
        -------
        int
            The current week number of the NFL season.
        """
        self._check_get_ngs_schedule_data()
        date_today = tC.get_current_time().date()
        reg_season_games = self.get_regular_season_games()

        # calculate week ends based on Monday games
        all_dates = [tC.convert_string_to_datetime(x['gameDate'], string_format='%m/%d/%Y') for x in 
                     reg_season_games if x['gameDate'] is not None]  # Monday games
        unique_dates = lC.return_unique_values(all_dates)
        mondays = [x for x in unique_dates if x.weekday() == 0]  # Monday games
        mondays.sort()

        week = 1
        for monday in mondays:
            if date_today <= monday.date():
                return week
            week += 1

        return week
    
    def get_week_date_bounds(self, week='current', date_format="%m/%d/%Y"):
        """
        NFL weeks start on Tuesday and end on Monday. This function returns the start and end dates of a given week.

        Parameters
        ----------
        week : str, optional
            The week number to retrieve the date bounds for, by default 'current'
        date_format : str, optional
            The format to return the dates in, by default "%m/%d/%Y"

        Returns
        -------
        dict
            A dictionary containing the start and end dates of the week, as well as their datetime objects.
        """
        
        if week == 'current':
            week = self.get_current_week()
        else:
            week = int(week)

        self._check_get_ngs_schedule_data()
        reg_season_games = self.get_regular_season_games()

        # calculate week ends based on Monday games
        all_dates = [tC.convert_string_to_datetime(x['gameDate'], string_format="%m/%d/%Y") for x in 
                     reg_season_games if x['gameDate'] is not None] 
        unique_dates = lC.return_unique_values(all_dates)
        mondays = [x for x in unique_dates if x.weekday() == 0]
        mondays.sort()

        # -6 to get the start of the week (Tuesday)
        tuesdays = [tC.add_days_to_date(
            tC.convert_date_to_string(x, string_format=date_format),
            -6,
            input_format=date_format,
            ouput_format=date_format) 
            for x in mondays]
        
        mondays = [tC.convert_date_to_string(x, string_format=date_format) for x in mondays]
        
        start_date = tuesdays[week - 1]
        end_date = mondays[week - 1]

        return {
            'start_date': start_date,
            'end_date': end_date,
            'start_datetime': tC.convert_string_to_datetime(start_date, string_format=date_format),
            'end_datetime': tC.convert_string_to_datetime(end_date, string_format=date_format)
        }
    
    def convert_team_names_to_specified_format(self, new_team_format='rapid', team_type='cityShort'):
        """
        Converts the team names in the schedule to a specified format using the TeamConversion utility.

        Parameters
        ----------
        new_team_format : str, optional
            The desired team name format (e.g., 'rapid', 'espn', 'nfl'), by default 'rapid'
        team_type : str, optional
            The type of team name to convert (e.g., 'cityShort', 'nickname'), by default 'cityShort'
        """
        self._check_create_team_conversion_object()
        from_provider = self.team_format['provider']
        from_team_type = self.team_format['teamType']
        to_provider = new_team_format
        to_team_type = team_type

        no_errors = True
        for game in self.ngs_schedule_data:
            try:
                self.team_converter.convert_team(game['homeTeamAbbr'], 
                                                 from_provider=from_provider,
                                                 to_provider=to_provider,
                                                 from_team_type=from_team_type,
                                                 to_team_type=to_team_type,
                                                 from_season='latest',
                                                 to_season='latest')
            except:
                print(f"Failed while converting team name {game['homeTeamAbbr']}.")
                print("Check for new names or error in source data")
                no_errors = False

            try:
                self.team_converter.convert_team(game['visitorTeamAbbr'], 
                                                 from_provider=from_provider,
                                                 to_provider=to_provider,
                                                 from_team_type=from_team_type,
                                                 to_team_type=to_team_type,
                                                 from_season='latest',
                                                 to_season='latest')
            except:
                print(f"Failed while converting team name {game['visitorTeamAbbr']}.")
                print("Check for new names or error in source data")
                no_errors = False

        self.team_format['provider'] = to_provider
        self.team_format['teamType'] = to_team_type

        return no_errors
    
    def get_games_for_week(self, week='current'):
        """
        Gets the games scheduled for a specific week.

        Parameters
        ----------
        week : str or int, optional
            Can be 'current' or an integer from 1 to 18 for regular season,
            OR "WC", "DIV", "CONF", "SB" for post-season, by default 'current'
            OR "P1", "P2", "P3" for pre-season
            OR "HOF" for Hall of Fame game

        Returns
        -------
        list
            A list of dictionaries containing the games scheduled for the specified week.
        """
        self._check_get_ngs_schedule_data()
        if week == 'current':
            week = self.get_current_week()

        try:
            week = int(week)
            results = [x for x in self.ngs_schedule_data if x['week'] == week and x['seasonType'] == 'REG']
        except ValueError:
            week = week.lower()
            results = [x for x in self.ngs_schedule_data if x['weekNameAbbr'].lower() == week]

        return results
