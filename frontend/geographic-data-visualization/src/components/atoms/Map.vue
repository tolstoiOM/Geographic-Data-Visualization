<script setup>
import { onMounted, ref } from 'vue'
import L from 'leaflet'
import 'leaflet-draw'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw/dist/leaflet.draw.css'
import osmtogeojson from "osmtogeojson"
import 'leaflet-spin'
import {Spinner} from 'spin.js'
import 'spin.js/spin.css'

// Refs
const mapContainer = ref(null)
const query = ref('')
const START_COORDS = [48.2082, 16.3738];
const START_ZOOM = 13;
let map = null
let geoJsonLayer = null
let spinner

// 📍 Karte initialisieren
onMounted(() => {
  if (!map) {
    map = L.map(mapContainer.value).setView(START_COORDS, START_ZOOM)
  }

  // Basiskarte
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap-Mitwirkende'
  }).addTo(map)

  // 🧩 Credit-Control
  const CreditControl = L.Control.extend({
    options: { position: 'bottomright' },
    onAdd: function (map) {
      const div = L.DomUtil.create('div', 'custom-credit')
      div.innerHTML = `
        Karten-Daten ©
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" style="text-decoration: underline; color: #2563eb;">
          OpenStreetMap
        </a>
        -Mitwirkende
      `
      return div
    }

  })
  map.addControl(new CreditControl())

  // Marker setzen
  const marker = L.marker(START_COORDS).addTo(map);
  marker.bindPopup('<b>Wien</b><br>Willkommen auf deiner OSM-Karte.');

  // Draw-Toolbar auf der Karte aktivieren
  const drawnItems = new L.FeatureGroup()
  map.addLayer(drawnItems)
  const drawControl = new L.Control.Draw({
    draw: {
      polygon: true,
      rectangle: true,
      circle: true,
      marker: true,
      polyline: true,
      circlemarker: true
    },
    edit: {
      featureGroup: drawnItems
    }
  })
  map.addControl(drawControl)

// Beim Zeichnen: GeoJSON exportieren
map.on(L.Draw.Event.CREATED, async function (event) {
  const layer = event.layer
  drawnItems.addLayer(layer)
  const layer_geojson = layer.toGeoJSON()
  console.log('GeoJSON-Layer:', layer_geojson)
  const geojson = await exportGeoJSON(layer_geojson)
  console.log('GeoJSON:', geojson)

  // JSON generieren
  //const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(geojson))

  // Nutzer fragen, ob exportiert werden soll
  if (window.confirm('Möchten Sie die OSM-Objekte aus dem gezeichneten Bereich als GeoJSON exportieren?')) {
    downloadGeoJSON(geojson, 'osm_objekte.geojson')
    /*const dlAnchor = document.createElement('a')
    dlAnchor.setAttribute('href', dataStr)
    dlAnchor.setAttribute('download', 'export.geojson')
    document.body.appendChild(dlAnchor)
    dlAnchor.click()
    dlAnchor.remove()*/
  } else {
    console.log('Export abgebrochen. GeoJSON:', geojson)
  }
})

  spinner = new Spinner({
    lines: 12,
    length: 38,
    width: 10,
    radius: 45,
    scale: 4,
    corners: 1,
    speed: 1,
    rotate: 0,
    animation: 'spinner-line-shrink',
    direction: 1,
    color: '#2563eb',
    fadeColor: 'transparent',
    top: '50%',
    left: '50%',
    shadow: '0 0 1px transparent',
    zIndex: 9999,
    className: 'spinner',
    position: 'absolute',
  });
})

// 🔍 Ortssuche über Nominatim (OpenStreetMap)
let searchMarker = null
async function handleSearch() {
  if (!query.value) return
  spinner.spin(mapContainer.value); // Spinner starten
  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query.value)}`)
    const data = await res.json()
    if (data && data.length > 0) {
      const { lat, lon, display_name } = data[0]
      map.setView([lat, lon], 15)

      // Alten Marker löschen
      if (searchMarker) {
        map.removeLayer(searchMarker)
      }

      searchMarker  = L.marker([lat, lon]).addTo(map).bindPopup(display_name).openPopup()
    } else {
      alert('Ort nicht gefunden.')
    }
  } catch (err) {
    console.error('Fehler bei der Suche:', err)
  } finally {
    spinner.stop();
  }
}

// 📂 Datei-Upload (GeoJSON anzeigen)
async function handleUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  spinner.spin(mapContainer.value); // Spinner starten

  const reader = new FileReader()
  reader.onload = async (e) => {
    try {
      const geojson = JSON.parse(e.target.result)
      if (!geojson.type || (geojson.type !== 'FeatureCollection' && geojson.type !== 'Feature')) {
        throw new Error('Nicht unterstützter GeoJSON-Typ');
      } else if (geoJsonLayer) geoJsonLayer.remove()
      geoJsonLayer = L.geoJSON(geojson, {
        style: { color: '#000000', fillColor: '#000000', fillOpacity: 0.7, weight: 1 }
      }).addTo(map)
      map.fitBounds(geoJsonLayer.getBounds())

      // 🧠 Nutzer fragen, ob in DB speichern
      if (window.confirm("Möchtest du diese GeoJSON-Daten in die Datenbank speichern?")) {
        await saveGeoJSONToDB(geojson)
        alert("GeoJSON-Daten wurden an das Backend gesendet.")
      }

    } catch (err) {
      console.error('Fehler beim Lesen der Datei:', err)
      alert('Ungültige GeoJSON-Datei.')
    } finally {
      spinner.stop();
    }
  }
  reader.readAsText(file)
}

// GEOJSON-Fetch-Aufruf
async function saveGeoJSONToDB(geojson) {
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/upload-geojson`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(geojson),
    })
    if (!res.ok) {
      const msg = await res.text()
      throw new Error(msg || "Fehler beim Speichern der Daten.")
    }
  } catch (err) {
    console.error("Fehler beim Senden der GeoJSON-Daten:", err)
    alert("Fehler beim Speichern in der Datenbank.")
  }
}

// 📍 Benutzer-Standort
function handleLocate() {
  spinner.spin(mapContainer.value); // Spinner starten
  map.locate({ setView: true, maxZoom: 16 })
  map.on('locationfound', (e) => {
    L.marker(e.latlng).addTo(map).bindPopup('📍 Du bist hier').openPopup()
    spinner.stop();
  })
  map.on('locationerror', () => {
    alert('Standort konnte nicht ermittelt werden.')
    spinner.stop();
  })
}

async function exportGeoJSON(layer_geojson) {
  try {
    spinner.spin(mapContainer.value); // Spinner starten

    const coords = layer_geojson.geometry.coordinates[0]; // Array von [lng, lat] Paaren
    const polyString = coords.map(ll => `${ll[1]} ${ll[0]}`).join(' '); // Beachte: lat lng Reihenfolge für Overpass

    const overpassQuery = `
      [out:json][timeout:25];
      (
        way(poly:"${polyString}");
        node(poly:"${polyString}");
      );
      out body;
    `

    const res = await fetch("https://overpass-api.de/api/interpreter", {
      method: "POST",
      body: "data=" + encodeURIComponent(overpassQuery),
    })
    const data = await res.json()

    // In GeoJSON konvertieren
    const geojson = osmtogeojson(data)  // Benötigt Bibliothek: osmtogeojson
    return geojson
  } catch (err) {
    console.error("Fehler beim Abrufen von OSM-Daten:", err)
    alert("OSM-Daten konnten nicht geladen werden.")
  } finally {
    spinner.stop();
  }
}

function downloadGeoJSON(geojson, filename) {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(geojson))
  const dlAnchor = document.createElement("a")
  dlAnchor.setAttribute("href", dataStr)
  dlAnchor.setAttribute("download", filename)
  document.body.appendChild(dlAnchor)
  dlAnchor.click()
  dlAnchor.remove()
}
</script>

<template>
  <div class="relative w-full h-screen">
    <!-- Leaflet Karte -->
    <div ref="mapContainer" class="w-full h-full">

    <!-- Toolbar unten links -->
    <div class="toolbar">
      <button
        @click="handleLocate"
        class="bg-blue-600 text-white rounded px-3 py-2 hover:bg-blue-700 transition font-semibold"
      >
        📍 Standort
      </button>

      <!-- Suche -->
      <div class="flex items-center gap-1">
        <input
          v-model="query"
          type="text"
          placeholder=" Ort suchen"
          class="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 search-input"
          @keyup.enter="handleSearch"
        />
      </div>

      <!-- Upload -->
        <label
          class="bg-green-600 text-white px-3 py-2 rounded cursor-pointer hover:bg-green-700 transition font-semibold"
        >
          Upload
          <input
            type="file"
            accept=".geojson,.json,application/geo+json,application/json"
            @change="handleUpload"
            class="hidden"
          />
        </label>
      </div>
    </div>
  </div>
</template>

<style scoped>
.absolute div {
  font-family: Arial, sans-serif;
  font-size: 14px;
}
.toolbar {
  position: absolute;
  bottom: 1rem;
  left: 1rem;
  z-index: 1000;
  display: flex;
  gap: 0.5rem;
  background: white;
  box-shadow: 0 0 10px rgba(0,0,0,0.2);
  border-radius: 0.5rem;
  padding: 0.75rem;
  align-items: center;
  font-family: Arial, sans-serif;
  font-size: 14px;
}
.search-input {
  width: 150px;
  max-width: 50vw;
}
</style>
