import unittest

if __name__ == '__main__':
    # This will discover and run all tests in the tests directory
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests')
    
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)
