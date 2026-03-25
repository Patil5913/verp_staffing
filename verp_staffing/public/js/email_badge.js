(function () {
  'use strict';

  let _emailAccount  = null;
  let _senderEmail   = null;
  let _badgeCount    = 0;
  let _initialized   = false;

  /* ─── Inject badge CSS once ─── */
  function injectStyles() {
    if (document.getElementById('ew-badge-style')) return;
    const s = document.createElement('style');
    s.id = 'ew-badge-style';
    s.textContent = `
      .ew-sidebar-badge {
        display: inline-flex !important;
        align-items: center;
        justify-content: center;
        min-width: 18px;
        height: 18px;
        padding: 0 5px;
        border-radius: 99px;
        background: #E24B4A;
        color: #fff;
        font-size: 10px;
        font-weight: 600;
        line-height: 1;
        margin-left: auto;
        margin-right: 5px;
        flex-shrink: 0;
        pointer-events: none;
        box-shadow: 0 1px 3px rgba(226,75,74,0.40);
      }
      .ew-sidebar-badge.ew-pop {
        animation: ewPop 0.25s ease;
      }
      @keyframes ewPop {
        0%   { transform: scale(0.6); opacity: 0.4; }
        60%  { transform: scale(1.2); }
        100% { transform: scale(1);   opacity: 1;   }
      }
      .sidebar-item-container .item-anchor {
        display: flex !important;
        align-items: center !important;
      }
    `;
    document.head.appendChild(s);
  }

  /* ─── Paint badge DOM ─── */
  function setBadge(count) {
    _badgeCount = count;
    window.__ewSetBadge    = setBadge;       // keep bridge pointer fresh
    window.__ewUnreadCount = count;

    document.querySelectorAll('.ew-sidebar-badge').forEach(b => b.remove());
    if (count <= 0) return;

    document.querySelectorAll('.sidebar-item-container .item-anchor').forEach(link => {
      const label = link.querySelector('.sidebar-item-label');
      if (!label || label.textContent.trim() !== 'Email Inbox') return;

      const badge = document.createElement('span');
      badge.className = 'ew-sidebar-badge';
      badge.textContent = count > 99 ? '99+' : count;

      requestAnimationFrame(() => {
        badge.classList.add('ew-pop');
        badge.addEventListener('animationend', () => badge.classList.remove('ew-pop'), { once: true });
      });

      link.appendChild(badge);
    });
  }

  /* ─── DB query — fallback when widget is not on screen ─── */
  async function fetchUnreadCount() {
    try {
      if (!_emailAccount && !_senderEmail) return;
      const res = await frappe.call({
        method: 'frappe.client.get_list',
        args: {
          doctype   : 'Communication',
          filters   : [
            ['communication_type', '=', 'Communication'],
            ['communication_medium', '=', 'Email'],
            ['sent_or_received',    '=', 'Received'],
            ['seen',                '=', 0]
          ],
          or_filters: [
            ['email_account', '=', _emailAccount],
            ['recipients', 'like', '%' + (_senderEmail || '') + '%']
          ],
          fields: ['name'],
          limit : 100
        }
      });
      setBadge((res.message || []).length);
    } catch (e) {
      console.warn('[EmailBadge] fetchUnreadCount error:', e);
    }
  }

  /* ─── Resolve user account once ─── */
  async function resolveEmailAccount() {
    try {
      const user = frappe.session.user;
      if (!user || user === 'Guest') return false;

      const ur = await frappe.call({
        method: 'frappe.client.get',
        args: { doctype: 'User', name: user }
      });
      const ud = ur.message;
      const ue = ud?.user_emails || [];
      if (!ue.length) return false;

      _emailAccount = ue[0].email_account;
      _senderEmail  = ud?.email || null;

      try {
        const ea = await frappe.call({
          method: 'frappe.client.get',
          args: { doctype: 'Email Account', name: _emailAccount }
        });
        if (ea.message?.email_id) _senderEmail = ea.message.email_id;
      } catch(_) {}

      return true;
    } catch (e) {
      console.warn('[EmailBadge] resolveEmailAccount error:', e);
      return false;
    }
  }

  /* ─── Realtime binding ───────────────────────────────────────────────────
   *
   * ROOT CAUSE OF BUG 1:
   * Frappe's SPA calls `frappe.realtime.off()` (clears ALL listeners) on
   * every page navigation. Calling bindRealtime() once at init means all
   * handlers die after the first page change.
   *
   * FIX: Re-register all frappe.realtime handlers after EVERY page-change.
   * We use a named jQuery namespace (.ew-badge) so we can safely unbind
   * just our handler without touching anything else.
   *
   ──────────────────────────────────────────────────────────────────────── */
  function registerRealtimeHandlers() {
    // Always wipe previous registrations before re-adding — prevents doubles
    frappe.realtime.off('new_email');
    frappe.realtime.off('doc_update');
    frappe.realtime.off('list_update');

    frappe.realtime.on('new_email', () => {
      // Give widget 800 ms to push its own count first; fall back if it doesn't
      clearTimeout(window._ewBadgeNewTimer);
      window._ewBadgeNewTimer = setTimeout(fetchUnreadCount, 800);
    });

    frappe.realtime.on('doc_update', (data) => {
      if (data?.doctype === 'Communication') {
        clearTimeout(window._ewBadgeDocTimer);
        window._ewBadgeDocTimer = setTimeout(fetchUnreadCount, 600);
      }
    });

    frappe.realtime.on('list_update', (data) => {
      if (data?.doctype === 'Communication') {
        clearTimeout(window._ewBadgeListTimer);
        window._ewBadgeListTimer = setTimeout(fetchUnreadCount, 600);
      }
    });
  }

  /* ─── page-change handler ────────────────────────────────────────────────
   *
   * Two jobs on every navigation:
   *   1. Re-stamp badge DOM (sidebar re-renders, old badge node is gone)
   *   2. Re-register realtime handlers (Frappe wiped them)
   *
   ──────────────────────────────────────────────────────────────────────── */
  function bindPageChange() {
    $(document).off('page-change.ew-badge').on('page-change.ew-badge', () => {
      // Instant repaint with cached count — no flicker
      setTimeout(() => setBadge(_badgeCount), 250);

      // Re-register socket listeners — THIS is the fix for cross-page badge
      setTimeout(registerRealtimeHandlers, 300);

      // Fresh count: prefer widget push, fall back to DB query
      setTimeout(() => {
        if (typeof window.__ewUnreadCount === 'number') {
          setBadge(window.__ewUnreadCount);
        } else {
          fetchUnreadCount();
        }
      }, 700);
    });
  }

  /* ─── Periodic fallback poll ─── */
  function startPolling() {
    clearInterval(window._ewBadgePollTimer);
    window._ewBadgePollTimer = setInterval(() => {
      if (!document.hidden) fetchUnreadCount();
    }, 90 * 1000);
  }

  /* ─── Init ─── */
  async function init() {
    if (_initialized) return;
    _initialized = true;

    window.__ewSetBadge = setBadge;   // expose bridge immediately

    injectStyles();

    const ok = await resolveEmailAccount();
    if (!ok) return;

    // Initial count
    if (typeof window.__ewUnreadCount === 'number') {
      setBadge(window.__ewUnreadCount);
    } else {
      await fetchUnreadCount();
    }

    registerRealtimeHandlers();
    bindPageChange();
    startPolling();
  }

  frappe.after_ajax(() => setTimeout(init, 800));

})();