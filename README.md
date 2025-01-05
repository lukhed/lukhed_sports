# lukhed_sports
A collection of sports analysis utility functions and API wrappers

```bash
pip install lukhed-sports
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

### Basic Usage
```python
from lukhed_sports import SportsPage
```

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

Partial example resopnse below, for full example response [see here.](https://github.com/lukhed/lukhed_sports/blob/main/lukhed_sports/example_responses/getRankings.json)
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

