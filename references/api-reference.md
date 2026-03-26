# Zig API Reference

Base URL: `https://api.zig.live`

## Authentication Endpoints

### Send OTP
```
POST /auth/otp/v1.0/send
```
**Request:**
```json
{
  "mobile": 91234567,
  "countryCode": 65,
  "connection": "sms",
  "userType": "PAX",
  "deviceType": "IPHONE",
  "deviceUDID": "<uuid>"
}
```
**Response:**
```json
{
  "status": "successful",
  "message": "SMS OTP sent successfully.\nThe OTP will expire in 120 seconds"
}
```

### Verify OTP
```
POST /auth/otp/v1.0/verify
```
**Request:**
```json
{
  "mobile": 91234567,
  "countryCode": 65,
  "code": 1234,
  "connection": "sms",
  "userType": "PAX",
  "deviceType": "IPHONE",
  "deviceUDID": "<uuid>"
}
```
**Response:**
```json
{
  "verified": true,
  "otpSessionToken": "eyJ..."
}
```

### Login
```
POST /auth/accounts/v1.0/login
Headers: Authorization: Bearer <otpSessionToken>
```
**Request:**
```json
{
  "mobile": 91234567,
  "countryCode": 65,
  "deviceUDID": "<uuid>"
}
```
**Response:**
```json
{
  "refreshStatus": "success",
  "accessToken": "eyJ...",
  "refreshToken": "a1b2c...",
  "expiresIn": 43200,
  "tokenType": "Bearer"
}
```

### Refresh Token
```
POST /auth/tokens/v1.0/refresh
```
**Request:**
```json
{
  "refreshToken": "a1b2c..."
}
```
**Response:** Same format as login. Both `accessToken` and `refreshToken` rotate on each refresh.

### Logout
```
POST /auth/accounts/v1.0/logout
```
**Request:**
```json
{
  "refreshToken": "a1b2c..."
}
```

## Address Endpoints

All require `Authorization: Bearer <accessToken>`.

### Resolve Nearest Address
```
POST /pdcp/address/v1.0/nearest
```
**Request:**
```json
{
  "lat": 1.3000,
  "lng": 103.9033
}
```
**Response:**
```json
{
  "responseCode": 0,
  "message": "Success",
  "name": "Silversea",
  "building": "Silversea",
  "address": "52 Marine Parade Road, Singapore 449308",
  "postcode": "449308",
  "geoDistance": 674781.0,
  "addrRef": "674781",
  "addrLat": 1.3000290890545216,
  "addrLng": 103.903135658494
}
```

### Search Pickup
```
POST /pdcp/address/v1.0/search-pickup
```
**Request:**
```json
{
  "searchStr": "Bedok Mall",
  "lat": 1.30,
  "lng": 103.90,
  "radius": 1000,
  "source": "GOOGLE",
  "sessionToken": "<uuid>"
}
```
**Response:** Array of addresses with nested `reference` object containing `addrRef`. Pickup results have `addrRef` inside the `reference` sub-object.

### Search Destination
```
POST /pdcp/address/v1.0/search-destination
```
Same request format as search-pickup. Destination results have `addrRef` at the top level (no `reference` nesting).

### Suggest Destinations
```
POST /pdcp/address/v1.0/suggestions-destination
```
**Request:** `{}`
**Response:** Recent destinations with `addrRef`.

## Booking / Fare Endpoints

### Get Possible Vehicles
```
POST /pdcp/booking-trips/v1.0/bookings/possible-vehicle
```
**Request:**
```json
{
  "pickupAddrRef": "674781"
}
```
**Response:**
```json
{
  "vehicleTypeIds": [132, 105],
  "responseCode": 0,
  "message": "Success"
}
```

### Get Fare Quotes
```
POST /pdcp/booking-trips/v1.0/bookings/fare?structured=true
```
**Request:**
```json
{
  "pickupAddrRef": "674781",
  "pickupAddrLat": 1.3000,
  "pickupAddrLng": 103.9031,
  "destAddrRef": "717472",
  "destAddrLat": 1.3382,
  "destAddrLng": 103.9299,
  "vehTypeIDs": ["128","130","133","132","0","105","3","2","36","35","1","104"],
  "jobType": "IMMEDIATE",
  "paymentMode": 0,
  "fareVersion": 2,
  "freeInsurance": 0,
  "insuranceActivated": 0,
  "userEligibility": 0
}
```
**Response:** Structured fares grouped by section (all, child, wheelchair) and vehicle group (Recommended, 4-Seater Limo, 6-Seater Limo). Each item includes:
- `description`: Vehicle name
- `seater`: "4" or "6"
- `fareType`: "METER" or "FLAT"
- `vehTypeId`: Vehicle type ID
- `oriFareLower` / `oriFareUpper`: Price range in SGD
- `surgeIndicator`: -1 (no surge), 0 (normal), >0 (surge active)
- `pdtDisclaimer`: e.g. "Fees may apply"
- `vehicleTags`: `{child: true, wheelchair: true}`

### Get Active Bookings
```
GET /pdcp/booking-trips/v1.3/bookings/active-bookings
```

### Get Outstanding Fees
```
GET /pdcp/booking-trips/v1.3/outstanding-fees
```

## User Endpoints

### Get Profile
```
GET /onecp/users/profile
```
**Response:**
```json
{
  "paxName": "JOHN",
  "salutation": "Mr",
  "mobile": "91234567",
  "countryCode": "65",
  "email": "john@example.com",
  "birthDate": "011990",
  "deviceType": "IPHONE"
}
```

### Get User ID
```
GET /onecp/users/me
```

### Update Profile
```
PUT /onecp/profiles/<userId>
```

## Common Headers

All authenticated requests use:
```
Authorization: Bearer <accessToken>
Content-Type: application/json
Accept: */*
Accept-Language: en-US,en;q=0.9
X-Device-Info: <base64 encoded device info JSON>
X-Device-UDID: <device UUID>
X-Device-Type: IPHONE
X-Datadog-Trace-Id: <random uint64>
X-Datadog-Parent-Id: <random uint64>
X-Datadog-Sampling-Priority: 2
X-Datadog-Origin: rum
```

### X-Device-Info payload (base64 encoded)
```json
{
  "appName": "sg.com.comfortdelgro.taxibooking",
  "appVersion": "8.6.1",
  "model": "iPhone17,1",
  "osVersion": "26.4",
  "platform": "iOS"
}
```

## Vehicle Type IDs

| ID | Type |
|----|------|
| 0 | Standard Comfort Taxi (4-seat) |
| 1 | 6-Seater Limo |
| 2 | 4-Seater Limo Transfer |
| 3 | ComfortRIDE (flat rate) |
| 105 | PHC 4-Seater |
| 130 | 6-Seater (XL) |
| 132 | PHC 6-Seater |
| 133 | 4-Seater Limo (meter) |

## Error Responses

All errors follow this format:
```json
{
  "traceId": "uuid",
  "responseCode": 2,
  "message": "Expired Token",
  "error": {
    "code": "ExpiredToken",
    "message": "Expired Token"
  },
  "timestamp": "26/Mar/2026:04:06:26 +0000",
  "path": "/endpoint/path"
}
```

Common error codes: `ExpiredToken`, `InvalidToken`, `InvalidRequest`.
