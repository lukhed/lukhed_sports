import unittest
from lukhed_sports.gameAnalysis import (
    convert_odds_format,
    calculate_implied_probability
)

class TestGameAnalysis(unittest.TestCase):
    def test_convert_odds_format(self):
        tolerance = 1.5
        test_cases = [
            {'fraction': '1/100', 'decimal': 1.01, 'american': -10000},
            {'fraction': '1/5', 'decimal': 1.20, 'american': -500},
            {'fraction': '2/9', 'decimal': 1.22, 'american': -450},
            {'fraction': '1/4', 'decimal': 1.25, 'american': -400},
            {'fraction': '2/7', 'decimal': 1.29, 'american': -350},
            {'fraction': '23/20', 'decimal': 2.15, 'american': 115},
            {'fraction': '6/5', 'decimal': 2.20, 'american': 120},
            {'fraction': '5/4', 'decimal': 2.25, 'american': 125},
            {'fraction': '11/8', 'decimal': 2.38, 'american': 138},
            {'fraction': '7/5', 'decimal': 2.40, 'american': 140},
            {'fraction': '6/4', 'decimal': 2.50, 'american': 150},
            {'fraction': '8/5', 'decimal': 2.60, 'american': 160},
        ]
        
        def fraction_to_decimal(fraction_str):
            """Convert fraction string to decimal value"""
            num, denom = map(int, fraction_str.split('/'))
            return num / denom
        
        def calculate_percentage_difference(value1, value2):
            """Calculate percentage difference between two values"""
            return abs((value1 - value2) / value2) * 100
        
        # Test decimal to american with mathematical comparison
        for case in test_cases:
            with self.subTest(f"Decimal {case['decimal']} to American"):
                result = convert_odds_format(case['decimal'], 'decimal', 'american')
                result_value = float(result.replace('+', ''))
                expected_value = float(str(case['american']).replace('+', ''))
                difference = calculate_percentage_difference(result_value, expected_value)
                self.assertLessEqual(
                    difference,
                    tolerance,
                    f"Conversion difference {difference:.2f}% exceeds {tolerance}% tolerance. Got {result} expected {case['american']}"
                )
                # Verify the +/- sign is correct
                self.assertEqual(result.startswith('+'), case['american'] > 0, 
                               f"Sign mismatch. Got {result}, expected {'positive' if case['american'] > 0 else 'negative'}")
        
        # Test decimal to fractional with mathematical comparison
        for case in test_cases:
            with self.subTest(f"Decimal {case['decimal']} to Fractional"):
                result = convert_odds_format(case['decimal'], 'decimal', 'fractional')
                result_decimal = fraction_to_decimal(result)
                expected_decimal = fraction_to_decimal(case['fraction'])
                difference = calculate_percentage_difference(result_decimal, expected_decimal)
                self.assertLessEqual(
                    difference, 
                    tolerance,
                    f"Conversion difference {difference:.2f}% exceeds {tolerance}% tolerance. Got {result} expected {case['fraction']}"
                )
                
        # Test american to decimal
        for case in test_cases:
            with self.subTest(f"American {case['american']} to Decimal"):
                result = convert_odds_format(case['american'], 'american', 'decimal')
                result_decimal = float(result)
                difference = calculate_percentage_difference(result_decimal, case['decimal'])
                self.assertLessEqual(
                    difference,
                    tolerance,
                    f"Conversion difference {difference:.2f}% exceeds {tolerance}% tolerance"
                )
                
        # Test fractional to decimal
        for case in test_cases:
            with self.subTest(f"Fractional {case['fraction']} to Decimal"):
                result = convert_odds_format(case['fraction'], 'fractional', 'decimal')
                result_decimal = float(result)
                difference = calculate_percentage_difference(result_decimal, case['decimal'])
                self.assertLessEqual(
                    difference,
                    tolerance,
                    f"Conversion difference {difference:.2f}% exceeds {tolerance}% tolerance"
                )
                
        # Test error cases
        with self.subTest("Invalid input format"):
            self.assertEqual(convert_odds_format(100, 'invalid', 'decimal'), "Invalid input format")
            
        with self.subTest("Invalid output format"):
            self.assertEqual(convert_odds_format(100, 'american', 'invalid'), "Invalid output format")
            
        with self.subTest("Invalid fractional format"):
            self.assertEqual(convert_odds_format('1:2', 'fractional', 'decimal'), "Invalid fractional odds format")

    def test_calculate_implied_probability(self):
        tolerance = 1
        test_cases = [
            {'fraction': '1/100', 'decimal': 1.01, 'american': -10000, 'probability': 0.99},
            {'fraction': '1/5', 'decimal': 1.20, 'american': -500, 'probability': 0.833},
            {'fraction': '2/9', 'decimal': 1.22, 'american': -450, 'probability': 0.818},
            {'fraction': '1/4', 'decimal': 1.25, 'american': -400, 'probability': 0.80},
            {'fraction': '2/7', 'decimal': 1.29, 'american': -350, 'probability': 0.778},
            {'fraction': '3/10', 'decimal': 1.30, 'american': -333, 'probability': 0.769},
            {'fraction': '1/3', 'decimal': 1.33, 'american': -300, 'probability': 0.75},
            {'fraction': '4/11', 'decimal': 1.36, 'american': -275, 'probability': 0.733},
            {'fraction': '2/5', 'decimal': 1.40, 'american': -250, 'probability': 0.714},
            {'fraction': '4/9', 'decimal': 1.44, 'american': -225, 'probability': 0.692},
            {'fraction': '1/2', 'decimal': 1.50, 'american': -200, 'probability': 0.667},
            {'fraction': '8/15', 'decimal': 1.53, 'american': -188, 'probability': 0.652},
            {'fraction': '4/7', 'decimal': 1.57, 'american': -175, 'probability': 0.636},
            {'fraction': '8/13', 'decimal': 1.62, 'american': -163, 'probability': 0.619},
            {'fraction': '4/6', 'decimal': 1.67, 'american': -150, 'probability': 0.60},
            {'fraction': '8/11', 'decimal': 1.73, 'american': -138, 'probability': 0.579},
            {'fraction': '4/5', 'decimal': 1.80, 'american': -125, 'probability': 0.556},
            {'fraction': '5/6', 'decimal': 1.83, 'american': -120, 'probability': 0.545},
            {'fraction': '10/11', 'decimal': 1.91, 'american': -110, 'probability': 0.524},
            {'fraction': '1/1', 'decimal': 2.00, 'american': 100, 'probability': 0.50},
            {'fraction': '21/20', 'decimal': 2.05, 'american': 105, 'probability': 0.488},
            {'fraction': '11/10', 'decimal': 2.10, 'american': 110, 'probability': 0.476},
            {'fraction': '23/20', 'decimal': 2.15, 'american': 115, 'probability': 0.465},
            {'fraction': '6/5', 'decimal': 2.20, 'american': 120, 'probability': 0.455},
            {'fraction': '5/4', 'decimal': 2.25, 'american': 125, 'probability': 0.444},
            {'fraction': '12/5', 'decimal': 3.40, 'american': 240, 'probability': 0.294},
            {'fraction': '5/2', 'decimal': 3.50, 'american': 250, 'probability': 0.286},
            {'fraction': '13/5', 'decimal': 3.60, 'american': 260, 'probability': 0.278},
            {'fraction': '11/4', 'decimal': 3.75, 'american': 275, 'probability': 0.267},
            {'fraction': '3/1', 'decimal': 4.00, 'american': 300, 'probability': 0.25},
            {'fraction': '16/5', 'decimal': 4.20, 'american': 320, 'probability': 0.238},
            {'fraction': '10/3', 'decimal': 4.33, 'american': 333, 'probability': 0.231},
            {'fraction': '7/2', 'decimal': 4.50, 'american': 350, 'probability': 0.222},
            {'fraction': '4/1', 'decimal': 5.00, 'american': 400, 'probability': 0.20},
            {'fraction': '9/2', 'decimal': 5.50, 'american': 450, 'probability': 0.182},
            {'fraction': '5/1', 'decimal': 6.00, 'american': 500, 'probability': 0.167},
            {'fraction': '11/2', 'decimal': 6.50, 'american': 550, 'probability': 0.154},
        ]

        def calculate_percentage_difference(value1, value2):
            """Calculate percentage difference between two values"""
            return abs((value1 - value2) / value2) * 100

        # Test American odds to implied probability
        for case in test_cases:
            with self.subTest(f"American {case['american']} to Probability"):
                result = calculate_implied_probability(case['american'], odds_type='american')
                difference = calculate_percentage_difference(result, case['probability'])
                self.assertLessEqual(
                    difference,
                    tolerance,
                    f"Conversion difference {difference:.2f}% exceeds {tolerance}% tolerance. Got {result} expected {case['probability']}"
                )

        # Test Decimal odds to implied probability  
        for case in test_cases:
            with self.subTest(f"Decimal {case['decimal']} to Probability"):
                result = calculate_implied_probability(case['decimal'], odds_type='decimal')
                difference = calculate_percentage_difference(result, case['probability'])
                self.assertLessEqual(
                    difference,
                    tolerance,
                    f"Conversion difference {difference:.2f}% exceeds {tolerance}% tolerance. Got {result} expected {case['probability']}"
                )

        # Test Fractional odds to implied probability
        for case in test_cases:
            with self.subTest(f"Fractional {case['fraction']} to Probability"):
                result = calculate_implied_probability(case['fraction'], odds_type='fractional')
                difference = calculate_percentage_difference(result, case['probability'])
                self.assertLessEqual(
                    difference,
                    tolerance,
                    f"Conversion difference {difference:.2f}% exceeds {tolerance}% tolerance. Got {result} expected {case['probability']}"
                )

        # Test error cases
        with self.subTest("Invalid odds type"):
            self.assertIsNone(calculate_implied_probability(100, 'invalid'))

        with self.subTest("Invalid odds value"):
            self.assertIsNone(calculate_implied_probability('invalid', 'american'))