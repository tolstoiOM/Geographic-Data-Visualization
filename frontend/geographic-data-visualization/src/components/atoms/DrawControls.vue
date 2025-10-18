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
    try {
      const exportedGeoJson = await helpers?.exportGeoJSON(geojson)
      if (exportedGeoJson && window.confirm('Möchten Sie die OSM-Objekte aus dem gezeichneten Bereich als GeoJSON exportieren?')) {
        helpers?.downloadGeoJSON(exportedGeoJson, 'osm_objekte.geojson')
      }
    } catch (err) {
      console.error('Error exporting GeoJSON:', err)
    }
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
