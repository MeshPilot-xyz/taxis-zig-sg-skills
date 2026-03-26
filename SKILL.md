---
name: zig-fare
license: MIT
description: Query real-time taxi fare estimates from CDG Zig (ComfortDelGro) in Singapore. Search addresses, get fare quotes for all vehicle types between any two locations. Use when user asks to "check taxi fare", "how much to go from X to Y by taxi", "Zig fare", "CDG taxi price", "ComfortDelGro fare estimate", "book a taxi in Singapore", or any Singapore taxi fare query.
---

# Zig Fare

Query real-time taxi fare estimates from the **Zig** app (CDG ComfortDelGro, Singapore) via their reverse-engineered mobile API.

## Setup

### Dependencies
```bash
pip3 install "httpx[http2]>=0.27" "rich>=13.0" "click>=8.1"
```

### First-time setup
Generates a random device UDID and saves it to `~/.zig-fare/.env`:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup
```

### Authentication
Requires SMS OTP to the user's Singapore phone number. Tokens last 12 hours and auto-refresh.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py login --mobile <phone_number>
```

### Session refresh
Tokens auto-refresh, but can be manually refreshed:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py refresh
```

## Commands

### Get fare quotes

```bash
# By location name (auto-selects first search result)
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py fare "Bedok Mall" "Changi Airport"

# JSON output for scripting
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py fare "MBS" "Orchard" --json-output

# Custom reference lat/lng for better search results
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py fare "NUS" "Jurong East" --lat 1.2966 --lng 103.7764
```

### Search addresses

```bash
# Search pickup locations
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py search "Bugis Junction" --type pickup

# Search destinations
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py search "Changi Airport" --type dest

# JSON output
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py search "Orchard" --json-output
```

### Resolve coordinates

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py nearest 1.3000 103.9033
```

### Check session status

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py status
```

## How it works

### Authentication flow
1. `POST /auth/otp/v1.0/send` — sends SMS OTP to phone
2. `POST /auth/otp/v1.0/verify` — verifies code, returns `otpSessionToken`
3. `POST /auth/accounts/v1.0/login` — exchanges session token for `accessToken` (12h TTL) + `refreshToken`
4. `POST /auth/tokens/v1.0/refresh` — auto-called before expiry, returns new token pair

### Fare query flow
1. `POST /pdcp/address/v1.0/search-pickup` — resolve pickup name to `addrRef`
2. `POST /pdcp/address/v1.0/search-destination` — resolve destination name to `addrRef`
3. `POST /pdcp/booking-trips/v1.0/bookings/fare?structured=true` — get all vehicle pricing

### Fare response
Returns pricing for all vehicle types in one call:
- **Comfort Taxi** (4-seat, metered) — fare range
- **ComfortRIDE** (4-seat, flat rate) — fixed price
- **Taxi or Car** (nearest available, flat) — fixed price
- **Taxi or Car XL** (6-seat, flat) — fixed price
- **Limo / Limo Transfer** (4 or 6 seat) — premium pricing

Each option includes: fare type (METER/FLAT), price range, surge indicator, vehicle tags (child-friendly, wheelchair).

## Common workflows

### Example 1: Check taxi fare
User says: "How much is a taxi from Marina Bay Sands to Changi Airport?"
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py fare "Marina Bay Sands" "Changi Airport"
```

### Example 2: Compare options for a route
User says: "What are the cheapest taxi options from Orchard to Bedok?"
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py fare "Orchard" "Bedok"
```
Present the results table, highlighting the cheapest option.

### Example 3: Find an address
User says: "Find the nearest pickup point to Bugis"
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py search "Bugis" --type pickup
```

### Example 4: First-time setup
User says: "Set up the Zig fare checker"
```bash
pip3 install "httpx[http2]>=0.27" "rich>=13.0" "click>=8.1"
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py login --mobile <ask user for number>
# User receives SMS, enters OTP code when prompted
```

## Troubleshooting

### Error: Not logged in
Run `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py login --mobile <number>` to authenticate via SMS OTP.

### Error: Expired Token
Tokens auto-refresh, but if both tokens expired (>12h idle), re-login is required.

### Error: Invalid destination address ref
Some search results lack an `addrRef`. Try a more specific search query.

## Config

Stored at `~/.zig-fare/` (outside the repo):

| File | Contents |
|------|----------|
| `.env` | `ZIG_DEVICE_UDID` — auto-generated random device ID |
| `tokens.json` | Access + refresh tokens, phone number |

## File structure

```
zig-fare/
  SKILL.md                           # This file (skill instructions)
  README.md                          # Human-readable docs for GitHub
  scripts/
    run.py                           # Standalone entry point
    cli.py                           # Click CLI commands
    client.py                        # Async API client
    auth.py                          # Token lifecycle manager
    config.py                        # Constants and device config
    models.py                        # Data models (Address, FareQuote)
  references/
    api-reference.md                 # Full API endpoint documentation
```

For full API endpoint documentation, see [references/api-reference.md](references/api-reference.md).

## Disclaimer

This is an unofficial, reverse-engineered tool for educational and research purposes only. It is not affiliated with or endorsed by ComfortDelGro, CDG Zig, or any related entity. Use may violate the Zig app's Terms of Service. Use at your own risk.
