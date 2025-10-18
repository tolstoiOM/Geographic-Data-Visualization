<template>
  <div class="relative w-full h-screen">
    <div ref="mapContainer" class="w-full h-full"></div>
    <!-- DrawControls does not render DOM into the map pane; keep it as a child so it can access mapRef -->
    <DrawControls />
    <!-- Toolbar is rendered outside the raw Leaflet map container to avoid DOM interference -->
    <MapToolbar />
  </div>
</template>

<script setup>
import { onMounted, ref, provide } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import osmtogeojson from 'osmtogeojson'
import { Spinner } from 'spin.js'
import 'spin.js/spin.css'
import DrawControls from './DrawControls.vue'
import MapToolbar from './MapToolbar.vue'

const mapContainer = ref(null)
const map = ref(null)
const START_COORDS = [48.2082, 16.3738]
const START_ZOOM = 13
let spinner


// Expose map and helper functions to child components
provide('mapRef', map)

// helper placeholders will be provided and populated later
const provided = {}
provide('helpers', provided)

onMounted(() => {
  if (!map.value) {
    map.value = L.map(mapContainer.value).setView(START_COORDS, START_ZOOM)
  }

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap-Mitwirkende'
  }).addTo(map.value)

  // small credit control
  const CreditControl = L.Control.extend({
    options: { position: 'bottomright' },
    onAdd: function () {
      const div = L.DomUtil.create('div', 'custom-credit')
      div.innerHTML = `Karten-Daten © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>`
      return div
    }
  })
  map.value.addControl(new CreditControl())

  L.marker(START_COORDS).addTo(map.value).bindPopup('<b>Wien</b><br>Willkommen auf deiner OSM-Karte.')

  spinner = new Spinner({
    lines: 12, length: 38, width: 10, radius: 45, scale: 1.5,
    color: '#2563eb', zIndex: 9999, className: 'spinner'
  })

  // readableArea override to avoid leaflet-draw minified bug
  try {
    if (L && L.GeometryUtil && typeof L.GeometryUtil.readableArea === 'function') {
      const PREC = { km: 2, ha: 2, m: 0, mi: 2, ac: 2, yd: 0, ft: 0, nm: 2 }
      const originalReadableArea = L.GeometryUtil.readableArea
      L.GeometryUtil.readableArea = function(area, metric, opts) {
        try {
          if (metric) {
            const typ = typeof metric
            let units
            if (typ === 'string') units = [metric]
            else if (typ === 'boolean') units = ['ha', 'm']
            else units = metric

            if (area >= 1e6 && units.indexOf('km') !== -1) return L.GeometryUtil.formattedNumber(area * 1e-6, PREC.km) + ' km²'
            if (area >= 1e4 && units.indexOf('ha') !== -1) return L.GeometryUtil.formattedNumber(area * 1e-4, PREC.ha) + ' ha'
            return L.GeometryUtil.formattedNumber(area, PREC.m) + ' m²'
          } else {
            const a = area / 0.836127
            if (a >= 3097600) return L.GeometryUtil.formattedNumber(a / 3097600, PREC.mi) + ' mi²'
            if (a >= 4840) return L.GeometryUtil.formattedNumber(a / 4840, PREC.ac) + ' acres'
            return L.GeometryUtil.formattedNumber(a, PREC.yd) + ' yd²'
          }
        } catch (err) {
          try { return originalReadableArea(area, metric, opts) } catch (e) { return '' }
        }
      }
    }
  } catch (err) {
    console.warn('Could not apply readableArea override:', err)
  }

  // populate helper functions after map is available
  provided.handleSearch = async function(query) {
    if (!query) return
    try { spinner.spin(mapContainer.value) } catch (e) {}
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`)
      const data = await res.json()
      if (data && data.length > 0) {
        const { lat, lon, display_name } = data[0]
        // Remove any previous search marker before changing view to avoid
        // the marker being detached during an ongoing zoom animation
        if (provided._searchMarker) {
          try { map.value.removeLayer(provided._searchMarker) } catch (e) { /* ignore */ }
          provided._searchMarker = null
        }

        // Center the map (may animate). Add the new marker and open its popup
        // only after movement has finished to avoid Leaflet trying to animate
        // a marker whose internal _map reference might be temporarily null.
        map.value.setView([lat, lon], 15)
        const newMarker = L.marker([lat, lon]).addTo(map.value).bindPopup(display_name)
        provided._searchMarker = newMarker
        try {
          map.value.once('moveend', () => { try { newMarker.openPopup() } catch (e) { /* ignore */ } })
        } catch (e) {
          try { newMarker.openPopup() } catch (err) { /* ignore */ }
        }
      } else alert('Ort nicht gefunden.')
    } catch (err) { console.error('Fehler bei der Suche:', err) }
    try { spinner.stop() } catch (e) {}
  }

  provided.handleUpload = async function(file) {
    if (!file) return
    try { spinner.spin(mapContainer.value) } catch (e) {}
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const geojson = JSON.parse(e.target.result)
        if (!geojson.type || (geojson.type !== 'FeatureCollection' && geojson.type !== 'Feature')) throw new Error('Nicht unterstützter GeoJSON-Typ')
        if (provided._geoJsonLayer) {
          try { map.value.removeLayer(provided._geoJsonLayer) } catch (e) { /* ignore */ }
          provided._geoJsonLayer = null
        }
        provided._geoJsonLayer = L.geoJSON(geojson, {
          style: function(feature) {
            if (feature.properties && feature.properties.building) {
              return { color: '#000', fillColor: '#000', fillOpacity: 0.9, weight: 1 };
            }
            return { color: '#888', fillColor: '#fff', fillOpacity: 0.1, weight: 0.5 };
          },
          pointToLayer: function() { return null; } // Prevent markers for points
        }).addTo(map.value)
        try { map.value.fitBounds(provided._geoJsonLayer.getBounds()) } catch (e) { console.warn('fitBounds failed', e) }
        if (window.confirm('Möchtest du diese GeoJSON-Daten in die Datenbank speichern?')) {
          await provided.saveGeoJSONToDB(geojson)
          alert('GeoJSON-Daten wurden an das Backend gesendet.')
        }
      } catch (err) {
        console.error('Fehler beim Lesen der Datei:', err)
        alert('Ungültige GeoJSON-Datei.')
      } finally { try { spinner.stop() } catch (e) {} }
    }
    reader.readAsText(file)
  }

  provided.saveGeoJSONToDB = async function(geojson) {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/upload-geojson`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(geojson)
      })
      if (!res.ok) { const msg = await res.text(); throw new Error(msg || 'Fehler beim Speichern') }
    } catch (err) { console.error('Fehler beim Senden der GeoJSON-Daten:', err); alert('Fehler beim Speichern in der Datenbank.') }
  }

  provided.handleLocate = function() {
    try { spinner.spin(mapContainer.value) } catch (e) {}
    map.value.locate({ setView: true, maxZoom: 16 })
    map.value.once('locationfound', (e) => {
      const m = L.marker(e.latlng).addTo(map.value).bindPopup('📍 Du bist hier')
      try {
        map.value.once('moveend', () => { try { m.openPopup() } catch (e) { /* ignore */ } })
      } catch (err) { try { m.openPopup() } catch (e) { /* ignore */ } }
      try { spinner.stop() } catch (e) {}
    })
    map.value.once('locationerror', () => { alert('Standort konnte nicht ermittelt werden.'); try { spinner.stop() } catch (e) {} })
  }

  provided.exportGeoJSON = async function(layer_geojson) {
    try { try { spinner.spin(mapContainer.value) } catch (e) {};
      const coords = layer_geojson.geometry.coordinates[0]
      const polyString = coords.map(ll => `${ll[1]} ${ll[0]}`).join(' ')
      const overpassQuery = `\n        [out:json][timeout:25];\n        (\n          way(poly:"${polyString}");\n          node(poly:"${polyString}");\n        );\n        out body;\n      `
      const res = await fetch('https://overpass-api.de/api/interpreter', { method: 'POST', body: 'data=' + encodeURIComponent(overpassQuery) })
      const data = await res.json()
      const geojson = osmtogeojson(data)
      return geojson
    } catch (err) { console.error('Fehler beim Abrufen von OSM-Daten:', err); alert('OSM-Daten konnten nicht geladen werden.') }
    finally { try { spinner.stop() } catch (e) {} }
  }

  provided.downloadGeoJSON = function(geojson, filename) {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(geojson))
    const dlAnchor = document.createElement('a')
    dlAnchor.setAttribute('href', dataStr)
    dlAnchor.setAttribute('download', filename)
    document.body.appendChild(dlAnchor)
    dlAnchor.click()
    dlAnchor.remove()
  }

  // helpers object was provided earlier; we've now populated it

})
</script>

<style scoped>
.custom-credit { font-size: 12px; padding: 6px; background: rgba(255,255,255,0.9); border-radius: 4px }
.leaflet-draw-fallback { display:flex; align-items:center; justify-content:center; width:34px; height:34px; background:white; border:1px solid rgba(0,0,0,0.15); border-radius:3px }
.leaflet-draw-fallback:hover { background:#f3f4f6 }
</style>
