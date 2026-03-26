"""Zig API configuration constants extracted from mitmproxy captures."""

import base64
import json
import os
import uuid
from pathlib import Path

BASE_URL = "https://api.zig.live"
CONTENT_URL = "https://content.zig.live"

# Config directory (also stores .env)
TOKEN_DIR = Path.home() / ".zig-fare"
TOKEN_FILE = TOKEN_DIR / "tokens.json"
ENV_FILE = TOKEN_DIR / ".env"


def _load_env() -> dict:
    """Load key=value pairs from .env file."""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _get_device_udid() -> str:
    """Get DEVICE_UDID from environment, .env file, or generate one."""
    # 1. Check environment variable
    udid = os.environ.get("ZIG_DEVICE_UDID")
    if udid:
        return udid

    # 2. Check .env file
    import stat

    env = _load_env()
    udid = env.get("ZIG_DEVICE_UDID")
    if udid:
        # Ensure permissions are tight on existing files
        if ENV_FILE.exists():
            os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
        if TOKEN_DIR.exists():
            os.chmod(TOKEN_DIR, stat.S_IRWXU)
        return udid

    # 3. Generate and persist a new one
    import stat

    udid = str(uuid.uuid4()).upper()
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(TOKEN_DIR, stat.S_IRWXU)
    with open(ENV_FILE, "a") as f:
        f.write(f"ZIG_DEVICE_UDID={udid}\n")
    os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return udid


# Device identity — loaded from ~/.zig-fare/.env (auto-generated on first run)
DEVICE_UDID = _get_device_udid()
DEVICE_TYPE = "IPHONE"

# Device info blob sent as base64 in x-device-info header
DEVICE_INFO = {
    "appName": "sg.com.comfortdelgro.taxibooking",
    "appVersion": "8.6.1",
    "model": "iPhone17,1",
    "osVersion": "26.4",
    "platform": "iOS",
}

DEVICE_INFO_B64 = base64.b64encode(
    json.dumps(DEVICE_INFO, separators=(",", ":")).encode()
).decode()

# Token refresh buffer (seconds before expiry to trigger refresh)
REFRESH_BUFFER = 300  # 5 minutes

# All vehicle type IDs the app sends when requesting fares
DEFAULT_VEHICLE_TYPE_IDS = [
    "128", "130", "133", "132", "0", "105",
    "3", "2", "36", "35", "1", "104",
]

# Default Singapore coordinates (city center)
DEFAULT_LAT = 1.3000
DEFAULT_LNG = 103.9033
