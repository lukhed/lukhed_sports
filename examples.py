from lukhed_sports import leagueData
from lukhed_sports.espnWrapper import EspnNflStats
from lukhed_sports.dkWrapper import DkSportsbook

def team_translation_example():
    # Example of how to use the TeamConversion class to translate team names between providers
    from_team = "San Francisco 49ers"
    from_provider = "Action Network"
    to_provider = "ESPN"

    print(f"This example will:\n"
          f"1. Instantiate the TeamConversion class with reset cache option = True\n"
          f"2. Check available providers supported by the class\n"
          f"3. Download the latest TeamConversion data from the cloud given instantiation method in #1\n"
          f"4. Translate the {from_team} team name as utilized by {from_provider} to the {to_provider} provider "
          f"cityShort format.\n")
    
    # Instantiate the TeamConversion class
    conversion = leagueData.TeamConversion(
        'nfl',
        reset_cache=True     # Optional, reset cache if you have not used the class in awhile
        )

    # Understand available providers for translation
    providers = conversion.get_supported_providers()
    print(f"\n\nAvilable providers:\n{providers}")

    # Translate a team name from one provider to another
    converted_team = conversion.convert_team(
        "San Francisco 49ers",
        from_provider=from_provider,
        to_provider=to_provider,
        from_team_type="long",
        to_team_type="cityShort",
        to_season=2022
        )
    
    print(f"The translated result is: {converted_team}")

#################################
# ESPN NFL Stats Wrapper Examples
def espn_nfl_stats_swrapper_build_player_list():
    # Build the player list: should be done periodically to ensure the most up-to-date data (roster changes, etc.)
    espn = EspnNflStats()
    espn.build_player_list()

def espn_nfl_stats_wrapper_player_search():
    espn = EspnNflStats()

    # Understand the positions and teams in the data
    team_list = espn.get_team_list()
    postion_list = espn.get_position_list()

    # Trying to look by full name by default, but misspelled will return []
    missspelled_name = espn.player_search('roquon smith')

    # I know how to spell his last name...Thats a lot of players named smith!
    all_players_with_last_name_smith = espn.player_search('smith', last_name_search=True)

    # I meant the one on the Ravens
    # Note: this will return multiple players if there are multiple players with the same name on the same team
    smith_lb_on_baltimore = espn.player_search('smith', team='Bal', position='LB')

    # Next time i'll use fuzzy match
    exact_player_match = espn.player_search('roquon smith', fuzzy_search=True)

def espn_nfl_stats_wrapper_get_player_stats():
    espn = EspnNflStats()
    # See example page: https://www.espn.com/nfl/player/gamelog/_/id/4430807/bijan-robinson

    # Get what is showing on game log page for player
    game_log_stats = espn.get_player_stat_gamelog('roquan smith', team='bal')

    # Specify a prior season (also showing advanced search options)
    prior_season_stats = espn.get_player_stat_gamelog('jackson', last_name_search=True, team='bal', season=2022, 
                                                      position='QB')
    
    # Get the last year college stats for player (2017 for Lamar jackson)
    college_stats = espn.get_player_stat_gamelog('jackson', last_name_search=True, team='bal', 
                                                 position='QB', league='college')
    
    # Get a specific college year stat (lamar freshman year)
    college_stats = espn.get_player_stat_gamelog('jackson', last_name_search=True, team='bal', season=2015, 
                                                 position='QB', league='college')

def dk_wrapper_example():
    """"
    This example uses default instantiation of dkWrapper which utilizes local cache for keeping basic 
    sports and league data. This limits the amount of api calls needed for many methods.
    
    If you have not used the class in awhile, you can reset the cache by setting reset_cache=True."
    """

    dk = DkSportsbook()

    # First understand what leagues are available at dk
    leagues = dk.get_available_leagues('basketball')
    print(f"Available leagues: {leagues}")

    # assuming college basketball (m) is a valid league and has lines available
    lines = dk.get_gamelines_for_league('college basketball (m)', filter_market='moneyline')
    print(f"Gamelines for college basketball (m): {lines}")