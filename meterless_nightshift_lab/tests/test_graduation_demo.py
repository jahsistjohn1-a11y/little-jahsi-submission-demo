import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graduation_demo import ensure_demo, wire_demo
from lab import checked_bytes


class GraduationDemoTests(unittest.TestCase):
    def test_refuses_changed_patch_anchors(self):
        with self.assertRaisesRegex(ValueError, "anchor changed"):
            wire_demo("<html><head></head><body>unexpected new upstream</body></html>")

    def test_corrupt_existing_original_never_runs_or_silently_redownloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dest = root / ".runtime" / "graduation-loop-original.html"
            dest.parent.mkdir()
            dest.write_bytes(b"modified original")
            with self.assertRaisesRegex(ValueError, "differs"):
                ensure_demo(root, lambda _: self.fail("must not replace evidence"), checked_bytes)


if __name__ == "__main__":
    unittest.main()
