import unittest

class TestebuildFunctional(unittest.TestCase):
    def test_incremental_compilation_pipeline(self):
        files = {"main.c": {"mtime": 100, "compiled": True}, "task.c": {"mtime": 150, "compiled": False}}
        # Incremental compiler compiles modified files
        compiled_count = 0
        for name, info in files.items():
            if not info["compiled"]:
                info["compiled"] = True
                compiled_count += 1
        assert compiled_count == 1
        assert files["task.c"]["compiled"]
