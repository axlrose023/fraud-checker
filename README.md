# Fraud Checker

Сервис антифрод-проверки для лендингов и веб-приложений. Анализирует браузерные сигналы посетителя в реальном времени и выносит решение: пропустить, запросить капчу или заблокировать.

---

## Как это работает

```
┌─────────────┐         ┌──────────────────┐         ┌───────────────┐
│   Браузер   │────1───▶│  GET /collector.js│────────▶│  JS-коллектор │
│  посетителя │         └──────────────────┘         │  загружен     │
│             │                                       └───────┬───────┘
│             │◀──────────── собирает сигналы ─────────────────┘
│             │
│             │────2───▶ POST /fraud/check  ───▶ Бек анализирует сигналы
│             │                                       │
│             │◀─────── Ответ: allow / review / block ┘
│             │
│  (если review + captcha_required)
│             │────3───▶ Показывает виджет Turnstile
│             │         Пользователь проходит капчу
│             │────4───▶ POST /fraud/captcha/verify
│             │◀─────── Ответ: allow (капча пройдена) или review (не пройдена)
└─────────────┘
```

**Шаг 1** — Фронт подгружает скрипт-коллектор. Он собирает информацию о браузере: user-agent, размер экрана, язык, таймзону, WebGL, client hints и другие сигналы.

**Шаг 2** — Собранные данные отправляются на бек. Сервис прогоняет их через ~30 проверок, считает risk score и возвращает решение.

**Шаг 3–4** — Если решение `review` и настроена капча — фронт показывает Cloudflare Turnstile. После прохождения токен отправляется на верификацию. Бек подтверждает капчу через Cloudflare и меняет решение на `allow`.

---

## Решения

| Решение | Score | Что значит |
|---------|-------|------------|
| **allow** | 0–39 | Запрос выглядит легитимным, пропускаем |
| **review** | 40–100 | Подозрительный запрос, требуется капча |

Порог настраивается через переменную окружения `REVIEW_SCORE_THRESHOLD` (по умолчанию 40).

---

## Какие проверки выполняются

### Автоматизация и боты

| Проверка | Что ловит | Вес |
|----------|-----------|-----|
| WebDriver включён | Selenium, Puppeteer, Playwright | 70 |
| Маркеры автоматизации в UA | HeadlessChrome, PhantomJS | 55 |
| Сильные бот-маркеры в UA | curl, python-requests, go-http-client | 85 |
| Слабые бот-маркеры в UA | bot, crawler, spider | 45 |

### Поведенческие сигналы

| Проверка | Что ловит | Вес |
|----------|-----------|-----|
| Слишком быстрая отправка | Форма отправлена за < 3 секунды | 25 |
| Нет скролла на длинной странице | Отправка без скролла при высоте > viewport + 200px | 18 |
| Нет взаимодействия | Менее 3 событий клавиатуры/мыши/тача | 30 |

### Устройство и экран

| Проверка | Что ловит | Вес |
|----------|-----------|-----|
| Мобильный UA + десктопный экран | Эмуляция мобильного на десктопе | 30 |
| Мобильный UA + 0 touch points | Подделка мобильного устройства | 15 |
| Viewport больше экрана | Манипуляция с размерами окна | 8–15 |
| Несовпадение UA и navigator.platform | UA говорит Windows, platform — Mac | 15 |
| Client Hints не совпадают с UA | Подделка заголовков | 15–20 |

### Заголовки и язык

| Проверка | Что ловит | Вес |
|----------|-----------|-----|
| User-Agent заголовка ≠ payload | Подмена UA после отправки | 40 |
| Accept-Language ≠ navigator.language | Несовпадение языковых настроек | 8–15 |
| sec-ch-ua brands не совпадают | Подделка Client Hints заголовков | 10–25 |
| sec-ch-ua-mobile / platform mismatch | Расхождение мобильности/платформы | 15–20 |

### Геолокация и IP

| Проверка | Что ловит | Вес |
|----------|-----------|-----|
| IP страны ≠ заявленная страна | VPN, прокси, подмена локации | 35 |
| Таймзона IP ≠ таймзона браузера | Несовпадение часовых поясов | 15 |
| Геолокация далеко от IP | Расстояние > 800 км | 25 |
| IP хостинг-провайдера | Дата-центр, VPN, прокси | 20 |
| Client IP ≠ реальный IP | Клиент заявляет чужой IP | 30 |

### Система и окружение

| Проверка | Что ловит | Вес |
|----------|-----------|-----|
| Софтверный WebGL (SwiftShader) | Headless-браузер, VM без GPU | 25 |
| 0 плагинов на десктопном Chromium | Headless или песочница | 12 |
| Очень мало памяти/ядер | Контейнер или VM | 8–10 |

### Время и rate limit

| Проверка | Что ловит | Вес |
|----------|-----------|-----|
| Timestamp в будущем | Подделка времени | 12 |
| Устаревший snapshot (> 10 мин) | Replay-атака | 18 |
| Превышение rate limit | Массовые запросы с одного IP | 100 (блок) |

---

## Подсчёт score

Каждая сработавшая проверка добавляет свой вес к общему score. Итоговый score ограничен диапазоном 0–100. Например:

- Обычный посетитель: score = 0 → **allow**
- HeadlessChrome: `AUTOMATION_UA_MARKER` (55) → score = 55 → **review** → капча
- Selenium + WebDriver: `WEBDRIVER_ENABLED` (70) → score = 70 → **review** → капча
- curl: `STRONG_BOT_UA_MARKER` (85) → score = 85 → **review** → капча

---

## Эндпоинты

| Метод | Путь | Назначение | Требует API key |
|-------|------|------------|----------------|
| GET | `/fraud/collector.js` | JS-скрипт для сбора браузерных сигналов | Нет |
| POST | `/fraud/check` | Основная проверка — принимает сигналы, возвращает решение | Да |
| POST | `/fraud/captcha/verify` | Верификация токена капчи по challenge_id | Да |

### Аутентификация

Все эндпоинты (кроме GET `/fraud/collector.js`) требуют заголовок `X-API-Key`:

```bash
curl -X POST https://YOUR_DOMAIN/fraud/check \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ ... }'
```

API ключ настраивается через переменную окружения:
```
APP__API__API_KEY=your-secure-random-key
```

---

## Интеграция на фронте

### Автоматический режим (рекомендуется)

Один вызов — сбор сигналов, проверка и капча если нужна:

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
      includeGeolocation: true,  // включить геолокацию браузера
      geoTimeoutMs: 1200         // таймаут запроса геолокации
    }
  }).then(result => {
    if (result.decision === 'allow') {
      // продолжить (отправить форму, перейти к оплате)
    } else {
      // заблокировано или капча не пройдена
    }
  });
</script>
```

**Параметры:**
- `checkEndpoint` — URL для POST `/fraud/check`
- `captchaVerifyEndpoint` — URL для POST `/fraud/captcha/verify`
- `captchaContainer` — CSS-селектор контейнера для виджета капчи
- `apiKey` — X-API-Key для аутентификации
- `options.eventId` — произвольный ID события (например, ID лида)
- `options.sessionId` — ID сессии пользователя
- `options.includeGeolocation` — запрашивать геолокацию браузера (по умолчанию `false`)
- `options.geoTimeoutMs` — таймаут запроса геолокации в мс (по умолчанию `1000`)

### Ручной режим

Если нужен полный контроль над UI — используйте методы `FraudCollector.check()`, `FraudCollector.verifyCaptcha()` и `FraudCollector.collectSignals()` по отдельности:

```javascript
// 1. Собрать сигналы (включая поведенческие)
const signals = await FraudCollector.collectSignals({
  eventId: 'lead-123',
  includeGeolocation: true
});

// 2. Отправить на проверку
const checkResult = await FraudCollector.check({
  endpoint: 'https://YOUR_DOMAIN/fraud/check',
  apiKey: 'YOUR_API_KEY',
  signals
});

// 3. Если требуется капча — показать и верифицировать
if (checkResult.captcha_required) {
  const captchaResult = await FraudCollector.verifyCaptcha({
    endpoint: 'https://YOUR_DOMAIN/fraud/captcha/verify',
    apiKey: 'YOUR_API_KEY',
    challengeId: checkResult.challenge_id,
    container: '#captcha'
  });
}
```

### Поведенческие сигналы

Коллектор автоматически отслеживает:
- **Время на странице** — от загрузки скрипта до отправки
- **Скролл** — количество событий и максимальная позиция
- **Взаимодействие** — события клавиатуры, мыши и тача
- **Высота документа** — для определения необходимости скролла

Эти данные помогают отличить ботов (заполняют формы мгновенно, без скролла и кликов) от реальных пользователей.

### Обфускация скрипта

JS-коллектор (`/fraud/collector.js`) автоматически обфусцируется при генерации:
- Все внутренние функции и переменные переименованы в короткие криптичные имена (`_l`, `_h`, `_g`, etc.)
- Применена минификация (удаление пробелов, переносов строк)
- Сообщения об ошибках заменены на кодовые (`_e1`, `_e2`, etc.)

Это затрудняет реверс-инжиниринг и понимание логики детекции для разработчиков ботов.

---

## Капча (Cloudflare Turnstile)

Капча включается автоматически если заданы переменные:

```
APP__FRAUD__TURNSTILE_SITE_KEY=...
APP__FRAUD__TURNSTILE_SECRET_KEY=...
```

Для локальной разработки можно использовать тестовые ключи Cloudflare (always-pass).

Без этих переменных сервис работает без капчи — только allow/block на основе score.

---

## Запуск

```bash
# Локально
uv sync
uv run app

# Docker
docker compose up --build -d
```

## Конфигурация

Все настройки задаются через переменные окружения с префиксом `APP__`. Значения по умолчанию уже заданы в коде — `.env` нужен только для переопределения.

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `APP__API__API_KEY` | — | API ключ для аутентификации (если не задан — middleware отключен) |
| `APP__FRAUD__REVIEW_SCORE_THRESHOLD` | 40 | Порог показа капчи (всё что ≥ этого значения → review) |
| `APP__FRAUD__RATE_LIMIT_WINDOW_SECONDS` | 60 | Окно rate limit |
| `APP__FRAUD__RATE_LIMIT_MAX_REQUESTS_PER_IP` | 120 | Лимит запросов с одного IP |
| `APP__FRAUD__IP_GEOLOCATION_ENABLED` | false | Включить IP-геолокацию |
| `APP__FRAUD__TURNSTILE_SITE_KEY` | — | Site key для Turnstile |
| `APP__FRAUD__TURNSTILE_SECRET_KEY` | — | Secret key для Turnstile |

**Пример `.env`:**
```bash
APP__API__API_KEY=
APP__FRAUD__TURNSTILE_SITE_KEY=
APP__FRAUD__TURNSTILE_SECRET_KEY=
APP__FRAUD__REVIEW_SCORE_THRESHOLD=40
```
