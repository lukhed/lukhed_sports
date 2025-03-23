from lukhed_sports import leagueData
from lukhed_sports.espnWrapper import EspnStats

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

def espn_wrapper():
    # Build the player list: should be done periodically to ensure the most up-to-date data (roster chagnes, etc.)
    espn = EspnStats(sport='nfl')

    espn.build_player_list()
    # team_stats = espn.get_all_teams_stats('2023')
    stop = 1