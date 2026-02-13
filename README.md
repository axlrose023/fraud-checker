# Fraud Checker API

Публичный сервис antifraud-проверки браузерных сигналов.

- Лендинг отправляет сигналы браузера в `POST /fraud/check`.
- Сервис возвращает решение: `allow` / `review` / `block` и список причин.

## Setup:
```bash
uv sync
```

### Start with uv
```bash
uv run app
```

### Start with docker
```bash
docker compose up --build -d
```

## Public Fraud API

### Endpoints
- `POST /fraud/check` - проверка события.
- `POST /fraud/step-up` - шаг капчи (проверка токена по `challenge_id`).
- `GET /fraud/collector.js` - готовый JS-коллектор браузерных сигналов.

### Что отправлять с браузера

Обязательные блоки:
- `navigator`: `user_agent`, `language`, `languages`, `platform`, `webdriver`, `hardware_concurrency`, `device_memory`, `max_touch_points`, `cookie_enabled`, `plugins_count`
- `screen`: `width`, `height`, `avail_width`, `avail_height`, `color_depth`, `pixel_ratio`
- `viewport`: `width`, `height`

Опциональные блоки:
- `webgl`: `vendor`, `renderer`
- `location`: `country_iso`, `timezone`, `utc_offset_minutes`, `latitude`, `longitude`, `accuracy_meters`
- `client_hints`: `mobile`, `platform`, `brands`
- `client_reported_ip`, `event_id`, `session_id`

### Пример запроса
```bash
curl -X POST http://localhost:8000/fraud/check \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "lead-123",
    "session_id": "sess-1",
    "navigator": {
      "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
      "language": "en-US",
      "languages": ["en-US", "en"],
      "platform": "iPhone",
      "webdriver": false,
      "hardware_concurrency": 6,
      "device_memory": 4,
      "max_touch_points": 5,
      "cookie_enabled": true,
      "plugins_count": 0
    },
    "screen": {
      "width": 390,
      "height": 844,
      "avail_width": 390,
      "avail_height": 820,
      "color_depth": 24,
      "pixel_ratio": 3
    },
    "viewport": {
      "width": 390,
      "height": 730
    },
    "location": {
      "country_iso": "US",
      "timezone": "America/New_York",
      "utc_offset_minutes": -300
    },
    "collected_at": "2026-02-12T12:00:00Z"
  }'
```

### Пример ответа
```json
{
  "decision": "review",
  "risk_score": 45,
  "fingerprint_id": "4f9ea34f08d91a3f813f9ac2",
  "request_ip": "203.0.113.10",
  "ip_country_iso": "US",
  "signals": [
    {
      "code": "AUTOMATION_UA_MARKER",
      "severity": "high",
      "weight": 45,
      "message": "User-Agent contains known automation markers."
    }
  ],
  "captcha_required": false,
  "captcha_verified": false,
  "captcha_provider": null,
  "captcha_site_key": null,
  "captcha_error_codes": [],
  "challenge_id": null,
  "evaluated_at": "2026-02-12T12:00:00Z"
}
```

## Captcha Step-Up (Опционально)

Если включить капчу, то при решении `review` сервис вернет `captcha_required=true` и `challenge_id`.
После прохождения капчи лендинг должен отправить `captcha_token` на `POST /fraud/step-up`.

### Интеграция с лендинга
Лендинг сам собирает browser-сигналы и отправляет JSON в `POST /fraud/check`.

### Интеграция через collector.js
```html
<script src="https://YOUR_API_DOMAIN/fraud/collector.js"></script>
<script>
  FraudCollector.check("https://YOUR_API_DOMAIN/fraud/check", {
    eventId: "lead-123",
    sessionId: "sess-1",
    countryIso: "US",
    includeGeolocation: false
  }).then((result) => {
    console.log(result.decision, result.risk_score, result.signals);
  });
</script>
```

### collector.js + авто step-up (Turnstile)
```html
<div id="captcha"></div>
<script src="https://YOUR_API_DOMAIN/fraud/collector.js"></script>
<script>
  FraudCollector.run({
    checkEndpoint: "https://YOUR_API_DOMAIN/fraud/check",
    stepUpEndpoint: "https://YOUR_API_DOMAIN/fraud/step-up",
    captchaContainer: "#captcha",
    options: {
      eventId: "lead-123",
      sessionId: "sess-1",
      countryIso: "US",
      includeGeolocation: false
    }
  }).then((result) => {
    console.log(result.decision, result.captcha_verified, result.risk_score);
  });
</script>
```

## Pre-commit hooks

Install and setup pre-commit hooks:
```bash
uv sync --group dev
pre-commit install
```

Run hooks manually:
```bash
pre-commit run --all-files
```
