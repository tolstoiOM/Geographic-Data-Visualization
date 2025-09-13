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
const geojsonUpload = document.getElementById('geojson-upload');
geojsonUpload.addEventListener('change', function(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(evt) {
    try {
      const geojson = JSON.parse(evt.target.result);
      const layer = L.geoJSON(geojson, {
        style: function(feature) {
          if (feature.properties && feature.properties.typ === 'Wohngebiet') {
            return { color: 'blue', fillColor: 'blue', fillOpacity: 0.5 };
          }
          if (feature.properties && feature.properties.typ === 'Parkgebiet') {
            return { color: 'green', fillColor: 'green', fillOpacity: 0.5 };
          }
          return { color: 'gray', fillOpacity: 0.3 };
        },
        onEachFeature: function (feature, layer) {
          if (feature.properties && feature.properties.name) {
            layer.bindPopup(feature.properties.name);
          }
        }
      }).addTo(map);
      map.fitBounds(layer.getBounds());
    } catch (err) {
      alert('Ungültige GeoJSON-Datei!');
    }
  };
  reader.readAsText(file);
});
