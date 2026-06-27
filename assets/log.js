/* ============================================================
   cyberwitchery log — behaviour (vanilla, no dependencies)
   1. theme toggle: system default, manual override, persisted
   2. tag filter on the index
   Load with <script src="/log/assets/log.js" defer></script>.

   NOTE: the *initial* theme must be set BEFORE first paint to
   avoid a flash. Do that with the tiny inline snippet in <head>
   (see the "no-flash theme init" script in the templates) — this
   file only handles the click-to-toggle + live system changes.

   data-tags is COMMA-separated, not whitespace: tag names here
   contain spaces ("network automation"), so a comma is the only
   safe delimiter.
   ============================================================ */
(function () {
  var STORAGE_KEY = 'cw-log-theme';
  var root = document.documentElement;

  /* ---- theme toggle ------------------------------------- */
  function stored() {
    try { var v = localStorage.getItem(STORAGE_KEY); return (v === 'light' || v === 'dark') ? v : null; }
    catch (e) { return null; }
  }
  function apply(theme) { root.setAttribute('data-theme', theme); }

  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      apply(next);
      try { localStorage.setItem(STORAGE_KEY, next); } catch (e) {}
    });
  }

  /* follow the OS while the visitor hasn't made an explicit choice */
  if (window.matchMedia) {
    var mql = window.matchMedia('(prefers-color-scheme: light)');
    var onScheme = function (e) {
      if (stored()) return;
      apply(e.matches ? 'light' : 'dark');
    };
    if (mql.addEventListener) mql.addEventListener('change', onScheme);
    else if (mql.addListener) mql.addListener(onScheme); /* old Safari */
  }

  /* ---- tag filter (index only) -------------------------- */
  var filterBar = document.querySelector('.tag-filter');
  if (!filterBar) return;

  var rows  = Array.prototype.slice.call(document.querySelectorAll('.log-list .row'));
  var count = document.querySelector('.log-count');
  var active = null; /* null = "all" */

  function plural(n) { return n + (n === 1 ? ' entry' : ' entries'); }

  /* split a comma-separated data-tags value into trimmed tag names */
  function tagsOf(row) {
    var raw = (row.getAttribute('data-tags') || '').split(',');
    var out = [];
    for (var i = 0; i < raw.length; i++) {
      var t = raw[i].trim();
      if (t) out.push(t);
    }
    return out;
  }

  function render() {
    var shown = 0;
    rows.forEach(function (row) {
      var match = !active || tagsOf(row).indexOf(active) !== -1;
      row.hidden = !match;
      if (match) shown++;
    });
    Array.prototype.forEach.call(filterBar.querySelectorAll('button'), function (b) {
      var t = b.getAttribute('data-tag') || null;
      b.classList.toggle('is-active', t === active);
    });
    if (count) count.textContent = plural(shown) + (active ? ' tagged #' + active : '');
  }

  filterBar.addEventListener('click', function (e) {
    var btn = e.target.closest('button');
    if (!btn) return;
    var tag = btn.getAttribute('data-tag') || null; /* the "all" button has no data-tag */
    active = (tag && tag === active) ? null : tag;   /* click active tag again → back to all */
    render();
  });

  render();
})();
