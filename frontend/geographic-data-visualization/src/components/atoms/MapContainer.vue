<template>
  <div class="relative w-full h-screen">
      <div ref="mapContainer" class="w-full h-full relative">
  <SpinnerComp :visible="spinner.isVisible.value" />
      </div>
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
import { booleanIntersects, booleanWithin, intersect as turfIntersect } from '@turf/turf'
import SpinnerComp from './Spinner.vue'
import { useSpinner } from '../../composables/useSpinner'
import DrawControls from './DrawControls.vue'
import MapToolbar from './MapToolbar.vue'
import Credit from './Credit.vue'
import { createApp } from 'vue'
import ColorLegend from './ColorLegend.vue'

const mapContainer = ref(null)
const map = ref(null)
const START_COORDS = [48.2082, 16.3738]
const START_ZOOM = 13
const spinner = useSpinner()
// color mapping helpers
const COLOR_MAP = {
  residential: '#60a5fa',
  commercial: '#f97316',
  industrial: '#64748b',
  education: '#10b981',
  healthcare: '#ef4444',
  religious: '#8b5cf6',
  leisure: '#34d399',
  tourism: '#f59e0b',
  unknown: '#888888'
}

function getFeatureType(feature) {
  const p = feature.properties || {}
  if (p.amenity) {
    const a = String(p.amenity).toLowerCase()
    if (a === 'school' || a === 'university') return 'education'
    if (a === 'hospital' || a === 'clinic' || a === 'doctors') return 'healthcare'
    if (a === 'place_of_worship') return 'religious'
    return 'amenity'
  }
  if (p.building) {
    const b = String(p.building).toLowerCase()
    if (b.includes('resid') || b === 'house' || b === 'apartments') return 'residential'
    if (b.includes('commer') || b.includes('retail') || b.includes('shop')) return 'commercial'
    if (b.includes('indust')) return 'industrial'
    if (b.includes('church') || b.includes('cathedral')) return 'religious'
    return 'building'
  }
  if (p.shop || p.office) return 'commercial'
  if (p.leisure) return 'leisure'
  if (p.tourism) return 'tourism'
  if (p.landuse) {
    if (p.landuse === 'residential') return 'residential'
    if (p.landuse === 'industrial') return 'industrial'
    if (p.landuse === 'commercial') return 'commercial'
    if (p.landuse === 'forest' || p.landuse === 'park') return 'leisure'
  }
  if (feature.geometry && feature.geometry.type === 'Point') return 'point'
  return 'unknown'
}

function getStyleForFeature(feature) {
  const t = getFeatureType(feature)
  const color = COLOR_MAP[t] || COLOR_MAP.unknown
  return { color: color, fillColor: color, fillOpacity: 0.35, weight: 2 }
}
let _locTimer = null


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

  // small credit control using a Vue component mounted into the control
  const CreditControl = L.Control.extend({
    options: { position: 'bottomright' },
    onAdd: function () {
      const container = L.DomUtil.create('div', 'custom-credit')
      // mount the Credit.vue into this container so it's managed by Vue
      this._vueApp = createApp(Credit)
      this._vueApp.mount(container)
      return container
    },
    onRemove: function () {
      if (this._vueApp) {
        try { this._vueApp.unmount() } catch (e) { /* ignore */ }
        this._vueApp = null
      }
    }
  })

  map.value.addControl(new CreditControl())

  // mount legend as a leaflet control
  const LegendControl = L.Control.extend({ options: { position: 'topright' }, onAdd: function() {
    const container = L.DomUtil.create('div', 'color-legend-control')
    // pass a callback so the legend can notify the map when selection changes
    const app = createApp(ColorLegend, {
      onSelectionChange: (selectedCategories) => {
        try { applyLegendFilter(selectedCategories) } catch (e) { console.warn('Legend selection handler failed', e) }
      }
    })
    this._vueApp = app
    this._vueApp.mount(container)
    return container
  }, onRemove: function() { if (this._vueApp) { try { this._vueApp.unmount() } catch(e){} this._vueApp = null } }
  })
  map.value.addControl(new LegendControl())

  L.marker(START_COORDS).addTo(map.value).bindPopup('<b>Wien</b><br>Willkommen auf deiner OSM-Karte.')
  // spinner is managed via the useSpinner() composable


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
    spinner.show()
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
    spinner.hide()
  }

  provided.handleUpload = async function(file) {
    if (!file) return
    spinner.show()
    const reader = new FileReader()
    reader.onerror = (e) => {
      console.error('FileReader error', e)
      alert('Fehler beim Lesen der Datei.')
      try { spinner.hide() } catch (err) {}
    }
    reader.onload = async (e) => {
      try {
        const geojson = JSON.parse(e.target.result)
        if (!geojson.type || (geojson.type !== 'FeatureCollection' && geojson.type !== 'Feature')) throw new Error('Nicht unterstützter GeoJSON-Typ')
        if (provided._geoJsonLayer) {
          try { map.value.removeLayer(provided._geoJsonLayer) } catch (e) { /* ignore */ }
          provided._geoJsonLayer = null
        }
        // store last raw geojson so legend filtering can reuse it
        provided._lastGeoJSON = geojson
        provided._geoJsonLayer = L.geoJSON(geojson, {
          style: getStyleForFeature,
          pointToLayer: function(feature, latlng) {
            const s = getStyleForFeature(feature)
            return L.circleMarker(latlng, { radius: 6, fillColor: s.fillColor, color: '#fff', weight: 1, fillOpacity: 1 })
          },
          onEachFeature: function(feature, layer) {
            // attach a helpful popup showing type and key tags
            try {
              const t = getFeatureType(feature)
              const props = feature.properties || {}
              const title = props.name || props.id || (props.type || t)
              const html = `<div><strong>${title}</strong><div>Typ: ${t}</div></div>`
              layer.bindPopup(html)
            } catch (e) { /* ignore */ }
          }
        }).addTo(map.value)
        try { map.value.fitBounds(provided._geoJsonLayer.getBounds()) } catch (e) { console.warn('fitBounds failed', e) }
        if (window.confirm('Möchtest du diese GeoJSON-Daten in die Datenbank speichern?')) {
          await provided.saveGeoJSONToDB(geojson)
          alert('GeoJSON-Daten wurden an das Backend gesendet.')
        }
      } catch (err) {
        console.error('Fehler beim Lesen der Datei:', err)
        alert('Ungültige GeoJSON-Datei.')
      } finally { spinner.hide() }
    }
    reader.readAsText(file)
  }

  // apply legend filter by rebuilding the geojson layer from provided._lastGeoJSON
  function applyLegendFilter(selectedCategories) {
    try {
      // if no stored geojson, nothing to do
      if (!provided._lastGeoJSON) return
      // remove existing layer if present
      if (provided._geoJsonLayer) {
        try { map.value.removeLayer(provided._geoJsonLayer) } catch (e) { /* ignore */ }
        provided._geoJsonLayer = null
      }
      // build filtered FeatureCollection
      const filtered = { type: 'FeatureCollection', features: (provided._lastGeoJSON.features || []).filter(f => {
        try {
          const t = getFeatureType(f)
          // show features where type is in selectedCategories OR when selected includes 'unknown' and type is unknown
          return selectedCategories.includes(t) || (t === 'unknown' && selectedCategories.includes('unknown'))
        } catch (e) { return false }
      }) }
      provided._geoJsonLayer = L.geoJSON(filtered, {
        style: getStyleForFeature,
        pointToLayer: function(feature, latlng) {
          const s = getStyleForFeature(feature)
          return L.circleMarker(latlng, { radius: 6, fillColor: s.fillColor, color: '#fff', weight: 1, fillOpacity: 1 })
        },
        onEachFeature: function(feature, layer) {
          try {
            const t = getFeatureType(feature)
            const props = feature.properties || {}
            const title = props.name || props.id || (props.type || t)
            const html = `<div><strong>${title}</strong><div>Typ: ${t}</div></div>`
            layer.bindPopup(html)
          } catch (e) { /* ignore */ }
        }
      }).addTo(map.value)
      try { map.value.fitBounds(provided._geoJsonLayer.getBounds()) } catch (e) { /* ignore */ }
    } catch (err) { console.warn('applyLegendFilter failed', err) }
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
    // start locate and add a fallback timeout to stop locating if nothing happens
    map.value.locate({ setView: true, maxZoom: 16 })
    if (_locTimer) clearTimeout(_locTimer)
    _locTimer = setTimeout(() => {
      try { map.value.stopLocate(); console.warn('Locate timed out, stopped location watch.') } catch (e) {}
      _locTimer = null
    }, 15000)

    map.value.once('locationfound', (e) => {
      const m = L.marker(e.latlng).addTo(map.value).bindPopup('📍 Du bist hier')
      try {
        map.value.once('moveend', () => { try { m.openPopup() } catch (e) { /* ignore */ } })
      } catch (err) { try { m.openPopup() } catch (e) { /* ignore */ } }
      spinner.hide()
      if (_locTimer) { clearTimeout(_locTimer); _locTimer = null }
    })
  map.value.once('locationerror', () => { alert('Standort konnte nicht ermittelt werden.'); try { spinner.hide() } catch (e) {} if (_locTimer) { clearTimeout(_locTimer); _locTimer = null } })
  }

  provided.exportGeoJSON = async function(layer_geojson) {
    try { try { spinner.show() } catch (e) {};
      const coords = layer_geojson.geometry.coordinates[0]
      const polyString = coords.map(ll => `${ll[1]} ${ll[0]}`).join(' ')
        const overpassQuery = `\n        [out:json][timeout:25];\n        (\n          way(poly:"${polyString}");\n          relation(poly:"${polyString}");\n          node(poly:"${polyString}");\n        );\n        out geom;\n      `
      const res = await fetch('https://overpass-api.de/api/interpreter', { method: 'POST', body: 'data=' + encodeURIComponent(overpassQuery) })
      const data = await res.json()
      const geojson = osmtogeojson(data)
      // Filter features: only include those that intersect the drawn polygon
      try {
        if (geojson && geojson.type === 'FeatureCollection' && Array.isArray(geojson.features)) {
          const seen = new Set()
          const resultFeatures = []
          for (const f of geojson.features) {
            try {
              // dedupe by id if present
              const fid = f.id || (f.properties && (f.properties.id || f.properties['@id']))
              if (fid && seen.has(fid)) continue
              // Points: keep only if fully within drawn polygon
              let clipped = null
              const geomType = f.geometry && f.geometry.type
              if (geomType === 'Point' || geomType === 'MultiPoint') {
                try {
                  if (booleanWithin(f, layer_geojson)) clipped = f
                } catch (e) { /* ignore */ }
              } else {
                // For lines/polygons, prefer clipping the geometry to the drawn polygon
                try {
                  const inter = turfIntersect(f, layer_geojson)
                  if (inter) {
                    // ensure properties are preserved
                    inter.properties = Object.assign({}, f.properties)
                    clipped = inter
                  } else if (booleanIntersects(f, layer_geojson)) {
                    // fallback: include original if it intersects but couldn't be clipped
                    clipped = f
                  }
                } catch (e) {
                  // intersect may fail for some geometry types - fallback to intersects
                  try { if (booleanIntersects(f, layer_geojson)) clipped = f } catch (e2) { /* ignore */ }
                }
              }
              if (clipped) {
                if (fid) seen.add(fid)
                resultFeatures.push(clipped)
              }
            } catch (err) {
              // skip problematic feature
            }
          }
          return { type: 'FeatureCollection', features: resultFeatures }
        }
      } catch (err) { console.warn('Filtering geojson failed', err) }
      return geojson
  } catch (err) { console.error('Fehler beim Abrufen von OSM-Daten:', err); alert('OSM-Daten konnten nicht geladen werden.') }
  finally { try { spinner.hide() } catch (e) {} }
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
