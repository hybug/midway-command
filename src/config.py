"""Configuration and constants."""
import os
from dotenv import load_dotenv

load_dotenv()

# Kimi Code - primary LLM provider
# Note: Kimi Code uses api.kimi.com, not api.moonshot.cn
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = "https://api.kimi.com/coding/v1"
MODEL = "kimi-for-coding"
MAX_TOKENS = 4096

# Legacy Anthropic config (kept for compatibility)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# Midway time constants
# MVP covers 1942-06-04 04:00 to 08:00 (Z+12, Midway time zone)
START_HOUR = 4
END_HOUR = 8
START_MINUTE = 0
