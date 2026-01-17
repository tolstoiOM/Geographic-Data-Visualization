<template>
  <div class="credit-wrapper">
    Karten-Daten © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>
  </div>
</template>

<script setup>
// simple presentational component for map credit
</script>

<style scoped>
.credit-wrapper { font-size: 12px; padding: 8px 10px; background: var(--glass); border: 1px solid var(--glass-border); border-radius: 999px; color: var(--text); box-shadow: var(--shadow); backdrop-filter: blur(10px) }
.credit-wrapper a { color: var(--accent); font-weight: 600 }
</style>
