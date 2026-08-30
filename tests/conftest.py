"""
Pytest configuration for the test suite.

Registers the `live` marker and automatically skips tests that need
access to the real HiMedia sandbox and a real API key unless
RUN_LIVE_TESTS=1 is explicitly set in the environment.
"""

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: needs network access to the real HiMedia sandbox")
    config.addinivalue_line(
        "markers", "needs_model: additionally needs a real model API key")


def _model_key_present() -> bool:
    """Any provider the project is wired for. brain.py currently reads
    GEMINI_API_KEY, so that is the one that actually unblocks a reply."""
    return any(os.getenv(name) for name in
               ("GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"))


def pytest_collection_modifyitems(config, items):
    """Two independent gates, so a missing model key does not hide the
    sandbox tests that would have run perfectly well without one."""
    run_live = os.getenv("RUN_LIVE_TESTS") == "1"
    have_model = _model_key_present()

    skip_live = pytest.mark.skip(
        reason="set RUN_LIVE_TESTS=1 to run tests against the real sandbox")
    skip_model = pytest.mark.skip(
        reason="no model API key set — sandbox-only tests still run")

    for item in items:
        if "live" in item.keywords and not run_live:
            item.add_marker(skip_live)
        elif "needs_model" in item.keywords and not have_model:
            item.add_marker(skip_model)
