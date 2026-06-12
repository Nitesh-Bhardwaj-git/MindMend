(function() {
  const chartLabels = window.MOOD_TRACKER_DATA ? (window.MOOD_TRACKER_DATA.labels || []) : [];
  const chartData = window.MOOD_TRACKER_DATA ? (window.MOOD_TRACKER_DATA.data || []) : [];

  const ctx = document.getElementById('moodChart');
  if (ctx) {
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: chartLabels,
        datasets: [{
          data: chartData,
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
        plugins: { legend: { display: false }},
        scales: {
          x: {
            ticks: { color: '#6b7280', font: { size: 10 }},
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

  /* Activity Chips */
  const moodInputs = document.querySelectorAll('.mood-input');
  const energyInputs = document.querySelectorAll('.energy-input');

  function syncMood() {
    moodInputs.forEach(input => {
      const card = input.nextElementSibling;
      if (!card) return;
      if (input.checked) {
        card.classList.add('border-[#00d1b2]', 'bg-[#00d1b2]/10');
      } else {
        card.classList.remove('border-[#00d1b2]', 'bg-[#00d1b2]/10');
      }
    });
  }

  function syncEnergy() {
    energyInputs.forEach(input => {
      const pill = input.nextElementSibling;
      if (!pill) return;
      if (input.checked) {
        pill.classList.add('bg-[#00d1b2]/20', 'text-white', 'border', 'border-[#00d1b2]/40');
      } else {
        pill.classList.remove('bg-[#00d1b2]/20', 'text-white', 'border', 'border-[#00d1b2]/40');
      }
    });
  }

  moodInputs.forEach(input => input.addEventListener('change', syncMood));
  energyInputs.forEach(input => input.addEventListener('change', syncEnergy));
  syncMood();
  syncEnergy();

  const chips = document.querySelectorAll('.activity-chip');
  const input = document.querySelector('[name="activities"]');
  if (!chips.length || !input) return;

  function parseValues() {
    return (input.value || '')
      .split(',')
      .map(v => v.trim().toLowerCase())
      .filter(Boolean);
  }

  function syncState() {
    const selected = new Set(parseValues());
    chips.forEach(chip => {
      const value = (chip.dataset.value || '').toLowerCase();
      chip.classList.toggle('bg-[#00d1b2]/10', selected.has(value));
      chip.classList.toggle('text-[#00d1b2]', selected.has(value));
      chip.classList.toggle('border-[#00d1b2]', selected.has(value));
    });
  }

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const value = (chip.dataset.value || '').toLowerCase();
      const values = parseValues();
      const idx = values.indexOf(value);
      if (idx >= 0) values.splice(idx, 1);
      else {
        if (values.length >= 3) {
          alert("You can select up to 3 activities at once.");
          return;
        }
        values.push(value);
      }
      input.value = values.join(', ');
      syncState();
    });
  });

  input.addEventListener('input', syncState);
  syncState();
})();
