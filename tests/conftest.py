"""Pytest configuration and test markers."""

import os

import pytest


def pytest_configure(config):
    # Register custom test markers.
    config.addinivalue_line(
        "markers", "live: needs network access to the real HiMedia sandbox")
    config.addinivalue_line(
        "markers", "needs_model: additionally needs a real model API key")


def _model_key_present() -> bool:
    """Checks whether a model API key is available."""
    return any(
        os.getenv(name)
        for name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY")
    )


def pytest_collection_modifyitems(config, items):
    """Skips tests when required services are unavailable."""
    run_live = os.getenv("RUN_LIVE_TESTS") == "1"
    have_model = _model_key_present()

    skip_live = pytest.mark.skip(
        reason="set RUN_LIVE_TESTS=1 to run tests against the real sandbox"
    )
    skip_model = pytest.mark.skip(
        reason="no model API key set — sandbox-only tests still run"
    )

    for item in items:
        if "live" in item.keywords and not run_live:
            item.add_marker(skip_live)

        elif "needs_model" in item.keywords and not have_model:
            item.add_marker(skip_model)