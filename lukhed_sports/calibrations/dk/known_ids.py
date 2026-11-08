"""
Known DraftKings ids. Using these skips the navigation/league lookup calls entirely, which matters because
DraftKings rate limits on the total number of calls. Ids not listed here are discovered via the API at runtime.

Keys are lowercase and stripped. Last verified 2026-11-08 (see reference/dk_api.md).
"""

sport_ids = {
    "football": "3",
    "basketball": "2",
    "baseball": "7",
    "hockey": "8",
}

# Keyed by (sport, league)
league_ids = {
    ("football", "nfl"): "88808",
    ("football", "college football"): "87637",
    ("football", "college football - fcs"): "154752",
    ("basketball", "nba"): "42648",
    ("basketball", "wnba"): "94682",
    ("basketball", "college basketball (m)"): "92483",
    ("basketball", "college basketball (w)"): "36647",
}

# Keyed by league id -> {category name: category id}
category_ids = {
    "88808": {
        "game lines": 492,
        "td scorers": 1003,
        "live td scorers": 1054,
        "passing props": 1000,
        "rushing props": 1001,
        "receiving props": 1342,
        "defensive props": 1744,
        "kicking props": 638,
        "halves": 526,
        "quarters": 527,
        "game props": 528,
        "team props": 530,
        "futures": 529,
        "1st drive": 1303,
    },
}
