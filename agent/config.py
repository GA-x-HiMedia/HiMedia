"""
Reads environment variables and stops. No logic, no requests here — that's
the one rule for this file (Chapter 22).
"""
import os

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("HIMEDIA_BASE_URL", "https://ga-sandbox-production.up.railway.app")
API_KEY = os.getenv("HIMEDIA_API_KEY", "")

# Gemini free tier hit its 20-requests/day cap — switched brain.py over to
# Groq (also reached via the OpenAI-compatibility layer, so no code in
# brain.py beyond config values changes). Left GEMINI_* here, unused, in
# case we need to switch back or split load across providers later.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

HEADERS = {"X-API-Key": API_KEY}