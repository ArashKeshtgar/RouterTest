// FastMile demo: scan the label, and the page logs in with it and checks the
// unit against it. Runs in the router's own page and sends nothing anywhere. It
// clicks only Sign in and the device on the Network map, tries the login once,
// and never touches Reset, Reboot or a setting. Nothing is saved.
(function () {
  var VERSION = 'fastmile demo v1';
  var BOX_ID = 'rt-demo';
  var MODEL = 'FastMile 5G Gateway 12';
  var WAIT_MS = 30000;
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

  async function waitFor(what, read) {
    var end = Date.now() + WAIT_MS;
    while (Date.now() < end) {
      var value = read();
      if (value) return value;
      await sleep(200);
    }
    throw new Error('timed out waiting for ' + what);
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
    '<p id="rt-status" style="margin:8px 0">Scan the QR label now.</p>' +
    '<textarea id="rt-scan" rows="3" style="width:100%;box-sizing:border-box"></textarea>' +
    '<table id="rt-rows" style="width:100%;border-collapse:collapse"></table>' +
    '<textarea id="rt-result" rows="4" readonly style="display:none;width:100%;box-sizing:border-box;margin-top:8px"></textarea>';
  document.body.appendChild(box);
  var scan = box.querySelector('#rt-scan');
  var status = box.querySelector('#rt-status');
  var rows = box.querySelector('#rt-rows');
  var result = box.querySelector('#rt-result');
  box.querySelector('#rt-close').onclick = function () { box.remove(); };
  scan.focus();

  var started = 0;
  var checks = [];

  function show(message, color) {
    status.textContent = message;
    status.style.color = color || '#111';
    status.style.fontWeight = color ? 'bold' : 'normal';
  }

  function report(name, state, note) {
    var seconds = Math.round((Date.now() - started) / 1000);
    checks.push(name + ' ' + state + ' ' + seconds + 's');
    var row = rows.insertRow();
    row.insertCell().textContent = state;
    row.insertCell().textContent = name;
    row.insertCell().textContent = note || '';
    row.cells[0].style.cssText = 'font-weight:bold;padding:2px 6px 2px 0;color:' +
      (state === 'PASS' ? '#0a7a2f' : state === 'FAIL' ? '#b00020' : '#555');
    return state === 'PASS' || state === 'INFO';
  }

  function matches(name, expected, actual) {
    if (expected === actual) return report(name, 'PASS', lastFour(actual));
    return report(name, 'FAIL', 'unit ' + lastFour(actual) + ', label ' + lastFour(expected));
  }

  function finish(overall, reason) {
    var seconds = Math.round((Date.now() - started) / 1000);
    show(overall + (reason ? ': ' + reason : '') + ' (' + seconds + ' s)',
      overall === 'PASS' ? '#0a7a2f' : '#b00020');
    result.value = [VERSION, overall, reason || '-', seconds + 's'].concat(checks).join(' | ');
    result.style.display = 'block';
  }

  // Returns false when the unit refused the label, which is not a failed unit
  async function logIn(label) {
    var user = await waitFor('the login page or a logged-in page', function () {
      return find('#username-login-value') || find('div.sidenav-logout');
    });
    if (user.matches('div.sidenav-logout')) {
      report('Login', 'INFO', 'already logged in');
      return true;
    }
    type(user, String(label.U));
    type(find('#passwordLoginAria'), String(label.P));
    var button = await waitFor('the Sign in button', signInButton);
    button.click();
    var outcome = await waitFor('the login to finish', function () {
      if (rejected()) return 'rejected';
      return find('div[role="button"].mapClickArea') ? 'in' : '';
    });
    if (outcome === 'rejected') return false;
    report('Login', 'PASS');
    return true;
  }

  async function checkUnit(label) {
    var ok = true;

    location.hash = '#/wan/cellular-status';
    var imei = await waitFor('the IMEI', function () { return valueOf('IMEI'); });
    ok = matches('IMEI', String(label.IMEI), imei) && ok;
    var sim = await waitFor('the SIM status', function () { return valueOf('Status'); });
    ok = report('SIM', sim === 'Valid' ? 'PASS' : 'FAIL', sim) && ok;

    location.hash = '#/overview';
    var map = await waitFor('the Network map', function () {
      return find('div[role="button"].mapClickArea');
    });
    var signal = await waitFor('the 5G status', function () { return textAfter(/^5G\+? Signal$/); });
    ok = report('5G', signal === 'Connected' ? 'PASS' : 'FAIL', signal) && ok;
    ['2.4', '5', '6'].forEach(function (band) {
      var state = textAfter(new RegExp('^WiFi ' + band.replace('.', '\\.') + ' GHz$'));
      ok = report('Wi-Fi ' + band, /^Up/.test(state) ? 'PASS' : 'FAIL', state || 'not found') && ok;
    });

    map.click();
    var serial = await waitFor('the serial number', function () { return valueOf('Serial number'); });
    var name = valueOf('Device name');
    ok = report('Model', name === MODEL ? 'PASS' : 'FAIL', name) && ok;
    ok = matches('Serial', String(label.S), serial) && ok;
    ok = matches('MAC', normalMac(label['23S']), normalMac(valueOf('MAC address'))) && ok;
    report('Software', 'INFO', valueOf('Software version'));
    return ok;
  }

  async function run(label) {
    started = Date.now();
    scan.style.display = 'none';
    show('Testing, please wait...');
    try {
      if (!await logIn(label)) {
        report('Login', 'FAIL', 'label rejected');
        finish('RESET BY HAND', 'previous customer changed the login');
        return;
      }
      finish(await checkUnit(label) ? 'PASS' : 'FAIL');
    } catch (e) {
      report('Stopped', 'FAIL', e.message);
      finish('FAIL', e.message);
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
      show('Label is missing ' + missing.join(', ') + '. Scan again.', '#b00020');
      return;
    }
    run(label);
  });
})();
