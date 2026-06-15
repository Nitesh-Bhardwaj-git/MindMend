(function () {
  // ── Counsellor availability data from server ────────────────────────────
  const COUNSELLORS = window.COUNSELLORS_DATA || [];
  const SESSION_MIN = 30;

  const counsellorSel = document.getElementById('id_counsellor');
  const dateSel       = document.getElementById('id_date');
  const hiddenTime    = document.getElementById('id_time_slot');
  const slotGrid      = document.getElementById('slotGrid');
  const submitBtn     = document.getElementById('submitBtn');
  const bookingForm   = document.getElementById('bookingForm');

  const includeChat   = document.getElementById('id_include_chat');
  const includeVideo  = document.getElementById('id_include_video');

  let selectedSlot    = hiddenTime ? (hiddenTime.value || '') : '';
  let bookedStartTimes = new Set();

  // ── Inline validation toast ─────────────────────────────────────────────
  function showValidationError(msg) {
    // Remove any existing error
    const existing = document.getElementById('bookingValidationError');
    if (existing) existing.remove();

    const el = document.createElement('div');
    el.id = 'bookingValidationError';
    el.style.cssText = 'animation: fadeInUp .25s ease both;';
    el.className = [
      'flex items-start gap-3 mt-4 px-5 py-4 rounded-2xl',
      'bg-red-500/10 border border-red-500/30 text-red-300 text-sm font-medium',
    ].join(' ');
    el.innerHTML = `
      <span class="text-lg leading-none mt-0.5 shrink-0">⚠️</span>
      <span>${msg}</span>`;

    // Insert after the submit button's parent div
    const btnWrap = submitBtn ? submitBtn.parentElement : null;
    if (btnWrap && btnWrap.parentElement) {
      btnWrap.parentElement.insertBefore(el, btnWrap.nextSibling);
    } else if (bookingForm) {
      bookingForm.appendChild(el);
    }

    // Auto-dismiss after 4s
    setTimeout(function () { if (el.parentElement) el.remove(); }, 4000);

    // Scroll into view
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function clearValidationError() {
    const el = document.getElementById('bookingValidationError');
    if (el) el.remove();
  }

  // ── Client-side form validation on submit ───────────────────────────────
  function validateOnSubmit(e) {
    const isInstant = !slotGrid; // instant booking has no slot grid

    const cId = counsellorSel ? counsellorSel.value : null;
    const chatChecked  = includeChat  ? includeChat.checked  : false;
    const videoChecked = includeVideo ? includeVideo.checked : false;
    const timeChosen   = hiddenTime   ? hiddenTime.value     : '';

    // Build list of problems
    const errors = [];

    if (!cId) errors.push('Please select a counsellor.');
    if (!isInstant && !dateSel?.value) errors.push('Please select a date.');
    if (!isInstant && !timeChosen) errors.push('Please select an available time slot.');
    if (!chatChecked && !videoChecked) errors.push('Please select at least one session format (Chat or Video).');

    if (errors.length) {
      e.preventDefault();
      showValidationError(errors.join('<br>'));
      return false;
    }

    clearValidationError();
    return true;
  }

  if (bookingForm) {
    bookingForm.addEventListener('submit', validateOnSubmit);
  }

  // Clear error when user starts filling the form
  [counsellorSel, dateSel, includeChat, includeVideo].forEach(function (el) {
    if (el) el.addEventListener('change', clearValidationError);
  });

  // ── Helpers ────────────────────────────────────────────────────────────
  function getCounsellorData(id) {
    return COUNSELLORS.find(c => String(c.id) === String(id)) || null;
  }

  function timeToMinutes(hhmm) {
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + m;
  }

  function minutesToHHMM(mins) {
    const h = String(Math.floor(mins / 60)).padStart(2, '0');
    const m = String(mins % 60).padStart(2, '0');
    return `${h}:${m}`;
  }

  function generateSlots(start, end) {
    const slots = [];
    let cur = timeToMinutes(start);
    const endMin = timeToMinutes(end);
    while (cur + SESSION_MIN <= endMin) {
      slots.push(minutesToHHMM(cur));
      cur += SESSION_MIN;
    }
    return slots;
  }

  // ── Render slot grid ────────────────────────────────────────────────────
  function renderSlots(slots) {
    if (!slotGrid) return;
    if (!slots.length) {
      slotGrid.innerHTML = '<p class="text-sm text-gray-500 italic">No slots available for this counsellor\'s hours.</p>';
      return;
    }

    slotGrid.innerHTML = '';
    const grid = document.createElement('div');
    grid.className = 'grid grid-cols-3 sm:grid-cols-4 gap-2';

    slots.forEach(slot => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.dataset.slot = slot;
      btn.textContent = slot;
      applySlotStyle(btn, slot);
      btn.addEventListener('click', () => selectSlot(slot));
      btn.addEventListener('dblclick', () => deselectSlot(slot));
      grid.appendChild(btn);
    });

    slotGrid.appendChild(grid);
  }

  function applySlotStyle(btn, slot) {
    const isBooked   = bookedStartTimes.has(slot);
    const isSelected = slot === selectedSlot;

    btn.disabled = isBooked;
    btn.className = [
      'px-3 py-2.5 rounded-xl text-sm font-bold transition-all focus:outline-none',
      isBooked
        ? 'bg-red-500/10 text-red-400 border border-red-500/30 line-through cursor-not-allowed opacity-60'
        : isSelected
          ? 'bg-[#00d1b2] text-black border border-[#00d1b2] ring-2 ring-[#00d1b2]/40 scale-105'
          : 'bg-white/5 text-white border border-white/10 hover:bg-[#00d1b2]/20 hover:border-[#00d1b2]/40 cursor-pointer'
    ].join(' ');
  }

  function selectSlot(slot) {
    selectedSlot = slot;
    if (hiddenTime) hiddenTime.value = slot;
    clearValidationError();

    if (slotGrid) {
      slotGrid.querySelectorAll('button[data-slot]').forEach(btn => {
        applySlotStyle(btn, btn.dataset.slot);
      });
    }
  }

  function deselectSlot(slot) {
    if (selectedSlot !== slot) return;
    selectedSlot = '';
    if (hiddenTime) hiddenTime.value = '';

    if (slotGrid) {
      slotGrid.querySelectorAll('button[data-slot]').forEach(btn => {
        applySlotStyle(btn, btn.dataset.slot);
      });
    }
  }

  // ── Fetch booked slots & rebuild grid ──────────────────────────────────
  function refresh() {
    const cId   = counsellorSel ? counsellorSel.value : null;
    const date  = dateSel ? dateSel.value : null;
    const cData = getCounsellorData(cId);

    if (!slotGrid) return; // instant booking — no slot grid

    if (!cId || !date || !cData) {
      slotGrid.innerHTML = '<p class="text-sm text-gray-500 italic">Select a counsellor and date to see available time slots.</p>';
      return;
    }

    slotGrid.innerHTML = '<p class="text-sm text-gray-400 animate-pulse">Loading slots…</p>';

    fetch(`/api/counsellor/${cId}/booked-slots/?date=${date}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
      bookedStartTimes = new Set((data.booked_slots || []).map(s => s.start));
      const allSlots = generateSlots(cData.start, cData.end);
      renderSlots(allSlots);

      if (selectedSlot) {
        if (bookedStartTimes.has(selectedSlot) || !allSlots.includes(selectedSlot)) {
          selectedSlot = '';
          if (hiddenTime) hiddenTime.value = '';
        } else {
          selectSlot(selectedSlot);
        }
      }
    })
    .catch(() => {
      slotGrid.innerHTML = '<p class="text-sm text-red-400">Could not load slots. Please try again.</p>';
    });
  }

  // ── Events ─────────────────────────────────────────────────────────────
  if (counsellorSel) counsellorSel.addEventListener('change', () => {
    selectedSlot = '';
    if (hiddenTime) hiddenTime.value = '';
    refresh();
  });

  if (dateSel) dateSel.addEventListener('change', () => {
    selectedSlot = '';
    if (hiddenTime) hiddenTime.value = '';
    refresh();
  });

  // On page load — trigger slot grid if counsellor + date are prefilled
  if (slotGrid && counsellorSel && counsellorSel.value) {
    if (dateSel && dateSel.value) {
      refresh();
    }
  }

})();
