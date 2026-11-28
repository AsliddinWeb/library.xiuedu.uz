/* ===========================================================================
   XIU Library — umumiy UI xatti-harakati (v3)
   Ikki qiyofada ham ishlaydi: OPAC va Staff.

   Imkoniyatlar (qo'shimcha): mavzu tanlash, katalog ko'rinishi, yuqoriga qaytish.

   Imkoniyatlar:
     1. HTMX yuqori progress chizig'i
     2. toast("Matn", "success") — JS'dan yoki HTMX javobidan (HX-Trigger)
     3. Klaviatura: "/" yoki Ctrl+K — global qidiruv (staff panelida)
     4. data-confirm="..." — xavfli amal oldidan tasdiq
     5. data-reveal — ko'rinishga kirganda ochilish
     6. data-count="N" — sonlar sanab chiqiladi
     7. .site-header — aylantirilganda soya
     8. data-rail — gorizontal lentani tugma bilan surish
     9. data-form — sabab/summa so'raydigan oyna
    10. F2 — abonement deski; data-autofocus — yangilangandan keyin fokus
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

  // F2 — abonement deski (menyuda havolasi bor xodimda)
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'F2') return;
    const desk = document.querySelector('[data-desk-link]');
    if (!desk) return;
    event.preventDefault();
    window.location.assign(desk.getAttribute('href'));
  });

  // Yangilangan blokdagi asosiy maydonga fokus qaytadi (skaner ketma-ket o'qiydi)
  document.body.addEventListener('htmx:afterSettle', (event) => {
    const root = event.detail.elt;
    if (!root || !root.querySelector) return;
    const field = root.matches('[data-autofocus]') ? root : root.querySelector('[data-autofocus]');
    if (field && root.id === 'desk') {
      field.focus();
      field.select();
    }
  });

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

  /* --- 5. Reveal ------------------------------------------------------- */
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canObserve = 'IntersectionObserver' in window;

  const settle = (el) => {
    // Ochilib bo'lgach atribut olib tashlanadi — hover transformlari erkin qoladi
    const done = (event) => {
      if (event && event.target !== el) return;
      el.removeAttribute('data-reveal');
      el.classList.remove('is-in');
      el.removeEventListener('transitionend', done);
    };
    el.addEventListener('transitionend', done);
    window.setTimeout(done, 1800);
  };

  const revealer = canObserve && new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      revealer.unobserve(entry.target);
      entry.target.classList.add('is-in');
      settle(entry.target);
    });
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0.05 });

  /* --- 6. Sanagich ----------------------------------------------------- */
  const format = (n) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0');

  const countUp = (el) => {
    const target = parseInt(el.dataset.count, 10);
    if (!Number.isFinite(target) || reducedMotion) return;
    const duration = 1400;
    let start = null;
    const step = (time) => {
      start = start || time;
      const t = Math.min((time - start) / duration, 1);
      el.textContent = format(target * (1 - Math.pow(1 - t, 4)));
      if (t < 1) window.requestAnimationFrame(step);
    };
    el.textContent = '0';
    window.requestAnimationFrame(step);
    // Yashirin tabda rAF to'xtaydi — son baribir to'g'ri qolsin
    window.setTimeout(() => { el.textContent = format(target); }, duration + 300);
  };

  const counter = canObserve && new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      counter.unobserve(entry.target);
      countUp(entry.target);
    });
  }, { threshold: 0.4 });

  function enhance(root) {
    root.querySelectorAll('[data-reveal]').forEach((el) => {
      if (revealer) revealer.observe(el); else el.removeAttribute('data-reveal');
    });
    if (counter) root.querySelectorAll('[data-count]').forEach((el) => counter.observe(el));
  }

  enhance(document);
  document.body.addEventListener('htmx:afterSettle', (event) => enhance(event.target.parentElement || document));
  window.__uiReady = true;

  /* --- 7. Header soyasi ------------------------------------------------ */
  const header = document.querySelector('.site-header');
  if (header) {
    const sync = () => header.classList.toggle('is-scrolled', window.scrollY > 8);
    window.addEventListener('scroll', sync, { passive: true });
    sync();
  }

  /* --- 8. Lenta tugmalari: data-rail="ID" data-dir="1|-1" -------------- */
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-rail]');
    if (!button) return;
    const rail = document.getElementById(button.dataset.rail);
    if (rail) rail.scrollBy({ left: Number(button.dataset.dir || 1) * rail.clientWidth * 0.8 });
  });

  /* --- Mehmon himoyalangan havolani bossa — kirish oynasi -------------- */
  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-login]')) return;
    event.preventDefault();
    window.dispatchEvent(new CustomEvent('open-login'));
  });

  /* --- 4. Tasdiq (data-confirm) ---------------------------------------- */
  const askConfirm = (message, label) => new Promise((resolve) => {
    if (typeof HTMLDialogElement !== 'function') { resolve(window.confirm(message)); return; }
    const dialog = document.createElement('dialog');
    dialog.className = 'confirm';
    dialog.innerHTML = '<span class="icon-box icon-box-lg icon-box-danger">'
      + '<svg viewBox="0 0 24 24" class="size-7" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
      + '<path d="M10.3 4.5 2.8 17.5a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.5a2 2 0 0 0-3.4 0Z"/><path d="M12 9.500v4M12 17v.01"/></svg></span>'
      + '<p class="mt-4 text-base font-bold" data-text></p>'
      + '<div class="confirm-actions">'
      + '<button type="button" class="btn btn-secondary" value="no">Bekor qilish</button>'
      + '<button type="button" class="btn btn-danger" value="yes"></button></div>';
    dialog.querySelector('[data-text]').textContent = message;   // XSS'dan himoya
    dialog.querySelector('[value="yes"]').textContent = label || 'Tasdiqlash';
    const close = (answer) => { dialog.close(); dialog.remove(); resolve(answer); };
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) close(false);
      const button = event.target.closest('button');
      if (button) close(button.value === 'yes');
    });
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); close(false); });
    document.body.appendChild(dialog);
    dialog.showModal();
    dialog.querySelector('[value="no"]').focus();
  });

  document.body.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-confirm]');
    if (!trigger || trigger.dataset.confirmed) return;
    event.preventDefault();
    event.stopPropagation();
    askConfirm(trigger.getAttribute('data-confirm'), trigger.dataset.confirmLabel).then((ok) => {
      if (!ok) return;
      trigger.dataset.confirmed = '1';
      trigger.click();                       // forma yuborilishi yoki HTMX so'rovi
      delete trigger.dataset.confirmed;
    });
  }, true);

  /* --- 9. Kichik forma oynasi: data-form='[{"name":"note","label":"Sabab"}]' --
     Tasdiqlangach element qayta bosiladi va qiymatlar HTMX so'roviga qo'shiladi. */
  const askForm = (title, fields, label) => new Promise((resolve) => {
    const dialog = document.createElement('dialog');
    dialog.className = 'confirm';
    const form = document.createElement('form');
    const heading = document.createElement('p');
    heading.className = 'text-base font-bold';
    heading.textContent = title;
    form.appendChild(heading);

    fields.forEach((spec) => {
      const wrap = document.createElement('label');
      wrap.className = 'field mt-3';
      const caption = document.createElement('span');
      caption.className = 'label';
      caption.textContent = spec.label;
      const input = document.createElement('input');
      input.className = 'input';
      input.name = spec.name;
      input.type = spec.type || 'text';
      input.value = spec.value || '';
      input.required = spec.required !== false;
      input.maxLength = 200;
      if (input.type === 'number') { input.min = '0'; input.step = 'any'; }
      wrap.append(caption, input);
      form.appendChild(wrap);
    });

    const actions = document.createElement('div');
    actions.className = 'confirm-actions';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'btn btn-secondary';
    cancel.textContent = 'Bekor qilish';
    const ok = document.createElement('button');
    ok.type = 'submit';
    ok.className = 'btn btn-primary';
    ok.textContent = label || 'Saqlash';
    actions.append(cancel, ok);
    form.appendChild(actions);
    dialog.appendChild(form);

    const close = (answer) => { dialog.close(); dialog.remove(); resolve(answer); };
    cancel.addEventListener('click', () => close(null));
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); close(null); });
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      close(Object.fromEntries(new FormData(form)));
    });
    document.body.appendChild(dialog);
    dialog.showModal();
    const first = form.querySelector('input');
    if (first) first.focus();
  });

  document.body.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-form]');
    if (!trigger || trigger.formValues) return;
    event.preventDefault();
    event.stopPropagation();
    askForm(trigger.dataset.formTitle, JSON.parse(trigger.dataset.form), trigger.dataset.formLabel)
      .then((values) => {
        if (!values) return;
        trigger.formValues = values;
        trigger.click();
        delete trigger.formValues;
      });
  }, true);

  document.body.addEventListener('htmx:configRequest', (event) => {
    const values = event.detail.elt.formValues;
    if (!values) return;
    Object.keys(values).forEach((key) => { event.detail.parameters[key] = values[key]; });
  });

  /* --- 10. Mavzu: yorug' / tungi / tizimcha ----------------------------- */
  const root = document.documentElement;
  const darkMedia = window.matchMedia('(prefers-color-scheme: dark)');

  const paintCharts = () => {
    if (!window.Chart) return;
    const styles = getComputedStyle(root);
    window.Chart.defaults.color = styles.getPropertyValue('--color-content-muted').trim();
    window.Chart.defaults.borderColor = styles.getPropertyValue('--color-line').trim();
    Object.values(window.Chart.instances || {}).forEach((chart) => chart.update());
  };

  const applyTheme = (choice, animate) => {
    const dark = choice === 'dark' || (choice === 'system' && darkMedia.matches);
    const paint = () => {
      root.setAttribute('data-theme', dark ? 'dark' : 'light');
      root.setAttribute('data-theme-choice', choice);
      const meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute('content', dark ? '#0b1312' : '#0f524a');
      paintCharts();
    };
    if (animate && !reducedMotion && document.startViewTransition) document.startViewTransition(paint);
    else paint();
  };

  applyTheme(root.getAttribute('data-theme-choice') || 'system');
  darkMedia.addEventListener('change', () => {
    if (root.getAttribute('data-theme-choice') === 'system') applyTheme('system', true);
  });
  window.addEventListener('storage', (event) => {
    if (event.key === 'xiu-theme') applyTheme(event.newValue || 'system');
  });

  const remember = (key, value) => {
    try { window.localStorage.setItem(key, value); } catch (e) { /* saqlanmasa ham ishlaydi */ }
  };

  document.addEventListener('click', (event) => {
    const theme = event.target.closest('[data-theme-set]');
    if (theme) {
      remember('xiu-theme', theme.dataset.themeSet);
      applyTheme(theme.dataset.themeSet, true);
    }
    /* --- 11. Katalog ko'rinishi: to'r / ro'yxat --- */
    const view = event.target.closest('[data-view-set]');
    if (view) {
      remember('xiu-view', view.dataset.viewSet);
      root.setAttribute('data-view', view.dataset.viewSet);
    }
  });

  /* --- 12. Yuqoriga qaytish -------------------------------------------- */
  const toTop = document.querySelector('[data-to-top]');
  if (toTop) {
    const sync = () => toTop.classList.toggle('show', window.scrollY > 700);
    window.addEventListener('scroll', sync, { passive: true });
    toTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' }));
    sync();
  }
})();
