valid_input_last_update="12-30-2024"

leagues = ['nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab']

game_status = ['scheduled', 'in progress', 'final', 'canceled', 'delayed']

conferences = {
    'nfl': ['afc', 'nfc'],
    'nba': ['eastern', 'western'],
    'mlb': ['american league', 'national league'],
    'nhl': ['eastern', 'western'],
    'ncaaf': ['aac', 'big 12', 'big ten', 'conference usa', 'independent', 'mac', 'mountain west', 'pac 12', 
              'sec', 'sun belt'],
    'ncaab': ['aac', 'america east', 'atlantic 10', 'atlantic sun', 'big 12', 'big east', 'big sky', 'big south', 
              'big ten', 'big west', 'caa', 'conference usa', 'horizon league', 'ivy league', 'mac', 'meac', 
              'metro atlantic', 'missouri valley', 'mountain west', 'northeast', 'ohio valley', 'patriot league',
              'sec', 'swac', 'southern', 'southland', 'summit league', 'sun belt', 'west coast', 'western']
}

divisions = {
    'nfl': ['north', 'east', 'south', 'west'],
    'nba': ['atlantic', 'central', 'southeast', 'northwest', 'pacific', 'southwest'],
    'mlb': ['central', 'east', 'west'],
    'nhl': ['atlantic', 'metropolitan', 'central', 'pacific'],
    'ncaaf': ['n/a', 'east', 'west'],
    'ncaab': ['n/a', 'east', 'west']
}