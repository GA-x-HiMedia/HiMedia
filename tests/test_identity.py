"""
Identity tests. Checks that WhatsApp phone numbers are normalized
correctly across different formats before they are used to identify
a person. No network call.
"""
from agent.identity import tidy


def test_tidy_handles_whatsapp_prefix():
    assert tidy("whatsapp:+973 3300 0003") == "+97333000003"


def test_tidy_handles_00_prefix():
    assert tidy("00973 3300 0003") == "+97333000003"


def test_tidy_handles_bare_local_number():
    assert tidy("33000003") == "+97333000003"


def test_tidy_handles_already_correct_number():
    assert tidy("+97333000003") == "+97333000003"


def test_tidy_strips_punctuation():
    assert tidy("+973-3300-0003") == "+97333000003"


def test_tidy_handles_spaced_local_number():
    assert tidy("3300 0003") == "+97333000003"
