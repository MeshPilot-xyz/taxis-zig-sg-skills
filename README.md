# Zig Fare — CDG ComfortDelGro Taxi Fare Checker

> **Disclaimer:** This is an unofficial, reverse-engineered tool provided strictly for educational and research purposes. It is not affiliated with, endorsed by, or connected to ComfortDelGro Corporation, CDG Zig, or any related entity. Use of this tool may violate the Zig app's Terms of Service. **Use at your own risk.** See [full disclaimer](#disclaimer) below.

CLI tool to query real-time taxi fare estimates from the **Zig** app (CDG ComfortDelGro, Singapore) via their mobile API.

## How it works

This tool reverse-engineers the Zig iOS app's API (captured via mitmproxy) to:

1. **Authenticate** via SMS OTP (same flow as the app)
2. **Search addresses** using CDG's internal + Google Places database
3. **Get fare quotes** for all vehicle types between any two locations in Singapore

## Setup

```bash
cd zig-fare
pip install -r requirements.txt
python3 scripts/run.py setup
```

The `setup` command creates `~/.zig-fare/` and generates a random device UDID stored in `~/.zig-fare/.env`. This UDID identifies your "device" to the API — it's generated once and reused across sessions.

You can override it by setting the `ZIG_DEVICE_UDID` environment variable or editing `~/.zig-fare/.env`.

## Quick Start

### 1. Login (one-time, tokens last 12 hours)

```bash
python3 scripts/run.py login --mobile YOUR_PHONE_NUMBER
```

You'll receive an SMS OTP — enter it when prompted. Tokens are saved to `~/.zig-fare/tokens.json`.

### 2. Get fare quotes

```bash
python3 scripts/run.py fare "Bedok Mall" "Changi Airport"
```

Output:
```
Searching pickup: Bedok Mall...
  → Bedok Mall (311 New Upper Changi Road, Singapore 467360)
Searching destination: Changi Airport...
  → Changi Airport Terminal 1 (80 Airport Boulevard, Singapore 819642)
Fetching fares...

         Fares: Bedok Mall → Changi Airport Terminal 1
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Group          ┃ Vehicle          ┃ Seats┃ Type  ┃ Price            ┃ Surge ┃ Notes         ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Recommended    │ Comfort Taxi     │  4   │ METER │ $11.30 – $15.80  │       │ Child-friendly│
│ Recommended    │ Comfort Taxi     │  4   │ FLAT  │ $12.00           │       │ Fees may apply│
│ Recommended    │ Taxi or Car      │  4   │ FLAT  │ $12.00           │       │ Fees may apply│
│ Recommended    │ Taxi or Car XL   │  6   │ FLAT  │ $16.40           │       │ Fees may apply│
│ 4-Seater Limo  │ Limo Transfer    │  4   │ FLAT  │ $67.10           │       │               │
│ 4-Seater Limo  │ Limo             │  4   │ METER │ $24.80 – $28.30  │       │               │
│ 6-Seater Limo  │ Limo Transfer    │  6   │ FLAT  │ $72.10           │       │               │
│ 6-Seater Limo  │ Limo             │  6   │ METER │ $24.80 – $28.30  │       │               │
└────────────────┴──────────────────┴──────┴───────┴──────────────────┴───────┴───────────────┘
```

## Commands

### `login` — Authenticate via SMS OTP

```bash
python3 scripts/run.py login [--mobile NUMBER] [--country-code 65]
```

- Sends SMS OTP, prompts for code, saves tokens
- Tokens persist in `~/.zig-fare/tokens.json`
- Re-run to login again when tokens expire

### `status` — Check session info

```bash
python3 scripts/run.py status
```

Shows: name, mobile, token expiry, profile info.

### `refresh` — Manually refresh token

```bash
python3 scripts/run.py refresh
```

Extends the session by 12 hours. Also happens automatically when running other commands.

### `search` — Search for addresses

```bash
python3 scripts/run.py search "Bugis Junction" --type pickup
python3 scripts/run.py search "Changi Airport" --type dest
python3 scripts/run.py search "Orchard" --json-output
```

Returns address names, buildings, and `addrRef` IDs needed for fare queries.

### `nearest` — Resolve coordinates

```bash
python3 scripts/run.py nearest 1.3000 103.9033
```

Returns the nearest known address for given GPS coordinates.

### `fare` — Get fare quotes

```bash
# By name (auto-selects first search result)
python3 scripts/run.py fare "Silversea" "Bedok Mall"

# JSON output for scripting
python3 scripts/run.py fare "MBS" "Changi Airport" --json-output

# Custom reference lat/lng for better search results
python3 scripts/run.py fare "NUS" "Jurong East" --lat 1.2966 --lng 103.7764
```

## Token Lifecycle

```
┌──────────────┐    OTP     ┌──────────────┐   Verify   ┌──────────────┐
│  /otp/send   │ ────────→  │ /otp/verify  │ ────────→  │   /login     │
│  (SMS sent)  │            │ (code check) │            │ (get tokens) │
└──────────────┘            └──────────────┘            └──────┬───────┘
                                                               │
                                                               ▼
                                                    accessToken (12h TTL)
                                                    refreshToken (rotating)
                                                               │
                                                               ▼
                                                     ┌─────────────────┐
                                                     │ /tokens/refresh  │◄──┐
                                                     │ (extend session) │───┘
                                                     └─────────────────┘
                                                      auto-called before
                                                      each API request
```

- **Access token**: JWT, 12-hour TTL
- **Refresh token**: Opaque, rotates on each refresh
- **Auto-refresh**: The client checks token expiry before every request and refreshes automatically (with 5-minute buffer)
- **Persistence**: Tokens saved to `~/.zig-fare/tokens.json` — survives between CLI invocations

## API Endpoints Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/otp/v1.0/send` | POST | Send SMS OTP |
| `/auth/otp/v1.0/verify` | POST | Verify OTP → session token |
| `/auth/accounts/v1.0/login` | POST | Exchange session token → access + refresh |
| `/auth/tokens/v1.0/refresh` | POST | Refresh access token |
| `/pdcp/address/v1.0/nearest` | POST | Resolve coords → address |
| `/pdcp/address/v1.0/search-pickup` | POST | Search pickup locations |
| `/pdcp/address/v1.0/search-destination` | POST | Search destination locations |
| `/pdcp/booking-trips/v1.0/bookings/fare` | POST | Get fare quotes (all vehicle types) |
| `/pdcp/booking-trips/v1.0/bookings/possible-vehicle` | POST | Get available vehicle types |
| `/onecp/users/profile` | GET | User profile |

## File Locations

All sensitive data is stored in `~/.zig-fare/` (outside the repo):

| File | Contents |
|------|----------|
| `~/.zig-fare/.env` | `ZIG_DEVICE_UDID` — auto-generated random device ID |
| `~/.zig-fare/tokens.json` | Access + refresh tokens, phone number |

These files are in `.gitignore` and never committed.

## Disclaimer

**This is an unofficial, reverse-engineered tool provided strictly for educational and research purposes.**

- This project is **not affiliated with, endorsed by, or connected to** ComfortDelGro Corporation, CDG Zig, or any of their subsidiaries or partners.
- Use of this tool **may violate** the Zig app's Terms of Service. By using this software, you accept full responsibility for any consequences, including but not limited to account suspension or termination.
- This tool interacts with private, undocumented APIs that may change or break at any time without notice.
- The authors make **no warranties** of any kind, express or implied, about the completeness, accuracy, reliability, or suitability of this tool.
- **Do not use this tool** for any commercial purpose, automated fare scraping at scale, or any activity that could disrupt CDG's services.
- You are solely responsible for complying with all applicable laws and terms of service in your jurisdiction.

**USE AT YOUR OWN RISK.**
