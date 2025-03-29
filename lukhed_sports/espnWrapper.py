from typing import Optional
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import timeCommon as tC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import stringCommon as sC
from lukhed_basic_utils import listWorkCommon as lC
from lukhed_sports.leagueData import TeamConversion, advanced_player_search
import re
import json


class EspnStats():
    def __init__(self, sport='nfl'):
        self.sport = sport.lower()
        self.team_stats_raw_data = None
        self.team_format = {"provider": 'espn', "teamType": 'cityShort'}
        self.cache_dir = osC.create_file_path_string(['lukhed_sports', 'local_cache'])

        self.team_conversion_object = None                 # type: Optional[TeamConversion]

        # Holds the following page +: https://www.espn.com/nfl/stats/team. Use "get_all_team_stats"
        self.teams_stats = {
            "offenseTotals": [],
            "offenseVisibleTotals": [],
            "offensePassing": [],
            "offenseVisiblePassing": [],
            "offenseRushing": [],
            "offenseVisibleRushing": [],
            "defenseTotals": [],
            "defenseVisibleTotals": [],
            "defensePassing": [],
            "defenseVisiblePassing": [],
            "defenseRushing": [],
            "defenseVisibleRushing": [],
            "specialTeamsReturning": [],
            "specialTeamsVisibleReturning": [],
            "misc": [],
            "miscOpponent": []
        }

        # Holds working rosters (https://www.espn.com/nfl/team/depth/_/name/det/detroit-lions)
        self.team_roster = []

        # All players from (depth charts). Cached here: lukhed_sports/local_cache/espn_<sport>_players.json
        # Use self.build_player_list() to update the cache.
        self.player_list = []
        self.player_list_last_updated = None

        # Hold player stats
        self.player_stats = {}
        self.raw_player_stats = {}

    def _check_create_team_conversion_object(self):
        if self.team_conversion_object is None:
            self.team_conversion_object = TeamConversion(self.sport)

    def _get_team_rank_for_stat(self, team, stat_level_one, stat_key, more_is_better=True):
        team = team.lower()
        teams = [x['team'].lower() for x in self.teams_stats[stat_level_one]]
        indices = [x for x in range(0, 32)]
        stat = [x[stat_key] for x in self.teams_stats[stat_level_one]]

        teams = lC.sort_list_based_on_reference_list(stat, teams)
        indices = lC.sort_list_based_on_reference_list(stat, indices)

        if more_is_better:
            stat.sort(reverse=True)
            teams.reverse()
            indices.reverse()

        team_index = teams.index(team)
        rank = team_index + 1
        check_tie = True if stat.count(stat[team_index]) >= 2 else False
        return {"rank": rank, "tied": check_tie}

    def _check_load_player_list(self):
        if not self.player_list:
            self.get_league_player_list()

    @staticmethod
    def _special_request_handling(url):
        import requests
        from bs4 import BeautifulSoup
        from fake_useragent import UserAgent  # https://pypi.org/project/fake-useragent/#description

        # Create a session to persist cookies and settings
        session = requests.Session()

        # Set the maximum number of redirects
        max_redirects = 10

        # Try up to 5 times on the URL
        response = None
        got_response = False
        try_count = 0
        while try_count < 5:
            if got_response:
                break
            if try_count > 0:
                tC.sleep(1)       # don't spam on retries

            # Give a user agent
            headers = {}
            random_agent = UserAgent(fallback="chrome").random
            headers["User-Agent"] = random_agent

            # Manually follow redirects with a loop
            for _ in range(max_redirects):
                response = session.get(url, headers=headers, allow_redirects=False)

                # Check if the response is a redirect
                if response.is_redirect:
                    # Extract the new URL from the Location header
                    url = response.headers['Location']
                else:
                    # Break the loop if it's not a redirect
                    got_response = True
                    break
            else:
                # If the loop completes, it means too many redirects occurred, try again
                try_count = try_count + 1

        if got_response:
            return BeautifulSoup(response.content, 'html.parser')
        else:
            print("ERROR: Could not get response from ESPN. Too many redirects event after 5 tries.")
            return response

    @staticmethod
    def _get_json_from_script(soup):
        script_tags = soup.find_all('script')
        script_tag = next((x for x in script_tags[1:] if "__espnfitt__" in x.text), None)
        script_content = str(script_tag.string)
        # Use regular expressions to extract the dictionary inside window['__espnfitt__']
        match = re.search(r'window\[\'__espnfitt__\'\]\s*=\s*(\{.*?\});', script_content)
        return json.loads(match.group(1))

    ################################
    # General Helpers
    def convert_team_names_to_specified_format(self, to_format, team_type="long"):
        self._check_create_team_conversion_object()
        f_c = self.team_conversion_object.convert_team
        fp = self.team_format['provider']
        ft = self.team_format['teamType']
        for stat_key in self.teams_stats:
            temp_teams = self.teams_stats[stat_key]
            for team in temp_teams:
                team['team'] = f_c(team['team'], fp, to_format, ft, team_type)

        self.team_format = {"provider": to_format, "teamType": team_type}

    def get_team_list(self):
        self._check_load_player_list()
        all_teams = [x['team'] for x in self.player_list if x['team'] is not None or x['team'] != '']
        all_teams = lC.return_unique_values(all_teams)
        all_teams.sort()
        return all_teams

    ################################
    # Team Stats (done)
    def _get_check_team_stats_raw_data(self, season, regular_or_offseason):
        def _build_url():
            core_url = 'https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/statistics/' \
                       'byteam?region=us&lang=en&contentorigin=espn&sort='
            stat_type_string = 'team.passing'
            sort_string = '.netYardsPerGame&limit=32&'
            s_num = 2 if regular_or_offseason == 'regular' else 3
            season_string = f'season={season}&seasontype={s_num}'

            return core_url + stat_type_string + sort_string + season_string

        if self.team_stats_raw_data is None:
            api_url = _build_url()
            self.team_stats_raw_data = rC.request_json(api_url, add_user_agent=True)
            self.team_stats_raw_data.update({"season": season, "seasonType": regular_or_offseason})
        else:
            if (season != self.team_stats_raw_data['season'] or 
                regular_or_offseason != self.team_stats_raw_data["seasonType"]):
                
                api_url = _build_url()
                self.team_stats_raw_data = rC.request_json(api_url, add_user_agent=True)
                self.team_stats_raw_data.update({"season": season, "seasonType": regular_or_offseason})
            else:
                pass

    def _add_passing_and_total_stats_to_team_stats(self):
        pass_categories = [x for x in self.team_stats_raw_data['categories'] if x['name'] == 'passing'][0]['names']
        for team_data in self.team_stats_raw_data['teams']:
            temp_team = team_data['team']["abbreviation"]
            all_passing_dict = {"team": temp_team}
            all_passing_visibile_dict = {"team": temp_team}
            all_total_dict = {"team": temp_team}
            all_total_visibile_dict = {"team": temp_team}

            """
            Passing data
            """
            offsensive_passing = [x for x in team_data['categories'] if x['displayName'] == 'Own Passing'][0]['values']

            x = 0
            for cat in pass_categories:
                cf = cat.lower()
                if 'pass' in cf or 'completion' in cf or 'interceptions' in cf or 'sack' in cf or 'qb' in cf:
                    all_passing_dict.update({cat: offsensive_passing[x]})
                else:
                    all_total_dict.update({cat: offsensive_passing[x]})
                x = x + 1

            all_total_visibile_dict.update({"totalYds": all_total_dict['netTotalYards']})
            all_total_visibile_dict.update({"totalYdsPerGame": all_total_dict['netYardsPerGame']})
            all_total_visibile_dict.update({"points": all_total_dict['totalPoints']})
            all_total_visibile_dict.update({"pointsPerGame": all_total_dict['totalPointsPerGame']})
            all_passing_visibile_dict.update({"passingYds": all_passing_dict['netPassingYards']})
            all_passing_visibile_dict.update({"passingYdsPerGame": all_passing_dict['netPassingYardsPerGame']})

            self.teams_stats['offenseTotals'].append(all_total_dict.copy())
            self.teams_stats['offenseVisibleTotals'].append(all_total_visibile_dict.copy())
            self.teams_stats['offensePassing'].append(all_passing_dict.copy())
            self.teams_stats['offenseVisiblePassing'].append(all_passing_visibile_dict)

    def _add_rushing_stats_to_team_stats(self):
        categories = [x for x in self.team_stats_raw_data['categories'] if x['name'] == 'rushing'][0]['names']
        for team_data in self.team_stats_raw_data['teams']:
            temp_team = team_data['team']["abbreviation"]
            all_dict = {"team": temp_team}
            all_visibile_dict = {"team": temp_team}

            """
            data
            """
            data = [x for x in team_data['categories'] if x['displayName'] == 'Own Rushing'][0]['values']

            x = 0
            for cat in categories:
                all_dict.update({cat: data[x]})
                x = x + 1

            all_visibile_dict.update({"rushingYds": all_dict['rushingYards']})
            all_visibile_dict.update({"rushingYdsPerGame": all_dict['rushingYardsPerGame']})

            self.teams_stats['offenseRushing'].append(all_dict.copy())
            self.teams_stats['offenseVisibleRushing'].append(all_visibile_dict)

    def _add_defensive_rushing_stats_to_team_stats(self):
        categories = [x for x in self.team_stats_raw_data['categories'] if x['name'] == 'rushing'][0]['names']
        for team_data in self.team_stats_raw_data['teams']:
            temp_team = team_data['team']["abbreviation"]
            all_dict = {"team": temp_team}
            all_visibile_dict = {"team": temp_team}

            """
            data
            """
            data = [x for x in team_data['categories'] if x['displayName'] == 'Opponent Rushing'][0]['values']

            x = 0
            for cat in categories:
                all_dict.update({cat: data[x]})
                x = x + 1

            all_visibile_dict.update({"rushingYds": all_dict['rushingYards']})
            all_visibile_dict.update({"rushingYdsPerGame": all_dict['rushingYardsPerGame']})

            self.teams_stats['defenseRushing'].append(all_dict.copy())
            self.teams_stats['defenseVisibleRushing'].append(all_visibile_dict)

    def _add_defensive_passing_and_total_stats_to_team_stats(self):
        pass_categories = [x for x in self.team_stats_raw_data['categories'] if x['name'] == 'passing'][0]['names']
        for team_data in self.team_stats_raw_data['teams']:
            temp_team = team_data['team']["abbreviation"]
            all_passing_dict = {"team": temp_team}
            all_passing_visibile_dict = {"team": temp_team}
            all_total_dict = {"team": temp_team}
            all_total_visibile_dict = {"team": temp_team}

            """
            Passing data
            """
            offsensive_passing = [x for x in team_data['categories'] if x['displayName'] == 'Opponent Passing'][0]['values']

            x = 0
            for cat in pass_categories:
                cf = cat.lower()
                if 'pass' in cf or 'completion' in cf or 'interceptions' in cf or 'sack' in cf or 'qb' in cf:
                    all_passing_dict.update({cat: offsensive_passing[x]})
                else:
                    all_total_dict.update({cat: offsensive_passing[x]})
                x = x + 1

            all_total_visibile_dict.update({"totalYds": all_total_dict['netTotalYards']})
            all_total_visibile_dict.update({"totalYdsPerGame": all_total_dict['netYardsPerGame']})
            all_total_visibile_dict.update({"points": all_total_dict['totalPoints']})
            all_total_visibile_dict.update({"pointsPerGame": all_total_dict['totalPointsPerGame']})
            all_passing_visibile_dict.update({"passingYds": all_passing_dict['netPassingYards']})
            all_passing_visibile_dict.update({"passingYdsPerGame": all_passing_dict['netPassingYardsPerGame']})

            self.teams_stats['defenseTotals'].append(all_total_dict.copy())
            self.teams_stats['defenseVisibleTotals'].append(all_total_visibile_dict.copy())
            self.teams_stats['defensePassing'].append(all_passing_dict.copy())
            self.teams_stats['defenseVisiblePassing'].append(all_passing_visibile_dict)

    def _add_returning_teams_stats(self):
        categories = [x for x in self.team_stats_raw_data['categories'] if x['name'] == 'returning'][0]['names']
        for team_data in self.team_stats_raw_data['teams']:
            temp_team = team_data['team']["abbreviation"]
            all_dict = {"team": temp_team}
            all_visibile_dict = {"team": temp_team}

            """
            data
            """
            data = [x for x in team_data['categories'] if x['displayName'] == 'Own Returning'][0]['values']

            x = 0
            for cat in categories:
                all_dict.update({cat: data[x]})
                x = x + 1

            all_visibile_dict.update({"kickReturns": all_dict['kickReturns']})
            all_visibile_dict.update({"kickReturnYards": all_dict['kickReturnYards']})
            all_visibile_dict.update({"kickReturnAverage": all_dict['yardsPerKickReturn']})
            all_visibile_dict.update({"kickReturnLong": all_dict['longKickReturn']})
            all_visibile_dict.update({"kickReturnTouchdowns": all_dict['kickReturnTouchdowns']})

            all_visibile_dict.update({"puntReturns": all_dict['puntReturns']})
            all_visibile_dict.update({"puntReturnYards": all_dict['puntReturnYards']})
            all_visibile_dict.update({"puntReturnAverage": all_dict['yardsPerPuntReturn']})
            all_visibile_dict.update({"puntReturnLong": all_dict['longPuntReturn']})
            all_visibile_dict.update({"puntReturnTouchdowns": all_dict['puntReturnTouchdowns']})
            all_visibile_dict.update({"puntReturnFairCatches": all_dict['puntReturnFairCatches']})

            self.teams_stats['specialTeamsReturning'].append(all_dict.copy())
            self.teams_stats['specialTeamsVisibleReturning'].append(all_visibile_dict)

    def _add_misc_teams_stats(self, misc_type="Own"):
        categories = [x for x in self.team_stats_raw_data['categories'] if x['name'] == 'miscellaneous'][0]['names']
        for team_data in self.team_stats_raw_data['teams']:
            temp_team = team_data['team']["abbreviation"]
            all_dict = {"team": temp_team}
            all_visibile_dict = {"team": temp_team}

            """
            data
            """
            data = [x for x in team_data['categories'] if x['displayName'] == f'{misc_type} Miscellaneous'][0]['values']

            x = 0
            for cat in categories:
                all_dict.update({cat: data[x]})
                x = x + 1

            if misc_type == "Own":
                self.teams_stats['misc'].append(all_dict.copy())
            else:
                self.teams_stats['miscOpponent'].append(all_dict.copy())
    
    def get_all_teams_stats(self, season, regular_or_offseason='regular'):
        """
        Scrapes the following page: https://www.espn.com/nfl/stats/team

        :param season:
        :param regular_or_offseason:
        :return:
        """

        self._get_check_team_stats_raw_data(season, regular_or_offseason)
        self._add_passing_and_total_stats_to_team_stats()
        self._add_rushing_stats_to_team_stats()
        self._add_defensive_passing_and_total_stats_to_team_stats()
        self._add_defensive_rushing_stats_to_team_stats()
        self._add_returning_teams_stats()
        self._add_misc_teams_stats(misc_type="Own")
        self._add_misc_teams_stats(misc_type="Opponent")

        return self.teams_stats

    def team_stats_get_total_stats_for_team(self, team, ball_side="offense", visible_or_all="all"):
        team = team.lower()
        stat_key = ball_side.lower()
        key_term = f'{stat_key}Totals' if visible_or_all == "all" else f'{stat_key}VisibleTotals'
        return [x for x in self.teams_stats[key_term] if x['team'].lower() == team][0]

    def team_stats_get_passing_stats_for_team(self, team, ball_side="offense", visible_or_all="all"):
        team = team.lower()
        stat_key = ball_side.lower()
        key_term = f'{stat_key}Passing' if visible_or_all == "all" else f'{stat_key}VisiblePassing'
        return [x for x in self.teams_stats[key_term] if x['team'].lower() == team][0]

    def team_stats_get_rushing_stats_for_team(self, team, ball_side="offense", visible_or_all="all"):
        team = team.lower()
        stat_key = ball_side.lower()
        key_term = f'{stat_key}Rushing' if visible_or_all == "all" else f'{stat_key}VisibleRushing'
        return [x for x in self.teams_stats[key_term] if x['team'].lower() == team][0]

    def team_stats_get_ypg_summary(self, team, ball_side="offense"):
        """

        :param team:
        :param ball_side:       str(), offense or defense
        :return:
        """

        ball_side = ball_side.lower()
        stat_key = f'{ball_side}Totals'

        if not self.teams_stats[stat_key]:
            self._check_create_nfl_schedule()
            self.get_all_teams_stats(self.nfl_schedule.get_current_season())

        if ball_side == 'offense':
            total_stats = self.team_stats_get_total_stats_for_team(team, ball_side, visible_or_all='all')
            passing_stats = self.team_stats_get_passing_stats_for_team(team, ball_side, visible_or_all="all")
            rushing_stats = self.team_stats_get_rushing_stats_for_team(team, ball_side, visible_or_all="all")
        elif ball_side == 'defense':
            total_stats = self.team_stats_get_total_stats_for_team(team, ball_side, visible_or_all='all')
            passing_stats = self.team_stats_get_passing_stats_for_team(team, ball_side, visible_or_all="all")
            rushing_stats = self.team_stats_get_rushing_stats_for_team(team, ball_side, visible_or_all="all")
        else:
            print("ERROR: ball_side must be offesne or defense")
            return None

        t_ypg = total_stats["netYardsPerGame"]
        t_ppg = total_stats["totalPointsPerGame"]
        p_ypg = passing_stats["netPassingYardsPerGame"]
        p_ypa = passing_stats["netYardsPerPassAttempt"]
        r_ypg = rushing_stats["rushingYardsPerGame"]
        r_ypa = rushing_stats["yardsPerRushAttempt"]

        bp = True if ball_side == 'offense' else False
        t_ypg_rank = self._get_team_rank_for_stat(team, f'{ball_side}Totals', 'netYardsPerGame', more_is_better=bp)
        t_ppg_rank = self._get_team_rank_for_stat(team, f'{ball_side}Totals', 'totalPointsPerGame', more_is_better=bp)
        p_ypg_rank = self._get_team_rank_for_stat(team, f'{ball_side}Passing', 'netPassingYardsPerGame', more_is_better=bp)
        p_ypa_rank = self._get_team_rank_for_stat(team, f'{ball_side}Passing', 'netYardsPerPassAttempt', more_is_better=bp)
        r_ypg_rank = self._get_team_rank_for_stat(team, f'{ball_side}Rushing', 'rushingYardsPerGame', more_is_better=bp)
        r_ypa_rank = self._get_team_rank_for_stat(team, f'{ball_side}Rushing', 'yardsPerRushAttempt', more_is_better=bp)

        op_dict = {
            "totalYardsPerGame": t_ypg,
            "totalYardsPerGameRank": t_ypg_rank,
            "totalPointsPerGame": t_ppg,
            "totalPointsPerGameRank": t_ppg_rank,
            "passingYardsPerGame": p_ypg,
            "passingYardsPerGameRank": p_ypg_rank,
            "passingYardsPerAttempt": p_ypa,
            "passingYardsPerAttemptRank": p_ypa_rank,
            "rushingYardsPerGame": r_ypg,
            "rushingYardsPerGameRank": r_ypg_rank,
            "rushingYardsPerAttempt": r_ypa,
            "rushingYardsPerAttemptRank": r_ypa_rank
        }

        return op_dict

    ################################
    # Rosters
    def _check_load_player_list(self):
        if not self.player_list:
            self.get_league_player_list()
    
    def build_player_list(self):
        """
        Use this function to build a database of all players. This should be ran periodically to keep the list
        of players accurate.

        This function may take some time as it loops thru all depth charts

        The database is kept here:
        lukhed_sports/local_cache

        :return:
        """

        def _prevent_spam(count):
            if count != len(team_list) - 1:
                tC.sleep(1)

        fn = f'espn_{self.sport}_players.json'
        fp = osC.append_to_dir(self.cache_dir, fn)
        self._check_create_team_conversion_object()
        team_list = self.team_conversion_object.get_team_list('espn', 'cityShort', season="latest")
        op_dict = {"lastUpdate": tC.create_timestamp(), "players": None}

        all_players = []
        counter = 0
        for team in team_list:
            print(f'Getting roster for {team} ({counter + 1}/{len(team_list)})')

            dc = self.get_team_depth_chart(team)
            _prevent_spam(counter)

            if dc is None:
                print(f"ERROR: {team} roster could not get retrieved.")
            else:
                for group in dc:
                    position = group['position']
                    [x.update({"position": position, "team": team}) for x in group['players']]
                    all_players.extend(group['players'].copy())

            counter = counter + 1

        op_dict["players"] = all_players

        fC.dump_json_to_file(fp, op_dict)

        return all_players

    def get_league_player_list(self):
        fn = f'espn_{self.sport}_players.json'
        fp = osC.append_to_dir(self.cache_dir, fn)
        if osC.check_if_file_exists(fp):
            player_json = fC.load_json_from_file(fp)
        else:
            print("INFO: The player list has not been built yet. Building now.")
            self.build_player_list()
            player_json = fC.load_json_from_file(fp)

        self.player_list_last_updated = player_json["lastUpdate"]

        print(f"INFO: The player list was last updated: "
              f"{tC.convert_date_format(self.player_list_last_updated, '%Y%m%d%H%M%S')}. "
              f"You can run build_player_list() if it needs a refresh.")

        self.player_list = player_json["players"]

        return self.player_list

    def get_team_depth_chart(self, team):
        """
        This function scrapes from espn every time and does not cache. Use filter player list by team for getting
        all players on a team.
        :param team:
        :return:
        """
        self.team_roster = []
        team = team.lower()
        team.replace(" ", "-")
        url = f'https://www.espn.com/nfl/team/depth/_/name/{team}/'
        soup = self._special_request_handling(url)

        if soup is None:
            return None

        dc = self._get_json_from_script(soup)

        team_data = dc["page"]["content"]["depth"]["dethTeamGroups"]

        # Loop thru offense
        for grouping in team_data:
            for position in grouping["rows"]:
                position_name = position[0]
                table_name = grouping['name']
                players = [x for x in position[1:len(position)]]
                self.team_roster.append({"name": table_name, "team": team, "position": position_name,
                                         "players": players.copy()})

        return self.team_roster

    def player_search(self, name_to_search, last_name_search=False, first_name_search=False, team=None,
                      position=None, fuzzy_search=False, fuzzy_threshold=80):
        self._check_load_player_list()
        name_list = [x['name'] for x in self.player_list]
        matches_indices = advanced_player_search(name_to_search, name_list, search_last_name_only=last_name_search,
                                                  search_first_name_only=first_name_search, return_indices=True, 
                                                  fuzzy_search=fuzzy_search, fuzzy_threshold=fuzzy_threshold)
        player_dicts = [self.player_list[x] for x in matches_indices]

        if team is not None:
            player_dicts = [x for x in player_dicts if x["team"].lower() == team.lower()]

        if position is not None:
            player_dicts = [x for x in player_dicts if x["position"].lower() == position.lower()]

        return player_dicts

    def filter_player_list(self, team=None, position=None, injury=None):
        """

        :param team:            list or string

        :param position:        list or string: Use a grouping term or any individual position in the groupings.

                                Offense: QB, WR, TE, RB, FB, LT, LG, C, RG, RT
                                Defense: LDE, LDT, RDT, RDE, NT, WLB, MLB, SLB, LILB, RILB, LCB, SS, FS, RCB
                                ST: P, H, PR, KR, LS

                                QB: QB
                                Flex: WR, TE, RB, FB
                                OL: LT, LG, C, RG, RT
                                G: LG, RG
                                T: LT, RT
                                DL: LDE, LDT, RDT, RDE, NT
                                DE: LDE, RDE
                                DT: LDT, RDT, NT
                                LB: WLB, MLB, SLB, LILB, RILB
                                DB: LCB, SS, FS, RCB
                                S: SS, FS
                                CB: LCB, RCB
                                R (returner): PR, KR

        :param injury:          list or string: Use a grouping term or any individual injury in the groupings

                                NO (not out): Q or no injury designation. NOTE: if this is used it is the only term
                                              that can be used.
                                Q: Q
                                NP (not playing): O, SUSP, IR
                                D: D

        :return:                list of players that match the criteria
        """

        def _tune_position_list():
            if 'offense' in positions:
                positions.remove('offense')
                positions.extend(['qb', 'flex', 'ol'])
            if 'defense' in positions:
                positions.remove('defense')
                positions.extend(['dl', 'lb', 'db'])
            if 'flex' in positions:
                positions.remove("flex")
                positions.extend(['wr', 'rb', 'te'])
            if 'ol' in positions:
                positions.remove("ol")
                positions.extend(['lt', 'lg', 'c', 'rg', 'rt'])
            if 'g' in positions:
                positions.remove("g")
                positions.extend(['lg', 'rg'])
            if 't' in positions:
                positions.remove("t")
                positions.extend(['lt', 'rt'])
            if 'dl' in positions:
                positions.remove('dl')
                positions.extend(['lde', 'ldt', 'rdt', 'rde', 'nt'])
            if 'de' in positions:
                positions.remove('de')
                positions.extend(['lde', 'rde'])
            if 'dt' in positions:
                positions.remove('dt')
                positions.extend(['ldt', 'rdt', 'nt'])
            if 'lb' in positions:
                positions.remove('lb')
                positions.extend(['wlb', 'mlb', 'slb', 'lilb', 'rilb'])
            if 'db' in positions:
                positions.remove('db')
                positions.extend(['lcb', 'ss', 'fs', 'rcb'])
            if 'cb' in positions:
                positions.remove('cb')
                positions.extend(['lcb', 'rcb'])
            if 's' in positions:
                positions.remove('s')
                positions.extend(['ss', 'fs'])
            if 'st' in positions:
                positions.remove('st')
                positions.extend(['p', 'h', 'pr', 'kr', 'ls'])
            if 'r' in positions:
                positions.remove('r')
                positions.extend(['pr', 'kr'])


            return lC.return_unique_values(positions)

        def _tune_injury_list():
            if 'NP' in injuries:
                injuries.remove('NP')
                injuries.extend(['O', 'SUSP', 'IR'])

            return lC.return_unique_values(injuries)

        self._check_load_player_list()
        final_list = self.player_list
        if team is not None:
            if type(team) == list:
                teams = [x.lower() for x in team]
            else:
                teams = [team.lower()]

            final_list = [x for x in final_list if x['team'].lower() in teams]

        if position is not None:
            if type(position) == list:
                positions = [x.lower() for x in position]
            else:
                positions = [position.lower()]

            positions = _tune_position_list()

            final_list = [x for x in final_list if x['position'].lower() in positions]

        if injury is not None:
            if type(injury) == list:
                injuries = [x.upper() for x in injury]
            else:
                injuries = [injury.upper()]

            injuries = _tune_injury_list()

            if injuries == ['NO']:
                final_list = [x for x in final_list if 'Q' in x['injuries'] or x['injuries'] == []]
            else:
                final_list = [x for x in final_list if any(item in injuries for item in x['injuries'])]

        return final_list

    ################################
    # Player Stats
    def _player_search_common(self, player, last_name_only, first_name_only, team, position, force_single_result,
                              id_provided):
        self._check_load_player_list()

        if id_provided:
            player = str(player)
            try:
                return [x for x in self.player_list if f'http://www.espn.com/nfl/player/_/id/{player}' in x['href']][0]
            except IndexError:
                print("Player ID not found in player list. Try searching by name")
                return None
        else:
            search_result = self.player_search(player, last_name_search=last_name_only,
                                               first_name_search=first_name_only,
                                               team=team, position=position)
            if len(search_result) == 1 or force_single_result:
                try:
                    player_dict = search_result[0]
                    return player_dict
                except IndexError:
                    print("ERROR: No players match your search criteria.")
                    return None
            else:
                input(f"More than one player match the criteria. Enter the number of the player you want:\n")
                print("This function is not complete yet")
                return None

    def _scrape_player_data(self, url, data_type):
        """

        :param url:             Url is base url for player, for example:
                                'https://www.espn.com/nfl/player/_/id/4430807/bijan-robinson'

        :param data_type:       Below are the options and where it scrapes from:
                                overview - https://www.espn.com/nfl/player/_/id/4430807/bijan-robinson
                                bio - https://www.espn.com/nfl/player/bio/_/id/4430807/bijan-robinson
                                splits - https://www.espn.com/nfl/player/splits/_/id/4430807/bijan-robinson
                                gamelog - https://www.espn.com/nfl/player/gamelog/_/id/4430807/bijan-robinson

        :return:                dict(), stat dict based on input
        """

        def _overview_scrape():
            player_overall_stats = {
                "title": player_json['page']['content']['player']['stats']['title'],
                "stats": player_json['page']['content']['player']['stats']['splts']
            }
            player_recent_game_stats = {
                "title": player_json['page']['content']['player']['gmlg']['hdr'],
                "stats": player_json['page']['content']['player']['gmlg']['stats']
            }

            self.player_stats = {"overall": player_overall_stats, "recentGames": player_recent_game_stats}

        def _bio_scrape():
            self.raw_player_stats = player_json['page']['content']['player']["bio"]

        def _splits_scrape():
            self.raw_player_stats = player_json['page']['content']['player']["splt"]

        def _gamelog_scrape():
            self.raw_player_stats = player_json['page']['content']['player']["gmlog"]

        if data_type != 'overview':
            url_parts = url.split("/")
            url_parts.insert(5, data_type)
            url = '/'.join(url_parts)

        soup = self._special_request_handling(url)
        player_json = self._get_json_from_script(soup)


        if data_type == 'overview':
            _overview_scrape()
        elif data_type == 'bio':
            _bio_scrape()
        elif data_type == 'splits':
            _splits_scrape()
        elif data_type == 'gamelog':
            _gamelog_scrape()

        return self.raw_player_stats
    
    def get_player_stat_overview(self, player, last_name_only=False, first_name_only=False, team=None, position=None,
                                 force_single_result=False, id_provided=False):
        """
        Gets data from espn, the overview section for the player. See example page here:
        https://www.espn.com/nfl/player/_/id/4430807/bijan-robinson

        :param player:
        :param last_name_only:
        :param first_name_only:
        :param team:
        :param position:
        :param force_single_result:
        :param id_provided:
        :return:
        """

        res = self._player_search_common(player, last_name_only, first_name_only, team, position,
                                         force_single_result, id_provided)
        url = res['href']
        self._scrape_player_data(url, 'overview')
        self.raw_player_stats['playerDetails'] = res
        return self.player_stats

    def get_player_stat_bio(self, player, last_name_only=False, first_name_only=False, team=None, position=None,
                            force_single_result=False, id_provided=False):
        """
        Gets data from espn, the bio section for the player. See example page here:
        https://www.espn.com/nfl/player/bio/_/id/4430807/bijan-robinson

        :param player:
        :param last_name_only:
        :param first_name_only:
        :param team:
        :param position:
        :param force_single_result:
        :param id_provided:
        :return:
        """
        res = self._player_search_common(player, last_name_only, first_name_only, team, position, force_single_result,
                                         id_provided)
        url = res['href']
        self._scrape_player_data(url, 'bio')
        self.raw_player_stats['playerDetails'] = res
        return self.raw_player_stats

    def get_player_stat_splits(self, player, last_name_only=False, first_name_only=False, team=None, position=None,
                               force_single_result=False, id_provided=False):
        """
        Gets data from espn, the splits section for the player. See example page here:
        https://www.espn.com/nfl/player/splits/_/id/4430807/bijan-robinson

        :param player:
        :param last_name_only:
        :param first_name_only:
        :param team:
        :param position:
        :param force_single_result:
        :param id_provided:
        :return:
        """
        res = self._player_search_common(player, last_name_only, first_name_only, team, position, force_single_result,
                                         id_provided)
        url = res['href']
        self._scrape_player_data(url, 'splits')
        self.raw_player_stats['playerDetails'] = res
        return self.raw_player_stats

    def get_player_stat_gamelog(self, player, last_name_only=False, first_name_only=False, team=None, position=None,
                                force_single_result=False, id_provided=False):
        """
        Gets data from espn, the splits section for the player. See example page here:
        https://www.espn.com/nfl/player/splits/_/id/4430807/bijan-robinson

        :param player:
        :param last_name_only:
        :param first_name_only:
        :param team:
        :param position:
        :param force_single_result:
        :param id_provided:
        :return:
        """

        def _check_stat_applicability(stat_cat):
            try:
                return columns.index(stat_cat)
            except ValueError:
                return None

        res = self._player_search_common(player, last_name_only, first_name_only, team, position, force_single_result,
                                         id_provided)
        url = res['href']
        self._scrape_player_data(url, 'gamelog')

        self.player_stats = {
            "passing": {},
            "rushing": {},
            "receiving": {},
            "other": {},
            "tackles": {},
            "fumbles": {},
            "interceptions": {},
            "totals": {},
            "opponents": [],
            "gameDates": [],
            "gameResults": [],
            "playerDetails": res
        }

        stat_legend = {
            "passing": ['Completions', 'Passing Attempts', 'Passing Yards', 'Completion Percentage', 'Yards Per Pass Attempt', 'Passing Touchdowns', 'Interceptions', 'Longest Pass', 'Total Sacks', 'Passer Rating', 'Adjusted QBR'],
            "rushing": ["Rushing Attempts", "Rushing Yards", "Yards Per Rush Attempt", "Rushing Touchdowns", "Long Rushing"],
            "receiving": ['Receptions', 'Receiving Targets', 'Receiving Yards', 'Yards Per Reception', 'Receiving Touchdowns', 'Long Reception'],
            "other": ['Fumbles', 'Fumbles Lost', 'Forced Fumbles', 'Kicks Blocked'],
            "tackles": ["Total Tackles", "Solo Tackles", "Assist Tackles", "Sacks", "Stuffs", "Stuff Yards"],
            "fumbles": ["Fumbles", "Fumbles Lost", "Forced Fumbles", "Fumbles Recovered", "Kicks Blocked"],
            "interceptions": ["Interceptions", "Interception Yards", "Average Interception Yards", "Interception Touchdowns", "Long Interception", "Passes Defended"]
        }

        # Same for all
        try:
            self.player_stats["opponents"] = \
                [x['opp']['abbr'] for x in self.raw_player_stats['groups'][0]['tbls'][0]['events']]

            self.player_stats["gameDates"] = \
                [tC.convert_date_format(x['dt'], date_format='%Y-%m-%dT%H:%M:%S.%f%z', to_format="%a %m-%d")
                 for x in self.raw_player_stats['groups'][0]['tbls'][0]['events']]

            self.player_stats["gameResults"] = \
                [x['res']["abbr"] + f" {x['res']['score']}" for x in self.raw_player_stats['groups'][0]['tbls'][0]['events']]

            columns = [x['ttl'] for x in self.raw_player_stats['labels']]
        except:
            return self.player_stats


        # Get position dependent game stats
        applicable_stat_keys = []
        pos = res["position"]
        if pos == 'QB':
            applicable_stat_keys = ["passing", "rushing"]
        elif pos == "WR" or pos == "TE" or pos == "RB":
            applicable_stat_keys = ["rushing", "receiving", "other"]
        elif pos in ["LDE", "LDT", "RDT", "RDE", "NT", "WLB", "MLB", "SLB", "LILB", "RILB", "LCB", "SS", "FS", "RCB"]:
            applicable_stat_keys = ["tackles", "fumbles", "interceptions"]
        elif pos in ["PR", "KR"]:
            pass
        elif pos in ["P", "H", "PR", "KR", "LS"]:
            pass


        for stat_key in applicable_stat_keys:
            temp_stat_list = stat_legend[stat_key]
            for stat in temp_stat_list:
                temp_index = _check_stat_applicability(stat)
                if temp_index is not None:
                    game_results = []
                    for x in self.raw_player_stats['groups'][0]['tbls'][0]['events']:
                        try:
                            result = float(x['stats'][temp_index])
                            game_results.append(result)
                        except ValueError:
                            game_results.append('n/a')
                    self.player_stats[stat_key][stat.lower()] = game_results.copy()



        return self.player_stats
