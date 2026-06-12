(function() {
  // Chart
  const labelsNode = document.getElementById('sentiment-labels');
  const seriesNode = document.getElementById('sentiment-series');
  const labels = labelsNode ? JSON.parse(labelsNode.textContent || '[]') : [];
  const series = seriesNode ? JSON.parse(seriesNode.textContent || '[]') : [];
  const palette = ['#2563eb', '#7c3aed', '#ea580c', '#059669', '#f59e0b'];

  const chartEl = document.getElementById('sentimentChart');
  if (chartEl) {
    const ctx = chartEl.getContext('2d');
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: series.map((item, idx) => ({
          label: item.name,
          data: item.data,
          borderColor: palette[idx % palette.length],
          backgroundColor: palette[idx % palette.length] + '55',
          borderWidth: 1,
          borderRadius: 8,
          maxBarThickness: 26
        }))
      },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { 
            position: window.matchMedia('(max-width:640px)').matches ? 'bottom' : 'top', 
            labels: { color: '#fff', font: { size: 10, weight: '700' }, padding: 20 } 
          },
          tooltip: { backgroundColor: '#0a1428', titleColor: '#fff', bodyColor: '#fff', cornerRadius: 16, titleFont: { weight: '700' }, bodyFont: { weight: '700' } }
        },
        scales: {
          x: { ticks: { color: '#6b7280', font: { size: 10, weight: '700' } }, grid: { drawTicks: false, color: '#ffffff0a' } },
          y: { ticks: { color: '#6b7280', font: { size: 10, weight: '700' } }, grid: { drawTicks: false, color: '#ffffff0a' }, beginAtZero: true }
        }
      }
    });
  }

  // Filters
  let activeFilters = { age: '', gender: '', occupation: '' };

  window.toggleFilterMenu = function(key) {
    const el = document.getElementById('filterMenu-' + key);
    if (el) el.classList.toggle('hidden');
  };

  window.setFilter = function(key, value) {
    activeFilters[key] = value;
    const btn = document.getElementById('filterBtn-' + key);
    if (btn) {
      btn.innerText = value || 'All ' + key.charAt(0).toUpperCase() + key.slice(1) + 's';
    }
    const menu = document.getElementById('filterMenu-' + key);
    if (menu) menu.classList.add('hidden');
  };

  window.applyFilters = function() {
    console.log('Applying filters', activeFilters);
    alert('Filters applied! See console for demo data.');
  };
})();
