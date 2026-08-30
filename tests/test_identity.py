"""
Identity tests.

Checks that WhatsApp phone numbers are normalized correctly across different
formats before they are used to identify a person.

No network call is made.
"""

from agent.identity import tidy


def test_tidy_handles_whatsapp_prefix():
    """Removes the WhatsApp prefix and normalizes the number."""
    assert tidy("whatsapp:+973 3300 0003") == "+97333000003"


def test_tidy_handles_00_prefix():
    """Converts the international 00 prefix into +."""
    assert tidy("00973 3300 0003") == "+97333000003"


def test_tidy_handles_bare_local_number():
    """Adds the Bahrain country code to a local number."""
    assert tidy("33000003") == "+97333000003"


def test_tidy_handles_already_correct_number():
    """Leaves an already normalized number unchanged."""
    assert tidy("+97333000003") == "+97333000003"


def test_tidy_strips_punctuation():
    """Removes punctuation from the phone number."""
    assert tidy("+973-3300-0003") == "+97333000003"


def test_tidy_handles_spaced_local_number():
    """Removes spaces and adds the Bahrain country code."""
    assert tidy("3300 0003") == "+97333000003"