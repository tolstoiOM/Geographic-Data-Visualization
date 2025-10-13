<script setup>
import { ref } from 'vue'
const query = ref('')

const emit = defineEmits(['locate', 'search', 'upload'])

function onUpload(event) {
  const file = event.target.files[0]
  if (file) {
    emit('upload', file)
  }
}
</script>

<template>
  <div class="toolbar flex flex-col gap-2 bg-white/90 backdrop-blur-md p-3 rounded-lg shadow-md w-60">
    <button @click="$emit('locate')" class="bg-blue-600 text-white rounded px-2 py-1 hover:bg-blue-700 transition">📍 Standort</button>
    <div class="relative">
      <input v-model="query" type="text" placeholder="Ort suchen (z.B. Stephansdom)" class="w-full border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"/>
      <button @click="$emit('search', query)" class="absolute right-1 top-1 bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700 transition">Suche</button>
    </div>
    <label class="block bg-gray-100 border border-gray-300 rounded px-2 py-1 text-center cursor-pointer hover:bg-gray-200 transition">
      Upload
      <input type="file" accept="application/geo+json,application/json" @change="onUpload" class="hidden"/>
    </label>
  </div>
</template>

<style scoped>
.toolbar {
  pointer-events: auto;
}
</style>
