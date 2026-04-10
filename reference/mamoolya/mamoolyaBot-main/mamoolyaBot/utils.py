import datetime
import os
import subprocess
from pathlib import Path
from typing import Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]


def _iter_git_dirs() -> Iterable[Path]:
    """Yield unique candidate directories that may contain the git work tree."""
    candidates: List[Path] = []

    cwd = Path.cwd()
    candidates.append(REPO_ROOT)
    candidates.append(cwd)

    candidates.extend(REPO_ROOT.parents)
    candidates.extend(cwd.parents)

    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        yield resolved


def _git_describe_for_dir(path: Path) -> str:
    return (
        subprocess.check_output(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=path,
            stderr=subprocess.DEVNULL,
        )
        .decode("utf-8")
        .strip()
    )


def get_version() -> str:
    """
    Shows version from git tag.
    Needed to validate a version via /m_version command.

    Example output: v1.8.5-62-gb36a2ea-dirty

    Where:
    - v1.8.5 - closest last tag name
    - 62 - number of commits after the last tag
    - b36a2ea - short commit hash of the current deployed revision, if this specific revision is not tagged yet
    - dirty - if there are uncommitted changes. Means that someone messed up with files on the server directly.

    DO NOT TOUCH THIS.
    """
    for candidate in _iter_git_dirs():
        try:
            version = _git_describe_for_dir(candidate)
            if version:
                return version
        except Exception:
            continue

    env_version = os.getenv("MAMOOLYA_VERSION", "").strip()
    return env_version or "unknown"


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def utctoday() -> datetime.date:
    return utcnow().date()
