"""Async API client for Zig (CDG ComfortDelGro) taxi services."""

from __future__ import annotations

import random
import uuid

import httpx

from .auth import TokenManager
from .config import (
    BASE_URL,
    DEFAULT_VEHICLE_TYPE_IDS,
    DEVICE_INFO_B64,
    DEVICE_TYPE,
    DEVICE_UDID,
)
from .models import Address, FareQuote


def _trace_headers() -> dict:
    """Generate Datadog RUM trace headers with random IDs."""
    return {
        "x-datadog-trace-id": str(random.randint(1, 2**63)),
        "x-datadog-parent-id": str(random.randint(1, 2**63)),
        "x-datadog-sampling-priority": "2",
        "x-datadog-origin": "rum",
    }


class ZigClient:
    def __init__(self, tokens: TokenManager):
        self._tokens = tokens
        self._http = httpx.AsyncClient(
            http2=True,
            timeout=30.0,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    def _headers(self, access_token: str) -> dict:
        return {
            "authorization": f"Bearer {access_token}",
            "content-type": "application/json",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "x-device-info": DEVICE_INFO_B64,
            "x-device-udid": DEVICE_UDID,
            "x-device-type": DEVICE_TYPE,
            **_trace_headers(),
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated request with auto-retry on expired token."""
        token = await self._tokens.ensure_valid(self._http)
        resp = await self._http.request(
            method, f"{BASE_URL}{path}", headers=self._headers(token), **kwargs
        )
        data = resp.json()

        # Retry once on expired token
        if data.get("error", {}).get("code") == "ExpiredToken":
            await self._tokens.refresh(self._http)
            token = self._tokens.access_token
            resp = await self._http.request(
                method, f"{BASE_URL}{path}", headers=self._headers(token), **kwargs
            )
            data = resp.json()

        if data.get("responseCode", 0) not in (0, None) and "error" in data:
            raise ValueError(f"API error: {data.get('message', data)}")

        return data

    # --- Address APIs ---

    async def resolve_nearest(self, lat: float, lng: float) -> Address:
        """Resolve coordinates to the nearest known address."""
        data = await self._request("POST", "/pdcp/address/v1.0/nearest", json={"lat": lat, "lng": lng})
        return Address.from_nearest(data)

    async def search_pickup(self, query: str, lat: float, lng: float, radius: int = 1000) -> list[Address]:
        """Search for pickup locations by name."""
        data = await self._request(
            "POST",
            "/pdcp/address/v1.0/search-pickup",
            json={
                "searchStr": query,
                "lat": lat,
                "lng": lng,
                "radius": radius,
                "source": "GOOGLE",
                "sessionToken": str(uuid.uuid4()).upper(),
            },
        )
        return [Address.from_search(item) for item in data.get("data", [])]

    async def search_destination(self, query: str, lat: float, lng: float, radius: int = 1000) -> list[Address]:
        """Search for destination locations by name."""
        data = await self._request(
            "POST",
            "/pdcp/address/v1.0/search-destination",
            json={
                "searchStr": query,
                "lat": lat,
                "lng": lng,
                "radius": radius,
                "source": "GOOGLE",
                "sessionToken": str(uuid.uuid4()).upper(),
            },
        )
        return [Address.from_search(item) for item in data.get("data", [])]

    # --- Booking / Fare APIs ---

    async def get_possible_vehicles(self, pickup_addr_ref: str) -> list[int]:
        """Get available vehicle type IDs for a pickup location."""
        data = await self._request(
            "POST",
            "/pdcp/booking-trips/v1.0/bookings/possible-vehicle",
            json={"pickupAddrRef": pickup_addr_ref},
        )
        return data.get("vehicleTypeIds", [])

    async def get_fare(
        self,
        pickup: Address,
        dest: Address,
        vehicle_type_ids: list[str] | None = None,
    ) -> FareQuote:
        """Get fare quotes for all vehicle types between pickup and destination."""
        veh_ids = vehicle_type_ids or DEFAULT_VEHICLE_TYPE_IDS
        data = await self._request(
            "POST",
            "/pdcp/booking-trips/v1.0/bookings/fare",
            params={"structured": "true"},
            json={
                "pickupAddrRef": pickup.addr_ref,
                "pickupAddrLat": pickup.lat,
                "pickupAddrLng": pickup.lng,
                "destAddrRef": dest.addr_ref,
                "destAddrLat": dest.lat,
                "destAddrLng": dest.lng,
                "vehTypeIDs": veh_ids,
                "jobType": "IMMEDIATE",
                "paymentMode": 0,
                "fareVersion": 2,
                "freeInsurance": 0,
                "insuranceActivated": 0,
                "userEligibility": 0,
            },
        )
        return FareQuote.parse_structured(data, pickup, dest)

    # --- User APIs ---

    async def get_profile(self) -> dict:
        """Get the current user's profile."""
        return await self._request("GET", "/onecp/users/profile")

    async def get_active_bookings(self) -> list:
        """Get any active bookings."""
        data = await self._request("GET", "/pdcp/booking-trips/v1.3/bookings/active-bookings")
        return data.get("bookings", [])
