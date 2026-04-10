import unittest
from pathlib import Path
from unittest.mock import patch

from mamoolyaBot import utils


class GetVersionTests(unittest.TestCase):
    def test_get_version_tries_candidates_until_success(self):
        calls = []

        def fake_describe(path: Path) -> str:
            calls.append(path)
            if len(calls) < 2:
                raise RuntimeError("not a git repo")
            return "v1.2.3"

        with patch("mamoolyaBot.utils._git_describe_for_dir", side_effect=fake_describe):
            version = utils.get_version()

        self.assertEqual(version, "v1.2.3")
        self.assertGreaterEqual(len(calls), 2)

    def test_get_version_uses_env_fallback(self):
        with (
            patch("mamoolyaBot.utils._git_describe_for_dir", side_effect=RuntimeError("git error")),
            patch.dict("mamoolyaBot.utils.os.environ", {"MAMOOLYA_VERSION": "build-42"}, clear=False),
        ):
            version = utils.get_version()

        self.assertEqual(version, "build-42")

    def test_get_version_returns_unknown_on_error(self):
        with (
            patch("mamoolyaBot.utils._git_describe_for_dir", side_effect=RuntimeError("git error")),
            patch.dict("mamoolyaBot.utils.os.environ", {}, clear=True),
        ):
            version = utils.get_version()

        self.assertEqual(version, "unknown")


if __name__ == "__main__":
    unittest.main()
