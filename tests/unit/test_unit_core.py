import unittest

class TestebuildUnit(unittest.TestCase):
    def test_dependency_graph_cycle_detection(self):
        # Simulate dependency graph cycle detection
        graph = {"A": ["B"], "B": ["C"], "C": ["A"]} # Cycle A->B->C->A
        visited = set()
        def has_cycle(node, path):
            if node in path: return True
            if node in visited: return False
            visited.add(node)
            path.add(node)
            for dep in graph.get(node, []):
                if has_cycle(dep, path): return True
            path.remove(node)
            return False
        cycle_found = has_cycle("A", set())
        assert cycle_found, "Dependency graph failed to detect dependency cycle"
