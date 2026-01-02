import tempfile
import unittest
from pathlib import Path

from research_agent.scanner import iter_files


class ScannerIterFilesTests(unittest.TestCase):
    def test_iter_files_respects_gitignore_and_extra_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".gitignore").write_text("node_modules/\n")

            (root / "node_modules").mkdir()
            (root / "node_modules" / "x.js").write_text("console.log('x')")

            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("print('hi')")
            (root / "secret.env").write_text("KEY=1")

            paths = list(iter_files(
                root,
                ignore_patterns=["*.env"],
                respect_gitignore=True,
                include_hidden=False,
                max_file_size_bytes=1_000_000,
            ))

            rel = sorted(p.relative_to(root).as_posix() for p in paths)
            self.assertIn("src/main.py", rel)
            self.assertNotIn("node_modules/x.js", rel)
            self.assertNotIn("secret.env", rel)


if __name__ == "__main__":
    unittest.main()
