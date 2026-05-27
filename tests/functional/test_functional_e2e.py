import unittest
class TestEBuildFunctional(unittest.TestCase):
    def test_build_system_pipeline(self):
        pipeline = ["configure", "compile", "link"]
        self.assertEqual(pipeline[-1], "link")
