<script setup>
import { inject, watch, onUnmounted } from 'vue'
import L from 'leaflet'
import 'leaflet-draw'

const mapRef = inject('mapRef', null)
const helpers = inject('helpers', null)

let drawControl = null
const drawnItems = new L.FeatureGroup()

function initializeDrawControl(map) {
  if (!map) return

  map.addLayer(drawnItems)

  drawControl = new L.Control.Draw({
    edit: {
      featureGroup: drawnItems,
      remove: true
    },
    draw: {
      polygon: {
        allowIntersection: false,
        showArea: true,
        drawError: {
          color: '#e1e100',
          message: '<strong>Oh snap!</strong> you can\'t draw that!'
        },
        shapeOptions: {
          color: '#e11d48'
        }
      },
      rectangle: {
        shapeOptions: {
          color: '#e11d48'
        }
      },
      polyline: false,
      circle: false,
      marker: false,
      circlemarker: false
    }
  })

  map.addControl(drawControl)

  map.on(L.Draw.Event.CREATED, async (event) => {
    const layer = event.layer
    drawnItems.addLayer(layer)

    const geojson = layer.toGeoJSON()
    // store the last drawn polygon in helpers so other components can use it as 'clip'
    try {
      if (helpers) helpers._lastClip = geojson
    } catch (e) { /* ignore */ }
    try {
      const exportedGeoJson = await helpers?.exportGeoJSON(geojson)
      if (exportedGeoJson && window.confirm('Möchten Sie die OSM-Objekte aus dem gezeichneten Bereich als GeoJSON exportieren?')) {
        helpers?.downloadGeoJSON(exportedGeoJson, 'osm_objekte.geojson')
      }
    } catch (err) {
      console.error('Error exporting GeoJSON:', err)
    }
  })

  // update helper when layers are edited (update stored clip)
  map.on(L.Draw.Event.EDITED, function(e) {
    try {
      const layers = drawnItems.getLayers()
      if (layers && layers.length > 0) {
        // take the first layer as current clip
        const g = layers[0].toGeoJSON()
        if (helpers) helpers._lastClip = g
      } else {
        if (helpers) helpers._lastClip = null
      }
    } catch (err) { /* ignore */ }
  })

  // when a drawn layer is deleted, clear stored clip if none remain
  map.on(L.Draw.Event.DELETED, function(e) {
    try {
      const layers = drawnItems.getLayers()
      if (!layers || layers.length === 0) {
        if (helpers) helpers._lastClip = null
      } else {
        if (helpers) helpers._lastClip = layers[0].toGeoJSON()
      }
    } catch (err) { /* ignore */ }
  })
}

function removeDrawControl(map) {
  if (map && drawControl) {
    map.removeControl(drawControl)
    map.off(L.Draw.Event.CREATED)
  }
  if (map) {
    map.removeLayer(drawnItems)
  }
}

watch(mapRef, (newMap) => {
  if (newMap) {
    initializeDrawControl(newMap)
  }
}, { immediate: true })

onUnmounted(() => {
  if (mapRef.value) {
    removeDrawControl(mapRef.value)
  }
})
</script>

<template>
  <!-- This component now only contains logic and does not render any template -->
</template>

<style>
/* Styles for leaflet-draw are now global */
</style>
