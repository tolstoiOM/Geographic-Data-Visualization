<script setup>
import MapContainer from './MapContainer.vue'
import MapToolbar from './MapToolbar.vue'
import DrawControls from './DrawControls.vue'
// Map.vue is a simple wrapper; child components inject 'helpers' themselves
</script>

<template>
  <MapContainer />
</template>

<style scoped>
.search-input { width: 150px }
</style>
