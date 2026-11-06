// FastMile demo: opens the test station in its own Chrome tab, with the router's page
// inside it. Scan the label and it waits for the router, logs in with the label, checks
// the unit is the one on the label, factory resets it, logs in again, waits for the
// green light and runs the functional tests, reading every result twice. It asks the
// router for a page every few seconds and shows the answer all the time. It sends
// nothing anywhere. It clicks only Sign in, the device on the Network map and Factory
// default > Reset, which also reboots the unit. It tries each login once and changes
// no setting. The log says what was tried, what was seen and why a test did not run,
// with no device data, and is kept in the browser as it grows, so a closed tab loses
// nothing. A .json result in the shape of the three OLP stations holds the IMEI that
// OLP files units under, so it must not be uploaded. Nothing is sent to OLP.
(function () {
  function main(win, origin) {
    var document = win.document;
    var VERSION = 'fastmile demo v9';
    win.RT_VERSION = VERSION;
    // OLP's two results for every station are PASS and this
    var OLP_FAIL = 'FAIL-FAIL';
    var RESET_KEY = 'rt-demo-reset';
    var LOG_KEY = 'rt-demo-log';
    var STATS_KEY = 'rt-demo-stats';
    var PC_KEY = 'rt-demo-pc';
    var MODEL = 'FastMile 5G Gateway 12';
    var LABEL_NAMES = { '5G31-03W-B': 'Gateway 12 FastMile', '5G16-12W-A': 'Gateway 3.2 5G' };
    var OTHER_MODELS = ['5G16-12W-A'];
    // The router's own address sends it to its login page. The second is what the
    // captures showed, tried if the first brings up no login box
    var ADDRESSES = ['/', '/web_whw/#/login'];
    var POLL_MS = 3000;
    var PAGE_MS = 500;
    var ANSWER_MS = 2500;
    var READY_MS = 300000;
    var REOPEN_MS = 20000;
    var SETTLE_MS = 20000;
    var CONNECT_MS = 120000;
    var RECHECK_MS = 5000;
    var GREEN_MS = 120000;
    var WAIT_MS = 30000;
    var LOGIN_WAIT_MS = 90000;
    var RESTART_START_MS = 60000;
    var RESTART_END_MS = 300000;
    // The confirm dialog has not been captured yet, so its button is matched by word
    var CONFIRM_WORDS = ['reset', 'factory reset', 'confirm', 'ok', 'okay', 'yes', 'continue', 'proceed'];
    var STEPS = [
      ['label', 'Label scanned', 'Reads the model, serial and IMEI from the QR.'],
      ['link', 'Router ready', 'Waits until the router answers and its login page is up.'],
      ['login', 'Logged in with the label', 'Signs in with the username and password on the label.'],
      ['identity', 'Model, serial and MAC match the label', 'Compares the unit with the label before anything is erased.'],
      ['reset', 'Factory reset', 'Erases the unit. This cannot be undone.'],
      ['restart', 'Router restarted', 'Waits for the router to go down and come back.'],
      ['login2', 'Logged in again', 'A login that works here shows the reset really happened.'],
      ['green', 'Green light', 'Waits for 5G, then you confirm the green light.'],
      ['tests', 'IMEI, SIM, 5G and Wi-Fi', 'Reads every result twice, a few seconds apart.'],
      ['visual', 'Visual inspection', 'You press Pass or Fail after looking at the unit.']
    ];

    document.title = 'Router test station';
    var style = document.createElement('style');
    style.textContent =
      ':root{--line:#d9dde3;--soft:#f3f5f8;--text:#17212f;--muted:#5b6675;--good:#0a7a2f;--goodbg:#e4f5e9;' +
      '--bad:#b00020;--badbg:#fde8ec;--warn:#8a5a00;--warnbg:#fdf2d8;--busy:#124191;--busybg:#e6edfa}' +
      'html,body{margin:0;background:#e9ecf1;color:var(--text);font:14px Arial,sans-serif}' +
      '*{box-sizing:border-box}button{font:inherit;padding:8px 14px;border:1px solid var(--line);' +
      'border-radius:6px;background:#fff;cursor:pointer}button:disabled{opacity:.5;cursor:default}' +
      '.page{max-width:1280px;margin:16px auto;background:#fff;border:1px solid var(--line);border-radius:10px}' +
      '.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;' +
      'border-bottom:1px solid var(--line)}.top b{font-size:16px}.top small{color:var(--muted);margin-left:8px}' +
      '#rt-link{padding:6px 12px;border-radius:999px;font-weight:bold;background:var(--soft)}' +
      '#rt-link.up{background:var(--goodbg);color:var(--good)}#rt-link.down{background:var(--badbg);color:var(--bad)}' +
      '.scan{padding:14px 16px}.scan label{color:var(--muted)}.scanrow{display:flex;gap:8px;margin-top:6px}' +
      '#rt-scan{flex:1;font:14px Consolas,monospace;padding:9px;border:2px solid var(--busy);border-radius:6px}' +
      '#rt-unit{color:var(--muted);margin-top:6px;min-height:18px}' +
      '.main{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:16px;padding:0 16px 16px}' +
      '.steps{list-style:none;margin:0;padding:4px 12px;border:1px solid var(--line);border-radius:8px}' +
      '.steps>li{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}' +
      '.steps>li:last-child{border-bottom:0}.icon{width:20px;font-size:17px;text-align:center;color:var(--muted)}' +
      '.body{flex:1;min-width:0}.hint{color:var(--muted);font-size:12px}' +
      '.now{font-size:12px;color:var(--busy);margin-top:2px}.time{color:var(--muted);white-space:nowrap}' +
      '.sub{margin-top:4px;font-size:12px}.sub div{padding:1px 0}.steps .done .icon,.sub .PASS{color:var(--good)}' +
      '.steps .failed .icon,.sub .FAIL,.sub .UNSTABLE{color:var(--bad)}.steps .stopped .icon{color:var(--warn)}' +
      '.steps .running{background:var(--busybg);margin:0 -12px;padding:8px 12px}.steps .running .icon{color:var(--busy)}' +
      '#rt-card{border-radius:8px;padding:16px;text-align:center;background:var(--soft)}' +
      '#rt-card.PASS{background:var(--goodbg);color:var(--good)}#rt-card.FAIL{background:var(--badbg);color:var(--bad)}' +
      '#rt-card.NOTTESTED{background:var(--warnbg);color:var(--warn)}#rt-card.BUSY{background:var(--busybg);color:var(--busy)}' +
      '#rt-big{font-size:34px;font-weight:bold;line-height:1.2}#rt-why,#rt-next{margin-top:6px}#rt-next{font-weight:bold}' +
      '.side{display:flex;flex-direction:column;gap:12px;min-width:0}#rt-green{display:none;font-size:18px;' +
      'font-weight:bold;padding:14px;background:var(--good);color:#fff;border:0}' +
      '#rt-visual{display:none;gap:8px;justify-content:flex-end;margin-top:4px}' +
      '.tiles{display:grid;grid-template-columns:1fr 1fr;gap:8px}.tile{background:var(--soft);border-radius:8px;padding:10px}' +
      '.tile small{display:block;color:var(--muted)}.tile b{font-size:20px}#rt-top{font-size:14px}' +
      '.view{height:270px;overflow:hidden;border:1px solid var(--line);border-radius:8px;position:relative}' +
      '#rt-frame{width:1280px;height:900px;border:0;transform:scale(.36);transform-origin:top left}' +
      '#rt-note{padding:12px;color:var(--warn);display:none}' +
      '.logbox{padding:0 16px 16px}.logtop{display:flex;align-items:center;gap:8px;margin-bottom:6px}.logtop b{flex:1}' +
      '#rt-log{height:220px;overflow:auto;margin:0;padding:10px;background:#101722;color:#dbe4ef;border-radius:8px;' +
      'font:12px/1.5 Consolas,monospace;white-space:pre-wrap}#rt-result{width:100%;margin-top:8px;display:none}';
    document.head.appendChild(style);
    document.body.innerHTML =
      '<div class="page"><div class="top"><div><b>Router test station</b><small>Gateway 12 FastMile · ' + VERSION +
      '</small></div><div id="rt-link">Checking the router…</div></div>' +
      '<div class="scan"><label for="rt-scan">Scan the QR code on the back of the unit</label>' +
      '<div class="scanrow"><input id="rt-scan" autocomplete="off"><button id="rt-start">Start</button>' +
      '<button id="rt-stop" disabled>Stop test</button></div><div id="rt-unit"></div></div>' +
      '<div class="main"><ol class="steps" id="rt-steps"></ol><div class="side">' +
      '<div id="rt-card"><div id="rt-big">READY</div><div id="rt-why">Waiting for a scan.</div><div id="rt-next"></div></div>' +
      '<button id="rt-green">The light is green</button>' +
      '<div class="tiles"><div class="tile"><small>Tested today</small><b id="rt-count">0</b></div>' +
      '<div class="tile"><small>Pass rate</small><b id="rt-rate">–</b></div>' +
      '<div class="tile"><small>Avg per unit</small><b id="rt-average">–</b></div>' +
      '<div class="tile"><small>Top fail</small><b id="rt-top">–</b></div></div>' +
      '<div class="view"><div id="rt-note"></div><iframe id="rt-frame" title="Router page"></iframe></div>' +
      '</div></div>' +
      '<div class="logbox"><div class="logtop"><b>Log (no serial, MAC, IMEI or passwords)</b>' +
      '<button id="rt-copy">Copy log</button><button id="rt-save">Save log</button></div>' +
      '<pre id="rt-log"></pre><textarea id="rt-result" rows="3" readonly></textarea></div></div>';

    function byId(id) {
      return document.getElementById(id);
    }

    var scan = byId('rt-scan');
    var card = byId('rt-card');
    var frame = byId('rt-frame');
    var green = byId('rt-green');
    var logView = byId('rt-log');
    var result = byId('rt-result');
    var stepRows = {};

    STEPS.forEach(function (step) {
      var row = document.createElement('li');
      row.innerHTML = '<div class="icon">○</div><div class="body"><div class="title"></div><div class="hint"></div>' +
        '<div class="now"></div><div class="sub"></div></div><div class="time"></div>';
      row.querySelector('.title').textContent = step[1];
      row.querySelector('.hint').textContent = step[2];
      byId('rt-steps').appendChild(row);
      stepRows[step[0]] = row;
    });
    var visualBox = document.createElement('div');
    visualBox.id = 'rt-visual';
    visualBox.innerHTML = '<button id="rt-visual-pass">Pass</button><button id="rt-visual-fail">Fail</button>';
    stepRows.visual.querySelector('.body').appendChild(visualBox);

    var busy = false;
    var cancelled = false;
    var started = 0;
    var unit = null;
    var checks = [];
    var logLines = [];
    var wipe = { value: 'NOT-RUN', detail: '' };
    var testing = 'NOT-RUN';
    var visual = 'PENDING';
    var currentStep = '';
    var stepStarted = 0;
    var useOpener = false;
    var unreadable = 0;
    var stalePage = null;
    var addressIndex = 0;
    var greenSeen = false;
    var link = { up: null, status: 0, since: Date.now(), checked: 0, drops: 0 };

    function pad(number) {
      return String(number).padStart(2, '0');
    }

    function clock(now, gap) {
      return [pad(now.getHours()), pad(now.getMinutes()), pad(now.getSeconds())].join(gap);
    }

    function store() {
      try {
        return win.localStorage;
      } catch (e) {
        return null;
      }
    }

    function stored(key) {
      try {
        return store().getItem(key);
      } catch (e) {
        return null;
      }
    }

    function keep(key, value) {
      try {
        store().setItem(key, value);
      } catch (e) {
        return;
      }
    }

    function log(kind, message) {
      var seconds = started ? ' +' + Math.round((Date.now() - started) / 1000) + 's' : '';
      var line = '[' + clock(new Date(), ':') + seconds + '] ' + kind + ': ' + message;
      logLines.push(line);
      logView.textContent += line + '\n';
      logView.scrollTop = logView.scrollHeight;
      keep(LOG_KEY, logLines.join('\r\n'));
    }

    function saveFile(prefix, extension, type, content) {
      var now = new Date();
      var date = [now.getFullYear(), pad(now.getMonth() + 1), pad(now.getDate())].join('');
      var anchor = document.createElement('a');
      anchor.href = URL.createObjectURL(new Blob([content], { type: type }));
      anchor.download = prefix + date + '-' + clock(now, '') + extension;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    }

    function saveLog() {
      saveFile('fastmile-demo-log-', '.txt', 'text/plain', logLines.join('\r\n') + '\r\n');
    }

    // Same fields as the OLP history table, oldest station first
    function saveResult() {
      var when = new Date().toISOString();
      var record = function (station, value, detail) {
        return {
          TransactionType: station,
          FieldKey: 'RESULT',
          FieldValue: value,
          Status: unit.PN || '',
          TransactionDate: when,
          Detail: detail
        };
      };
      saveFile('DO-NOT-UPLOAD-olp-result-', '.json', 'application/json', JSON.stringify({
        Tool: VERSION,
        Note: 'Demo output. Not sent to OLP.',
        SerialNumber: String(unit.IMEI),
        PartNumber: unit.PN || '',
        Model: unit.N || '',
        Seconds: Math.round((Date.now() - started) / 1000),
        Checks: checks,
        Transactions: [
          record('ROUTER-DATA-WIPE', wipe.value, wipe.detail),
          record('ROUTER-TESTING', testing, ''),
          record('ROUTER-REFURB', visual, 'Visual check by the operator')
        ]
      }, null, 2) + '\n');
    }

    // The tab stays open between units, so a run that was cut off leaves its log here
    function recoverOldLog() {
      var old = stored(LOG_KEY);
      if (old && !/RESULT: /.test(old.split('\r\n').slice(-4).join(' ')) && /TEST: /.test(old)) {
        logLines = old.split('\r\n').concat(['--- the run above was cut off before a result ---']);
        logView.textContent = logLines.join('\n') + '\n';
        saveLog();
      }
    }

    function pcId() {
      var id = stored(PC_KEY);
      if (!id) {
        id = Math.random().toString(36).slice(2, 6).toUpperCase();
        keep(PC_KEY, id);
      }
      return id;
    }

    function logStation() {
      var chrome = /Chrome\/[\d.]+/.exec(navigator.userAgent);
      log('STATION', VERSION + ', PC id ' + pcId() + ', ' + (chrome ? chrome[0] : navigator.userAgent) +
        ', router at ' + origin + ', opened from ' + win.RT_OPENED_ON);
    }

    function setCard(kind, big, why, next) {
      card.className = kind;
      byId('rt-big').textContent = big;
      byId('rt-why').textContent = why || '';
      byId('rt-next').textContent = next || '';
    }

    function setStep(key, state, note) {
      var row = stepRows[key];
      row.className = state;
      row.querySelector('.icon').textContent = { running: '◐', done: '✓', failed: '✕', stopped: '!', skipped: '–' }[state] || '○';
      row.querySelector('.now').textContent = note || '';
      if (state !== 'running' && stepStarted && key === currentStep) {
        row.querySelector('.time').textContent = Math.round((Date.now() - stepStarted) / 1000) + 's';
      }
    }

    function begin(key, what) {
      if (currentStep && stepRows[currentStep].className === 'running') setStep(currentStep, 'done');
      currentStep = key;
      stepStarted = Date.now();
      setStep(key, 'running', what);
      var title = STEPS.filter(function (step) { return step[0] === key; })[0][1];
      log('TEST', title);
      setCard('BUSY', 'TESTING', title, what);
    }

    function explain(what) {
      stepRows[currentStep].querySelector('.now').textContent = what;
      byId('rt-next').textContent = what;
    }

    // screenOnly is for parts of a serial or IMEI, which stay out of the log
    function report(name, state, note, screenOnly) {
      var seconds = Math.round((Date.now() - started) / 1000);
      checks.push(name + ' ' + state + ' ' + seconds + 's');
      log('CHECK', name + ' ' + state + (note ? ' (' + note + ')' : ''));
      var row = document.createElement('div');
      row.className = state;
      row.textContent = state + ' · ' + name + (screenOnly || note ? ' · ' + (screenOnly || note) : '');
      stepRows[currentStep].querySelector('.sub').appendChild(row);
      if (state === 'FAIL' || state === 'UNSTABLE') stepRows[currentStep].dataset.bad = '1';
      return state === 'PASS' || state === 'INFO';
    }

    function giveUp(why, next) {
      var stop = new Error(why);
      stop.next = next;
      return stop;
    }

    function sleep(ms) {
      return new Promise(function (done) { setTimeout(done, ms); });
    }

    // Every wait of a run goes through here, so Stop test ends it at once
    async function wait(ms) {
      var end = Date.now() + ms;
      do {
        if (cancelled) throw giveUp('Stopped by the operator.', 'Scan again when ready.');
        await sleep(Math.min(200, Math.max(end - Date.now(), 0)));
      } while (Date.now() < end);
      if (cancelled) throw giveUp('Stopped by the operator.', 'Scan again when ready.');
    }

    function routerWindow() {
      return useOpener ? win.opener : frame.contentWindow;
    }

    // Null while the router's page is an error page, which happens during a restart
    function routerDocument() {
      try {
        return routerWindow().document.body ? routerWindow().document : null;
      } catch (e) {
        return null;
      }
    }

    function openRouter() {
      var address = origin + ADDRESSES[addressIndex % ADDRESSES.length];
      addressIndex++;
      stalePage = routerDocument();
      log('TRYING', 'open ' + address);
      if (useOpener) win.opener.location.href = address;
      else frame.src = address;
    }

    function routerPage() {
      try {
        return routerWindow().location.pathname + routerWindow().location.hash;
      } catch (e) {
        return 'not readable (error page)';
      }
    }

    // The old view stays on the page for a moment after the address changes
    async function goTo(hash) {
      // Device details has no address of its own, so leave it through another page
      if (routerWindow().location.hash === hash) {
        routerWindow().location.hash = '#/wan/cellular-status';
        await wait(PAGE_MS);
      }
      routerWindow().location.hash = hash;
      await wait(PAGE_MS);
    }

    function deep(root, found) {
      root.querySelectorAll('*').forEach(function (el) {
        found.push(el);
        if (el.shadowRoot) deep(el.shadowRoot, found);
      });
      return found;
    }

    // The old page stays readable until the new one replaces it, so it never counts
    function allElements() {
      var doc = routerDocument();
      return doc && doc !== stalePage ? deep(doc, []) : [];
    }

    function isVisible(el) {
      var box = el.getBoundingClientRect();
      return box.width > 0 && box.height > 0;
    }

    function text(el) {
      return (el.textContent || '').replace(/\s+/g, ' ').trim();
    }

    function find(selector) {
      return allElements().filter(function (el) {
        return el.matches(selector) && isVisible(el);
      })[0];
    }

    // Visible elements that hold text themselves, in page order
    function leaves() {
      return allElements().filter(function (el) {
        return !el.children.length && text(el) && isVisible(el) &&
          ['SCRIPT', 'STYLE', 'NOSCRIPT'].indexOf(el.tagName) < 0;
      });
    }

    function up(el, test) {
      while (el) {
        if (el.nodeType === 1 && test(el)) return el;
        el = el.parentNode || el.host;
      }
      return null;
    }

    // Details rows put the value in the next pv-text, Cellular Status rows in .right
    function valueOf(label) {
      var values = leaves().filter(function (el) { return text(el) === label; }).map(function (el) {
        var pv = up(el, function (e) { return e.tagName === 'PV-TEXT'; });
        var next = pv && pv.nextElementSibling;
        if (next && next.tagName === 'PV-TEXT') return text(next);
        var left = up(el, function (e) { return e.classList.contains('left'); });
        var right = left && left.nextElementSibling;
        return right && right.classList.contains('right') ? text(right) : '';
      });
      return values.filter(Boolean)[0] || '';
    }

    // Overview rows have no fixed shape: the value is the next text on the page
    function textAfter(pattern) {
      var all = leaves();
      for (var i = 0; i < all.length - 1; i++) {
        if (pattern.test(text(all[i]))) return text(all[i + 1]);
      }
      return '';
    }

    async function waitFor(what, read, ms) {
      var end = Date.now() + (ms || WAIT_MS);
      while (Date.now() < end) {
        var value = read();
        if (value) return value;
        await wait(200);
      }
      throw new Error('timed out waiting for ' + what);
    }

    // A freshly reset unit needs time to connect, so give a bad value time to change
    async function settled(read, good) {
      var end = Date.now() + CONNECT_MS;
      var value = read();
      while (!good(value) && Date.now() < end) {
        await wait(1000);
        value = read();
      }
      return value;
    }

    // Two equal readings make a result. When they differ the third decides, and a
    // value that keeps moving is reported as unstable, not as a failed unit
    async function readTwice(read, good) {
      var first = await settled(read, good);
      await wait(RECHECK_MS);
      var second = read();
      if (first === second) return { value: first, stable: true };
      log('SAW', 'two different readings, reading a third time');
      await wait(RECHECK_MS);
      var third = read();
      return { value: third, stable: third === second };
    }

    function wifiName() {
      var card = find('pv-wifi-card');
      var names = leaves().filter(function (el) { return card && card.contains(el); });
      return names.length ? text(names[0]) : '';
    }

    function type(el, value) {
      var view = routerWindow();
      var setter = Object.getOwnPropertyDescriptor(view.HTMLInputElement.prototype, 'value').set;
      el.focus();
      setter.call(el, value);
      ['input', 'change', 'blur'].forEach(function (name) {
        el.dispatchEvent(new view.Event(name, { bubbles: true }));
      });
    }

    function loginBoxes() {
      var user = find('#username-login-value');
      var pass = find('#passwordLoginAria');
      return user && pass ? { user: user, pass: pass } : null;
    }

    function signInButton() {
      return allElements().filter(function (el) {
        return el.tagName === 'BUTTON' && text(el) === 'Sign in' && isVisible(el) && !el.disabled;
      })[0];
    }

    function visibleButtons() {
      return allElements().filter(function (el) {
        return el.tagName === 'BUTTON' && isVisible(el);
      });
    }

    function isMainResetButton(el) {
      return !!up(el, function (e) { return e.id === 'factorydefaultbtn'; });
    }

    function rejected() {
      return leaves().some(function (el) { return /Invalid login credentials/.test(text(el)); });
    }

    function lastFour(value) {
      return '...' + String(value).slice(-4);
    }

    function normalMac(value) {
      return String(value).toUpperCase().replace(/[^0-9A-F]/g, '');
    }

    // Only for a page before login, and anything that could be device data is hidden
    function maskedPageText() {
      if (find('div.sidenav-logout')) return '(logged in, page text not logged)';
      var secrets = unit ? [unit.ID, unit.KY, unit.U, unit.P, unit.S, unit['23S'], unit.IMEI] : [];
      return leaves().map(text).join(' | ').split(' ').map(function (word) {
        var secret = secrets.some(function (value) { return value && word.indexOf(String(value)) >= 0; });
        return secret || /\d/.test(word) ? '***' : word;
      }).join(' ').slice(0, 300);
    }

    // Page facts for a stop, without any of the page's values
    function logPage() {
      log('SAW', 'router ' + (link.up ? 'answering, HTTP ' + link.status : 'not answering') +
        ', page ' + routerPage());
      log('SAW', 'page text: ' + (maskedPageText() || '(empty)'));
      ['IMEI', 'Status', 'Serial number', 'MAC address', 'Device name', 'WiFi 2.4 GHz', '5G+ Signal'].forEach(function (label) {
        var seen = leaves().some(function (el) { return text(el) === label; });
        if (seen) log('SAW', 'label "' + label + '": ' + (valueOf(label) ? 'has a value' : 'no value found'));
      });
      // Ids and types only: never what a field holds
      allElements().forEach(function (el) {
        if (el.tagName !== 'INPUT' && el.tagName !== 'IFRAME') return;
        log('SAW', 'field: ' + el.tagName.toLowerCase() + ' id="' + el.id + '" type="' + (el.type || '') +
          '" name="' + (el.name || '') + '" visible=' + isVisible(el));
      });
      log('SAW', 'map on page: ' + !!find('div[role="button"].mapClickArea') +
        ', sign out on page: ' + !!find('div.sidenav-logout'));
    }

    async function routerAnswers() {
      var stop = new AbortController();
      var timer = setTimeout(function () { stop.abort(); }, ANSWER_MS);
      try {
        var answer = await fetch(origin + '/', { cache: 'no-store', mode: 'no-cors', signal: stop.signal });
        return answer.status || 1;
      } catch (e) {
        return 0;
      } finally {
        clearTimeout(timer);
      }
    }

    function showLink() {
      var pill = byId('rt-link');
      var seconds = Math.round((Date.now() - link.since) / 1000);
      if (link.up === null) return;
      pill.className = link.up ? 'up' : 'down';
      pill.textContent = link.up ? 'Router connected · last check ' +
        Math.round((Date.now() - link.checked) / 1000) + 's ago' : 'No answer from the router for ' + seconds + 's';
    }

    // Runs all shift, whether a test is running or not
    async function watchLink() {
      while (true) {
        var status = await routerAnswers();
        var isUp = status > 0;
        link.checked = Date.now();
        if (isUp !== link.up) {
          log('SAW', isUp ? 'router started answering, HTTP ' + status : 'router stopped answering');
          link.since = Date.now();
          if (!isUp) link.drops++;
          // A unit was swapped or came back, so the page in the view is stale
          if (isUp && link.up === false && !busy) {
            openRouter();
            setCard('', 'READY', 'Router connected.', 'Scan the QR label.');
          }
          if (!isUp && !busy) setCard('', 'READY', 'No router is answering.', 'Connect the next unit and wait.');
        }
        link.up = isUp;
        link.status = status;
        await sleep(POLL_MS);
      }
    }

    function tickClock() {
      showLink();
      if (busy && currentStep) {
        stepRows[currentStep].querySelector('.time').textContent = Math.round((Date.now() - stepStarted) / 1000) + 's';
      }
    }

    // Some routers refuse to show inside another page, then the first tab does the work
    function checkPageIsReadable() {
      if (useOpener || routerDocument() || !link.up || !frame.getAttribute('src')) {
        unreadable = 0;
        return;
      }
      unreadable++;
      if (unreadable < 3) return;
      if (!win.opener) throw giveUp('The router will not show inside this page.', 'Open this demo again and allow pop-ups.');
      useOpener = true;
      log('TRYING', 'router refused to show here, using the tab the demo was opened from');
      frame.style.display = 'none';
      byId('rt-note').style.display = 'block';
      byId('rt-note').textContent = 'The router page is running in the first tab. Leave that tab open.';
      openRouter();
    }

    // Waits for the router, however long it takes it to come up, and says what it sees
    async function waitForRouter(afterReset) {
      var end = Date.now() + READY_MS;
      var opened = Date.now();
      addressIndex = 0;
      openRouter();
      while (Date.now() < end) {
        checkPageIsReadable();
        var boxes = loginBoxes();
        if (boxes) {
          log('SAW', 'login box found after ' + Math.round((Date.now() - stepStarted) / 1000) + 's, page ' + routerPage());
          return boxes;
        }
        if (!afterReset && find('div.sidenav-logout')) {
          log('SAW', 'already logged in');
          return null;
        }
        var waited = Math.round((Date.now() - stepStarted) / 1000);
        explain(link.up ? 'Router answers, waiting for the login box (' + waited + 's)' :
          'No answer yet, trying every few seconds (' + waited + 's)');
        if (link.up && Date.now() - opened > REOPEN_MS) {
          log('SAW', 'no login box on page ' + routerPage());
          opened = Date.now();
          openRouter();
        }
        await wait(500);
      }
      throw link.up ?
        giveUp('The router answers, but the login box never appeared.', 'Look at the router view on this page and the address on this PC.') :
        giveUp('The router is not answering.', 'Check the power, the cable and the LAN port.');
    }

    // Returns false when the unit refused the label, which is not a failed unit
    async function logIn(label, afterReset) {
      var boxes = await waitForRouter(afterReset);
      setStep('link', 'done');
      if (!boxes) {
        begin(afterReset ? 'login2' : 'login', 'Already logged in.');
        report('Login', 'INFO', 'already logged in');
        return true;
      }
      begin(afterReset ? 'login2' : 'login', 'Typing the username and password from the label.');
      type(boxes.user, String(label.U));
      type(boxes.pass, String(label.P));
      log('TRYING', 'filled username and password');
      var button = await waitFor('the Sign in button', signInButton);
      button.click();
      log('TRYING', 'clicked Sign in');
      var outcome = await waitFor('the login to finish', function () {
        if (rejected()) return 'rejected';
        return find('div[role="button"].mapClickArea') ? 'in' : '';
      }, LOGIN_WAIT_MS);
      if (outcome === 'rejected') return false;
      report('Login', 'PASS');
      return true;
    }

    function waitForMap() {
      return waitFor('the Network map', function () {
        return find('div[role="button"].mapClickArea');
      });
    }

    async function openDetails() {
      if (!find('#factorydefaultbtn button')) {
        log('TRYING', 'opening device details');
        await goTo('#/overview');
        (await waitForMap()).click();
      }
    }

    function reportRead(name, reading, good, note, screenOnly) {
      if (!reading.stable) return report(name, 'UNSTABLE', 'gave two different answers');
      return report(name, good ? 'PASS' : 'FAIL', note, screenOnly);
    }

    function matches(name, expected, reading) {
      var same = expected === reading.value;
      return reportRead(name, reading, same, same ? '' : 'does not match label',
        same ? lastFour(reading.value) : 'unit ' + lastFour(reading.value) + ', label ' + lastFour(expected));
    }

    function present(value) {
      return !!value;
    }

    async function checkIdentity(label) {
      await openDetails();
      await waitFor('the serial number', function () { return valueOf('Serial number'); });
      var name = await readTwice(function () { return valueOf('Device name'); }, present);
      var ok = reportRead('Model', name, name.value === MODEL, name.value);
      var serial = await readTwice(function () { return valueOf('Serial number'); }, present);
      ok = matches('Serial', String(label.S), serial) && ok;
      var mac = await readTwice(function () { return normalMac(valueOf('MAC address')); }, present);
      ok = matches('MAC', normalMac(label['23S']), mac) && ok;
      report('Software', 'INFO', valueOf('Software version'));
      return ok;
    }

    function signalValue() {
      return textAfter(/^5G\+? Signal$/);
    }

    async function waitForGreen() {
      begin('green', 'Waiting for the 5G signal.');
      log('TRYING', 'opening Overview');
      await goTo('#/overview');
      await waitForMap();
      var signal = await settled(signalValue, function (value) { return value === 'Connected'; });
      log('SAW', '5G signal: ' + (signal || 'not found'));
      greenSeen = false;
      green.style.display = 'block';
      explain('Look at the router. Press the green button when the light is green.');
      var end = Date.now() + GREEN_MS;
      while (!greenSeen && Date.now() < end) await wait(200);
      green.style.display = 'none';
      report('Green light', greenSeen ? 'PASS' : 'INFO', greenSeen ? 'operator saw it' : 'not confirmed by the operator');
    }

    async function checkUnit(label) {
      begin('tests', 'Reading each result twice, a few seconds apart.');
      log('TRYING', 'opening Cellular Status');
      await goTo('#/wan/cellular-status');
      await waitFor('the IMEI', function () { return valueOf('IMEI'); });
      var imei = await readTwice(function () { return valueOf('IMEI'); }, present);
      var ok = matches('IMEI', String(label.IMEI), imei);
      var sim = await readTwice(function () { return valueOf('Status'); }, function (value) {
        return value === 'Valid';
      });
      ok = reportRead('SIM', sim, sim.value === 'Valid', sim.value || 'not found') && ok;

      log('TRYING', 'opening Overview');
      await goTo('#/overview');
      await waitForMap();
      var signal = await readTwice(signalValue, function (value) { return value === 'Connected'; });
      ok = reportRead('5G', signal, signal.value === 'Connected', signal.value || 'not found') && ok;
      var bands = ['2.4', '5', '6'];
      for (var i = 0; i < bands.length; i++) {
        var pattern = new RegExp('^WiFi ' + bands[i].replace('.', '\\.') + ' GHz$');
        var state = await readTwice(function () { return textAfter(pattern); }, function (value) {
          return /^Up/.test(value);
        });
        ok = reportRead('Wi-Fi ' + bands[i], state, /^Up/.test(state.value), state.value || 'not found') && ok;
      }
      var expected = String(label.ID);
      var ssid = await readTwice(wifiName, function (value) { return value === expected; });
      ok = reportRead('Wi-Fi name', ssid, ssid.value === expected, ssid.value === expected ? '' : 'does not match label') && ok;
      return ok;
    }

    // Counts drops, so a short restart is not missed between two looks
    async function waitForRouterEvent(happened, ms, why, next) {
      var end = Date.now() + ms;
      while (Date.now() < end) {
        if (happened()) return;
        await wait(200);
      }
      throw giveUp(why, next);
    }

    function newButtons(before) {
      return visibleButtons().filter(function (el) {
        return before.indexOf(el) < 0 && !isMainResetButton(el);
      });
    }

    function confirmButton(before) {
      var fresh = newButtons(before);
      for (var i = 0; i < CONFIRM_WORDS.length; i++) {
        for (var j = 0; j < fresh.length; j++) {
          if (text(fresh[j]).toLowerCase() === CONFIRM_WORDS[i]) return fresh[j];
        }
      }
      return null;
    }

    async function factoryReset() {
      begin('reset', 'Pressing Factory default > Reset.');
      await openDetails();
      var reset = await waitFor('the factory Reset button', function () {
        return find('#factorydefaultbtn button');
      });
      var before = visibleButtons();
      log('TRYING', 'clicking Factory default > Reset');
      // The page can die with the unit, so keep what is known so far
      saveLog();
      reset.click();
      var confirm;
      try {
        confirm = await waitFor('the reset confirm button', function () { return confirmButton(before); });
      } catch (e) {
        log('SAW', 'new buttons on page: ' + newButtons(before).map(text).join(', '));
        throw giveUp('Reset was pressed, but no known confirm button appeared.', 'Check the unit and reset it by hand if needed.');
      }
      // The confirm dialog is not captured yet, so the first real run writes it down
      log('SAW', 'buttons after Reset: ' + newButtons(before).map(text).join(', '));
      log('TRYING', 'confirming with button "' + text(confirm) + '"');
      var drops = link.drops;
      confirm.click();
      report('Factory reset', 'PASS', 'confirmed');
      begin('restart', 'Waiting for the router to go down and come back.');
      await waitForRouterEvent(function () { return link.drops > drops; }, RESTART_START_MS,
        'The router did not restart after the reset.', 'Check the unit and reset it by hand if needed.');
      explain('Router is down. Waiting for it to come back.');
      await waitForRouterEvent(function () { return link.up; }, RESTART_END_MS,
        'The router did not come back after the reset.', 'Check the power and the light.');
      report('Back up', 'PASS');
      // The web page answers before the login service is ready
      explain('Router is back. Waiting for its services to start.');
      await wait(SETTLE_MS);
    }

    // This tab stays open, so a second scan does not reset twice
    function alreadyReset(label) {
      try {
        return win.sessionStorage.getItem(RESET_KEY) === lastFour(label.S);
      } catch (e) {
        return false;
      }
    }

    function rememberReset(label) {
      try {
        win.sessionStorage.setItem(RESET_KEY, lastFour(label.S));
      } catch (e) {
        log('SAW', 'could not remember the reset in this tab');
      }
    }

    function todayKey() {
      return new Date().toISOString().slice(0, 10);
    }

    function todayRuns() {
      try {
        var saved = JSON.parse(stored(STATS_KEY));
        return saved && saved.date === todayKey() ? saved.runs : [];
      } catch (e) {
        return [];
      }
    }

    function showStats() {
      var runs = todayRuns();
      var done = runs.filter(function (run) { return run.result !== 'NOT TESTED'; });
      var passed = done.filter(function (run) { return run.result === 'PASS'; });
      var counts = {};
      runs.forEach(function (run) { if (run.fail) counts[run.fail] = (counts[run.fail] || 0) + 1; });
      var top = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })[0];
      var total = done.reduce(function (sum, run) { return sum + run.seconds; }, 0);
      byId('rt-count').textContent = done.length;
      byId('rt-rate').textContent = done.length ? Math.round(100 * passed.length / done.length) + '%' : '–';
      byId('rt-average').textContent = done.length ? Math.floor(total / done.length / 60) + 'm ' +
        Math.round(total / done.length % 60) + 's' : '–';
      byId('rt-top').textContent = top || '–';
    }

    function firstFail() {
      var bad = checks.filter(function (check) { return / (FAIL|UNSTABLE) /.test(check); })[0];
      return bad ? bad.replace(/ (FAIL|UNSTABLE) .*/, '') : '';
    }

    function finish(overall, why, next) {
      var seconds = Math.round((Date.now() - started) / 1000);
      var bad = stepRows[currentStep].dataset.bad;
      setStep(currentStep, overall === 'PASS' ? 'done' : overall === 'FAIL' || bad ? 'failed' : 'stopped');
      STEPS.forEach(function (step) {
        if (step[0] !== 'visual' && !stepRows[step[0]].className) setStep(step[0], 'skipped');
      });
      setCard(overall === 'NOT TESTED' ? 'NOTTESTED' : overall, overall, (why || 'All checks passed') + ' · ' + seconds + 's',
        next || (overall === 'PASS' ? 'Do the visual inspection, then connect the next unit.' : ''));
      result.value = [VERSION, overall, why || '-', seconds + 's'].concat(checks).join(' | ');
      result.style.display = 'block';
      log('RESULT', overall + ' in ' + seconds + 's');
      if (why) log('WHY', why);
      if (next) log('DO NEXT', next);
      log('STATIONS', 'DATA-WIPE ' + wipe.value + ', TESTING ' + testing + ', REFURB ' + visual);
      saveLog();
      saveResult();
      var runs = todayRuns().concat([{ result: overall, seconds: seconds, fail: firstFail() }]);
      keep(STATS_KEY, JSON.stringify({ date: todayKey(), runs: runs }));
      showStats();
      if (overall !== 'NOT TESTED') {
        visualBox.style.display = 'flex';
        setStep('visual', 'running', 'Press Pass or Fail.');
      }
      busy = false;
      byId('rt-stop').disabled = true;
      byId('rt-start').disabled = false;
      scan.focus();
    }

    function clearRun() {
      checks = [];
      wipe = { value: 'NOT-RUN', detail: '' };
      testing = 'NOT-RUN';
      visual = 'PENDING';
      currentStep = '';
      cancelled = false;
      started = Date.now();
      result.style.display = 'none';
      visualBox.style.display = 'none';
      STEPS.forEach(function (step) {
        var row = stepRows[step[0]];
        row.className = '';
        delete row.dataset.bad;
        row.querySelector('.icon').textContent = '○';
        row.querySelector('.now').textContent = '';
        row.querySelector('.sub').textContent = '';
        row.querySelector('.time').textContent = '';
      });
    }

    async function run(label) {
      var stage = 'first login';
      busy = true;
      unit = label;
      clearRun();
      logLines = logLines.slice(-400);
      byId('rt-stop').disabled = false;
      byId('rt-start').disabled = true;
      logStation();
      begin('label', 'Reading the label.');
      log('SAW', 'label model code ' + String(label.N).slice(0, 20));
      report('Label', 'PASS', String(label.N).slice(0, 20));
      if (OTHER_MODELS.indexOf(label.N) >= 0) {
        finish('NOT TESTED', 'This is ' + LABEL_NAMES[label.N] + '. The demo only knows Gateway 12 FastMile.',
          'Test this unit by hand.');
        return;
      }
      try {
        begin('link', 'Checking that the router answers.');
        if (!await logIn(label)) {
          report('Login', 'FAIL', 'label rejected');
          rememberReset(label);
          wipe.detail = 'Operator to reset by hand';
          finish('NOT TESTED', 'The router refused the label login. The previous customer changed it.',
            'Reset the unit by hand, then scan again.');
          return;
        }
        stage = 'testing';
        begin('identity', 'Comparing the unit with the label before the reset.');
        if (!await checkIdentity(label)) {
          testing = OLP_FAIL;
          finish('FAIL', 'The unit does not match the label. It was not reset.', 'Check that this QR belongs to this unit.');
          return;
        }
        if (alreadyReset(label)) {
          begin('reset', 'This unit was already reset.');
          report('Factory reset', 'INFO', 'already reset');
          setStep('restart', 'skipped');
          setStep('login2', 'skipped');
          wipe = { value: 'PASS', detail: 'Reset before this run' };
        } else {
          stage = 'reset';
          await factoryReset();
          rememberReset(label);
          stage = 'second login';
          begin('link', 'Waiting for the login page after the reset.');
          if (!await logIn(label, true)) {
            report('Login', 'FAIL', 'label rejected after reset');
            wipe = { value: OLP_FAIL, detail: 'Label rejected after reset' };
            finish('FAIL', 'The label was rejected after the reset.', 'Check the unit by hand.');
            return;
          }
          wipe = { value: 'PASS', detail: 'Reset, then logged in with the label' };
          stage = 'testing';
        }
        await waitForGreen();
        var passed = await checkUnit(label);
        testing = passed ? 'PASS' : OLP_FAIL;
        finish(passed ? 'PASS' : 'FAIL', passed ? '' : firstFail() + ' did not pass.', passed ? '' : 'Check that part of the unit.');
      } catch (e) {
        log('SAW', 'stopped during ' + stage + ': ' + e.message);
        logPage();
        // No login means the tool never reached the unit, which says nothing about it
        if (stage === 'testing') testing = OLP_FAIL;
        else if (stage !== 'first login') wipe = { value: OLP_FAIL, detail: e.message };
        var next = e.next || { 'first login': 'Read the log below, then scan again.',
          reset: 'Check the unit and reset it by hand if needed.',
          'second login': 'The reset was done. Scan again when the router is up.',
          testing: 'Read the log below.' }[stage];
        finish(stage === 'testing' ? 'FAIL' : 'NOT TESTED', e.message, next);
      }
    }

    function startFromScan() {
      if (busy) return;
      var label;
      try {
        label = JSON.parse(scan.value);
      } catch (e) {
        return;
      }
      var missing = ['U', 'P', 'S', '23S', 'IMEI'].filter(function (key) { return !label[key]; });
      scan.value = '';
      if (missing.length) {
        setCard('NOTTESTED', 'SCAN AGAIN', 'The label is missing ' + missing.join(', ') + '.', 'Scan the QR again.');
        return;
      }
      byId('rt-unit').textContent = [String(label.N), LABEL_NAMES[label.N] || 'unknown model',
        'serial ' + lastFour(label.S), 'IMEI ' + lastFour(label.IMEI)].join(' · ');
      run(label);
    }

    scan.addEventListener('input', startFromScan);
    byId('rt-start').onclick = startFromScan;
    byId('rt-stop').onclick = function () { cancelled = true; };
    byId('rt-save').onclick = saveLog;
    byId('rt-copy').onclick = function () { navigator.clipboard.writeText(logLines.join('\r\n')); };
    green.onclick = function () { greenSeen = true; };

    function setVisual(value) {
      visual = value;
      log('CHECK', 'Visual inspection ' + value);
      setStep('visual', value === 'PASS' ? 'done' : 'failed');
      visualBox.style.display = 'none';
      saveResult();
    }

    byId('rt-visual-pass').onclick = function () { setVisual('PASS'); };
    byId('rt-visual-fail').onclick = function () { setVisual(OLP_FAIL); };
    win.addEventListener('beforeunload', function (event) {
      if (busy) event.preventDefault();
    });

    recoverOldLog();
    logStation();
    showStats();
    openRouter();
    watchLink();
    setInterval(tickClock, 1000);
    scan.focus();
  }

  // The label's password must never go into another site's login page. Routers
  // are always on a private address
  if (!/^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.|127\.)/.test(location.hostname)) {
    alert('This is not the router page. Going to 192.168.1.1 now. When the router page opens, click the bookmark again.');
    location.href = 'http://192.168.1.1/';
    return;
  }
  var openedOn = location.pathname + location.hash;
  var origin = location.origin;
  var station = window.open('', 'rt-station');
  if (station && station.RT_VERSION) {
    station.focus();
    return;
  }
  // Pop-ups blocked: the station takes over this tab instead
  if (!station) {
    station = window;
    var last = setTimeout(function () {}, 0);
    while (last--) {
      clearTimeout(last);
      clearInterval(last);
    }
  }
  var page = station.document;
  page.open();
  page.write('<!doctype html><html><head><meta charset="utf-8"><title>Router test station</title></head><body></body></html>');
  page.close();
  station.RT_OPENED_ON = openedOn;
  // Its own script, so the station keeps running when the first tab moves on
  var script = page.createElement('script');
  script.textContent = '(' + main + ')(window, ' + JSON.stringify(origin) + ')';
  page.head.appendChild(script);
  if (!station.RT_VERSION) main(station, origin);
})();
