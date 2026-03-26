"""Token lifecycle manager for Zig API authentication."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from .config import (
    BASE_URL,
    DEVICE_INFO_B64,
    DEVICE_TYPE,
    DEVICE_UDID,
    REFRESH_BUFFER,
    TOKEN_DIR,
    TOKEN_FILE,
)


def _auth_headers() -> dict:
    """Headers used for auth endpoints (no Bearer token needed)."""
    return {
        "content-type": "application/json",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "x-device-info": DEVICE_INFO_B64,
    }


class TokenManager:
    def __init__(self, token_file: Path = TOKEN_FILE):
        self.token_file = token_file
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.expires_at: float = 0.0
        self.mobile: int | None = None
        self.country_code: int = 65

    def load(self) -> bool:
        """Load tokens from disk. Returns True if valid tokens exist."""
        if not self.token_file.exists():
            return False
        try:
            data = json.loads(self.token_file.read_text())
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.expires_at = data.get("expires_at", 0.0)
            self.mobile = data.get("mobile")
            self.country_code = data.get("country_code", 65)
            return self.refresh_token is not None
        except (json.JSONDecodeError, KeyError):
            return False

    def save(self) -> None:
        """Persist tokens to disk with restricted permissions (owner-only)."""
        import os
        import stat

        TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        # Restrict config directory to owner-only
        os.chmod(TOKEN_DIR, stat.S_IRWXU)

        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "mobile": self.mobile,
            "country_code": self.country_code,
        }
        self.token_file.write_text(json.dumps(data, indent=2))
        # Restrict token file to owner read/write only
        os.chmod(self.token_file, stat.S_IRUSR | stat.S_IWUSR)

    def is_expired(self) -> bool:
        """Check if access token is expired or about to expire."""
        return time.time() >= (self.expires_at - REFRESH_BUFFER)

    async def send_otp(self, mobile: int, country_code: int, http: httpx.AsyncClient) -> dict:
        """Send OTP via SMS."""
        resp = await http.post(
            f"{BASE_URL}/auth/otp/v1.0/send",
            headers=_auth_headers(),
            json={
                "mobile": mobile,
                "countryCode": country_code,
                "connection": "sms",
                "userType": "PAX",
                "deviceType": DEVICE_TYPE,
                "deviceUDID": DEVICE_UDID,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def verify_otp(
        self, mobile: int, country_code: int, code: int, http: httpx.AsyncClient
    ) -> str:
        """Verify OTP and return otpSessionToken."""
        resp = await http.post(
            f"{BASE_URL}/auth/otp/v1.0/verify",
            headers=_auth_headers(),
            json={
                "mobile": mobile,
                "countryCode": country_code,
                "code": code,
                "connection": "sms",
                "userType": "PAX",
                "deviceType": DEVICE_TYPE,
                "deviceUDID": DEVICE_UDID,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("verified"):
            raise ValueError(f"OTP verification failed: {data}")
        return data["otpSessionToken"]

    async def login(
        self, mobile: int, country_code: int, otp_session_token: str, http: httpx.AsyncClient
    ) -> dict:
        """Login with OTP session token to get access + refresh tokens."""
        headers = _auth_headers()
        headers["authorization"] = f"Bearer {otp_session_token}"
        resp = await http.post(
            f"{BASE_URL}/auth/accounts/v1.0/login",
            headers=headers,
            json={
                "mobile": mobile,
                "countryCode": country_code,
                "deviceUDID": DEVICE_UDID,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("refreshStatus") != "success":
            raise ValueError(f"Login failed: {data}")

        self.access_token = data["accessToken"]
        self.refresh_token = data["refreshToken"]
        self.expires_at = time.time() + data.get("expiresIn", 43200)
        self.mobile = mobile
        self.country_code = country_code
        self.save()
        return data

    async def refresh(self, http: httpx.AsyncClient) -> None:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise ValueError("No refresh token available. Please login first.")
        resp = await http.post(
            f"{BASE_URL}/auth/tokens/v1.0/refresh",
            headers=_auth_headers(),
            json={"refreshToken": self.refresh_token},
        )
        resp.raise_for_status()
        data = resp.json()

        self.access_token = data.get("accessToken", self.access_token)
        new_refresh = data.get("refreshToken")
        if new_refresh:
            self.refresh_token = new_refresh
        self.expires_at = time.time() + data.get("expiresIn", 43200)
        self.save()

    async def ensure_valid(self, http: httpx.AsyncClient) -> str:
        """Return a valid access token, refreshing if needed."""
        if self.is_expired():
            await self.refresh(http)
        if not self.access_token:
            raise ValueError("No access token. Please login first.")
        return self.access_token
