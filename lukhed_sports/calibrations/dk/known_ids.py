"""
Known DraftKings ids. Using these skips the navigation/league lookup calls entirely, which matters because
DraftKings rate limits on the total number of calls. Ids not listed here are discovered via the API at runtime.

Keys are lowercase and stripped. Last verified 2026-11-08 (see reference/dk_api.md).

Category ids appear to be shared within a sport (e.g. all basketball leagues use 487 for game lines), but only ids
seen in a response are listed. NHL and MLB category ids are not captured yet and are discovered at runtime.
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
    ("hockey", "nhl"): "42133",
    ("baseball", "mlb"): "84240",
}

# Keyed by league id -> {category name: category id}
category_ids = {
    # NFL
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
    # College Football
    "87637": {
        "game lines": 492,
        "1st drive": 1303,
        "halves": 526,
        "quarters": 527,
        "game props": 528,
        "futures": 529,
        "awards": 787,
        "playoffs": 1076,
        "playoff": 1858,
    },
    # NBA
    "42648": {
        "game lines": 487,
        "nba cup": 1284,
        "quick hits": 1157,
        "player points": 1215,
        "player threes": 1218,
        "player rebounds": 1216,
        "player assists": 1217,
        "player combos": 583,
        "player defense": 1293,
        "combined player props": 1683,
        "either player props": 1684,
        "game leaders": 1320,
        "player specials": 1280,
        "h2h player props": 1206,
        "halves": 520,
        "quarters": 522,
        "game props": 521,
        "team props": 523,
        "team futures": 519,
        "wins/playoffs": 1017,
        "awards": 518,
        "player props": 1241,
        "early season specials": 1870,
        "regular season wins": 1893,
        "playoffs": 1894,
        "play in": 1895,
    },
    # College Basketball (M)
    "92483": {
        "game lines": 487,
        "quick hits": 1157,
        "player points": 1215,
        "player threes": 1218,
        "player rebounds": 1216,
        "player assists": 1217,
        "player combos": 583,
        "halves": 520,
        "game props": 521,
        "team props": 523,
        "team futures": 519,
        "team specials": 1178,
        "awards": 518,
        "both players": 1987,
        "either player": 1988,
    },
    # College Basketball (W)
    "36647": {
        "game lines": 487,
        "team futures": 519,
        "awards": 518,
    },
    # WNBA (offseason capture: futures/awards only)
    "94682": {
        "team futures": 519,
        "awards": 518,
    },
}
