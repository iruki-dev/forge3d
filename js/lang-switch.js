/* forge3d docs — language preference persistence
 *
 * Stores the user's language choice (en / ko) in localStorage.
 * On every page load:
 *   - if lang=ko and the current URL is NOT under /ko/, redirect there
 *   - if lang=en and the current URL IS under /ko/, redirect to the English path
 * Alternate-header link clicks are intercepted to navigate to the same page
 * in the chosen language rather than always going to the root.
 * The "한국어" nav tab is hidden visually (kept in nav config for sidebar generation).
 */
(function () {
  'use strict';

  var KEY = 'forge3d-lang';

  /* Prefixes that have no Korean equivalent — stay in English */
  var EN_ONLY = ['api/'];

  /* ── storage ──────────────────────────────────────────────── */
  function getLang() {
    try { return localStorage.getItem(KEY) || 'en'; } catch (e) { return 'en'; }
  }
  function setLang(v) {
    try { localStorage.setItem(KEY, v); } catch (e) {}
  }

  /* ── URL helpers ──────────────────────────────────────────── */
  function getBase() {
    // MkDocs Material stores a relative base path in the __config JSON element
    // (e.g. ".", "..", "../.." depending on page depth) — NOT in a <base> tag.
    var cfgEl = document.getElementById('__config');
    if (cfgEl) {
      try {
        var rel = JSON.parse(cfgEl.textContent).base;
        if (typeof rel === 'string') {
          // MkDocs pages are served as directories.  When the browser URL lacks a
          // trailing slash (e.g. /forge3d instead of /forge3d/), the URL is treated
          // as a *file* and new URL('../', ...) resolves one level too high.
          // Always add a trailing slash before resolving so /forge3d is a directory.
          var loc = window.location.href.split('?')[0].split('#')[0];
          if (!loc.endsWith('/')) loc += '/';
          return new URL(rel.replace(/\/?$/, '/'), loc).href;
        }
      } catch (e) {}
    }
    var el = document.querySelector('base');
    return el ? el.href : window.location.origin + '/';
  }

  function getRel() {
    var base = getBase();
    // Normalise: treat current page as a directory (add trailing slash if absent)
    var url  = window.location.href.split('?')[0].split('#')[0];
    if (!url.endsWith('/')) url += '/';
    if (url.startsWith(base)) return url.slice(base.length);
    var bp = new URL(base).pathname;
    var p  = window.location.pathname;
    if (!p.endsWith('/')) p += '/';
    return p.startsWith(bp) ? p.slice(bp.length) : p.replace(/^\//, '');
  }

  function isKo(rel)  { return rel === 'ko/' || rel.startsWith('ko/'); }
  function hasKo(rel) { return !EN_ONLY.some(function (p) { return rel.startsWith(p); }); }
  function toKo(rel)  { return 'ko/' + rel; }
  function toEn(rel)  { return rel.slice('ko/'.length); }

  /* ── redirect on load if stored language ≠ current path ──── */
  function syncLang() {
    var lang = getLang();
    var rel  = getRel();
    if (lang === 'ko' && !isKo(rel) && hasKo(rel)) {
      window.location.replace(getBase() + toKo(rel));
      return true;
    }
    if (lang === 'en' && isKo(rel)) {
      window.location.replace(getBase() + toEn(rel));
      return true;
    }
    return false;
  }

  /* ── hide the "한국어" nav tab (kept in config for sidebar) ── */
  function hideKoTab() {
    document.querySelectorAll('.md-tabs__item').forEach(function (item) {
      var link = item.querySelector('.md-tabs__link');
      if (link && link.textContent.trim() === '한국어') {
        item.style.display = 'none';
      }
    });
  }

  /* ── wire alternate-header links ─────────────────────────── */
  function wireLink(a) {
    if (a.dataset.lsWired) return;
    a.dataset.lsWired = '1';
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var tl   = this.getAttribute('hreflang');
      var rel  = getRel();
      var base = getBase();
      setLang(tl);
      if (tl === 'ko') {
        window.location.href = base + (hasKo(rel) ? toKo(rel) : 'ko/');
      } else {
        window.location.href = base + (isKo(rel) ? toEn(rel) : rel || '');
      }
    });
  }

  function wireSwitcher() {
    document.querySelectorAll('a[hreflang]').forEach(wireLink);
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(function () {
        document.querySelectorAll('a[hreflang]').forEach(wireLink);
        hideKoTab();
      }).observe(document.body, { childList: true, subtree: true });
    }
  }

  /* ── entry point ──────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    hideKoTab();
    if (!syncLang()) wireSwitcher();
  });
})();
