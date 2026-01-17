<template>
  <div class="toolbar">
    <div class="flex items-center gap-2">
      <input v-model="q" @keyup.enter="onSearch" placeholder="Ort suchen" class="search-input" />
      <button @click="onSearch" class="btn-secondary">Suchen</button>
    </div>

    <label class="btn-primary cursor-pointer">
      Upload
      <input type="file" accept=".geojson,.json" @change="onUpload" class="hidden" />
    </label>

    <button class="theme-toggle" type="button" @click="toggleTheme" :aria-label="theme === 'dark' ? 'Light mode' : 'Dark mode'">
      <span class="theme-icon">{{ theme === 'dark' ? '🌙' : '☀️' }}</span>
      <span class="theme-label">{{ theme === 'dark' ? 'Dark' : 'Light' }}</span>
      <span class="switch" :class="{ on: theme === 'dark' }" aria-hidden="true"></span>
    </button>
  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
const helpers = inject('helpers', null)
const q = ref('')
const theme = ref('light')
function onSearch() { if (q.value && helpers && typeof helpers.handleSearch === 'function') helpers.handleSearch(q.value) }
function onUpload(e) { const f = e.target.files && e.target.files[0]; if (f && helpers && typeof helpers.handleUpload === 'function') helpers.handleUpload(f) }
function applyTheme(nextTheme) {
  theme.value = nextTheme
  try { document.documentElement.setAttribute('data-theme', nextTheme) } catch (e) {}
  try { localStorage.setItem('theme', nextTheme) } catch (e) {}
}
function toggleTheme() {
  applyTheme(theme.value === 'dark' ? 'light' : 'dark')
}

onMounted(() => {
  const stored = (() => { try { return localStorage.getItem('theme') } catch (e) { return null } })()
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  applyTheme(stored || (prefersDark ? 'dark' : 'light'))
})
</script>

<style scoped>
.toolbar{position:absolute;bottom:1rem;left:1rem;z-index:1000;background:var(--glass);border:1px solid var(--glass-border);padding:.75rem 1rem;border-radius:999px;display:flex;gap:.75rem;align-items:center;box-shadow:var(--shadow);backdrop-filter:blur(12px)}
.search-input{width:180px;min-height:40px;padding:0 .85rem;border-radius:999px;border:1px solid var(--border);background:var(--input-bg);color:var(--input-text);outline:none;transition:border .15s ease, box-shadow .15s ease, background .15s ease}
.search-input::placeholder{color:var(--input-placeholder)}
.search-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent)}
.btn-primary{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:0 16px;border-radius:999px;background:linear-gradient(135deg,var(--accent),#7c3aed);color:#fff;font-weight:600;box-shadow:0 10px 24px rgba(79,70,229,.25);transition:transform .15s ease, box-shadow .15s ease}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 12px 28px rgba(79,70,229,.3)}
.btn-secondary{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:0 16px;border-radius:999px;background:var(--surface-2);color:var(--text);border:1px solid var(--border);font-weight:600;transition:background .15s ease, transform .15s ease}
.btn-secondary:hover{background:var(--control-hover);transform:translateY(-1px)}
.theme-toggle{display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:0 12px;border-radius:999px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-weight:600;transition:background .15s ease, transform .15s ease}
.theme-toggle:hover{background:var(--surface-2);transform:translateY(-1px)}
.theme-icon{font-size:14px}
.theme-label{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.switch{position:relative;width:36px;height:20px;border-radius:999px;background:var(--border);transition:background .15s ease}
.switch::after{content:'';position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#fff;box-shadow:0 4px 10px rgba(0,0,0,.15);transition:transform .15s ease}
.switch.on{background:var(--accent)}
.switch.on::after{transform:translateX(16px)}
</style>
