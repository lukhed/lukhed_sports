from lukhed_basic_utils import mathCommon as mC


def grade_wager_side(pick_score, opp_score, pick_spread):
    pick_spread = convert_spread_to_float(pick_spread)
    try:
        pickDiff = float(pick_score) + float(pick_spread) - float(opp_score)
    except:
        return "error", "error"


    if pickDiff > 0:
        grade = 'w'
    elif pickDiff < 0:
        grade = 'l'
    elif pickDiff == 0:
        grade = 'push'
    else:
        grade = 'error'

    return grade, pickDiff


def grade_wager_total(awayScore, homeScore, totalLine, totalBet):
    # If you do not know the individual scores for each team, just put the total score in away or home and 0 in other
    # totalLine is the total
    # totalBet is over or under

    pickDiff = float(awayScore) + float(homeScore) - float(totalLine)

    if pickDiff == 0:
        grade = 'push'
        return grade, 0

    if totalBet.lower() == 'under' and pickDiff < 0:
        grade = 'w'
    elif totalBet.lower() == 'over' and pickDiff > 0:
        grade = 'w'
    else:
        grade = 'l'

    return grade, pickDiff


def grade_wager_moneyline(pick_score, opp_score):
    try:
        pick_score = int(pick_score)
        opp_score = int(opp_score)
    except:
        return "n/a"

    if pick_score > opp_score:
        return "w"
    elif pick_score < opp_score:
        return "l"
    else:
        return "push"


def calculate_unit_profit(odds, units, grade):
    # odds is -110 or 200, integer
    # units is number of units wagered, float
    # grade is w, l, or push, string
    # returns the profit given these inputs in units

    odds = int(odds)
    units = float(units)

    if grade == 'l':
        profitUnits = units*-1
        return profitUnits
    elif grade == 'push':
        return 0
    else:
        if odds < 0:
            profitUnits = round(abs(100 / odds) * units, 2)
        else:
            profitUnits = round(odds / 100 * units, 2)
        return profitUnits


def calculate_unit_profit_given_record(record_string, odds=-110, units=1, round_num=2):
    total_wins = get_wins_given_record(record_string)
    total_losses = get_losses_given_record(record_string)

    i = 0
    sum_units = 0
    while i < total_wins:
        sum_units = sum_units + calculate_unit_profit(odds, units, "w")
        i = i + 1

    i = 0
    while i < total_losses:
        sum_units = sum_units + calculate_unit_profit(odds, units, "l")
        i = i + 1

    return mC.pretty_round_function(sum_units, round_num)


def calculate_odd_move(start_odd, end_odd, odd_type="spread"):
    """
    Calculates and returns the odd move
    :param start_odd: string, float, or int where odd started
    :param end_odd: string, float, or int where odd ended
    :param odd_type: string: "spread", "total", "odd"
    :return: tuple of floats: (absolute value of move, move)
    """

    odd_type = odd_type.lower()

    abs_val = "N/A"
    mov_val = "N/A"
    try:
        start_odd = float(start_odd)
        end_odd = float(end_odd)
    except ValueError:
        return abs_val, mov_val

    if odd_type == "spread":
        abs_val = abs(start_odd - end_odd)
        mov_val = (start_odd - end_odd) * -1

    if mov_val == 0:  # get rid of negative 0.0
        mov_val = 0.0

    return abs_val, mov_val


def calculate_ats_data_for_game(away_score, home_score, home_spread, total):
    try:
        away_score = int(away_score)
    except ValueError:
        away_score = "n/a"
    try:
        home_score = int(home_score)
    except ValueError:
        home_score = "n/a"
    try:
        home_spread = float(home_spread)
    except ValueError:
        home_spread = "n/a"
    try:
        total = float(total)
    except ValueError:
        total = "n/a"

    if away_score == "n/a" or home_score == "n/a":
        # Can't do any useful calculations, return error dict
        return {
        "awayScore": away_score,
        "homeScore": home_score,
        "homeSpread": home_spread,
        "total": total,
        "winner": "n/a",
        "atsWinner": "n/a",
        "homeWinBy": "n/a",
        "awayWinBy": "n/a",
        "awayAtsGrade": "n/a",
        "homeAtsGrade": "n/a",
        "awayCoverBy": "n/a",
        "homeCoverBy": "n/a",
        "totalGrade": "n/a",
        "overCoverBy": "n/a",
        "underCoverBy": "n/a",
        "totalCoverBy": "n/a"
        }

    home_win_by = home_score - away_score
    away_win_by = away_score - home_score

    if home_win_by == 0:
        winner = "tie"
    elif home_win_by > 0:
        winner = "home"
    else:
        winner = "away"

    if home_spread == "n/a":
        # Can't do side calculations
        home_ats = "n/a"
        away_ats = "n/a"
        home_cover_by = "n/a"
        away_cover_by = "n/a"
        ats_winner = "n/a"
    else:
        home_adjusted_score = home_spread + home_score
        home_ats = ""
        away_ats = ""
        if home_adjusted_score == away_score:
            home_ats = 'push'
            away_ats = 'push'

        elif home_adjusted_score < away_score:
            home_ats = "loss"
            away_ats = "win"

        elif home_adjusted_score > away_score:
            home_ats = "win"
            away_ats = "loss"

        home_cover_by = home_adjusted_score - away_score
        away_cover_by = home_cover_by * -1

        if home_cover_by == 0:
            ats_winner = "tie"
        elif home_cover_by > 0:
            ats_winner = "home"
        else:
            ats_winner = "away"

    total_score = home_score + away_score


    if total == "n/a":
        # Can't do total calculations
        total_grade = "n/a"
        under_cover_by = "n/a"
        over_cover_by = "n/a"
        total_cover_by = "n/a"
    else:
        total_grade = ""
        if total_score == total:
            total_grade = "push"
            under_cover_by = 0
            over_cover_by = 0
        elif total_score > total:
            total_grade = "over"
            over_cover_by = total_score - total
            under_cover_by = over_cover_by * -1
        else:
            total_grade = "under"
            under_cover_by = total - total_score
            over_cover_by = under_cover_by * -1

        total_cover_by = total_score - total

    op_dict = {
        "awayScore": away_score,
        "homeScore": home_score,
        "homeSpread": home_spread,
        "total": total,
        "winner": winner,
        "atsWinner": ats_winner,
        "homeWinBy": home_win_by,
        "awayWinBy": away_win_by,
        "awayAtsGrade": away_ats,
        "homeAtsGrade": home_ats,
        "awayCoverBy": away_cover_by,
        "homeCoverBy": home_cover_by,
        "totalGrade": total_grade,
        "overCoverBy": over_cover_by,
        "underCoverBy": under_cover_by,
        "totalCoverBy": total_cover_by
    }

    return op_dict


def add_to_record(result, record="0-0-0"):
    """
    Creates a record based on input

    :param result: str(), win, loss, or tie/push
    :param record: str(), "0-0-0" ("win-loss-push")
    :return: str(), ats record format: "0-0-0" ("win-loss-push")
    """
    result = result.lower()
    wins = int(record.split("-")[0])
    losses = int(record.split("-")[1])
    pushes = int(record.split("-")[2])

    if result == "win" or result == "w":
        wins = wins + 1
    elif result == "loss" or result == "l":
        losses = losses + 1
    elif result == "push" or result == "tie" or result == "p":
        pushes = pushes + 1
    else:
        return "Error: invalid result. Use one of the following: win, loss, push/tie"

    wins = str(wins)
    losses = str(losses)
    pushes = str(pushes)

    return wins + "-" + losses + "-" + pushes


def add_to_streak(current_streak, result):
    """
    :param current_streak: int() or "N/A"
    :param result: str(), win, loss, or push/tie
    :return: int(), int is number of games of current streak ats (0, 1, -1, etc. - positive is wins, negative losses)
    """

    # input handling
    result = result.lower()
    if str(current_streak).lower() == "n/a":
        current_streak = 0
    else:
        try:
            current_streak = int(current_streak)
        except ValueError:
            return "Error: current streak provided was not an int() or 'N/A'"

    adder = convert_result_to_int(result)

    new_streak = int()
    if current_streak > 0 and adder <= 0:
        new_streak = adder
    elif current_streak > 0 and adder > 0:
        new_streak = current_streak + adder
    elif current_streak < 0 and adder >= 0:
        new_streak = adder
    elif current_streak < 0 and adder < 0:
        new_streak = current_streak + adder
    elif current_streak == 0:
        new_streak = adder

    return new_streak


def convert_result_to_int(result):
    """
    :param result: str(), win, loss, or push/tie
    :return: int(), win = 1, loss = -1, tie = 0
    """
    result = result.lower()
    if result == "win" or result == 'w':
        return 1
    elif result == "loss" or result == 'l':
        return -1
    elif result == "push" or result == "tie" or result == "p":
        return 0
    else:
        return "Error: Result provided was not a correct value. Options are: win, loss, push"


def get_games_played_given_record(record):
    """
    Returns the amount of games played given a record
    :param record: str(), format: "0-0-0", "wins-losses-pushes"
    :return: int(), total games played
    """

    return sum(map(int, record.split("-")))


def get_wins_given_record(record):
    """
    :param record: str(), example format "0-0-0"
    :return:
    """

    return int(record.split("-")[0])


def get_losses_given_record(record):
    """
    :param record: str(), example format "0-0-0"
    :return:
    """

    return int(record.split("-")[1])


def get_pushes_given_record(record):
    """
        :param record: str(), example format "0-0-0"
        :return:
        """

    return int(record.split("-")[2])


def convert_result_list_into_record(result_list):
    """
    Takes a list of results and outputs a record in the common record format
    :param result_list: list(), list of outcomes [loss, win, push, win, loss, w, l, p] etc.
    :return: str(), record: "0-0-0" ("wins-losses-pushes")
    """

    record = "0-0-0"
    for result in result_list:
        record = add_to_record(result, record)

    return record


def convert_result_list_into_streak(result_list):
    """
    Takes a result list where the most recent results are at the end of the list, and returns a streak.
    :param result_list: list(), list of outcomes [loss, win, push, win, loss] etc.
    :return: int(), representing a streak, e.g. -1 is one game losing streak
    """

    list_len = len(result_list)
    counter = list_len - 1
    streak = 0
    remember_outcome = ""
    while counter > -1:
        temp_outcome = result_list[counter].lower()
        if counter == list_len - 1:
            remember_outcome = temp_outcome
            streak = convert_result_to_int(temp_outcome)
        else:
            if remember_outcome == temp_outcome:
                streak = streak + convert_result_to_int(temp_outcome)
            else:
                return streak

        counter = counter - 1

    return streak


def convert_result_list_into_int_result_list(result_list):
    """
    :param result_list: list(), list of outcomes [loss, win, push, win, loss] etc.
    :return: list(), [-1, 1, 0, 1, -1] where losses: -1, wins: 1, pushes: 0
    """

    converted_list = list()
    for result in result_list:
        converted_list.append(convert_result_to_int(result))

    return converted_list


def convert_result_list_into_streak_list(result_list):
    streak_list = []
    i = 0
    while i < len(result_list):
        streak_list.append(convert_result_list_into_streak(result_list[0:i]))
        i = i + 1
    return streak_list


def count_outcomes_in_result_list(result_list, outcome_type):
    """
    Counts the desired amount of outcomes matching the outcome_type in a result list.
    :param result_list: list(), list of outcomes [loss, win, push, win, loss] etc.
    :param outcome_type: str(), win, loss, push
    :return: int(), count of outcome_type
    """
    return result_list.count(outcome_type)


def calculate_spread_move(open_spread, latest_spread, move_type="absolute"):
    open_spread = float(open_spread)
    latest_spread = float(latest_spread)

    if move_type == "absolute":
        spread_diff = open_spread - latest_spread
        return abs(spread_diff)
    elif move_type == "value":
        # This will calculate the amount of spread points gained or lost due to the move, from the perspective
        # of the open spread as the one received by the better
        return open_spread - latest_spread


###############################
# Determine games
###############################
def determine_spread_winner(away_score, home_score, spread_float, spread_for="away"):
    spread_float = convert_spread_to_float(spread_float)

    try:
        if spread_for == "away":
            res = grade_wager_side(away_score, home_score, spread_float)[0]
            if res == "w":
                return "away"
            elif res == "l":
                return "home"
            else:
                return "push"
        elif spread_for == "home":
            res = grade_wager_side(home_score, away_score, spread_float)[0]
            if res == "w":
                return "home"
            elif res == "l":
                return "away"
            else:
                return "push"
        else:
            return "n/a"
    except:
        return "n/a"
    
def determine_game_winner(away_score, home_score):
    try:
        away_score = int(away_score)
        home_score = int(home_score)
    except:
        return "n/a"

    if away_score > home_score:
        return "away"
    elif away_score < home_score:
        return "home"
    else:
        return "push"
    
def determine_favorite_for_game(away_spread, home_spread, inverse=False):
    try:
        away_spread = float(away_spread)
    except ValueError:
        return "invalid away spread"

    try:
        home_spread = float(home_spread)
    except ValueError:
        return "invalid home spread"

    if away_spread == 0 or home_spread == 0:
        return "pk"
    elif away_spread > 0:
        if inverse:
            return "away"
        else:
            return "home"
    else:
        if inverse:
            return "home"
        else:
            return "away"
        

###############################
# Team record Conversions
###############################
def get_plus_minus_given_record(record_string):
    """
    Takes a record string and calculates the plus minus. Pushes are 0, losses are -1, and wins are 1.

    For example
    1-0-0 = 1
    0-1-0 = -1

    :param record_string:       str(), record example: '1-0-0'
    :return:                    int(), plush minus calculated
    """

    wins = get_wins_given_record(record_string)
    losses = get_losses_given_record(record_string)

    return wins - losses

def calculate_record_percentages(record, round_decimal_points=2):
    """
    Comprehensive win/loss/push percentage calculations based on records

    Parameters
    ----------
    record : str
        format: "w-l-t", for example "8-2-1"
    
    round_decimal_points : int
        The number of spots to round the decimal point to, default is 2

    Returns
    -------
    dict
        Comprehensive percentage calculations based on records in the form of a dict:
        1. winPercentage (Standard Definition): Wins divided by total games, including pushes.
        2. winPercentagePushesHalf: Each push is considered as half a win.
        3. winPercentageIgnorePushes: Pushes are excluded from the total game count.
        4. lossPercentage (Standard Definition): Losses divided by total games, including pushes.
        5. lossPercentagePushesHalf: Each push is considered as half a loss.
        6. lossPercentageIgnorePushes: Pushes are excluded from the total game count.
        7. pushPercentage: Proportion of games that resulted in a push.
    """

    wins, losses, pushes = map(int, record.split('-'))
    total_games = wins + losses + pushes
    
    # 1.
    win_percentage_standard = (wins / total_games) * 100 if total_games > 0 else 'undefined'
    
    # 2.
    win_percentage_half_push = ((wins + 0.5 * pushes) / total_games) * 100 if total_games > 0 else 'undefined'
    
    # 3.
    games_without_pushes = wins + losses
    win_percentage_ignore_push = (wins / games_without_pushes) * 100 if games_without_pushes > 0 else 'undefined'
    
    # 4.
    loss_percentage_standard = (losses / total_games) * 100 if total_games > 0 else 'undefined'
    
    # 5.
    loss_percentage_half_push = ((losses + 0.5 * pushes) / total_games) * 100 if total_games > 0 else 'undefined'
    
    # 6.
    loss_percentage_ignore_push = (losses / games_without_pushes) * 100 if games_without_pushes > 0 else 'undefined'
    
    # 7. Push percentage
    push_percentage = (pushes / total_games) * 100 if total_games > 0 else 'undefined'

    r = round_decimal_points
    return {
        "winPercentage": mC.pretty_round_function(win_percentage_standard, r),
        "winPercentagePushesHalf": mC.pretty_round_function(win_percentage_half_push, r),
        "winPercentageIgnorePushes": mC.pretty_round_function(win_percentage_ignore_push, r),
        "lossPercentage": mC.pretty_round_function(loss_percentage_standard, r),
        "lossPercentagePushesHalf": mC.pretty_round_function(loss_percentage_half_push, r),
        "lossPercentageIgnorePushes": mC.pretty_round_function(loss_percentage_ignore_push, r),
        "pushPercentage": mC.pretty_round_function(push_percentage, r)
    }

def calculate_win_rate_given_record(record, exclude_push=False):
    """
    :param record: str(), format: "w-l-t", for example "8-2-1"
    :param exclude_push: bool(), if true, win rate will ignore pushes, just use wins and losses. If false pushes
                         will be considered in the win rate.
    :return: str(), percent string, for example "56%"
    """

    record_list = record.split("-")
    wins = int(record_list[0])
    losses = int(record_list[1])
    pushes = int(record_list[2])

    if exclude_push:
        d = wins + losses
        n = wins
    else:
        d = wins + losses + pushes
        n = wins

    if d == 0:
        return "undefined"
    else:
        return mC.pretty_round_function(n/d, round_num=2)


###############################
# Odds Conversions
###############################
def calculate_implied_probability(odds, odds_type="american", round_digit=4):
    """
    Calculates the implied probability of a given odds value.

    Parameters
    ----------
    odds : int, float, str
        The odds value to calculate the implied probability for.
    odds_type : str, optional
        The type of odds value provided. Options are "american", "decimal", "fractional", by default "american"
    round_digit : int, optional
        The number of decimal places to round the implied probability to, by default 4

    Returns
    -------
    float or None
        The implied probability as a decimal (e.g., 0.6000 for 60%)
        Returns None if input is invalid or calculation fails
    """
    try:
        # Convert to decimal odds first
        decimal_odds = convert_odds_format(odds, odds_type, 'decimal')
        
        # Check if conversion failed
        if isinstance(decimal_odds, str):
            return None
            
        probability = 1 / float(decimal_odds)
        return round(probability, round_digit)
    except (ValueError, TypeError, ZeroDivisionError):
        return None
    
def convert_odds_format(odds, input_format, output_format):
    """
    Converts odds from one format to another.

    Parameters
    ----------
    odds : str, int, float
        The odds value to convert
    input_format : str
        The format of the input odds: 'american', 'decimal', or 'fractional'
    output_format : str
        The desired output format: 'american', 'decimal', or 'fractional'

    Returns
    -------
    str, int, or float
        The converted odds value in the requested format
    """
    input_format = input_format.lower()
    output_format = output_format.lower()

    if input_format == output_format:
        return odds

    # First convert input to decimal as intermediate format
    decimal_odds = None

    # Convert input to decimal odds with high precision
    if input_format == "american":
        american = float(odds)
        if american > 0:
            decimal_odds = round((american / 100.0) + 1, 6)
        else:
            decimal_odds = round((100.0 / abs(american)) + 1, 6)
    
    elif input_format == "decimal":
        decimal_odds = round(float(odds), 6)
    
    elif input_format == "fractional":
        if '/' in str(odds):
            num, denom = map(int, str(odds).split('/'))
            decimal_odds = round(num / denom + 1, 6)
        else:
            return "Invalid fractional odds format"
    else:
        return "Invalid input format"

    # Convert decimal odds to desired output format
    if output_format == "decimal":
        return round(decimal_odds, 3)
    
    elif output_format == "american":
        if decimal_odds >= 2.0:
            american = int(round((decimal_odds - 1) * 100))
            return f"+{american}"
        else:
            american = int(round(-100 / (decimal_odds - 1)))
            return str(american)
    
    elif output_format == "fractional":
        # Convert to simplified fraction
        decimal = decimal_odds - 1  # Remove the 1 to get just the profit part
        if decimal == 0:
            return "0/1"
        
        precision = 1000
        h = int(round(decimal * precision))
        k = precision
        
        # Find greatest common divisor
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a
        
        divisor = gcd(h, k)
        h = h // divisor
        k = k // divisor
        
        return f"{h}/{k}"
    
    else:
        return "Invalid output format"

def make_spread_pretty(spread):
    """
    Takes in a spread as an int() or str(). Returns the spread as a str() that is pretty for printing.
    EV is used for 0
    Positive spreads get a "+" in front

    :param spread:
    :return:
    """

    if type(spread) is str:
        spread = float(spread)

    if type(spread) is float or type(spread) is int:
        if spread > 0:
            return "+" + str(spread)
        elif spread < 0:
            return str(spread)
        else:
            return "EV"

    return None

def convert_american_odds_to_int(american_odds):
    return int(american_odds)

def convert_spread_to_float(spread_to_convert):
    try:
        return float(spread_to_convert)
    except:
        if type(spread_to_convert) is str:
            if spread_to_convert == "pk" or spread_to_convert == "PK" or spread_to_convert.lower() == "ev":
                return 0.0
            elif spread_to_convert == "" or spread_to_convert is None or spread_to_convert.lower() == "n/a":
                return "n/a"
        else:
            return "n/a"
