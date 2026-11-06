// FastMile demo: scan the label, and the page logs in with it, checks the unit is
// the one on the label, factory resets it, logs in again and runs the functional
// tests. Runs in the router's own page and sends nothing anywhere. It clicks only
// Sign in, the device on the Network map and Factory default > Reset, which also
// reboots the unit. It tries each login once and changes no setting. It saves a
// .txt log with steps and times but no device data, and a .json result in the
// shape of the three OLP stations, which holds the IMEI that OLP files units under.
// Nothing is sent to OLP. It also remembers in this tab, by the serial's last 4,
// that a unit was already reset.
(function () {
  var VERSION = 'fastmile demo v7';
  // OLP's two results for every station are PASS and this
  var OLP_FAIL = 'FAIL-FAIL';
  var RESET_KEY = 'rt-demo-reset';
  var SETTLE_MS = 20000;
  var CONNECT_MS = 120000;
  var BOX_ID = 'rt-demo';
  var MODEL = 'FastMile 5G Gateway 12';
  var WAIT_MS = 30000;
  var LOGIN_WAIT_MS = 90000;
  var RESTART_START_MS = 60000;
  var RESTART_END_MS = 300000;
  var POLL_MS = 3000;
  // The confirm dialog has not been captured yet, so its button is matched by word
  var CONFIRM_WORDS = ['reset', 'factory reset', 'confirm', 'ok', 'okay', 'yes', 'continue', 'proceed'];
  var old = document.getElementById(BOX_ID);
  if (old) old.remove();

  function deep(root, found) {
    root.querySelectorAll('*').forEach(function (el) {
      if (el.closest('#' + BOX_ID)) return;
      found.push(el);
      if (el.shadowRoot) deep(el.shadowRoot, found);
    });
    return found;
  }

  function isVisible(el) {
    var box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  }

  function text(el) {
    return (el.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function find(selector) {
    return deep(document, []).filter(function (el) {
      return el.matches(selector) && isVisible(el);
    })[0];
  }

  // Visible elements that hold text themselves, in page order
  function leaves() {
    return deep(document, []).filter(function (el) {
      return !el.children.length && text(el) && isVisible(el);
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

  function sleep(ms) {
    return new Promise(function (done) { setTimeout(done, ms); });
  }

  async function waitFor(what, read, ms) {
    var end = Date.now() + (ms || WAIT_MS);
    while (Date.now() < end) {
      var value = read();
      if (value) return value;
      await sleep(200);
    }
    throw new Error('timed out waiting for ' + what);
  }

  // A freshly reset unit needs time to connect, so give a bad value time to change
  async function settled(read, good) {
    var end = Date.now() + CONNECT_MS;
    var value = read();
    while (!good(value) && Date.now() < end) {
      await sleep(1000);
      value = read();
    }
    return value;
  }

  function wifiName() {
    var card = find('pv-wifi-card');
    var names = leaves().filter(function (el) { return card && card.contains(el); });
    return names.length ? text(names[0]) : '';
  }

  function type(el, value) {
    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    el.focus();
    setter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  function signInButton() {
    return deep(document, []).filter(function (el) {
      return el.tagName === 'BUTTON' && text(el) === 'Sign in' && isVisible(el) && !el.disabled;
    })[0];
  }

  function visibleButtons() {
    return deep(document, []).filter(function (el) {
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

  var box = document.createElement('div');
  box.id = BOX_ID;
  box.style.cssText = 'position:fixed;top:12px;right:12px;width:400px;max-height:94vh;overflow:auto;' +
    'z-index:2147483647;background:#fff;color:#111;border:2px solid #124191;padding:12px;' +
    'font:14px Arial,sans-serif;box-shadow:0 2px 10px rgba(0,0,0,.4)';
  box.innerHTML = '<strong>' + VERSION + '</strong>' +
    '<button id="rt-close" style="float:right">Close</button>' +
    '<button id="rt-save" style="float:right;margin-right:6px">Save log</button>' +
    '<p id="rt-status" style="margin:8px 0">Scan the QR label now.</p>' +
    '<textarea id="rt-scan" rows="3" style="width:100%;box-sizing:border-box"></textarea>' +
    '<table id="rt-rows" style="width:100%;border-collapse:collapse"></table>' +
    '<textarea id="rt-result" rows="4" readonly style="display:none;width:100%;box-sizing:border-box;margin-top:8px"></textarea>' +
    '<label id="rt-visual-box" style="display:none;margin-top:8px">Visual check (ROUTER-REFURB) ' +
    '<select id="rt-visual"><option>PENDING</option><option>PASS</option><option>FAIL-FAIL</option></select></label>';
  document.body.appendChild(box);
  var scan = box.querySelector('#rt-scan');
  var status = box.querySelector('#rt-status');
  var rows = box.querySelector('#rt-rows');
  var result = box.querySelector('#rt-result');
  var visualBox = box.querySelector('#rt-visual-box');
  var visual = box.querySelector('#rt-visual');
  box.querySelector('#rt-close').onclick = function () { box.remove(); };
  box.querySelector('#rt-save').onclick = function () { saveLog(); };
  visual.onchange = function () { saveResult(); };
  scan.focus();

  var started = 0;
  var checks = [];
  var logLines = [];
  var unit = null;
  var wipe = { value: 'NOT-RUN', detail: '' };
  var testing = 'NOT-RUN';

  function pad(number) {
    return String(number).padStart(2, '0');
  }

  function clock(now, gap) {
    return [pad(now.getHours()), pad(now.getMinutes()), pad(now.getSeconds())].join(gap);
  }

  function log(message) {
    var seconds = started ? ' +' + Math.round((Date.now() - started) / 1000) + 's' : '';
    logLines.push('[' + clock(new Date(), ':') + seconds + '] ' + message);
  }

  // Page facts for a stop, without any of the page's values
  function logPage() {
    log('page: ' + location.pathname + location.hash);
    ['IMEI', 'Status', 'Serial number', 'MAC address', 'Device name', 'WiFi 2.4 GHz', '5G+ Signal'].forEach(function (label) {
      var seen = leaves().some(function (el) { return text(el) === label; });
      var state = !seen ? 'not on page' : valueOf(label) ? 'has a value' : 'no value found';
      log('label "' + label + '": ' + state);
    });
    // Ids and types only: never what a field holds
    deep(document, []).forEach(function (el) {
      if (el.tagName !== 'INPUT' && el.tagName !== 'IFRAME') return;
      log('field: ' + el.tagName.toLowerCase() + ' id="' + el.id + '" type="' + (el.type || '') +
        '" name="' + (el.name || '') + '" visible=' + isVisible(el));
    });
    log('map on page: ' + !!find('div[role="button"].mapClickArea'));
    log('sign out on page: ' + !!find('div.sidenav-logout'));
  }

  function saveFile(prefix, extension, type, content) {
    var now = new Date();
    var date = [now.getFullYear(), pad(now.getMonth() + 1), pad(now.getDate())].join('');
    var link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([content], { type: type }));
    link.download = prefix + date + '-' + clock(now, '') + extension;
    document.body.appendChild(link);
    link.click();
    link.remove();
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
    saveFile('olp-result-', '.json', 'application/json', JSON.stringify({
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
        record('ROUTER-REFURB', visual.value, 'Visual check by the operator')
      ]
    }, null, 2) + '\n');
  }

  log(VERSION + ' opened on ' + location.pathname + location.hash);

  function show(message, color) {
    status.textContent = message;
    status.style.color = color || '#111';
    status.style.fontWeight = color ? 'bold' : 'normal';
  }

  // screenOnly is for parts of a serial or IMEI, which stay out of the log
  function report(name, state, note, screenOnly) {
    var seconds = Math.round((Date.now() - started) / 1000);
    checks.push(name + ' ' + state + ' ' + seconds + 's');
    log(name + ': ' + state + (note ? ' (' + note + ')' : ''));
    var row = rows.insertRow();
    row.insertCell().textContent = state;
    row.insertCell().textContent = name;
    row.insertCell().textContent = screenOnly || note || '';
    row.cells[0].style.cssText = 'font-weight:bold;padding:2px 6px 2px 0;color:' +
      (state === 'PASS' ? '#0a7a2f' : state === 'FAIL' ? '#b00020' : '#555');
    return state === 'PASS' || state === 'INFO';
  }

  function matches(name, expected, actual) {
    if (expected === actual) return report(name, 'PASS', '', lastFour(actual));
    return report(name, 'FAIL', 'does not match label',
      'unit ' + lastFour(actual) + ', label ' + lastFour(expected));
  }

  function finish(overall, reason) {
    var seconds = Math.round((Date.now() - started) / 1000);
    show(overall + (reason ? ': ' + reason : '') + ' (' + seconds + ' s)',
      overall === 'PASS' ? '#0a7a2f' : '#b00020');
    result.value = [VERSION, overall, reason || '-', seconds + 's'].concat(checks).join(' | ');
    result.style.display = 'block';
    log('RESULT: ' + overall + (reason ? ' - ' + reason : '') + ' in ' + seconds + 's');
    log('stations: DATA-WIPE ' + wipe.value + ', TESTING ' + testing + ', REFURB ' + visual.value);
    saveLog();
    saveResult();
    visualBox.style.display = 'block';
  }

  // This tab survives a page reload, so a second scan does not reset twice
  function alreadyReset(label) {
    try {
      return sessionStorage.getItem(RESET_KEY) === lastFour(label.S);
    } catch (e) {
      return false;
    }
  }

  function rememberReset(label) {
    try {
      sessionStorage.setItem(RESET_KEY, lastFour(label.S));
    } catch (e) {
      log('could not remember the reset in this tab');
    }
  }

  // Returns false when the unit refused the label, which is not a failed unit
  async function logIn(label, afterReset) {
    log('looking for the login page');
    var user = await waitFor('the login page', function () {
      return find('#username-login-value') || (!afterReset && find('div.sidenav-logout'));
    }, LOGIN_WAIT_MS);
    if (user.matches('div.sidenav-logout')) {
      report('Login', 'INFO', 'already logged in');
      return true;
    }
    if (rejected()) throw new Error('an old login error is on the page, reload it and scan again');
    type(user, String(label.U));
    type(find('#passwordLoginAria'), String(label.P));
    log('filled username and password');
    var button = await waitFor('the Sign in button', signInButton);
    button.click();
    log('clicked Sign in');
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
      log('opening device details');
      location.hash = '#/overview';
      (await waitForMap()).click();
    }
  }

  async function checkIdentity(label) {
    await openDetails();
    var serial = await waitFor('the serial number', function () { return valueOf('Serial number'); });
    var name = valueOf('Device name');
    var ok = report('Model', name === MODEL ? 'PASS' : 'FAIL', name);
    ok = matches('Serial', String(label.S), serial) && ok;
    ok = matches('MAC', normalMac(label['23S']), normalMac(valueOf('MAC address'))) && ok;
    report('Software', 'INFO', valueOf('Software version'));
    return ok;
  }

  async function checkUnit(label) {
    var ok = true;

    log('opening Cellular Status');
    location.hash = '#/wan/cellular-status';
    var imei = await waitFor('the IMEI', function () { return valueOf('IMEI'); });
    ok = matches('IMEI', String(label.IMEI), imei) && ok;
    var sim = await settled(function () { return valueOf('Status'); }, function (value) {
      return value === 'Valid';
    });
    ok = report('SIM', sim === 'Valid' ? 'PASS' : 'FAIL', sim || 'not found') && ok;

    log('opening Overview');
    location.hash = '#/overview';
    await waitForMap();
    var signal = await settled(function () { return textAfter(/^5G\+? Signal$/); }, function (value) {
      return value === 'Connected';
    });
    ok = report('5G', signal === 'Connected' ? 'PASS' : 'FAIL', signal || 'not found') && ok;
    var bands = ['2.4', '5', '6'];
    for (var i = 0; i < bands.length; i++) {
      var pattern = new RegExp('^WiFi ' + bands[i].replace('.', '\\.') + ' GHz$');
      var state = await settled(function () { return textAfter(pattern); }, function (value) {
        return /^Up/.test(value);
      });
      ok = report('Wi-Fi ' + bands[i], /^Up/.test(state) ? 'PASS' : 'FAIL', state || 'not found') && ok;
    }
    var expected = String(label.ID);
    var name = await settled(wifiName, function (value) { return value === expected; });
    ok = report('Wi-Fi name', name === expected ? 'PASS' : 'FAIL', name === expected ? '' : 'does not match label') && ok;
    return ok;
  }

  async function routerAnswers() {
    var stop = new AbortController();
    var timer = setTimeout(function () { stop.abort(); }, POLL_MS);
    try {
      await fetch(location.pathname, { cache: 'no-store', signal: stop.signal });
      return true;
    } catch (e) {
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  async function waitForRouter(answering, ms, what) {
    var end = Date.now() + ms;
    while (Date.now() < end) {
      if (await routerAnswers() === answering) return;
      await sleep(POLL_MS);
    }
    throw new Error(what);
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
    await openDetails();
    var reset = await waitFor('the factory Reset button', function () {
      return find('#factorydefaultbtn button');
    });
    var before = visibleButtons();
    log('clicking Factory default > Reset');
    reset.click();
    var confirm;
    try {
      confirm = await waitFor('the reset confirm button', function () { return confirmButton(before); });
    } catch (e) {
      log('new buttons on page: ' + newButtons(before).map(text).join(', '));
      throw e;
    }
    log('confirming with button "' + text(confirm) + '"');
    // The page can die with the unit, so keep what is known so far
    saveLog();
    confirm.click();
    report('Factory reset', 'PASS', 'confirmed');
    show('Reset running, waiting for the unit to return...');
    await waitForRouter(false, RESTART_START_MS, 'the unit did not restart after the reset');
    log('unit went down');
    await waitForRouter(true, RESTART_END_MS, 'the unit did not come back after the reset');
    report('Back up', 'PASS');
    // The web page answers before the login service is ready
    await sleep(SETTLE_MS);
  }

  async function run(label) {
    var stage = 'first login';
    unit = label;
    started = Date.now();
    scan.style.display = 'none';
    show('Testing, please wait...');
    try {
      if (!await logIn(label)) {
        report('Login', 'FAIL', 'label rejected');
        rememberReset(label);
        wipe.detail = 'Operator to reset by hand';
        finish('RESET BY HAND', 'previous customer changed the login. Then scan again');
        return;
      }
      stage = 'testing';
      if (!await checkIdentity(label)) {
        testing = OLP_FAIL;
        finish('FAIL', 'unit does not match the label, not reset');
        return;
      }
      if (alreadyReset(label)) {
        report('Factory reset', 'INFO', 'already reset');
        wipe = { value: 'PASS', detail: 'Reset before this run' };
      } else {
        stage = 'reset';
        await factoryReset();
        rememberReset(label);
        stage = 'second login';
        location.hash = '#/login';
        if (!await logIn(label, true)) {
          report('Login', 'FAIL', 'label rejected after reset');
          wipe = { value: OLP_FAIL, detail: 'Label rejected after reset' };
          finish('FAIL', 'label rejected after reset');
          return;
        }
        wipe = { value: 'PASS', detail: 'Reset, then logged in with the label' };
        stage = 'testing';
      }
      var passed = await checkUnit(label);
      testing = passed ? 'PASS' : OLP_FAIL;
      finish(passed ? 'PASS' : 'FAIL');
    } catch (e) {
      report('Stopped', 'FAIL', e.message);
      logPage();
      // No login means the tool never reached the unit, which says nothing about it
      if (stage === 'testing') testing = OLP_FAIL;
      else if (stage !== 'first login') wipe = { value: OLP_FAIL, detail: e.message };
      var outcome = stage === 'first login' ? 'NOT TESTED' :
        stage === 'reset' ? 'CHECK RESET BY HAND' :
        stage === 'second login' ? 'RESET DONE, RELOAD AND SCAN AGAIN' : 'FAIL';
      finish(outcome, e.message);
    }
  }

  scan.addEventListener('input', function () {
    var label;
    try {
      label = JSON.parse(scan.value);
    } catch (e) {
      return;
    }
    var missing = ['U', 'P', 'S', '23S', 'IMEI'].filter(function (key) { return !label[key]; });
    scan.value = '';
    if (missing.length) {
      log('scan is missing ' + missing.join(', '));
      show('Label is missing ' + missing.join(', ') + '. Scan again.', '#b00020');
      return;
    }
    log('label scanned, model field ' + String(label.N).slice(0, 20));
    run(label);
  });
})();
