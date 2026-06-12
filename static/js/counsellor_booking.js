(function () {
  // ── Counsellor availability data from server ────────────────────────────
  const COUNSELLORS = window.COUNSELLORS_DATA || [];
  const SESSION_MIN = 30;

  const counsellorSel = document.getElementById('id_counsellor');
  const dateSel       = document.getElementById('id_date');
  const hiddenTime    = document.getElementById('id_time_slot');
  const slotGrid      = document.getElementById('slotGrid');
  const submitBtn     = document.getElementById('submitBtn');
  const slotHint      = document.getElementById('slotHint');

  const includeChat   = document.getElementById('id_include_chat');
  const includeVideo  = document.getElementById('id_include_video');

  let selectedSlot    = hiddenTime ? (hiddenTime.value || '') : '';   // preserve on re-render after error
  let bookedStartTimes = new Set();               // "HH:MM" strings

  // ── Helpers ────────────────────────────────────────────────────────────
  function getCounsellorData(id) {
    return COUNSELLORS.find(c => String(c.id) === String(id)) || null;
  }

  function timeToMinutes(hhmm) {
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + m;
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

    // Enable submit
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.title = '';
    }
    if (slotHint) {
      slotHint.textContent = `✅ Selected: ${slot} – ${minutesToHHMM(timeToMinutes(slot) + SESSION_MIN)}`;
      slotHint.className = 'text-sm text-center text-[#00d1b2] mt-4 tracking-wide font-semibold';
    }

    // Re-style all buttons
    if (slotGrid) {
      slotGrid.querySelectorAll('button[data-slot]').forEach(btn => {
        applySlotStyle(btn, btn.dataset.slot);
      });
    }
  }

  function deselectSlot(slot) {
    // Only deselect if this slot is currently selected
    if (selectedSlot !== slot) return;
    selectedSlot = '';
    if (hiddenTime) hiddenTime.value = '';

    // Disable submit & reset hint
    disableSubmit();

    // Re-style all buttons so the slot loses its highlight
    if (slotGrid) {
      slotGrid.querySelectorAll('button[data-slot]').forEach(btn => {
        applySlotStyle(btn, btn.dataset.slot);
      });
    }
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

  // ── Instant booking button validation (no slot grid needed) ───────────
  function validateInstantBooking() {
    if (!submitBtn) return;
    const cId = counsellorSel ? counsellorSel.value : null;
    const chatChecked  = includeChat  ? includeChat.checked  : false;
    const videoChecked = includeVideo ? includeVideo.checked : false;
    if (cId && (chatChecked || videoChecked)) {
      submitBtn.disabled = false;
      submitBtn.title = '';
    } else {
      submitBtn.disabled = true;
      submitBtn.title = cId ? 'Please select at least one session format' : 'Please select a counsellor';
    }
  }

  // ── Fetch booked slots & rebuild grid ──────────────────────────────────
  function refresh() {

    const cId  = counsellorSel ? counsellorSel.value : null;
    const date = dateSel ? dateSel.value : null;
    const cData = getCounsellorData(cId);

    if (!slotGrid) {
      // Instant booking page — no time slot needed, validate counsellor + format
      validateInstantBooking();
      return;
    }

    if (!cId || !date || !cData) {
      slotGrid.innerHTML = '<p class="text-sm text-gray-500 italic">Select a counsellor and date to see available time slots.</p>';
      disableSubmit();
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

      // If a slot was previously selected (e.g. after form error), re-validate it
      if (selectedSlot) {
        if (bookedStartTimes.has(selectedSlot) || !allSlots.includes(selectedSlot)) {
          selectedSlot = '';
          if (hiddenTime) hiddenTime.value = '';
          disableSubmit();
        } else {
          selectSlot(selectedSlot);
        }
      }
    })
    .catch(() => {
      slotGrid.innerHTML = '<p class="text-sm text-red-400">Could not load slots. Please try again.</p>';
    });
  }

  function disableSubmit() {
    if (!submitBtn) return;
    submitBtn.disabled = true;
    submitBtn.title = 'Please select a time slot first';
    if (slotHint) {
      slotHint.textContent = 'Select a time slot above to continue.';
      slotHint.className = 'text-sm text-center text-gray-500 mt-4 tracking-wide';
    }
  }

  // ── Events ─────────────────────────────────────────────────────────────
  if (counsellorSel) counsellorSel.addEventListener('change', () => {
    selectedSlot = '';
    if (hiddenTime) hiddenTime.value = '';
    if (slotGrid) disableSubmit();
    refresh();
  });
  if (dateSel) dateSel.addEventListener('change', () => {
    selectedSlot = '';
    if (hiddenTime) hiddenTime.value = '';
    if (slotGrid) disableSubmit();
    refresh();
  });

  // Instant booking: re-validate when session format checkboxes change
  if (!slotGrid) {
    if (includeChat)  includeChat.addEventListener('change',  validateInstantBooking);
    if (includeVideo) includeVideo.addEventListener('change', validateInstantBooking);
  }

  // On page load — trigger if values are prefilled
  if (!slotGrid) {
    // Instant booking page: validate button state immediately
    validateInstantBooking();
  } else if (counsellorSel && counsellorSel.value) {
    if (dateSel && dateSel.value) {
      refresh();
    }
  }
})();
