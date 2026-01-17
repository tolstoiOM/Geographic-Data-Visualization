<template>
  <div class="chat-card" :style="cardStyle">
    <div class="chat-header drag-handle" @pointerdown="startDrag">
      <div class="chat-title">AI Chat</div>
      <button class="icon-btn" type="button" @click="isOpen = !isOpen">
        <span v-if="isOpen">–</span>
        <span v-else>+</span>
      </button>
    </div>

    <div v-if="isOpen" class="chat-body">
      <div class="chat-actions">
        <button class="ghost-btn" type="button" @click="triggerUpload" :disabled="loading">
          Upload JSON
        </button>
        <button class="ghost-btn" type="button" @click="downloadGeo" :disabled="loading || !latestGeojson">
          Download GeoJSON
        </button>
        <input ref="fileInput" type="file" accept=".json,.geojson,application/json" class="hidden" @change="handleFile" />
        <span v-if="uploadStatus" class="upload-status">{{ uploadStatus }}</span>
      </div>
      <div ref="listEl" class="chat-messages">
        <div v-for="(msg, idx) in messages" :key="idx" :class="['chat-bubble', msg.sender === 'You' ? 'bubble-you' : 'bubble-ai']">
          <div class="bubble-label">{{ msg.sender }}</div>
          <div class="bubble-text">{{ msg.text }}</div>
        </div>
        <div v-if="error" class="error-text">{{ error }}</div>
      </div>

      <form class="chat-input" @submit.prevent="handleSend">
        <input
          v-model="prompt"
          type="text"
          placeholder="Ask about the map or data..."
          :disabled="loading"
        />
        <button type="submit" :disabled="loading || !prompt.trim()">
          {{ loading ? 'Sending...' : 'Send' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { inject, nextTick, ref, computed, onBeforeUnmount, onMounted } from 'vue'
import { sendPromptToAI } from '@/services/geojsonService'

const helpers = inject('helpers', null)
const messages = ref([{ sender: 'AI', text: 'Hi! Ask me anything about your map or GeoJSON.' }])
const prompt = ref('')
const loading = ref(false)
const error = ref('')
const isOpen = ref(true)
const listEl = ref(null)
const fileInput = ref(null)
const uploadStatus = ref('')
const uploadedGeojson = ref(null)
const latestGeojson = ref(null)
const pos = ref({ x: 16, y: 16 })
const size = ref({ w: 320, h: 420 })
const dragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

const cardStyle = computed(() => ({
  position: 'fixed',
  right: 'auto',
  bottom: 'auto',
  left: pos.value.x + 'px',
  top: pos.value.y + 'px',
  width: size.value.w + 'px',
  height: size.value.h + 'px'
}))

function clamp(val, min, max) {
  return Math.min(Math.max(val, min), max)
}

function startDrag(e) {
  if (e.button !== 0) return
  dragging.value = true
  dragOffset.value = { x: e.clientX - pos.value.x, y: e.clientY - pos.value.y }
  try { window.addEventListener('pointermove', onDrag) } catch (err) {}
  try { window.addEventListener('pointerup', stopDrag, { once: true }) } catch (err) {}
}

function onDrag(e) {
  if (!dragging.value) return
  const maxX = window.innerWidth - 120
  const maxY = window.innerHeight - 80
  pos.value = {
    x: clamp(e.clientX - dragOffset.value.x, 8, maxX),
    y: clamp(e.clientY - dragOffset.value.y, 8, maxY)
  }
}

function stopDrag() {
  dragging.value = false
  try { window.removeEventListener('pointermove', onDrag) } catch (err) {}
}

const scrollToBottom = () => {
  try {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  } catch (e) { /* ignore */ }
}

const handleSend = async () => {
  const text = prompt.value.trim()
  if (!text || loading.value) return
  loading.value = true
  error.value = ''
  messages.value.push({ sender: 'You', text })
  prompt.value = ''
  await nextTick()
  scrollToBottom()
  try {
    const geojson = uploadedGeojson.value || latestGeojson.value || (helpers && helpers._lastGeoJSON ? helpers._lastGeoJSON : undefined)
    const reply = await sendPromptToAI(text, geojson)
    messages.value.push({ sender: 'AI', text: reply || 'No response' })
    // Try to parse returned text as GeoJSON; if valid, store as latest
    try {
      const parsed = JSON.parse(reply)
      if (parsed && (parsed.type === 'FeatureCollection' || parsed.type === 'Feature')) {
        latestGeojson.value = parsed
        if (helpers) helpers._lastGeoJSON = parsed
        uploadStatus.value = 'AI returned GeoJSON'
      }
    } catch (e) { /* ignore parse errors */ }
  } catch (err) {
    error.value = err?.message || 'Could not reach AI service.'
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

const triggerUpload = () => {
  if (fileInput.value) fileInput.value.click()
}

const handleFile = async (e) => {
  const file = e?.target?.files?.[0]
  if (!file) return
  uploadStatus.value = ''
  try {
    const text = await file.text()
    const parsed = JSON.parse(text)
    if (!parsed || (parsed.type !== 'FeatureCollection' && parsed.type !== 'Feature')) {
      throw new Error('File is not valid GeoJSON (Feature or FeatureCollection)')
    }
    uploadedGeojson.value = parsed
    latestGeojson.value = parsed
    if (helpers) helpers._lastGeoJSON = parsed
    uploadStatus.value = 'GeoJSON loaded'
  } catch (err) {
    uploadStatus.value = 'Upload failed'
    error.value = err?.message || 'Could not read file'
  } finally {
    if (fileInput.value) fileInput.value.value = ''
    await nextTick()
    scrollToBottom()
  }
}

const downloadGeo = () => {
  const obj = latestGeojson.value || uploadedGeojson.value || (helpers && helpers._lastGeoJSON)
  if (!obj) return
  const data = JSON.stringify(obj, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'geojson-ai.json'
  a.click()
  URL.revokeObjectURL(url)
}

onBeforeUnmount(() => {
  try { window.removeEventListener('pointermove', onDrag) } catch (err) {}
})

onMounted(() => {
  try {
    const padding = 16
    const w = size.value.w
    const h = size.value.h
    pos.value = {
      x: Math.max(padding, window.innerWidth - w - padding),
      y: Math.max(padding, window.innerHeight - h - padding)
    }
  } catch (err) { /* ignore */ }
})
</script>

<style scoped>
.chat-card { max-width: 90vw; max-height: 90vh; min-width: 260px; min-height: 260px; background: var(--glass); color: var(--text); border: 1px solid var(--glass-border); border-radius: 16px; box-shadow: var(--shadow); backdrop-filter: blur(12px); overflow: hidden; resize: both; }
.chat-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-bottom: 1px solid var(--border); background: linear-gradient(135deg, rgba(255,255,255,0.08), rgba(148,163,184,0.08)); }
.drag-handle { cursor: move; user-select: none; touch-action: none; }
.chat-title { font-weight: 700; letter-spacing: 0.02em; color: var(--text); }
.icon-btn { width: 28px; height: 28px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface-2); color: var(--text); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; transition: transform 0.15s ease, background 0.15s ease; }
.icon-btn:hover { background: var(--control-hover); transform: translateY(-1px); }
.chat-body { padding: 10px 12px 12px 12px; display: flex; flex-direction: column; gap: 10px; height: calc(100% - 44px); }
.chat-actions { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); }
.ghost-btn { padding: 8px 10px; border-radius: 10px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); cursor: pointer; transition: background 0.15s ease, transform 0.15s ease; }
.ghost-btn:hover { background: var(--control-hover); transform: translateY(-1px); }
.upload-status { opacity: 0.8; }
.chat-messages { flex: 1; min-height: 120px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding-right: 4px; }
.chat-bubble { padding: 10px 12px; border-radius: 12px; background: var(--surface-2); border: 1px solid var(--border); box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
.bubble-you { align-self: flex-end; background: linear-gradient(135deg, var(--accent), #6366f1); color: #ffffff; border-color: transparent; }
.bubble-ai { align-self: flex-start; }
.bubble-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.75; margin-bottom: 4px; }
.bubble-text { white-space: pre-wrap; word-break: break-word; font-size: 14px; line-height: 1.4; }
.chat-input { display: flex; gap: 8px; align-items: center; }
.chat-input input { flex: 1; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--input-bg); color: var(--input-text); outline: none; transition: border 0.15s ease, background 0.15s ease; }
.chat-input input::placeholder { color: var(--input-placeholder); }
.chat-input input:focus { border-color: var(--accent); background: var(--surface); }
.chat-input button { padding: 10px 14px; border-radius: 10px; border: none; background: linear-gradient(135deg, var(--accent-2), var(--accent)); color: #0f172a; font-weight: 700; cursor: pointer; min-width: 90px; box-shadow: 0 10px 25px rgba(34,197,94,0.25); transition: transform 0.15s ease, box-shadow 0.15s ease; }
.chat-input button:disabled { opacity: 0.6; cursor: not-allowed; box-shadow: none; }
.chat-input button:not(:disabled):hover { transform: translateY(-1px); box-shadow: 0 12px 28px rgba(59,130,246,0.3); }
.error-text { color: #ef4444; font-size: 13px; border: 1px solid rgba(239,68,68,0.3); background: rgba(239,68,68,0.1); padding: 8px 10px; border-radius: 10px; }
</style>
