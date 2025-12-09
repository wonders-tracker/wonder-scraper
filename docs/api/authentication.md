# Authentication

WondersTracker API supports two authentication methods: API keys for programmatic access and JWT tokens for authenticated web sessions.

## API Key Authentication

API keys are the recommended method for scripts, bots, and integrations.

### Getting an API Key

1. Log in to your WondersTracker account
2. Navigate to **Settings > API Access**
3. Click **Generate New Key**
4. Copy and securely store your key (it's only shown once)

### Using Your API Key

Include the key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: wt_your_api_key_here" \
  "https://api.wonderstrader.com/api/v1/cards"
```

### Rate Limits

| Limit | Value |
|-------|-------|
| Per minute | 60 requests |
| Per day | 10,000 requests |

When rate limited, you'll receive:

```json
{
  "detail": "Rate limit exceeded. Please slow down."
}
```

With header: `Retry-After: 60` (seconds)

### Managing API Keys

**List your keys:**
```bash
GET /api/v1/users/api-keys
```

**Create a new key:**
```bash
POST /api/v1/users/api-keys
Content-Type: application/json

{"name": "My Discord Bot"}
```

**Delete a key:**
```bash
DELETE /api/v1/users/api-keys/{key_id}
```

**Toggle key active status:**
```bash
PUT /api/v1/users/api-keys/{key_id}/toggle
```

### API Key Format

Keys are prefixed with `wt_` for identification:
```
wt_1a2b3c4d5e6f7g8h9i0j...
```

Only the prefix (`wt_1a2b3c4d`) is stored in our database - the full key is hashed for security.

---

## JWT Token Authentication

For web applications using session-based auth.

### Login

```bash
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=yourpassword
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using JWT Tokens

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  "https://api.wonderstrader.com/api/v1/users/me"
```

### Token Expiry

JWT tokens expire after the configured session duration. When expired:

```json
{
  "detail": "Could not validate credentials"
}
```

Re-authenticate to obtain a new token.

---

## Discord OAuth

Users can also authenticate via Discord:

```bash
GET /api/v1/auth/discord/login
```

This redirects to Discord for authorization, then back to:
```
/api/v1/auth/discord/callback?code=...
```

---

## Unauthenticated Access

Some endpoints are publicly accessible without authentication:

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/cards` | Card list (rate limited by IP) |
| `GET /api/v1/cards/{id}` | Card detail |
| `GET /api/v1/market/overview` | Market overview |
| `GET /api/v1/blokpax/*` | Blokpax data |

**Public Rate Limits (by IP):**
- 60 requests per minute
- 10 requests per 5 seconds (burst)

Authenticated requests bypass IP-based rate limiting.

---

## Security Notes

1. **Never share your API key** - Treat it like a password
2. **Use environment variables** - Don't hardcode keys in code
3. **Rotate compromised keys** - Delete and regenerate if exposed
4. **Use HTTPS only** - All API requests must use HTTPS

### Example: Secure Key Storage

**Environment variable:**
```bash
export WONDERS_API_KEY="wt_your_key_here"
```

**Python:**
```python
import os
import requests

API_KEY = os.environ.get("WONDERS_API_KEY")
headers = {"X-API-Key": API_KEY}
response = requests.get(
    "https://api.wonderstrader.com/api/v1/cards",
    headers=headers
)
```

**Node.js:**
```javascript
const API_KEY = process.env.WONDERS_API_KEY;
const response = await fetch(
  "https://api.wonderstrader.com/api/v1/cards",
  { headers: { "X-API-Key": API_KEY } }
);
```
