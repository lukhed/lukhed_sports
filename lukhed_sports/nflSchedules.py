from typing import Optional
from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import requestsCommon as rC


class NextGenStatsSchedule:

    def __init__(self, season):
        """
        This class utilizes Next Gen Stats public APIs to get the NFL schedule.

        season: str, optional
            The season for which to retrieve the schedule.
        """
        self.ngs_header = {'Referer': 'https://nextgenstats.nfl.com/stats/game-center/2023100200'}

        self.ngs_current_data = {}
        self.ngs_schedule_data = {}
        self.ngs_regular_season_schedule = {}
        self.ngs_game_ids = {}
        self.season = int(season)

        self._check_get_ngs_schedule_data(force_overwrite=True)

    def _check_set_season_and_week(self, season_input):
        if self.season is None:
            self._check_get_ngs_current_file()

        self.season = int(season_input) if season_input != 'current' else self.ngs_current_data['season']
        self.week = self.ngs_current_data['week']

    def _check_get_ngs_current_file(self):
        """
        Look in the console, this document is labeled 'current'
        :return:
        """
        if self.ngs_current_data == {}:
            url = 'https://nextgenstats.nfl.com/api/league/schedule/current'
            self.ngs_current_data = self._call_api(url)

    def _check_get_ngs_schedule_data(self, force_overwrite=False):
        """
        Gets the scheduled based on the current season. Param force_overwrite is used by change_season function.

        :param force_overwrite:         bool(), will get the schedule again (to be used when user wants to change
                                        season.
        :return:
        """

        if self.ngs_schedule_data == {} or force_overwrite:
            url = f'https://nextgenstats.nfl.com/api/league/schedule?season={self.season}'
            self.ngs_schedule_data = self._call_api(url)
            self.ngs_regular_season_schedule = [x for x in self.ngs_schedule_data if x['seasonType'] == 'REG']

    def _call_api(self, url):
        return rC.request_json(url, add_user_agent=True, headers=self.ngs_header)

    def change_season(self, season):
        self._check_set_season_and_week(season)
        self._check_get_ngs_schedule_data(force_overwrite=True)

    def get_game_data(self, team, week):
        self._check_get_ngs_schedule_data()
        team = team.lower()
        team_data = [x for x in self.ngs_regular_season_schedule if
                     (x['visitorTeamAbbr'].lower() == team or x['homeTeamAbbr'].lower() == team) and
                     x['week'] == int(week)][0]


        return team_data

    def get_game_id(self, team, week):
        return self.get_game_data(team, week)['gameId']

    def get_team_id(self, team):
        self._check_get_ngs_schedule_data()
        team = team.lower()
        team_id = None
        for game in self.ngs_regular_season_schedule:
            if game['visitorTeamAbbr'].lower() == team or game['homeTeamAbbr'].lower() == team:
                team_id = game['homeTeamId'] if game['homeTeamAbbr'].lower() == team else game['visitorTeamId']
                break

        return team_id

    def get_game_overview_for_team(self, team, week):
        game_id = self.get_game_id(team, week)
        url = f'https://nextgenstats.nfl.com/api/gamecenter/overview?gameId={game_id}'
        game_overview = self._call_api(url)
        return game_overview

    def get_schedule(self, force_overwrite=False):
        self._check_get_ngs_schedule_data(force_overwrite=force_overwrite)

       
