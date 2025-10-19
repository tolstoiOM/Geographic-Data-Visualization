<template>
  <div class="color-legend">
    <div class="legend-title">Legende</div>
    <ul>
      <li v-for="(label, key) in labels" :key="key">
        <span class="swatch" :style="{ background: colors[key] }"></span>
        <span class="label">{{ label }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
// Keep labels/colors in sync with MapContainer helper
const labels = reactive({
  residential: 'Wohnen',
  commercial: 'Gewerbe/Einzelhandel',
  industrial: 'Industrie',
  education: 'Bildung',
  healthcare: 'Gesundheit',
  religious: 'Religiös',
  leisure: 'Freizeit / Park',
  tourism: 'Tourismus',
  unknown: 'Unbekannt'
})
const colors = reactive({
  residential: '#60a5fa',
  commercial: '#f97316',
  industrial: '#64748b',
  education: '#10b981',
  healthcare: '#ef4444',
  religious: '#8b5cf6',
  leisure: '#34d399',
  tourism: '#f59e0b',
  unknown: '#888888'
})
</script>

<style scoped>
.color-legend { font-size: 12px; background: rgba(255,255,255,0.95); padding: 8px; border-radius: 6px; box-shadow: 0 6px 18px rgba(0,0,0,0.08) }
.legend-title { font-weight: 600; margin-bottom: 6px }
.color-legend ul { list-style: none; padding: 0; margin: 0; }
.color-legend li { display:flex; align-items:center; gap:8px; margin:4px 0 }
.swatch { width: 14px; height: 14px; border-radius: 3px; border: 1px solid rgba(0,0,0,0.08) }
.label { color: #111827 }
</style>
