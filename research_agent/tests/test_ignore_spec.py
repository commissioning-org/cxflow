import tempfile
import unittest
from pathlib import Path

from research_agent.ignore import IgnoreSpec, load_ignore_rules


class IgnoreSpecTests(unittest.TestCase):
    def test_gitignore_like_rules_ignore_and_unignore(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".gitignore").write_text("""
# Ignore logs
*.log
!keep.log

# Ignore a directory
build/
""".strip() + "\n")

            (root / "a.log").write_text("x")
            (root / "keep.log").write_text("x")
            (root / "build").mkdir()
            (root / "build" / "out.txt").write_text("x")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("print('hi')")

            rules = load_ignore_rules(root, [".gitignore"])
            spec = IgnoreSpec(root=root, rules=rules)

            self.assertTrue(spec.is_ignored(root / "a.log"))
            self.assertFalse(spec.is_ignored(root / "keep.log"))
            self.assertTrue(spec.is_ignored(root / "build", is_dir=True))
            self.assertTrue(spec.is_ignored(root / "build" / "out.txt"))
            self.assertFalse(spec.is_ignored(root / "src" / "main.py"))


if __name__ == "__main__":
    unittest.main()
