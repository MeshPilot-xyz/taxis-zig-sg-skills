#!/usr/bin/env python3
"""CLI for Zig taxi fare queries."""

from __future__ import annotations

import asyncio
import json
import sys

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .auth import TokenManager
from .client import ZigClient
from .config import DEFAULT_LAT, DEFAULT_LNG, DEVICE_UDID, ENV_FILE, TOKEN_DIR

console = Console()


def _run(coro):
    """Bridge async to sync for click commands."""
    return asyncio.run(coro)


def _load_tokens() -> TokenManager:
    tm = TokenManager()
    if not tm.load():
        console.print("[red]Not logged in.[/red] Run: [bold]python -m zig-fare login[/bold]")
        sys.exit(1)
    return tm


# --- CLI Group ---

@click.group()
def cli():
    """Zig Fare — CDG ComfortDelGro taxi fare checker for Singapore."""
    pass


# --- Setup ---

@cli.command()
def setup():
    """Initialize config and generate a device UDID."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    console.print(f"Config directory: [bold]{TOKEN_DIR}[/bold]")
    console.print(f"Device UDID:     [cyan]{DEVICE_UDID}[/cyan]")
    console.print(f"Env file:        {ENV_FILE}")
    if ENV_FILE.exists():
        console.print(f"[green]Already configured.[/green]")
    else:
        console.print(f"[green]Generated new UDID and saved to .env[/green]")
    console.print()
    console.print("Next: [bold]python -m zig-fare login --mobile YOUR_NUMBER[/bold]")


# --- Login ---

@cli.command()
@click.option("--mobile", type=int, help="Phone number (without country code)")
@click.option("--country-code", type=int, default=65, help="Country code (default: 65)")
def login(mobile: int | None, country_code: int):
    """Login via SMS OTP."""

    async def _login():
        tm = TokenManager()
        # Try loading existing tokens for saved mobile
        tm.load()
        if mobile:
            phone = mobile
        elif tm.mobile:
            phone = tm.mobile
            console.print(f"Using saved number: [bold]+{country_code} {phone}[/bold]")
        else:
            phone = click.prompt("Phone number (without country code)", type=int)

        async with httpx.AsyncClient(http2=True, timeout=30.0) as http:
            # Send OTP
            console.print(f"Sending OTP to [bold]+{country_code} {phone}[/bold]...")
            result = await tm.send_otp(phone, country_code, http)
            console.print(f"[green]{result.get('message', 'OTP sent')}[/green]")

            # Get OTP from user
            code = click.prompt("Enter OTP code", type=int)

            # Verify OTP
            console.print("Verifying OTP...")
            otp_token = await tm.verify_otp(phone, country_code, code, http)
            console.print("[green]OTP verified[/green]")

            # Login
            console.print("Logging in...")
            data = await tm.login(phone, country_code, otp_token, http)
            expires_h = data.get("expiresIn", 0) / 3600
            console.print(
                f"[green bold]Login successful![/green bold] "
                f"Token expires in {expires_h:.0f}h. "
                f"Saved to {tm.token_file}"
            )

    _run(_login())


# --- Status ---

@cli.command()
def status():
    """Show current session status."""

    async def _status():
        tm = _load_tokens()
        import time
        remaining = tm.expires_at - time.time()
        hours = remaining / 3600

        table = Table(title="Session Status", show_header=False)
        table.add_column("Key", style="bold")
        table.add_column("Value")
        table.add_row("Mobile", f"+{tm.country_code} {tm.mobile}")
        table.add_row("Token expires in", f"{hours:.1f}h" if remaining > 0 else "[red]EXPIRED[/red]")
        table.add_row("Token file", str(tm.token_file))

        if remaining > 0:
            async with ZigClient(tm) as client:
                try:
                    profile = await client.get_profile()
                    table.add_row("Name", f"{profile.get('salutation', '')} {profile.get('paxName', '')}")
                    table.add_row("Email", profile.get("email", ""))
                except Exception as e:
                    table.add_row("Profile", f"[red]Error: {e}[/red]")

        console.print(table)

    _run(_status())


# --- Refresh ---

@cli.command()
def refresh():
    """Manually refresh the access token."""

    async def _refresh():
        tm = _load_tokens()
        async with httpx.AsyncClient(http2=True, timeout=30.0) as http:
            console.print("Refreshing token...")
            await tm.refresh(http)
            import time
            hours = (tm.expires_at - time.time()) / 3600
            console.print(f"[green]Token refreshed.[/green] Expires in {hours:.0f}h")

    _run(_refresh())


# --- Search ---

@cli.command()
@click.argument("query")
@click.option("--type", "search_type", type=click.Choice(["pickup", "dest"]), default="pickup", help="Search type")
@click.option("--lat", type=float, default=DEFAULT_LAT, help="Reference latitude")
@click.option("--lng", type=float, default=DEFAULT_LNG, help="Reference longitude")
@click.option("--json-output", is_flag=True, help="Output raw JSON")
def search(query: str, search_type: str, lat: float, lng: float, json_output: bool):
    """Search for an address by name."""

    async def _search():
        tm = _load_tokens()
        async with ZigClient(tm) as client:
            if search_type == "pickup":
                results = await client.search_pickup(query, lat, lng)
            else:
                results = await client.search_destination(query, lat, lng)

        if json_output:
            click.echo(json.dumps([vars(r) for r in results], indent=2, default=str))
            return

        if not results:
            console.print(f"[yellow]No results for '{query}'[/yellow]")
            return

        table = Table(title=f"Search: '{query}' ({search_type})")
        table.add_column("#", style="dim", width=3)
        table.add_column("Name", style="bold")
        table.add_column("Building")
        table.add_column("Address")
        table.add_column("Ref", style="cyan")

        for i, addr in enumerate(results, 1):
            table.add_row(str(i), addr.name, addr.building, addr.address, addr.addr_ref)

        console.print(table)

    _run(_search())


# --- Nearest ---

@cli.command()
@click.argument("lat", type=float)
@click.argument("lng", type=float)
def nearest(lat: float, lng: float):
    """Resolve coordinates to the nearest address."""

    async def _nearest():
        tm = _load_tokens()
        async with ZigClient(tm) as client:
            addr = await client.resolve_nearest(lat, lng)

        console.print(Panel(
            f"[bold]{addr.name}[/bold]\n"
            f"{addr.building}\n"
            f"{addr.address}\n"
            f"Ref: [cyan]{addr.addr_ref}[/cyan]  |  "
            f"Lat: {addr.lat:.6f}  Lng: {addr.lng:.6f}",
            title="Nearest Address",
        ))

    _run(_nearest())


# --- Fare ---

@cli.command()
@click.argument("pickup")
@click.argument("destination")
@click.option("--pickup-ref", help="Pickup addrRef (skip search)")
@click.option("--dest-ref", help="Destination addrRef (skip search)")
@click.option("--lat", type=float, default=DEFAULT_LAT, help="Reference latitude for searches")
@click.option("--lng", type=float, default=DEFAULT_LNG, help="Reference longitude for searches")
@click.option("--json-output", is_flag=True, help="Output raw JSON")
def fare(
    pickup: str,
    destination: str,
    pickup_ref: str | None,
    dest_ref: str | None,
    lat: float,
    lng: float,
    json_output: bool,
):
    """Get fare quotes between two locations.

    Examples:

        python -m zig-fare fare "Bedok Mall" "Changi Airport"

        python -m zig-fare fare _ _ --pickup-ref 674781 --dest-ref 717472
    """

    async def _fare():
        tm = _load_tokens()
        async with ZigClient(tm) as client:
            # Resolve pickup
            if pickup_ref:
                # Use nearest with a dummy search to resolve the ref
                pickup_results = await client.search_pickup(pickup, lat, lng)
                pickup_addr = next((a for a in pickup_results if a.addr_ref == pickup_ref), None)
                if not pickup_addr:
                    console.print(f"[red]Pickup ref {pickup_ref} not found in search results[/red]")
                    return
            else:
                console.print(f"Searching pickup: [bold]{pickup}[/bold]...")
                pickup_results = await client.search_pickup(pickup, lat, lng)
                if not pickup_results:
                    console.print(f"[red]No results for pickup '{pickup}'[/red]")
                    return
                pickup_addr = pickup_results[0]
                console.print(f"  → [cyan]{pickup_addr.name}[/cyan] ({pickup_addr.address})")

            # Resolve destination
            if dest_ref:
                dest_results = await client.search_destination(destination, lat, lng)
                dest_addr = next((a for a in dest_results if a.addr_ref == dest_ref), None)
                if not dest_addr:
                    console.print(f"[red]Dest ref {dest_ref} not found in search results[/red]")
                    return
            else:
                console.print(f"Searching destination: [bold]{destination}[/bold]...")
                dest_results = await client.search_destination(destination, lat, lng)
                if not dest_results:
                    console.print(f"[red]No results for destination '{destination}'[/red]")
                    return
                dest_addr = dest_results[0]
                console.print(f"  → [cyan]{dest_addr.name}[/cyan] ({dest_addr.address})")

            # Get fares
            console.print("Fetching fares...")
            quote = await client.get_fare(pickup_addr, dest_addr)

        if json_output:
            data = {
                "pickup": vars(quote.pickup),
                "destination": vars(quote.destination),
                "options": [vars(o) for o in quote.options],
            }
            click.echo(json.dumps(data, indent=2, default=str))
            return

        if not quote.options:
            console.print("[yellow]No fare options available for this route.[/yellow]")
            return

        table = Table(title=f"Fares: {quote.pickup.name} → {quote.destination.name}")
        table.add_column("Group", style="dim")
        table.add_column("Vehicle", style="bold")
        table.add_column("Seats", justify="center")
        table.add_column("Type", justify="center")
        table.add_column("Price", justify="right", style="green")
        table.add_column("Surge", justify="center")
        table.add_column("Notes")

        for opt in quote.options:
            surge_style = "red bold" if opt.surge_indicator > 0 else ""
            table.add_row(
                opt.group_name,
                opt.description,
                opt.seater,
                opt.fare_type,
                opt.price_display,
                f"[{surge_style}]{opt.surge_display}[/{surge_style}]" if opt.surge_display else "",
                opt.disclaimer or opt.remarks or "",
            )

        console.print(table)
        console.print(f"[dim]Fare ID: {quote.fare_id}[/dim]")

    _run(_fare())


# --- Entrypoint ---

def main():
    cli()


if __name__ == "__main__":
    main()
