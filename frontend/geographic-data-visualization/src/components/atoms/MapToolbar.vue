<template>
  <div class="toolbar">
    <button @click="onLocate" class="bg-blue-600 text-white rounded px-3 py-2">📍 Standort</button>

    <div class="flex items-center gap-1">
      <input v-model="q" @keyup.enter="onSearch" placeholder="Ort suchen" class="search-input" />
      <button @click="onSearch" class="px-3 py-2 bg-gray-200 rounded">Suchen</button>
    </div>

      <label class="bg-green-600 text-white px-3 py-2 rounded cursor-pointer">
        Upload
        <input type="file" accept=".geojson,.json" @change="onUpload" class="hidden" />
      </label>

      <!-- AI script selector -->
      <div class="flex items-center gap-2">
        <select v-model="selectedScript" class="px-2 py-1 border rounded bg-white">
          <option disabled value="">AI-Skript wählen</option>
          <option v-for="s in scripts" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <button @click="runAI" :disabled="!selectedScript" class="px-3 py-2 bg-indigo-600 text-white rounded">AI ausführen</button>
      </div>

      <!-- Free-form prompt to Groq -->
      <div class="flex items-center gap-2">
        <input v-model="promptText" placeholder="Prompt an Groq..." class="px-2 py-1 border rounded w-48" />
        <button @click="sendPrompt" :disabled="!promptText" class="px-3 py-2 bg-amber-600 text-white rounded">Prompt senden</button>
      </div>
  </div>
</template>

<script setup>
import { ref, inject } from 'vue'
import { listAIScripts, augmentGeoJSON } from '@/services/geojsonService'
const helpers = inject('helpers', null)
const q = ref('')
const scripts = ref([])
const selectedScript = ref('')
const promptText = ref('')
function onSearch() { if (q.value && helpers && typeof helpers.handleSearch === 'function') helpers.handleSearch(q.value) }
function onUpload(e) { const f = e.target.files && e.target.files[0]; if (f && helpers && typeof helpers.handleUpload === 'function') helpers.handleUpload(f) }
function onLocate() { if (helpers && typeof helpers.handleLocate === 'function') helpers.handleLocate() }
async function handleGeojsonFileUpload(file, onGeojsonLoaded) {
  if (!file.name.toLowerCase().endsWith(".geojson")) {
    alert("Bitte eine .geojson Datei auswählen.");
    return;
  }

  const text = await file.text();
  let gj;
  try {
    gj = JSON.parse(text);
  } catch (e) {
    alert("Ungültiges GeoJSON.");
    return;
  }

  const doProcess = window.confirm("GeoJSON mit Test‑Python‑Skript überarbeiten? (Ja = schwarz markieren)");

  const endpoint = doProcess ? "/upload-geojson/process?process=true" : "/upload-geojson";

  // Wenn kein Server-Proxy konfiguriert ist, ändere Basis-URL auf backend-Host
  const url = endpoint;

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(gj)
  });

  if (!resp.ok) {
    const text = await resp.text();
    alert("Server-Fehler: " + text);
    return;
  }

  const data = await resp.json();
  // Bei process-Endpoint ist die GeoJSON im Feld `geojson`
  const resultGeojson = data.geojson || gj;

  // Download anbieten
  const blob = new Blob([JSON.stringify(resultGeojson, null, 2)], { type: "application/geo+json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  const base = file.name.replace(/\.geojson$/i, "");
  a.download = base + "_edited.geojson";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);

  // Anzeige: übergebe an Map / Parent-Component
  if (typeof onGeojsonLoaded === "function") {
    onGeojsonLoaded(resultGeojson);
    } else {
      // processed geojson passed to caller; debug log removed during cleanup
    }
}

// load available AI scripts on component mount
;(async function loadScripts(){
  try {
    const list = await listAIScripts()
    scripts.value = list
  } catch (e) {
    // ignore - UI will remain without scripts
    console.warn('Could not load AI scripts', e)
  }
})()

async function runAI() {
  if (!selectedScript.value) { alert('Bitte ein AI-Skript auswählen'); return }
  if (!helpers || !helpers._lastGeoJSON) { alert('Keine GeoJSON-Daten vorhanden. Bitte zuerst hochladen oder zeichnen.'); return }

  try {
    // build payload; include clip if user has drawn a polygon
    let payload = helpers._lastGeoJSON
    try {
      if (helpers && helpers._lastClip) {
        // shallow clone to avoid mutating original
        payload = Object.assign({}, helpers._lastGeoJSON)
        payload.clip = helpers._lastClip
        // optionally include a default min_area_fraction (0.0). Adjust if you want stricter filtering.
        payload.min_area_fraction = payload.min_area_fraction || 0.0
      }
    } catch (e) { /* ignore and fallback to sending lastGeoJSON only */ }

    const result = await augmentGeoJSON(payload, selectedScript.value)
    if (result) {
      // If this is the place_enrich script, offer the enriched GeoJSON for download
      if (selectedScript.value === 'place_enrich') {
        try {
          const want = window.confirm('Place enrichment completed. Möchtest du die ergänzte GeoJSON-Datei herunterladen?')
          if (want) {
            const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/geo+json' })
            const a = document.createElement('a')
            a.href = URL.createObjectURL(blob)
            a.download = 'place_enriched.geojson'
            document.body.appendChild(a)
            a.click()
            a.remove()
            URL.revokeObjectURL(a.href)
          }
        } catch (err) { console.warn('Download offer failed', err) }
      }

      if (helpers && typeof helpers.showProcessedGeoJSON === 'function') {
        helpers.showProcessedGeoJSON(result)
        // After showing the enriched GeoJSON, offer to upload it to the DB
        try {
          const uploadNow = window.confirm('Möchtest du die angereicherte GeoJSON jetzt hochladen?')
          if (uploadNow && helpers && typeof helpers.saveGeoJSONToDB === 'function') {
            try {
              await helpers.saveGeoJSONToDB(result)
              alert('Angereicherte GeoJSON wurde hochgeladen.')
            } catch (err) {
              console.error('Upload failed:', err)
              alert('Fehler beim Hochladen der angereicherten GeoJSON.')
            }
          }
        } catch (e) { /* ignore confirm errors */ }
      } else {
        const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/geo+json' })
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = 'ai_augmented.geojson'
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(a.href)
      }
      alert('AI-Skript erfolgreich ausgeführt.')
    }
  } catch (err) {
    console.error('AI run failed', err)
    alert('Fehler beim Ausführen des AI-Skripts: ' + (err.message || err))
  }
}

async function sendPrompt() {
  if (!promptText.value) { alert('Bitte einen Prompt eingeben'); return }
  if (!helpers || typeof helpers.sendPrompt !== 'function') { alert('Prompt-Senden ist derzeit nicht verfügbar.'); return }
  try {
    await helpers.sendPrompt(promptText.value)
  } catch (err) {
    console.error('Prompt send failed', err)
    alert('Fehler beim Senden des Prompts: ' + (err.message || err))
  }
}
</script>

<style scoped>
.toolbar{position:absolute;bottom:1rem;left:1rem;z-index:1000;background:white;padding:.75rem;border-radius:.5rem;display:flex;gap:.5rem;align-items:center}
.search-input{width:150px}
</style>
