"""
Pytest configuration for the test suite.

Registers the `live` marker and automatically skips tests that need
access to the real HiMedia sandbox and a real API key unless
RUN_LIVE_TESTS=1 is explicitly set in the environment.
"""
import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "live: needs network access to the real HiMedia sandbox + a real OPENAI_API_KEY")


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_LIVE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="set RUN_LIVE_TESTS=1 in your shell to run tests against the real sandbox")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
