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
  </div>
</template>

<script setup>
import { ref, inject } from 'vue'
const helpers = inject('helpers', null)
const q = ref('')
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
    console.log("Processed GeoJSON ready for display", resultGeojson);
  }
}
</script>

<style scoped>
.toolbar{position:absolute;bottom:1rem;left:1rem;z-index:1000;background:white;padding:.75rem;border-radius:.5rem;display:flex;gap:.5rem;align-items:center}
.search-input{width:150px}
</style>
