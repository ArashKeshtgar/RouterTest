// Read-only look at the current page, for writing the model profiles in
// routertest/pages.py. It lists the page's fields, buttons and text as CSS
// selectors, and shows them in a box to copy. It sends nothing, clicks nothing
// and never reads what is typed in an input.
(function () {
  var BOX_ID = 'rt-capture';
  var MAX_LINES = 300;
  var old = document.getElementById(BOX_ID);
  if (old) old.remove();

  // Serials, MACs, IMEIs, IPs and versions all contain digits: hide any word that does
  function mask(text) {
    return (text || '').replace(/\s+/g, ' ').trim().split(' ').map(function (word) {
      return /\d/.test(word) && word.length >= 4 ? '***' : word;
    }).join(' ').slice(0, 60);
  }

  function allElements(root, found) {
    root.querySelectorAll('*').forEach(function (el) {
      found.push(el);
      if (el.shadowRoot) allElements(el.shadowRoot, found);
    });
    return found;
  }

  function isVisible(el) {
    var box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  }

  function kindOf(el) {
    var tag = el.tagName.toLowerCase();
    if (tag === 'input' || tag === 'select' || tag === 'textarea') return 'field';
    if (tag === 'button' || tag === 'a' || el.getAttribute('role') === 'button') return 'click';
    if (getComputedStyle(el).cursor === 'pointer' &&
        (!el.parentElement || getComputedStyle(el.parentElement).cursor !== 'pointer')) return 'click';
    if (el.children.length === 0 && el.textContent.trim()) return 'text';
    return null;
  }

  function selectorFor(el) {
    if (el.id) return '#' + el.id;
    var selector = el.tagName.toLowerCase();
    ['name', 'formcontrolname', 'type', 'role', 'data-testid', 'data-test', 'data-cy'].forEach(function (attr) {
      var value = el.getAttribute(attr);
      if (value) selector += '[' + attr + '="' + value + '"]';
    });
    Array.prototype.slice.call(el.classList).filter(function (name) {
      return !/^(ng-|_ng|cdk-)/.test(name);
    }).slice(0, 3).forEach(function (name) {
      selector += '.' + CSS.escape(name);
    });
    return selector;
  }

  function describe(el) {
    var parts = [el.getAttribute('placeholder'), el.getAttribute('aria-label'), el.getAttribute('title')];
    if (el.tagName.toLowerCase() !== 'input') parts.unshift(el.textContent);
    return mask(parts.filter(Boolean).join(' / '));
  }

  var lines = [];
  allElements(document, []).forEach(function (el) {
    if (el.closest('#' + BOX_ID) || !isVisible(el)) return;
    var kind = kindOf(el);
    if (!kind) return;
    var selector = selectorFor(el);
    var root = el.getRootNode();
    var shadow = root === document ? '' : ' [shadow]';
    var count = root.querySelectorAll(selector).length;
    lines.push(kind + ' | ' + selector + ' | x' + count + shadow + ' | ' + describe(el));
  });

  var header = [
    'capture v1',
    'page: ' + location.pathname + location.hash.split('?')[0],
    'iframes: ' + document.querySelectorAll('iframe').length,
    'lines: ' + lines.length + (lines.length > MAX_LINES ? ' (cut to ' + MAX_LINES + ')' : '')
  ];
  var output = header.concat(lines.slice(0, MAX_LINES)).join('\n');

  var box = document.createElement('div');
  box.id = BOX_ID;
  box.style.cssText = 'position:fixed;right:12px;bottom:12px;width:520px;max-width:90vw;' +
    'background:#fff;color:#000;border:2px solid #005aff;padding:8px;z-index:2147483647;font:13px sans-serif';

  var text = document.createElement('textarea');
  text.id = BOX_ID + '-output';
  text.readOnly = true;
  text.value = output;
  text.style.cssText = 'width:100%;height:260px;box-sizing:border-box;font:11px monospace';

  function button(label, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.style.cssText = 'margin:6px 6px 0 0;padding:4px 12px';
    b.addEventListener('click', onClick);
    return b;
  }

  box.appendChild(text);
  // The admin page is plain http, where navigator.clipboard is not available
  box.appendChild(button('Copy', function () {
    text.select();
    document.execCommand('copy');
  }));
  box.appendChild(button('Close', function () {
    box.remove();
  }));
  document.body.appendChild(box);
})();
