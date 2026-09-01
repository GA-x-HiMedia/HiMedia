"""Which language the agent answers in.

The reply language is decided in Python from the message, then handed to the
model as an instruction. So this function alone decides whether a Bahraini
customer gets answered in the language they wrote in.

The case that matters here is code-switching, which is normal in Bahrain
rather than an edge case: people borrow English production terms inside an
Arabic sentence, and Arabic words inside an English one. Deciding on the
presence of a single Arabic character meant one borrowed word turned the whole
reply Arabic.

No network and no model key - this is pure text.
"""

import pytest

from agent import brain


@pytest.mark.parametrize("message", [
    "شنو التاسكات اللي عندي؟",
    "وش وضع الحملة؟",
    "تمام",
])
def test_arabic_messages_are_answered_in_arabic(message):
    assert brain._language_of(message) == "ar"


@pytest.mark.parametrize("message", [
    "what are my tasks?",
    "ok",
    "shno el tasks 3endi?",          # Arabic sounds, Latin letters
])
def test_english_and_latin_script_are_answered_in_english(message):
    assert brain._language_of(message) == "en"


@pytest.mark.parametrize("message", [
    "hi تمام thanks",
    "can you check the الحملة status please?",
])
def test_one_borrowed_arabic_word_does_not_flip_an_english_message(message):
    """The regression this file exists for: a single Arabic word inside an
    English sentence used to force the entire reply into Arabic."""
    assert brain._language_of(message) == "en"


@pytest.mark.parametrize("message", [
    "شنو الـ status حق الـ project؟",
    "وش صار على الـ deadline؟",
])
def test_english_terms_inside_an_arabic_sentence_stay_arabic(message):
    """The mirror case. English production words are longer, so counting
    characters would hand these to English; counting words does not."""
    assert brain._language_of(message) == "ar"


def test_a_message_with_no_letters_does_not_crash():
    for message in ("", "   ", "12345", "!!!"):
        assert brain._language_of(message) in ("ar", "en")
