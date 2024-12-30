# lukhed_sports
A collection of sports analysis utility functions and API wrappers

```bash
pip install lukhed-sports
```


## Sportspage Feeds Wrapper
This class is a custom wrapper for the sportspagefeeds API (https://sportspagefeeds.com/documentation). 

It provides:
- Management of api key -> You can store api key locally (by default) or with a private github repo 
    so you can use the api efficiently across different hardware.
- Optionally manage api limits (on by default) 
- Methods to utilize each endpoint
- Optionally validate input (on by default), to ensure you do not waste API calls
- Methods to get valid inputs for each endpoint, as documentation is sparse
- Methods to parse data returned by basic (non-paid) endpoints 

### Basic Usage
```python
from lukhed-sports import SportsPage
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
games = api.get_games('nba')
```

#### Check API Usage
```python
sP.check_api_limit()

>>>
You have 4 api calls remaining
Your reset time is set for 20241230194114 US/Eastern
Your limit is 20
```




#### Games
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
            "schedule": {
                "date": "2024-12-31T01:15:00.000Z",
                "tbaTime": false
            },
            "status": "scheduled",
            "teams": {
                "away": {
                    "team": "Detroit Lions",
                    "location": "Detroit",
                    "mascot": "Lions",
                    "abbreviation": "DET",
                    "conference": "NFC",
                    "division": "North"
                },
                "home": {
                    "team": "San Francisco 49ers",
                    "location": "San Francisco",
                    "mascot": "49ers",
                    "abbreviation": "SF",
                    "conference": "NFC",
                    "division": "West"
                }
            },
            "lastUpdated": "2024-12-30T19:10:22.234Z",
            "gameId": 312013,
            "venue": {
                "name": "Levi's Stadium",
                "neutralSite": false,
                "city": "Santa Clara",
                "state": "CA"
            },
            "odds": [
                {
                    "spread": {
                        "open": {
                            "away": -3.5,
                            "home": 3.5,
                            "awayOdds": -110,
                            "homeOdds": -110
                        },
                        "current": {
                            "away": -3.5,
                            "home": 3.5,
                            "awayOdds": -115,
                            "homeOdds": -110
                        }
                    },
                    "moneyline": {
                        "open": {
                            "awayOdds": -189,
                            "homeOdds": 158
                        },
                        "current": {
                            "awayOdds": -200,
                            "homeOdds": 167
                        }
                    },
                    "total": {
                        "open": {
                            "total": 51.5,
                            "overOdds": -110,
                            "underOdds": -110
                        },
                        "current": {
                            "total": 50,
                            "overOdds": -115,
                            "underOdds": -110
                        }
                    },
                    "openDate": "2024-12-23T08:36:31.974Z",
                    "lastUpdated": "2024-12-30T19:08:42.326Z"
                }
            ]
        }
    ]
}
```
