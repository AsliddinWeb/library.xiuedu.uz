/* ===========================================================================
   XIU Library — umumiy UI xatti-harakati (v3)
   Ikki qiyofada ham ishlaydi: OPAC va Staff.

   Imkoniyatlar:
     1. HTMX yuqori progress chizig'i
     2. toast("Matn", "success") — JS'dan yoki HTMX javobidan (HX-Trigger)
     3. Klaviatura: "/" yoki Ctrl+K — global qidiruv (staff panelida)
     4. data-confirm="..." — xavfli amal oldidan tasdiq
=========================================================================== */
(function () {
  'use strict';

  /* --- 1. HTMX progress chizig'i --------------------------------------- */
  const bar = document.getElementById('htmx-bar');
  if (bar) {
    document.body.addEventListener('htmx:beforeRequest', () => bar.classList.add('on'));
    document.body.addEventListener('htmx:afterRequest', () => bar.classList.remove('on'));
    document.body.addEventListener('htmx:sendError', () => bar.classList.remove('on'));
  }

  /* --- 2. Toast -------------------------------------------------------- */
  const LEVELS = { success: 'toast-success', danger: 'toast-danger', warning: 'toast-warning' };

  function toast(text, level, timeout) {
    const host = document.getElementById('toast-host');
    if (!host || !text) return;

    const el = document.createElement('div');
    el.className = 'toast' + (LEVELS[level] ? ' ' + LEVELS[level] : '');

    const span = document.createElement('span');
    span.className = 'flex-1';
    span.textContent = text;            // XSS'dan himoya: faqat matn
    el.appendChild(span);

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'opacity-70 hover:opacity-100';
    close.setAttribute('aria-label', 'Yopish');
    close.textContent = '✕';
    close.addEventListener('click', () => el.remove());
    el.appendChild(close);

    host.appendChild(el);
    window.setTimeout(() => el.remove(), timeout || 4500);
  }

  window.toast = toast;

  // HTMX javobi:  HX-Trigger: {"toast": {"text": "Saqlandi", "level": "success"}}
  document.body.addEventListener('toast', (event) => {
    const data = event.detail || {};
    toast(data.text || data.value, data.level, data.timeout);
  });

  // Dastlabki (Django messages) toastlarni avtomatik yopish
  document.querySelectorAll('#toast-host .toast').forEach((el) => {
    window.setTimeout(() => el.remove(), 5000);
  });

  /* --- 3. Klaviatura yorliqlari ---------------------------------------- */
  const isTyping = (el) => el && (
    el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' ||
    el.isContentEditable
  );

  document.addEventListener('keydown', (event) => {
    const search = document.querySelector('[data-global-search]');
    if (!search) return;

    const slash = event.key === '/' && !isTyping(document.activeElement);
    const ctrlK = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k';

    if (slash || ctrlK) {
      event.preventDefault();
      search.focus();
      search.select();
    }
    if (event.key === 'Escape' && document.activeElement === search) {
      search.blur();
    }
  });

  /* --- 4. Tasdiq (data-confirm) ---------------------------------------- */
  document.body.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-confirm]');
    if (!trigger) return;
    if (!window.confirm(trigger.getAttribute('data-confirm'))) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);
})();
