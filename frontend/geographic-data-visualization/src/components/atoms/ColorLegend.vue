<template>
  <div class="color-legend">
    <div class="legend-title">Legende</div>
    <div class="legend-actions" style="display:flex;gap:6px;margin-bottom:6px">
      <button @click="selectAll" class="btn-small">Alle</button>
      <button @click="clearAll" class="btn-small">Keine</button>
    </div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <input type="checkbox" id="chk-ai-polygon" v-model="aiVisible" @change="onToggleAIPolygon" />
      <label for="chk-ai-polygon">KI-Polygon anzeigen</label>
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
import { reactive, onMounted, ref } from 'vue'

// allow parent to pass initial selection and a callback function
const props = defineProps({
  initialSelection: { type: Array, default: () => [] },
  // parent can pass a function to be called when selection changes
  onSelectionChange: { type: Function, required: false },
  onAIPolygonToggle: { type: Function, required: false }
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

// AI polygon visibility
const aiVisible = ref(true)

function onToggleAIPolygon() {
  if (typeof props.onAIPolygonToggle === 'function') {
    try { props.onAIPolygonToggle(aiVisible.value) } catch (e) { console.warn('onAIPolygonToggle threw', e) }
  }
}

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
onMounted(() => { emitSelection(); onToggleAIPolygon() })
</script>

<style scoped>
.color-legend { font-size: 12px; background: var(--glass); padding: 10px; border-radius: 10px; border: 1px solid var(--glass-border); box-shadow: var(--shadow); backdrop-filter: blur(10px); color: var(--text) }
.legend-title { font-weight: 700; margin-bottom: 6px; letter-spacing: 0.02em }
.color-legend ul { list-style: none; padding: 0; margin: 0; max-height: 260px; overflow:auto }
.color-legend li { display:flex; align-items:center; gap:8px; margin:6px 0 }
.swatch { width: 14px; height: 14px; border-radius: 4px; border: 1px solid var(--border) }
.label { color: var(--text) }
.btn-small { background: var(--surface-2); border:1px solid var(--border); padding:4px 10px; border-radius:8px; font-size:11px; color: var(--text); font-weight:600; transition: background .15s ease, transform .15s ease }
.btn-small:hover { background: var(--control-hover); transform: translateY(-1px) }
</style>
