# lukhed_sports
A collection of sports analysis utility functions and API wrappers

## Installation
```bash
pip install lukhed-sports
```

## Available Wrappers
[Sportspage Feeds Wrapper](#sportspage-feeds-wrapper) - For sports schedules and odds from [sportspagefeeds API](https://sportspagefeeds.com/documentation)
[Draftkings Sports Wrapper](#drafkings-sportsbook-wrapper) - For obtaining live data from [Draftkings sportsbook](https://sportsbook.draftkings.com/)


## Drafkings Sportsbook Wrapper
Access live data from Draftkings Sportsbook via their API methods. Quick start information below. Full documentation coming.

### Table of Contents
- [Instantiation](#instantiation)
- [get_available_leagues(sport)](#get_available_leagues)
- [get_spread_for_team(league, sport)](#get_spread_for_team)
- [get_game_lines_for_league(league)](#get_game_lines_for_league)
- [get_basic_touchdown_scorer_props(league, prop_type_filter=None, game_filter=None)](#get_basic_touchdown_scorer_props)

### Instantiation
```python
from lukhed_sports import DkSportsbook

api = DkSportsbook()
```

### get_available_leagues
```python
leagues = api.get_available_leagues('basketball')
```

```json
[
    "argentina - liga nacional de basquetbol",
    "australia - nbl",
    "brazil - nbb",
    "china - cba",
    "college basketball (m)",
    "college basketball (w)",
    "croatia premier league",
    "germany - bundesliga",
    "greece - basket league",
    "israel - super league (w)",
    "italy - lega 1",
    "korea - basketball league (w)",
    "nba",
    "turkey - bsl",
    "wnba"
]
```


### get_spread_for_team
```python
spread = api.get_spread_for_team('nfl', 'commanders')
```

```json
{
    "spread": 5.5,
    "odds": {
        "american": "-108",
        "decimal": "1.92",
        "fractional": "25/27"
    }
}
```

### get_gamelines_for_league
```python
gamelines = api.get_gamelines_for_league('nfl')
```
[Full example response](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/gamelinesForLeague.json)


### get_basic_touchdown_scorer_props
```python
gamelines = api.get_gamelines_for_league('nfl')
```

```json
[
    {
        "id": "0QA229129141#130806310_13L87637Q1477509025Q20",
        "marketId": "229129141",
        "label": "Jeremiah Smith",
        "displayOdds": {
            "american": "-140",
            "decimal": "1.71",
            "fractional": "5/7"
        },
        "trueOdds": 1.71428572,
        "outcomeType": "Anytime Scorer",
        "participants": [
            {
                "id": "786772",
                "name": "Jeremiah Smith",
                "type": "Player",
                "seoIdentifier": "Jeremiah Smith"
            }
        ],
        "sortOrder": 3001710,
        "tags": [
            "SGP",
            "1stFavorite"
        ],
        "metadata": {}
    },
    {
        "id": "0QA229129141#130806308_13L87637Q1709721529Q20",
        "marketId": "229129141",
        "label": "TreVeyon Henderson",
        "displayOdds": {
            "american": "-140",
            "decimal": "1.71",
            "fractional": "5/7"
        },
        "trueOdds": 1.71428572,
        "outcomeType": "Anytime Scorer",
        "participants": [
            {
                "id": "570977",
                "name": "TreVeyon Henderson",
                "type": "Player",
                "seoIdentifier": "TreVeyon Henderson"
            }
        ],
        "sortOrder": 3001710,
        "tags": [
            "SGP",
            "2ndFavorite"
        ],
        "metadata": {}
    },
    ...
```


## Sportspage Feeds Wrapper
This class is a custom wrapper for the [sportspagefeeds API](https://sportspagefeeds.com/documentation). 

It provides:
- Management of api key -> You can store api key locally (by default) or with a private github repo 
    so you can use the api efficiently across different hardware.
- Optionally manage api limits (on by default) 
- Methods to utilize each endpoint from sportspagefeeds
- Optionally validate input (on by default), to ensure you do not waste API calls
- Methods to get valid inputs for each endpoint, as documentation is sparse
- Methods to parse data returned by basic (non-paid) endpoints 

Full documentation for this class is in development.

#### API Key Management Locally
```python
# Upon first use, class will take you thru setup (copy and paste your Sportspage key)
api = SportsPage()
games = api.get_games('nfl')
```

#### API Key Managment with Private Github Repo
```python
# Upon first use, class will take you thru setup (github token and Sportspage key)
api = SportsPage(
    config_file_preference='github', 
    github_project='any_project_name'
    )
```

#### Games
```python
# Get games occuring today
api.get_games('nfl')
```

Partial example resopnse below, for full example response [see here.](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/nflGames.json)
```json
{
    "status": 200,
    "time": "2024-12-30T19:11:10.045Z",
    "games": 1,
    "skip": 0,
    "results": [
        {
            "summary": "Detroit Lions @ San Francisco 49ers",
            "details": {
                "league": "NFL",
                "seasonType": "regular",
                "season": 2024,
                "conferenceGame": true,
                "divisionGame": false
            },
    ...
```

#### Rankings
```python
rankings = api.get_rankings('ncaaf')
```

Partial example resopnse below, for full example response [see here.](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/getRankings.json)
```json
{
    "status": 200,
    "time": "2025-01-05T17:12:24.613Z",
    "results": [
        {
            "name": "College Football Playoff",
            "rankings": [
                {
                    "rank": 1,
                    "team": "Oregon",
                    "teamId": 1388
                },
                {
                    "rank": 2,
                    "team": "Georgia",
                    "teamId": 1365
                },
        ...
```

#### Check API Usage
```python
api.check_api_limit()

# print to console
>>>
You have 4 api calls remaining
Your reset time is set for 20241230194114 US/Eastern
Your limit is 20
```

Response
```json
{
    "limit": 20,
    "remaining": 15,
    "resetTime": "20250105194115",
    "lastCall": "20250105121251"
}
```


#### All Endpoints
```python
api.get_games           # Get schedule/status of games
api.get_rankings        # Get rankings for various leagues    
api.get_teams           # Get teams in leagues/conferences
api.get_conferences     # Get conferences in leagues
api.get_game_by_id      # Get info about a game by its ID
api.get_odds            # Get odds for a game (requires paid tier)
```

Example responses
<br>
[get_games nfl](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/nflGames.json)
<br>
[get_rankings ncaaf](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/getRankings.json)
<br>
[get_teams ncaaf](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/ncaafTeams.json)
<br>
[get_conferences ncaab](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/ncaabConferences.json)
<br>
[get_game_by_id nfl game id](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/getGameId.json)
<br>
[get_odds error response for non paid](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/getOddsById.json)

