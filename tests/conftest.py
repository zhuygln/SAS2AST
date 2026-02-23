"""Fixture file loading helpers for sas2ast tests."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

SAS_CODE_DIR = Path(__file__).parent.parent / "sas_code"

FIXTURE_DIRS = {
    "data_step": SAS_CODE_DIR / "data_step",
    "proc": SAS_CODE_DIR / "proc",
    "macro": SAS_CODE_DIR / "macro",
    "mixed": SAS_CODE_DIR / "mixed",
    "deferred": SAS_CODE_DIR / "deferred",
}


def load_sas_fixture(category: str, name: str) -> str:
    """Load a SAS fixture file by category and name.

    Args:
        category: One of 'data_step', 'proc', 'macro', 'mixed', 'deferred'.
        name: Filename without extension (e.g., 'data_manipulation').

    Returns:
        The SAS source code as a string.
    """
    path = FIXTURE_DIRS[category] / f"{name}.sas"
    return path.read_text(encoding="utf-8")


def all_fixture_paths() -> list[Path]:
    """Return paths to all .sas fixture files."""
    return sorted(SAS_CODE_DIR.rglob("*.sas"))


@pytest.fixture
def sas_fixture():
    """Pytest fixture that returns a loader function."""
    return load_sas_fixture


@pytest.fixture
def all_fixtures():
    """Pytest fixture returning all .sas file paths."""
    return all_fixture_paths()
