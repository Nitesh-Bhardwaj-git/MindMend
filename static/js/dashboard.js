(function() {
  const dataEl = document.getElementById('mood-trend-data');
  const data = dataEl ? JSON.parse(dataEl.textContent || "[]") : [];

  const labels = data.map(d => d.date);
  const values = data.map(d => d.mood);
  const chartEl = document.getElementById('mood-trend-chart');

  if (chartEl) {
    new Chart(chartEl, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          borderColor: '#00d1b2',
          backgroundColor: 'rgba(0, 209, 178, 0.1)',
          borderWidth: 3,
          pointBackgroundColor: '#fff',
          pointBorderColor: '#00d1b2',
          pointRadius: 4,
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: { color: '#6b7280', font: { size: 10 } },
            grid: { display: false }
          },
          y: {
            min: 1,
            max: 5,
            ticks: { color: '#6b7280', stepSize: 1 },
            grid: { color: 'rgba(255,255,255,0.05)' }
          }
        }
      }
    });
  }
})();

(function () {
    const trendDataNode = document.getElementById('trend-charts-data');
    const trendData = trendDataNode ? JSON.parse(trendDataNode.textContent || '{}') : {};

    const slider = document.getElementById('trend-slider');
    const modeBtn = document.getElementById('trend-mode-btn');
    const modeMenu = document.getElementById('trend-mode-menu');
    const startEl = document.getElementById('window-start');
    const endEl = document.getElementById('window-end');
    if (!slider || !modeBtn || !modeMenu) return;

    const state = {
        mode: 'daily',
        windowByMode: { daily: 30, weekly: 16, monthly: 12 }
    };

    function carryForward(values) {
        const out = [];
        let lastSeen = null;
        for (let i = 0; i < values.length; i++) {
            const v = values[i];
            if (v === null || typeof v === 'undefined') out.push(lastSeen);
            else { lastSeen = Number(v); out.push(lastSeen); }
        }
        return out;
    }

    function draw(canvasId, color, minY, maxY) {
        const el = document.getElementById(canvasId);
        if (!el) return null;
        return new Chart(el, {
            type: 'line',
            data: { labels: [], datasets: [{ data: [], borderColor: color, fill: false, spanGaps: true, tension: 0.35, pointRadius: 0, pointHoverRadius: 0 }] },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { title: { display: true, text: 'Date, Month' } }, y: { beginAtZero: true, min: minY, max: maxY } }
            }
        });
    }

    const charts = {
        phq9: draw('chart-phq9', '#2563eb', 0, 27),
        gad7: draw('chart-gad7', '#7c3aed', 0, 21),
        pss: draw('chart-pss', '#ea580c', 0, 30),
        mood: draw('chart-mood', '#059669', 1, 5)
    };

    function modeLabel(mode) { return mode === 'weekly' ? 'Weekly Trend' : mode === 'monthly' ? 'Monthly Trend' : 'Daily Trend'; }
    function updateTitles() {
        const suffix = modeLabel(state.mode);
        ['title-phq9','title-gad7','title-pss','title-mood'].forEach(id => {
            const el = document.getElementById(id);
            if(el) el.textContent = el.textContent.split(' ')[0] + ' ' + suffix;
        });
    }

    function getModeData(mode) {
        const md = trendData[mode] || {};
        return { labels: md.labels||[], phq9: md.phq9||[], gad7: md.gad7||[], pss: md.pss||[], mood: md.mood||[] };
    }

    function updateSliderBounds() {
        const md = getModeData(state.mode);
        const total = md.labels.length;
        const windowSize = Math.min(state.windowByMode[state.mode] || total, total);
        slider.max = String(Math.max(0, total - windowSize));
        slider.value = slider.max;
    }

    function updateCharts() {
        const md = getModeData(state.mode);
        const total = md.labels.length;
        const windowSize = Math.min(state.windowByMode[state.mode] || total, total);
        const start = Math.min(parseInt(slider.value||'0',10), Math.max(0,total-windowSize));
        const end = Math.min(total,start+windowSize);
        const labels = md.labels.slice(start,end);
        if(startEl) startEl.textContent = labels[0]||'-';
        if(endEl) endEl.textContent = labels[labels.length-1]||'-';

        const series = { phq9: carryForward(md.phq9).slice(start,end), gad7: carryForward(md.gad7).slice(start,end),
                         pss: carryForward(md.pss).slice(start,end), mood: carryForward(md.mood).slice(start,end) };

        Object.keys(charts).forEach(metric => {
            const c = charts[metric];
            if(!c) return;
            c.data.labels = labels;
            c.data.datasets[0].data = series[metric];
            c.update();
        });
    }

    modeBtn.addEventListener('click',()=>modeMenu.classList.toggle('hidden'));
    document.addEventListener('click',e=>{if(!modeMenu.contains(e.target) && e.target!==modeBtn) modeMenu.classList.add('hidden');});
    modeMenu.querySelectorAll('[data-mode]').forEach(item=>{
        item.addEventListener('click',()=>{
            state.mode = item.getAttribute('data-mode')||'daily';
            modeBtn.textContent = modeLabel(state.mode) + ' ⌄';
            modeMenu.classList.add('hidden');
            updateSliderBounds();
            updateTitles();
            updateCharts();
        });
    });

    slider.addEventListener('input',updateCharts);

    updateSliderBounds();
    updateTitles();
    updateCharts();
})();
