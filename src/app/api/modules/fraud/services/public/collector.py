def build_collector_script(default_endpoint: str = "/fraud/check") -> str:
    return f"""(function(global) {{
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
      collected_at: new Date().toISOString()
    }};

    return payload;
  }}

  async function check(apiUrl, options) {{
    const endpoint = apiUrl || '{default_endpoint}';
    const payload = await collectSignals(options || {{}});
    const response = await fetch(endpoint, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload)
    }});

    if (!response.ok) {{
      const body = await response.text();
      throw new Error('Fraud check failed: ' + response.status + ' ' + body);
    }}

    return response.json();
  }}

  global.FraudCollector = {{
    collectSignals,
    check
  }};
}})(window);
"""

