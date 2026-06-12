(function() {
  const markers = window.HEATMAP_DATA.markers || [];
  const metric = window.HEATMAP_DATA.metric || 'mood';

  function getColor(m) {
    if (metric === 'mood') {
      if (m.avg_mood == null) return '#9ca3af';
      if (m.avg_mood <= 2) return '#ef4444';
      if (m.avg_mood <= 3) return '#f59e0b';
      return '#22c55e';
    }

    if (metric === 'stress') {
      if (m.avg_pss == null) return '#9ca3af';
      if (m.avg_pss >= 15) return '#ef4444';
      if (m.avg_pss >= 11) return '#f59e0b';
      return '#22c55e';
    }

    if (metric === 'depression') {
      if (m.avg_phq9 == null) return '#9ca3af';
      if (m.avg_phq9 >= 15) return '#ef4444';
      if (m.avg_phq9 >= 10) return '#f59e0b';
      return '#22c55e';
    }

    return '#6b7280';
  }

  const map = L.map('map').setView([20.5937, 78.9629], 4);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap'
  }).addTo(map);

  markers.forEach(m => {
    if (m.lat && m.lon) {

      const popup = `
        <b>${m.label || "Unknown"}</b><br/>
        ${m.avg_mood != null ? `Mood: ${m.avg_mood}/5<br/>` : ""}
        ${m.avg_pss != null ? `Stress: ${m.avg_pss}<br/>` : ""}
        ${m.avg_phq9 != null ? `Depression: ${m.avg_phq9}<br/>` : ""}
        Sample: ${m.n || 0}
      `;

      L.circleMarker([m.lat, m.lon], {
        radius: Math.min(8 + (m.n || 1) * 2, 25),
        fillColor: getColor(m),
        color: '#111',
        weight: 1,
        fillOpacity: 0.7
      })
      .addTo(map)
      .bindPopup(popup);
    }
  });

})();
