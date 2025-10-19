<template>
  <div class="color-legend">
    <div class="legend-title">Legende</div>
    <div class="legend-actions" style="display:flex;gap:6px;margin-bottom:6px">
      <button @click="selectAll" class="btn-small">Alle</button>
      <button @click="clearAll" class="btn-small">Keine</button>
    </div>
    <ul>
      <li v-for="(label, key) in labels" :key="key">
        <input type="checkbox" :id="`chk-${key}`" v-model="selected[key]" @change="onChange" />
        <label :for="`chk-${key}`" style="display:flex;align-items:center;gap:8px">
          <span class="swatch" :style="{ background: colors[key] }"></span>
          <span class="label">{{ label }}</span>
        </label>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'

// allow parent to pass initial selection and a callback function
const props = defineProps({
  initialSelection: { type: Array, default: () => [] },
  // parent can pass a function to be called when selection changes
  onSelectionChange: { type: Function, required: false }
})

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

// selected state keyed by category
const selected = reactive({})
// initialize all keys; if initialSelection provided, use that
for (const k of Object.keys(labels)) selected[k] = (props.initialSelection.length === 0) ? true : props.initialSelection.includes(k)

function emitSelection() {
  const arr = Object.keys(selected).filter(k => selected[k])
  if (typeof props.onSelectionChange === 'function') {
    try { props.onSelectionChange(arr) } catch (e) { console.warn('onSelectionChange threw', e) }
  }
}

function onChange() { emitSelection() }
function selectAll() { for (const k of Object.keys(selected)) selected[k] = true; emitSelection() }
function clearAll() { for (const k of Object.keys(selected)) selected[k] = false; emitSelection() }

// call once on mount to notify parent of initial selection
onMounted(() => { emitSelection() })
</script>

<style scoped>
.color-legend { font-size: 12px; background: rgba(255,255,255,0.95); padding: 8px; border-radius: 6px; box-shadow: 0 6px 18px rgba(0,0,0,0.08) }
.legend-title { font-weight: 600; margin-bottom: 6px }
.color-legend ul { list-style: none; padding: 0; margin: 0; max-height: 260px; overflow:auto }
.color-legend li { display:flex; align-items:center; gap:8px; margin:4px 0 }
.swatch { width: 14px; height: 14px; border-radius: 3px; border: 1px solid rgba(0,0,0,0.08) }
.label { color: #111827 }
.btn-small { background:#f3f4f6; border:1px solid rgba(0,0,0,0.06); padding:4px 8px; border-radius:4px; font-size:11px }
</style>
