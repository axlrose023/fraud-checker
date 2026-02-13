# Fraud Checker

Anti-fraud service for landing pages and web apps. It collects browser signals in real time, computes a risk score, and returns a decision: `allow`, `review` (captcha), or `block` (hard block, e.g. rate limiting).

---

## How It Works

```
┌─────────────┐            ┌──────────────────────────┐           ┌───────────────┐
│  Visitor's  │─────1─────▶│  GET /fraud/collector.js  │──────────▶│  JS collector │
│   browser   │            └──────────────────────────┘           │   loaded      │
│             │                                                    └──────┬────────┘
│             │◀──────────────────── collects signals ─────────────────────┘
│             │
│             │─────2─────▶  POST /fraud/check   ───▶ backend evaluates signals
│             │                                      │
│             │◀──────────── response: allow / review / block ─────────────┘
│             │
│   (if review + captcha_required)
│             │─────3─────▶ render Turnstile widget
│             │            user completes captcha
│             │─────4─────▶ POST /fraud/captcha/verify
│             │◀──────────── response: allow (passed) or review (failed) ───┘
└─────────────┘
```

1. Frontend loads the collector script and gathers signals: user agent, screen/viewport, language/timezone, WebGL, Client Hints, and optional behavior + geolocation.
2. Collected data is sent to the backend. The service runs checks, computes `risk_score` (0..100) and returns a decision.
3. If the decision is `review` and Turnstile is configured, the frontend shows the captcha.
4. The captcha token is verified server-side; on success the decision becomes `allow`.

---

## Decisions

| Decision | Score | Meaning |
|---------|-------|---------|
| **allow** | 0..(threshold-1) | Request looks legitimate |
| **review** | threshold..100 | Suspicious, captcha may be required |
| **block** | n/a | Hard block (currently used for rate limiting) |

The threshold is controlled by `APP__FRAUD__REVIEW_SCORE_THRESHOLD` (default: `40`).

---

## Checks Performed

### Automation and bots

| Check | What it catches | Weight |
|------|------------------|--------|
| WebDriver enabled | Selenium, Puppeteer, Playwright | 70 |
| Automation markers in UA | HeadlessChrome, PhantomJS | 55 |
| Strong bot markers in UA | curl, python-requests, go-http-client | 85 |
| Weak bot markers in UA | bot, crawler, spider | 45 |

### Behavioral signals

| Check | What it catches | Weight |
|------|------------------|--------|
| Too fast submission | form submitted in < 3 seconds | 25 |
| No scroll on a long page | submit without scrolling when doc is taller than viewport | 18 |
| No interaction | fewer than 3 keyboard/mouse/touch events | 30 |

### Device and screen

| Check | What it catches | Weight |
|------|------------------|--------|
| Mobile UA + desktop-like screen | mobile emulation | 30 |
| Mobile UA + 0 touch points | spoofed mobile device | 15 |
| Viewport larger than screen | window size manipulation | 8..15 |
| UA vs `navigator.platform` mismatch | e.g. UA says Windows, platform says Mac | 15 |
| Client Hints mismatch with UA | spoofed headers | 15..20 |

### Headers and language

| Check | What it catches | Weight |
|------|------------------|--------|
| Header UA != payload UA | UA changed between request and payload | 40 |
| Accept-Language != `navigator.language` | language settings mismatch | 8..15 |
| `sec-ch-ua` brands mismatch | spoofed Client Hints | 10..25 |
| `sec-ch-ua-mobile` / platform mismatch | inconsistent mobile/platform signals | 15..20 |

### Geo and IP

| Check | What it catches | Weight |
|------|------------------|--------|
| IP country != claimed country | VPN/proxy, spoofed location | 35 |
| IP timezone != browser timezone | timezone mismatch | 15 |
| Geo far from IP | distance > 800 km | 25 |
| Hosting provider IP | datacenter/VPN/proxy | 20 |
| Client-reported IP != request IP | client claims someone else's IP | 30 |

### System and environment

| Check | What it catches | Weight |
|------|------------------|--------|
| Software WebGL (SwiftShader) | headless / VM without GPU | 25 |
| 0 plugins in desktop Chromium | headless / sandbox | 12 |
| Very low memory/CPU | container/VM | 8..10 |

### Time and rate limiting

| Check | What it catches | Weight |
|------|------------------|--------|
| Timestamp in the future | fake time | 12 |
| Stale snapshot (> 10 min) | replay attack | 18 |
| Rate limit exceeded | bursty traffic from one IP | 100 (block) |

---

## Score Calculation

Each triggered check adds its weight to the total score. The final `risk_score` is clamped to `0..100`. Examples:

- Normal user: score = 0 -> **allow**
- HeadlessChrome: `AUTOMATION_UA_MARKER` (55) -> score = 55 -> **review** -> captcha
- Selenium + WebDriver: `WEBDRIVER_ENABLED` (70) -> score = 70 -> **review** -> captcha
- curl: `STRONG_BOT_UA_MARKER` (85) -> score = 85 -> **review** -> captcha

---

## API

| Method | Path | Purpose | Requires API key |
|-------|------|---------|------------------|
| GET | `/fraud/collector.js` | JS collector script | No |
| POST | `/fraud/check` | Evaluate signals and return a decision | Yes (if enabled) |
| POST | `/fraud/captcha/verify` | Verify captcha token for a `challenge_id` | Yes (if enabled) |

### Authentication

All endpoints except `GET /fraud/collector.js` require `X-API-Key` if `APP__API__API_KEY` is set:

```bash
curl -X POST https://YOUR_DOMAIN/fraud/check \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ ... }'
```

Enable API key auth via:

```bash
APP__API__API_KEY=your-secure-random-key
```

---

## Frontend Integration

### Automatic mode (recommended)

One call: collect signals, check, and show captcha if required:

```html
<div id="captcha"></div>
<script src="https://YOUR_DOMAIN/fraud/collector.js"></script>
<script>
  FraudCollector.run({
    checkEndpoint: 'https://YOUR_DOMAIN/fraud/check',
    captchaVerifyEndpoint: 'https://YOUR_DOMAIN/fraud/captcha/verify',
    captchaContainer: '#captcha',
    apiKey: 'YOUR_API_KEY',
    options: {
      eventId: 'lead-123',
      sessionId: 'sess-1',
      includeGeolocation: true,  // request browser geolocation
      geoTimeoutMs: 1200         // geolocation request timeout (ms)
    }
  }).then(result => {
    if (result.decision === 'allow') {
      // proceed (submit form, go to checkout, etc.)
    } else {
      // blocked or captcha not passed
    }
  });
</script>
```

Parameters:

- `checkEndpoint`: URL for `POST /fraud/check`
- `captchaVerifyEndpoint`: URL for `POST /fraud/captcha/verify`
- `captchaContainer`: CSS selector for the captcha container
- `apiKey`: value for `X-API-Key`
- `options.eventId`: arbitrary event ID (e.g. lead ID)
- `options.sessionId`: user session ID
- `options.includeGeolocation`: request browser geolocation (default: `false`)
- `options.geoTimeoutMs`: geolocation timeout in ms (default: `1000`)

### Manual mode

If you need full UI control, use `FraudCollector.collectSignals()`, `FraudCollector.check()`, and `FraudCollector.verifyCaptcha()` separately:

```javascript
// 1) Collect signals (optionally including behavioral signals)
const signals = await FraudCollector.collectSignals({
  eventId: 'lead-123',
  includeGeolocation: true
});

// 2) Send to backend
const checkResult = await FraudCollector.check({
  endpoint: 'https://YOUR_DOMAIN/fraud/check',
  apiKey: 'YOUR_API_KEY',
  signals
});

// 3) If captcha is required - render and verify
if (checkResult.captcha_required) {
  const captchaResult = await FraudCollector.verifyCaptcha({
    endpoint: 'https://YOUR_DOMAIN/fraud/captcha/verify',
    apiKey: 'YOUR_API_KEY',
    challengeId: checkResult.challenge_id,
    container: '#captcha'
  });
}
```

### Behavioral signals

The collector tracks:

- time on page (from script load to submission)
- scroll stats (count and max Y)
- interaction stats (keyboard/mouse/touch)
- document height (to detect whether scrolling would be expected)

This helps distinguish bots (instant submits, no scroll/clicks) from real users.

### Script obfuscation

The JS collector (`/fraud/collector.js`) is obfuscated during generation:

- internal functions/variables are renamed to short names (`_l`, `_h`, `_g`, etc.)
- minification is applied
- error messages are replaced with codes (`_e1`, `_e2`, etc.)

This makes reverse engineering and tuning bot payloads harder.

---

## Captcha (Cloudflare Turnstile)

Captcha is enabled automatically if these env vars are set:

```bash
APP__FRAUD__TURNSTILE_SITE_KEY=...
APP__FRAUD__TURNSTILE_SECRET_KEY=...
```

For local development you can use Cloudflare test keys (always-pass).

If Turnstile is not configured, the service still returns `allow` / `review` decisions, but will not require captcha.

---

## Running

```bash
# Local
uv sync
uv run app

# Docker
docker compose up --build -d
```

## Configuration

All settings are configured via env vars with the `APP__` prefix (nested via `__`). Defaults are in code; use `.env` only to override.

| Variable | Default | Description |
|---------|---------|-------------|
| `APP__API__API_KEY` | unset | API key (if unset, API key middleware is disabled) |
| `APP__FRAUD__REVIEW_SCORE_THRESHOLD` | 40 | Review threshold (score >= threshold -> `review`) |
| `APP__FRAUD__RATE_LIMIT_WINDOW_SECONDS` | 60 | Rate limit window (seconds) |
| `APP__FRAUD__RATE_LIMIT_MAX_REQUESTS_PER_IP` | 120 | Max requests per IP per window |
| `APP__FRAUD__TRUST_FORWARDED_IP` | false | Trust `X-Forwarded-For` when resolving client IP |
| `APP__FRAUD__IP_GEOLOCATION_ENABLED` | false | Enable IP geolocation lookup |
| `APP__FRAUD__TURNSTILE_SITE_KEY` | unset | Turnstile site key |
| `APP__FRAUD__TURNSTILE_SECRET_KEY` | unset | Turnstile secret key |

Example `.env`:

```bash
APP__API__API_KEY=
APP__FRAUD__TURNSTILE_SITE_KEY=
APP__FRAUD__TURNSTILE_SECRET_KEY=
APP__FRAUD__REVIEW_SCORE_THRESHOLD=40
```

