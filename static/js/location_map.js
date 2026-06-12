(function() {
    // ================= BACKEND DATA =================
    const markers = window.LOCATION_DATA ? (window.LOCATION_DATA.markers || []) : [];

    // ================= MAP =================
    const map = L.map('map').setView([20.5937, 78.9629], 4);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap'
    }).addTo(map);

    // ================= STORE MARKERS =================
    let leafletMarkers = [];

    // ================= ADD USER MARKERS =================
    markers.forEach(m => {
        if (m.lat && m.lon) {

            const marker = L.marker([m.lat, m.lon]).addTo(map)
            .bindPopup(`
                <div class="text-black">
                    <b>${m.label || "User"}</b><br>
                    ${m.user || "Anonymous"}<br>
                    ${m.date || ""}<br>
                    ${m.page || ""}<br>
                    ${m.source === 'browser' ? '📍 GPS' : 'IP'}
                </div>
            `);

            leafletMarkers.push({
                marker: marker,
                state: m.state
            });
        }
    });

    // ================= AUTO FIT =================
    if (leafletMarkers.length > 0) {
        const bounds = L.latLngBounds(
            leafletMarkers.map(m => m.marker.getLatLng())
        );
        map.fitBounds(bounds.pad(0.2));
    }

    // ================= FOCUS STATE =================
    window.focusState = function(state) {
        const filtered = leafletMarkers.filter(m => m.state === state);

        if (filtered.length === 0) return;

        const bounds = L.latLngBounds(
            filtered.map(m => m.marker.getLatLng())
        );

        map.fitBounds(bounds.pad(0.3));
    };
})();
