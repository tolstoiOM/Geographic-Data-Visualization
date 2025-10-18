<template>
  <div class="toolbar">
    <button @click="$emit('locate')" class="bg-blue-600 text-white rounded px-3 py-2">📍 Standort</button>

    <div class="flex items-center gap-1">
      <input v-model="q" @keyup.enter="onSearch" placeholder="Ort suchen" class="search-input" />
      <button @click="onSearch" class="px-3 py-2 bg-gray-200 rounded">Suchen</button>
    </div>

    <label class="bg-green-600 text-white px-3 py-2 rounded cursor-pointer">
      Upload
      <input type="file" accept=".geojson,.json" @change="onUpload" class="hidden" />
    </label>
  </div>
</template>

<script setup>
import { ref, inject } from 'vue'
const helpers = inject('helpers', null)
const q = ref('')
function onSearch() { if (q.value && helpers && typeof helpers.handleSearch === 'function') helpers.handleSearch(q.value) }
function onUpload(e) { const f = e.target.files && e.target.files[0]; if (f && helpers && typeof helpers.handleUpload === 'function') helpers.handleUpload(f) }
function onLocate() { if (helpers && typeof helpers.handleLocate === 'function') helpers.handleLocate() }
</script>

<style scoped>
.toolbar{position:absolute;bottom:1rem;left:1rem;z-index:1000;background:white;padding:.75rem;border-radius:.5rem;display:flex;gap:.5rem;align-items:center}
.search-input{width:150px}
</style>
