"""Constants for the OpenRouter Credits integration."""

import logging

DOMAIN = "openrouter_credits"
LOGGER = logging.getLogger(__package__)

API_BASE = "https://openrouter.ai/api/v1"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 15  # minutes
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 1440
