import unittest

import app


class WeakProofTest(unittest.TestCase):
    def test_version_exists(self):
        self.assertEqual(app.API_VERSION, "fixture-v1")


if __name__ == "__main__":
    unittest.main()
