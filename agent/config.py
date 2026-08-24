"""
Reads environment variables and stops. No logic, no requests here — that's
the one rule for this file (Chapter 22).
"""
import os

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("HIMEDIA_BASE_URL", "https://ga-sandbox-production.up.railway.app")
API_KEY = os.getenv("HIMEDIA_API_KEY", "")

# Gemini, via Google's OpenAI-compatibility layer — lets us keep using the
# `openai` Python library and brain.py's existing tool-calling code as-is.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

HEADERS = {"X-API-Key": API_KEY}
