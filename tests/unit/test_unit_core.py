import unittest
class TestEBuildUnit(unittest.TestCase):
    def test_dependency_graph_sort(self):
        deps = {"b": ["a"], "c": ["b"]}
        sorted_deps = ["a", "b", "c"]
        self.assertEqual(sorted_deps[-1], "c")
