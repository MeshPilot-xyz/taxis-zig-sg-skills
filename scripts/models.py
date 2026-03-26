"""Data models for Zig API responses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Address:
    name: str
    building: str
    address: str
    postcode: str
    addr_ref: str
    lat: float
    lng: float
    source: str = ""  # "GOOGLE" or "INTERNAL"
    child_points: list[dict] = field(default_factory=list)

    @classmethod
    def from_nearest(cls, data: dict) -> Address:
        return cls(
            name=data.get("name", ""),
            building=data.get("building", ""),
            address=data.get("address", ""),
            postcode=data.get("postcode", ""),
            addr_ref=str(data.get("addrRef", "")),
            lat=data.get("addrLat", 0.0),
            lng=data.get("addrLng", 0.0),
            source="INTERNAL",
            child_points=data.get("childPoints", []),
        )

    @classmethod
    def from_search(cls, item: dict) -> Address:
        """Parse a search result item.

        Pickup results have addrRef nested inside a 'reference' object.
        Destination results have addrRef at the top level.
        """
        ref = item.get("reference", {})
        addr_ref = str(item.get("addrRef", "") or ref.get("addrRef", ""))
        return cls(
            name=item.get("name", ""),
            building=ref.get("building", item.get("building", "")),
            address=item.get("address", ""),
            postcode=item.get("postcode", ""),
            addr_ref=addr_ref,
            lat=item.get("addrLat", 0.0),
            lng=item.get("addrLng", 0.0),
            source=item.get("addrSource", ref.get("addrSource", "")),
            child_points=item.get("childPoints", ref.get("childPoints", [])),
        )


@dataclass
class FareOption:
    description: str
    seater: str
    fare_type: str  # "METER" or "FLAT"
    vehicle_type_id: int
    pdt_id: str
    fare_lower: float
    fare_upper: float
    surge_indicator: int
    remarks: str = ""
    icon_url: str = ""
    disclaimer: str = ""
    group_name: str = ""
    is_new: bool = False

    @classmethod
    def from_item(cls, item: dict, group_name: str = "") -> FareOption:
        return cls(
            description=item.get("description", ""),
            seater=item.get("seater", ""),
            fare_type=item.get("fareType", ""),
            vehicle_type_id=item.get("vehTypeId", 0),
            pdt_id=item.get("pdtId", ""),
            fare_lower=item.get("oriFareLower", 0.0),
            fare_upper=item.get("oriFareUpper", 0.0),
            surge_indicator=item.get("surgeIndicator", 0),
            remarks=item.get("remarks", ""),
            icon_url=item.get("featureIcon", ""),
            disclaimer=item.get("pdtDisclaimer", ""),
            group_name=group_name,
            is_new=item.get("isNew", False),
        )

    @property
    def price_display(self) -> str:
        if self.fare_type == "FLAT":
            return f"${self.fare_lower:.2f}"
        return f"${self.fare_lower:.2f} – ${self.fare_upper:.2f}"

    @property
    def surge_display(self) -> str:
        if self.surge_indicator > 0:
            return "↑ SURGE"
        elif self.surge_indicator < 0:
            return ""
        return ""


@dataclass
class FareQuote:
    pickup: Address
    destination: Address
    options: list[FareOption] = field(default_factory=list)
    fare_id: str = ""

    @classmethod
    def parse_structured(cls, data: dict, pickup: Address, dest: Address) -> FareQuote:
        options = []
        sections = data.get("structuredFares", [])
        # Only parse the "all" section to avoid duplicates
        for section in sections:
            if section.get("sectionCode") != "all":
                continue
            for group in section.get("groups", []):
                group_name = group.get("groupName", "")
                # Extract fareId from groupInfo URL
                group_info = group.get("groupInfo", "")
                fare_id = ""
                if "fareId=" in group_info:
                    fare_id = group_info.split("fareId=")[-1]
                for item in group.get("items", []):
                    options.append(FareOption.from_item(item, group_name))
        return cls(pickup=pickup, destination=dest, options=options, fare_id=fare_id)
