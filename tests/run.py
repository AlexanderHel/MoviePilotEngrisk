import unittest

from tests.test_cookiecloud import CookieCloudTest
from tests.test_filter import FilterTest
from tests.test_metainfo import MetaInfoTest
from tests.test_recognize import RecognizeTest
from tests.test_transfer import TransferTest

if __name__ == '__main__':
    suite = unittest.TestSuite()

    #  Test filter
    suite.addTest(FilterTest('test_filter'))
    #  Test name identification
    suite.addTest(MetaInfoTest('test_metainfo'))
    #  Test media recognition
    suite.addTest(RecognizeTest('test_recognize'))
    #  Beta (software)CookieCloud Synchronization
    suite.addTest(CookieCloudTest('test_cookiecloud'))
    #  Test file transfer
    suite.addTest(TransferTest('test_transfer'))

    #  Operational test
    runner = unittest.TextTestRunner()
    runner.run(suite)
