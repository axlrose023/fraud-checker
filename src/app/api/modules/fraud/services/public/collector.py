def build_collector_script(
    default_check_endpoint: str = "/fraud/check",
    default_captcha_verify_endpoint: str = "/fraud/captcha/verify",
    turnstile_js_url: str = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit",
) -> str:
    return f"""(function(global) {{
  const _scriptPromises = {{}};

  function loadScriptOnce(src) {{
    if (_scriptPromises[src]) return _scriptPromises[src];
    _scriptPromises[src] = new Promise((resolve, reject) => {{
      const s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.defer = true;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('Failed to load script: ' + src));
      document.head.appendChild(s);
    }});
    return _scriptPromises[src];
  }}

  function resolveContainer(container) {{
    if (!container) return null;
    if (typeof container === 'string') return document.querySelector(container);
    return container;
  }}

  async function postJson(endpoint, body) {{
    const response = await fetch(endpoint, {{
      method: 'POST',
      credentials: 'omit',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(body)
    }});

    if (!response.ok) {{
      const text = await response.text();
      throw new Error('Request failed: ' + response.status + ' ' + text);
    }}

    return response.json();
  }}

  async function maybeGetGeo(options) {{
    if (!options || !options.includeGeolocation || !navigator.geolocation) {{
      return null;
    }}

    const timeoutMs = options.geoTimeoutMs || 1200;
    return await new Promise((resolve) => {{
      const done = (value) => resolve(value);
      navigator.geolocation.getCurrentPosition(
        (pos) => done({{
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy_meters: pos.coords.accuracy
        }}),
        () => done(null),
        {{
          maximumAge: 0,
          timeout: timeoutMs,
          enableHighAccuracy: false
        }}
      );
    }});
  }}

  function getWebGLInfo() {{
    try {{
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) return null;
      const dbg = gl.getExtension('WEBGL_debug_renderer_info');
      return {{
        vendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : null,
        renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null
      }};
    }} catch (_) {{
      return null;
    }}
  }}

  function getClientHints() {{
    const uaData = navigator.userAgentData;
    if (!uaData) return null;
    return {{
      mobile: !!uaData.mobile,
      platform: uaData.platform || null,
      brands: Array.isArray(uaData.brands)
        ? uaData.brands.map((b) => b.brand).filter(Boolean)
        : []
    }};
  }}

  // ---- Behavioral tracking ----
  const _bhv = {{
    t0: Date.now(),
    maxY: 0,
    scrolls: 0,
    keys: 0,
    mouse: 0,
    touch: 0
  }};
  (function() {{
    if (typeof document === 'undefined') return;
    var opts = {{ passive: true }};
    document.addEventListener('scroll', function() {{
      _bhv.scrolls++;
      var y = global.pageYOffset || document.documentElement.scrollTop || 0;
      if (y > _bhv.maxY) _bhv.maxY = y;
    }}, opts);
    document.addEventListener('keydown', function() {{ _bhv.keys++; }}, opts);
    document.addEventListener('mousemove', function() {{ _bhv.mouse++; }}, opts);
    document.addEventListener('touchstart', function() {{ _bhv.touch++; }}, opts);
  }})();

  function getBehavior() {{
    var docH = Math.max(
      document.body ? document.body.scrollHeight : 0,
      document.documentElement ? document.documentElement.scrollHeight : 0
    );
    return {{
      time_on_page_ms: Date.now() - _bhv.t0,
      max_scroll_y: _bhv.maxY,
      scroll_count: _bhv.scrolls,
      document_height: docH,
      keydown_count: _bhv.keys,
      mouse_move_count: _bhv.mouse,
      touch_count: _bhv.touch
    }};
  }}

  async function collectSignals(options) {{
    const geo = await maybeGetGeo(options || {{}});
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || null;
    const utcOffsetMinutes = -new Date().getTimezoneOffset();

    const payload = {{
      event_id: (options && options.eventId) || null,
      session_id: (options && options.sessionId) || null,
      client_reported_ip: (options && options.clientReportedIp) || null,
      navigator: {{
        user_agent: navigator.userAgent,
        language: navigator.language || null,
        languages: Array.isArray(navigator.languages) ? navigator.languages : [],
        platform: navigator.platform || null,
        webdriver: typeof navigator.webdriver === 'boolean' ? navigator.webdriver : null,
        hardware_concurrency: navigator.hardwareConcurrency || null,
        device_memory: navigator.deviceMemory || null,
        max_touch_points: navigator.maxTouchPoints || 0,
        cookie_enabled: typeof navigator.cookieEnabled === 'boolean' ? navigator.cookieEnabled : null,
        plugins_count: navigator.plugins ? navigator.plugins.length : null
      }},
      screen: {{
        width: screen.width,
        height: screen.height,
        avail_width: screen.availWidth,
        avail_height: screen.availHeight,
        color_depth: screen.colorDepth,
        pixel_ratio: global.devicePixelRatio || 1
      }},
      viewport: {{
        width: global.innerWidth,
        height: global.innerHeight
      }},
      webgl: getWebGLInfo(),
      location: {{
        country_iso: (options && options.countryIso) || null,
        timezone: tz,
        utc_offset_minutes: utcOffsetMinutes,
        latitude: geo ? geo.latitude : null,
        longitude: geo ? geo.longitude : null,
        accuracy_meters: geo ? geo.accuracy_meters : null
      }},
      client_hints: getClientHints(),
      behavior: getBehavior(),
      collected_at: new Date().toISOString()
    }};

    return payload;
  }}

  async function check(apiUrl, options) {{
    const endpoint = apiUrl || '{default_check_endpoint}';
    const payload = await collectSignals(options || {{}});
    return postJson(endpoint, payload);
  }}

  async function verifyCaptcha(apiUrl, challengeId, captchaToken) {{
    const endpoint = apiUrl || '{default_captcha_verify_endpoint}';
    return postJson(endpoint, {{
      challenge_id: challengeId,
      captcha_token: captchaToken
    }});
  }}

  async function getTurnstileToken(siteKey, container, options) {{
    await loadScriptOnce('{turnstile_js_url}');
    if (!global.turnstile || !global.turnstile.render) {{
      throw new Error('Turnstile is not available after loading the script');
    }}

    const el = resolveContainer(container);
    if (!el) {{
      throw new Error('Captcha container not found');
    }}
    el.innerHTML = '';

    const timeoutMs = (options && options.timeout) || 60000;
    return await new Promise((resolve, reject) => {{
      const timer = setTimeout(() => reject(new Error('Captcha timed out')), timeoutMs);
      global.turnstile.render(el, {{
        sitekey: siteKey,
        size: (options && options.size) || 'normal',
        action: (options && options.action) || undefined,
        cData: (options && options.cdata) || undefined,
        callback: (token) => {{ clearTimeout(timer); resolve(token); }},
        'error-callback': () => {{ clearTimeout(timer); reject(new Error('Captcha error')); }},
      }});
    }});
  }}

  async function run(params) {{
    const opts = (params && params.options) || {{}};
    const checkEndpoint = (params && params.checkEndpoint) || '{default_check_endpoint}';
    const captchaVerifyEndpoint = (params && params.captchaVerifyEndpoint) || '{default_captcha_verify_endpoint}';
    const captchaContainer = params && params.captchaContainer;

    const initial = await check(checkEndpoint, opts);
    if (!initial || !initial.captcha_required) {{
      return initial;
    }}

    // If the caller did not provide a container, return the challenge so the
    // landing can render captcha itself.
    if (!captchaContainer) {{
      return initial;
    }}

    if (initial.captcha_provider === 'turnstile' && initial.captcha_site_key) {{
      if (!initial.challenge_id) {{
        throw new Error('Captcha challenge_id is missing from the response');
      }}
      const token = await getTurnstileToken(
        initial.captcha_site_key,
        captchaContainer,
        {{
          action: (params && params.captchaAction) || undefined,
          cdata: initial.challenge_id || undefined,
          size: (params && params.captchaSize) || 'normal',
        }}
      );
      return await verifyCaptcha(captchaVerifyEndpoint, initial.challenge_id, token);
    }}

    // Provider not supported by this collector script yet.
    return initial;
  }}

  global.FraudCollector = {{
    collectSignals,
    check,
    verifyCaptcha,
    getTurnstileToken,
    run
  }};
}})(window);
"""
