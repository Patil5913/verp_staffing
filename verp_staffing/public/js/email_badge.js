(function () {
  'use strict';

  let _emailAccount = null;
  let _senderEmail  = null;
  let _badgeCount   = 0;
  let _initialized  = false;

  /* ─── Inject badge CSS once ─── */
  function injectStyles() {
    if (document.getElementById('ew-badge-style')) return;
    const s = document.createElement('style');
    s.id = 'ew-badge-style';
    s.textContent = [
      '.ew-sidebar-badge{display:inline-flex!important;align-items:center;justify-content:center;',
      'min-width:18px;height:18px;padding:0 5px;border-radius:99px;background:#E24B4A;color:#fff;',
      'font-size:10px;font-weight:600;line-height:1;margin-left:auto;margin-right:5px;flex-shrink:0;',
      'pointer-events:none;box-shadow:0 1px 3px rgba(226,75,74,.40)}',
      '.ew-sidebar-badge.ew-pop{animation:ewPop .25s ease}',
      '@keyframes ewPop{0%{transform:scale(.6);opacity:.4}60%{transform:scale(1.2)}100%{transform:scale(1);opacity:1}}',
      '.sidebar-item-container .item-anchor{display:flex!important;align-items:center!important}'
    ].join('');
    document.head.appendChild(s);
  }

  /* ─── Paint badge DOM ─── */
  function setBadge(count) {
    _badgeCount = count;
    window.__ewSetBadge    = setBadge;
    window.__ewUnreadCount = count;

    document.querySelectorAll('.ew-sidebar-badge').forEach(function(b) { b.remove(); });
    if (count <= 0) return;

    document.querySelectorAll('.sidebar-item-container .item-anchor').forEach(function(link) {
      const label = link.querySelector('.sidebar-item-label');
      if (!label || label.textContent.trim() !== 'Email Inbox') return;

      const badge = document.createElement('span');
      badge.className = 'ew-sidebar-badge';
      badge.textContent = count > 99 ? '99+' : count;

      requestAnimationFrame(function() {
        badge.classList.add('ew-pop');
        badge.addEventListener('animationend', function() {
          badge.classList.remove('ew-pop');
        }, { once: true });
      });

      link.appendChild(badge);
    });
  }

  /* ─── DB query ───────────────────────────────────────────────────────────
   *
   * BUG: Using a single get_list with both `filters` + `or_filters` causes
   * Frappe to emit SQL like:
   *
   *   WHERE (seen=0 AND sent_or_received='Received' AND ...)
   *      OR (email_account = 'X')        <-- bypasses seen=0!
   *      OR (recipients LIKE '%y%')      <-- bypasses seen=0!
   *
   * FIX: Run two separate queries, each with seen=0 in its own filters,
   * then deduplicate by name before counting.
   *
   ──────────────────────────────────────────────────────────────────────── */
  async function fetchUnreadCount() {
    try {
      if (!_emailAccount && !_senderEmail) return;

      const seen = new Set();
      const baseFilters = [
        ['communication_type',  '=', 'Communication'],
        ['communication_medium','=', 'Email'],
        ['sent_or_received',    '=', 'Received'],
        ['seen',                '=', 0]
      ];

      if (_emailAccount) {
        const r1 = await frappe.call({
          method: 'frappe.client.get_list',
          args: {
            doctype: 'Communication',
            filters: baseFilters.concat([['email_account', '=', _emailAccount]]),
            fields: ['name'],
            limit: 100
          }
        });
        (r1.message || []).forEach(function(e) { seen.add(e.name); });
      }

      if (_senderEmail) {
        const r2 = await frappe.call({
          method: 'frappe.client.get_list',
          args: {
            doctype: 'Communication',
            filters: baseFilters.concat([['recipients', 'like', '%' + _senderEmail + '%']]),
            fields: ['name'],
            limit: 100
          }
        });
        (r2.message || []).forEach(function(e) { seen.add(e.name); });
      }

      setBadge(seen.size);
    } catch (e) {
      console.warn('[EmailBadge] fetchUnreadCount error:', e);
    }
  }

  /* ─── Resolve user account once ─── */
  async function resolveEmailAccount() {
    try {
      const user = frappe.session.user;
      if (!user || user === 'Guest') return false;

      const ur = await frappe.call({ method: 'frappe.client.get', args: { doctype: 'User', name: user } });
      const ud = ur.message;
      const ue = (ud && ud.user_emails) || [];
      if (!ue.length) return false;

      _emailAccount = ue[0].email_account;
      _senderEmail  = (ud && ud.email) || null;

      try {
        const ea = await frappe.call({ method: 'frappe.client.get', args: { doctype: 'Email Account', name: _emailAccount } });
        if (ea.message && ea.message.email_id) _senderEmail = ea.message.email_id;
      } catch (_) {}

      return true;
    } catch (e) {
      console.warn('[EmailBadge] resolveEmailAccount error:', e);
      return false;
    }
  }

  /* ─── Realtime binding ───────────────────────────────────────────────────
   *
   * Frappe's router calls frappe.realtime.off(event) without a handler ref
   * on every page change, wiping all listeners globally.
   *
   * Fix: always .off() before .on() to prevent stacking, and re-call this
   * function from the page-change handler with a 600 ms delay — enough for
   * Frappe's router cleanup to finish before we re-register.
   *
   ──────────────────────────────────────────────────────────────────────── */
  function registerRealtimeHandlers() {
    frappe.realtime.off('new_email');
    frappe.realtime.off('doc_update');
    frappe.realtime.off('list_update');

    frappe.realtime.on('new_email', function() {
      clearTimeout(window._ewBadgeNewTimer);
      // 900 ms: let the widget push its count first; fall back to DB query if it doesn't
      window._ewBadgeNewTimer = setTimeout(function() {
        const widgetPushedRecently = window.__ewUnreadCountTs &&
          (Date.now() - window.__ewUnreadCountTs) < 2000;
        if (!widgetPushedRecently) fetchUnreadCount();
      }, 900);
    });

    frappe.realtime.on('doc_update', function(data) {
      if (data && data.doctype === 'Communication') {
        clearTimeout(window._ewBadgeDocTimer);
        window._ewBadgeDocTimer = setTimeout(fetchUnreadCount, 700);
      }
    });

    frappe.realtime.on('list_update', function(data) {
      if (data && data.doctype === 'Communication') {
        clearTimeout(window._ewBadgeListTimer);
        window._ewBadgeListTimer = setTimeout(fetchUnreadCount, 700);
      }
    });
  }

  /* ─── page-change handler ────────────────────────────────────────────────
   *
   * Every navigation does three things:
   *  1. Re-paint badge node immediately (sidebar re-renders, old node gone)
   *  2. Re-register socket listeners at 600 ms (after Frappe's cleanup)
   *  3. Fresh DB count at 900 ms (always — never trust the stale global)
   *
   ──────────────────────────────────────────────────────────────────────── */
  function bindPageChange() {
    $(document).off('page-change.ew-badge').on('page-change.ew-badge', function() {
      // 1 — instant repaint with last cached count
      setTimeout(function() { setBadge(_badgeCount); }, 250);

      // 2 — re-register AFTER Frappe's router cleanup (600 ms > typical cleanup window)
      setTimeout(registerRealtimeHandlers, 600);

      // 3 — always query DB; ignore window.__ewUnreadCount (may be stale)
      setTimeout(fetchUnreadCount, 900);
    });
  }

  /* ─── Visibility change — refresh badge when tab regains focus ─── */
  function bindVisibilityChange() {
    document.addEventListener('visibilitychange', function() {
      if (!document.hidden) fetchUnreadCount();
    });
  }

  /* ─── Short polling fallback (30 s) ─── */
  function startPolling() {
    clearInterval(window._ewBadgePollTimer);
    window._ewBadgePollTimer = setInterval(function() {
      if (!document.hidden) fetchUnreadCount();
    }, 30 * 1000);
  }

  /* ─── Init ─── */
  async function init() {
    if (_initialized) return;
    _initialized = true;

    window.__ewSetBadge = setBadge;
    injectStyles();

    const ok = await resolveEmailAccount();
    if (!ok) return;

    // Always do a real DB query — never trust any window global at startup
    await fetchUnreadCount();

    registerRealtimeHandlers();
    bindPageChange();
    bindVisibilityChange();
    startPolling();
  }

  frappe.after_ajax(function() { setTimeout(init, 800); });

})();