"""
Reads environment variables and stops. No logic, no requests here — that's
the one rule for this file (Chapter 22).
"""
import os

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("HIMEDIA_BASE_URL", "https://ga-sandbox-production.up.railway.app")
API_KEY = os.getenv("HIMEDIA_API_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

HEADERS = {"X-API-Key": API_KEY}
