<template>
  <div class="spinner-overlay" v-if="visible" :style="overlayStyle" role="status" :aria-label="label">
    <div class="loader" :style="loaderStyle"></div>
    <span class="sr-only" v-if="label">{{ label }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  visible: { type: Boolean, default: false },
  size: { type: [Number, String], default: 48 },
  color: { type: String, default: '#34db82' },
  label: { type: String, default: 'Lädt...' }
})
const overlayStyle = computed(() => ({
  position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, pointerEvents: 'none'
}))
const loaderStyle = computed(() => ({
  width: typeof props.size === 'number' ? props.size + 'px' : props.size,
  height: typeof props.size === 'number' ? props.size + 'px' : props.size,
  borderTopColor: props.color
}))
</script>

<style scoped>
.spinner-overlay { background: rgba(255,255,255,0.15); }
.loader { border: 6px solid rgba(243,243,243,1); border-top: 6px solid #34db82; border-radius: 50%; animation: spin 1s linear infinite; pointer-events: auto; }
.sr-only { position: absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0 }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
