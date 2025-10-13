<script setup>
import { onMounted, ref } from 'vue'
import L from 'leaflet'
import 'leaflet-draw'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw/dist/leaflet.draw.css'
import osmtogeojson from "osmtogeojson"

// Refs
const mapContainer = ref(null)
const loading = ref(false) // für Spinner
const query = ref('')
const START_COORDS = [48.2082, 16.3738];
const START_ZOOM = 13;
let map = null
let geoJsonLayer = null

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
})

// 🔍 Ortssuche über Nominatim (OpenStreetMap)
let searchMarker = null
async function handleSearch() {
  if (!query.value) return
  loading.value = true
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
    loading.value = false
  }
}

// 📂 Datei-Upload (GeoJSON anzeigen)
function handleUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  loading.value = true
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const geojson = JSON.parse(e.target.result)
      if (!geojson.type || (geojson.type !== 'FeatureCollection' && geojson.type !== 'Feature')) {
        throw new Error('Nicht unterstützter GeoJSON-Typ');
      } else if (geoJsonLayer) geoJsonLayer.remove()
      geoJsonLayer = L.geoJSON(geojson, {
        style: { color: '#000000', fillColor: '#000000', fillOpacity: 0.7, weight: 1 }
      }).addTo(map)
      map.fitBounds(geoJsonLayer.getBounds())
    } catch (err) {
      console.error('Fehler beim Lesen der Datei:', err)
      alert('Ungültige GeoJSON-Datei.')
    } finally {
      loading.value = false
    }
  }
  reader.readAsText(file)
}

// 📍 Benutzer-Standort
function handleLocate() {
  loading.value = true
  map.locate({ setView: true, maxZoom: 16 })
  map.on('locationfound', (e) => {
    L.marker(e.latlng).addTo(map).bindPopup('📍 Du bist hier').openPopup()
    loading.value = false
  })
  map.on('locationerror', () => {
    alert('Standort konnte nicht ermittelt werden.')
    loading.value = false
  })
}

async function exportGeoJSON(layer_geojson) {
  try {
    loading.value = true

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
    loading.value = false
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
    <div ref="mapContainer" class="w-full h-full"></div>

    <!-- Toolbar oben links -->
    <div class="absolute top-4 left-4 z-[1000] flex flex-col gap-2 bg-white/90 backdrop-blur-md p-3 rounded-lg shadow-md w-60">
      <button
        @click="handleLocate"
        class="bg-blue-600 text-white rounded px-2 py-1 hover:bg-blue-700 transition"
      >
        📍 Standort
      </button>
      <div class="relative">
        <input
          v-model="query"
          type="text"
          placeholder="Ort suchen (z.B. Stephansdom)"
          class="w-full border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
          @keyup.enter="handleSearch"
        />
        <button
          @click="handleSearch"
          class="absolute right-1 top-1 bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700 transition"
        >
          Suche
        </button>
      </div>
        <label
          class="block bg-gray-100 border border-gray-300 rounded px-2 py-1 text-center cursor-pointer hover:bg-gray-200 transition"
        >
          Upload
          <input
            type="file"
            accept="application/geo+json,application/json"
            @change="handleUpload"
            class="hidden"
          />
        </label>
      </div>

    <!-- Spinner -->
    <div
      v-if="loading"
      class="fixed top-0 left-0 w-full h-full bg-white/60 flex items-center justify-center z-[2000]"
    >
      <div class="loader border-8 border-gray-200 border-t-blue-500 rounded-full w-12 h-12 animate-spin"></div>
    </div>
  </div>
</template>

<style scoped>
.custom-credit {
  background: white;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: #333;
}
.map-container {
  width: 100%;
  height: 100%;
}
</style>
