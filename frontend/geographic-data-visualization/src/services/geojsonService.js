// Small frontend service for calling backend GeoJSON/AI endpoints
// Usage:
// import { listAIScripts, augmentGeoJSON, fetchProcessedGeoJSON } from '@/services/geojsonService'
// (Vite resolves `import.meta.env.VITE_API_URL` at build/dev time)

const API_BASE = import.meta.env.VITE_API_URL || ''

function handleResponseError(res) {
  return res.text().then(text => {
    const msg = text || res.statusText || `HTTP ${res.status}`
    throw new Error(msg)
  })
}

function isValidGeoJSON(obj) {
  return obj && (obj.type === 'FeatureCollection' || obj.type === 'Feature')
}

export async function listAIScripts() {
  const url = `${API_BASE}/ai-scripts`
  const res = await fetch(url)
  if (!res.ok) return handleResponseError(res)
  const data = await res.json()
  return data.scripts || []
}

export async function augmentGeoJSON(geojson, scriptId) {
  if (!isValidGeoJSON(geojson)) throw new Error('Invalid GeoJSON input')
  if (!scriptId) throw new Error('scriptId is required')

  const url = `${API_BASE}/augment?script_id=${encodeURIComponent(scriptId)}`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(geojson)
  })
  if (!res.ok) return handleResponseError(res)

  const data = await res.json()
  // backend returns { status, script_id, geojson }
  if (data && data.geojson && isValidGeoJSON(data.geojson)) return data.geojson
  throw new Error('Invalid response from augment endpoint')
}

// Optional: try to fetch previously processed GeoJSON (if you implement GET /processed-geojson)
export async function fetchProcessedGeoJSON() {
  const url = `${API_BASE}/processed-geojson`
  const res = await fetch(url)
  if (!res.ok) {
    if (res.status === 404) return null
    return handleResponseError(res)
  }
  const data = await res.json()
  if (!isValidGeoJSON(data)) throw new Error('Invalid GeoJSON received')
  return data
}
