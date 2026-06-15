(function () {
  'use strict';

  // ── Config ────────────────────────────────────────────────────────────────
  const CFG = window.MOOD_TRACKER_DATA || {};
  const MOOD_LABELS = ['', '😢 Very Low', '😔 Low', '😐 Neutral', '🙂 Good', '😊 Great'];
  const MOOD_COLORS = ['', '#ef4444', '#f97316', '#eab308', '#22c55e', '#00d1b2'];

  // ── Inline Toast (replaces browser alert) ─────────────────────────────────
  function showToast(msg, type) {
    type = type || 'info';
    var colors = {
      info:    'bg-[#00d1b2]/10 border-[#00d1b2]/30 text-[#00d1b2]',
      warning: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-300',
      error:   'bg-red-500/10 border-red-500/30 text-red-400',
      success: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    };
    var t = document.createElement('div');
    t.className = 'mm-toast fixed bottom-6 right-6 z-[9999] px-5 py-3.5 rounded-2xl border text-sm font-medium shadow-2xl ' + (colors[type] || colors.info);
    t.style.backdropFilter = 'blur(12px)';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () {
      t.style.animation = 'toastOut .3s ease forwards';
      setTimeout(function () { t.remove(); }, 300);
    }, 3200);
  }

  // ── Mood Ring Animation ───────────────────────────────────────────────────
  (function animateMoodRing() {
    var arc = document.getElementById('moodRingArc');
    if (!arc || !CFG.avgMood) return;
    var pct = CFG.avgMood / 5;
    var circumference = 2 * Math.PI * 22; // r=22
    var dash = Math.round(pct * circumference * 10) / 10;
    setTimeout(function () {
      arc.setAttribute('stroke-dasharray', dash + ' ' + circumference);
    }, 300);
  })();

  // ── Chart ─────────────────────────────────────────────────────────────────
  var moodChart = null;
  var currentPeriod = 7;

  function buildGradient(ctx) {
    var gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(0,209,178,0.38)');
    gradient.addColorStop(0.6, 'rgba(0,209,178,0.08)');
    gradient.addColorStop(1, 'rgba(0,209,178,0.00)');
    return gradient;
  }

  function getChartDataset(period) {
    var key = 'chart' + period;
    var d = CFG[key] || CFG.chart7 || { labels: [], data: [] };
    return { labels: d.labels, data: d.data };
  }

  function initChart() {
    var canvas = document.getElementById('moodChart');
    var emptyMsg = document.getElementById('chartEmpty');
    if (!canvas) return;

    var d = getChartDataset(7);
    if (!d.data.length) {
      if (emptyMsg) emptyMsg.classList.remove('hidden');
      return;
    }

    var ctx = canvas.getContext('2d');
    var gradient = buildGradient(ctx);

    moodChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: d.labels,
        datasets: [{
          data: d.data,
          borderColor: '#00d1b2',
          backgroundColor: gradient,
          borderWidth: 2.5,
          pointBackgroundColor: d.data.map(function (v) { return MOOD_COLORS[v] || '#00d1b2'; }),
          pointBorderColor: '#050b1a',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointHoverBackgroundColor: '#00d1b2',
          fill: true,
          tension: 0.45,
          spanGaps: true,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 900,
          easing: 'easeInOutQuart',
        },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0a1428',
            borderColor: 'rgba(0,209,178,0.3)',
            borderWidth: 1,
            titleColor: '#00d1b2',
            bodyColor: '#fff',
            padding: 12,
            cornerRadius: 14,
            displayColors: false,
            callbacks: {
              label: function (ctx) {
                var v = ctx.raw;
                return ' ' + (MOOD_LABELS[v] || ('Mood ' + v));
              }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              color: '#6b7280',
              font: { size: 10 },
              maxRotation: 45,
              maxTicksLimit: 10,
            },
            grid: { display: false },
            border: { display: false },
          },
          y: {
            min: 0.5,
            max: 5.5,
            ticks: {
              color: '#6b7280',
              stepSize: 1,
              callback: function (v) {
                var map = { 1: '😢', 2: '😔', 3: '😐', 4: '🙂', 5: '😊' };
                return map[v] || '';
              }
            },
            grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
            border: { display: false },
          }
        }
      }
    });
  }

  function switchChartPeriod(period) {
    if (!moodChart) return;
    var d = getChartDataset(period);
    var emptyMsg = document.getElementById('chartEmpty');

    if (!d.data.length) {
      if (emptyMsg) emptyMsg.classList.remove('hidden');
      moodChart.data.labels = [];
      moodChart.data.datasets[0].data = [];
      moodChart.update();
      return;
    }
    if (emptyMsg) emptyMsg.classList.add('hidden');

    var ctx = moodChart.ctx;
    moodChart.data.labels = d.labels;
    moodChart.data.datasets[0].data = d.data;
    moodChart.data.datasets[0].backgroundColor = buildGradient(ctx);
    moodChart.data.datasets[0].pointBackgroundColor = d.data.map(function (v) { return MOOD_COLORS[v] || '#00d1b2'; });
    moodChart.update('active');
  }

  // Chart period tabs
  document.querySelectorAll('.chart-tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var period = parseInt(this.dataset.period, 10);
      currentPeriod = period;
      document.querySelectorAll('.chart-tab').forEach(function (b) { b.classList.remove('active'); });
      this.classList.add('active');
      switchChartPeriod(period);
    });
  });

  initChart();

  // ── Mood Card Selection ───────────────────────────────────────────────────
  var moodInputs = document.querySelectorAll('.mood-input');

  function syncMoodCards() {
    moodInputs.forEach(function (input) {
      var card = input.nextElementSibling;
      if (!card) return;
      if (input.checked) {
        card.classList.add('mood-card-selected');
      } else {
        card.classList.remove('mood-card-selected');
      }
    });
  }

  moodInputs.forEach(function (input) {
    input.addEventListener('change', function () {
      var card = this.nextElementSibling;
      if (card) {
        card.classList.add('mood-bounce');
        card.addEventListener('animationend', function () {
          card.classList.remove('mood-bounce');
        }, { once: true });
      }
      syncMoodCards();
    });
  });
  syncMoodCards();

  // ── Energy Pills ──────────────────────────────────────────────────────────
  var energyInputs = document.querySelectorAll('.energy-input');

  function syncEnergyPills() {
    energyInputs.forEach(function (input) {
      var pill = input.nextElementSibling;
      if (!pill) return;
      if (input.checked) {
        pill.classList.add('energy-pill-selected');
      } else {
        pill.classList.remove('energy-pill-selected');
      }
    });
  }

  energyInputs.forEach(function (input) {
    input.addEventListener('change', syncEnergyPills);
  });
  syncEnergyPills();

  // ── Activity Chips ────────────────────────────────────────────────────────
  var chips     = document.querySelectorAll('.activity-chip');
  var actInput  = document.getElementById('activitiesInput');

  function parseValues() {
    return (actInput ? actInput.value : '')
      .split(',')
      .map(function (v) { return v.trim().toLowerCase(); })
      .filter(Boolean);
  }

  function syncChips() {
    var selected = new Set(parseValues());
    chips.forEach(function (chip) {
      var val = (chip.dataset.value || '').toLowerCase();
      if (selected.has(val)) {
        chip.classList.add('activity-chip-selected');
      } else {
        chip.classList.remove('activity-chip-selected');
      }
    });
  }

  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      var val = (this.dataset.value || '').toLowerCase();
      var values = parseValues();
      var idx = values.indexOf(val);
      if (idx >= 0) {
        values.splice(idx, 1);
      } else {
        if (values.length >= 3) {
          showToast('You can select up to 3 activities.', 'warning');
          return;
        }
        values.push(val);
      }
      if (actInput) actInput.value = values.join(', ');
      syncChips();
    });
  });

  syncChips();

  // ── Notes Character Counter ───────────────────────────────────────────────
  var notesField   = document.querySelector('[name="notes"]');
  var notesCounter = document.getElementById('notesCounter');

  if (notesField && notesCounter) {
    function updateCounter() {
      var len = notesField.value.length;
      notesCounter.textContent = len + ' / 300';
      notesCounter.style.color = len > 270 ? '#f97316' : '';
    }
    notesField.addEventListener('input', updateCounter);
    updateCounter();
  }

  // ── Save Button Loading State ─────────────────────────────────────────────
  var form       = document.getElementById('moodForm');
  var saveBtn    = document.getElementById('saveBtn');
  var saveBtnTxt = document.getElementById('saveBtnText');
  var saveBtnIco = document.getElementById('saveBtnIcon');

  if (form && saveBtn) {
    form.addEventListener('submit', function () {
      saveBtn.disabled = true;
      saveBtn.classList.remove('btn-shimmer');
      saveBtn.style.background = 'rgba(0,209,178,0.6)';
      if (saveBtnIco) saveBtnIco.textContent = '⟳';
      if (saveBtnTxt) saveBtnTxt.textContent = 'Saving…';
    });
  }

})();
