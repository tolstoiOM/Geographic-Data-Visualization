// main.js für die Leaflet-Karte und Funktionen
const START_COORDS = [48.2082, 16.3738];
const START_ZOOM = 13;
const map = L.map('map').setView(START_COORDS, START_ZOOM);
const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende'
}).addTo(map);
const marker = L.marker(START_COORDS).addTo(map);
marker.bindPopup('<b>Wien</b><br>Willkommen auf deiner OSM-Karte.');
const locateBtn = document.getElementById('locate');
locateBtn.addEventListener('click', () => {
  if (!navigator.geolocation) {
    alert('Geolokalisierung wird von deinem Browser nicht unterstützt.');
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;
      const here = [latitude, longitude];
      map.setView(here, 15);
      L.marker(here).addTo(map).bindPopup('Du bist hier.').openPopup();
    },
    (err) => {
      console.error(err);
      alert('Konnte Standort nicht bestimmen. Erlaube Zugriff oder versuche es später erneut.');
    },
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
  );
});
const searchInput = document.getElementById('search');
const goBtn = document.getElementById('go');
async function geocode(q) {
  const url = new URL('https://nominatim.openstreetmap.org/search');
  url.searchParams.set('q', q);
  url.searchParams.set('format', 'json');
  url.searchParams.set('addressdetails', '0');
  url.searchParams.set('limit', '1');
  const res = await fetch(url, { headers: { 'Accept-Language': 'de' } });
  if (!res.ok) throw new Error('Suche fehlgeschlagen: ' + res.status);
  const data = await res.json();
  return data[0];
}
async function handleSearch() {
  const q = searchInput.value.trim();
  if (!q) return;
  try {
    const r = await geocode(q);
    if (!r) { alert('Kein Ergebnis gefunden.'); return; }
    const lat = parseFloat(r.lat), lon = parseFloat(r.lon);
    map.setView([lat, lon], 15);
    L.circleMarker([lat, lon], { radius: 8 }).addTo(map).bindPopup(r.display_name).openPopup();
  } catch (e) {
    console.error(e);
    alert('Fehler bei der Suche. Bitte später erneut versuchen.');
  }
}
goBtn.addEventListener('click', handleSearch);
searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSearch(); });
document.addEventListener('keydown', (e) => {
  if (e.key === '+') map.zoomIn();
  if (e.key === '-') map.zoomOut();
});

// Styling and popup helpers are placed in outer scope so they can be reused
function styleByProps(feature, schwarz = false) {
  const props = feature.properties || {};
  const layerName = (props.LAYER || '').toLowerCase();
  if (schwarz) {
    return { color: '#000000', fillColor: '#000000', fillOpacity: 0.85, weight: 1 };
  }
  if (layerName.includes('geb')) return { color: '#8B0000', fillColor: '#8B0000', fillOpacity: 0.6 };
  if (layerName.includes('überbauung') || layerName.includes('bau')) return { color: '#1f77b4', fillColor: '#1f77b4', fillOpacity: 0.4 };
  if (layerName.includes('flugdach')) return { color: '#ff7f0e', fillColor: '#ff7f0e', fillOpacity: 0.5 };
  if (layerName.includes('grün') || layerName.includes('park')) return { color: 'green', fillColor: 'green', fillOpacity: 0.4 };
  const klasse = props.F_KLASSE;
  if (typeof klasse === 'number') {
    if (klasse >= 13) return { color: '#6a3d9a', fillColor: '#6a3d9a', fillOpacity: 0.5 };
    if (klasse >= 11) return { color: '#b15928', fillColor: '#b15928', fillOpacity: 0.5 };
  }
  return { color: 'gray', fillOpacity: 0.3 };
}

function popupContent(props) {
  if (!props) return '';
  const lines = [];
  if (props.BEZUG) lines.push('<b>Bezug:</b> ' + props.BEZUG);
  if (props.LAYER) lines.push('<b>Layer:</b> ' + props.LAYER);
  if (props.F_KLASSE !== undefined) lines.push('<b>F_KLASSE:</b> ' + props.F_KLASSE);
  if (props.RN_NUTZUNG_LEVEL2) lines.push('<b>Nutzung:</b> ' + props.RN_NUTZUNG_LEVEL2);
  if (props.RN_FLAECHE) lines.push('<b>Fläche:</b> ' + props.RN_FLAECHE.toFixed(1) + ' m²');
  if (props.FMZK_ID) lines.push('<small>FMZK_ID: ' + props.FMZK_ID + '</small>');
  return lines.join('<br/>');
}
const geojsonUpload = document.getElementById('geojson-upload');
// Keep a reference to the last added geojson layer so we can remove it on new uploads
let currentGeoJsonLayer = null;
geojsonUpload.addEventListener('change', function(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(evt) {
    try {
      const geojson = JSON.parse(evt.target.result);
      // Basic validation
      if (!geojson.type || (geojson.type !== 'FeatureCollection' && geojson.type !== 'Feature')) {
        throw new Error('Nicht unterstützter GeoJSON-Typ');
      }

      // Remove previous layer if present
      if (currentGeoJsonLayer) {
        map.removeLayer(currentGeoJsonLayer);
        currentGeoJsonLayer = null;
      }

      // Use schwarz (black) style by default for uploaded GeoJSON (Schwarzplan)
      currentGeoJsonLayer = L.geoJSON(geojson, {
        style: function(f) { return styleByProps(f, true); },
        onEachFeature: function(feature, layer) {
          const content = popupContent(feature.properties);
          if (content) layer.bindPopup(content);
        },
        pointToLayer: function(feature, latlng) {
          return L.circleMarker(latlng, { radius: 6, fillOpacity: 0.8 });
        }
      }).addTo(map);

      // fit map to the geojson bounds if possible
      try {
        const bounds = currentGeoJsonLayer.getBounds();
        if (bounds.isValid && bounds.isValid()) {
          map.fitBounds(bounds);
        } else {
          map.setView(START_COORDS, START_ZOOM);
        }
      } catch (e) {
        // fallback
        map.setView(START_COORDS, START_ZOOM);
      }
    } catch (err) {
      console.error(err);
      alert('Ungültige GeoJSON-Datei: ' + (err.message || err));
    }
  };
  reader.readAsText(file);
});

// Note: uploaded GeoJSON is rendered in Schwarzplan (black) style by default.
