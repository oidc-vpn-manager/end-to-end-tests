#!/usr/bin/env python3
"""
Configuration for pre-flight tests
"""
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def repository_root():
    """
    Dynamically determine the repository root directory.
    This works regardless of whether tests are run from /home/user/... or /workspaces/...

    Returns:
        Path: Absolute path to the repository root
    """
    # Start from the current file's location and traverse up to find the repo root
    current_file = Path(__file__).resolve()

    # tests/pre-flight-tests/conftest.py -> tests/ -> repo_root/
    repo_root = current_file.parent.parent.parent

    # Verify this is actually the repository root by checking for key files
    assert (repo_root / "LLM_INTRO.md").exists(), f"Repository root not found from {current_file}"
    assert (repo_root / "tests").exists(), f"Tests directory not found in {repo_root}"

    return repo_root


@pytest.fixture(scope="session")
def tests_dir(repository_root):
    """
    Get the tests directory path.

    Returns:
        Path: Absolute path to the tests directory
    """
    return repository_root / "tests"
