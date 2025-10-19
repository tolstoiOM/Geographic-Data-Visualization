import { ref } from 'vue'

export function useSpinner({ autoHideMs = 60000 } = {}) {
  const count = ref(0)
  const isVisible = ref(false)
  let _timeout = null

  function _startAutoHide() {
    if (_timeout) clearTimeout(_timeout)
    if (autoHideMs > 0) {
      _timeout = setTimeout(() => {
        console.warn('[useSpinner] auto-hiding spinner after timeout')
        count.value = 0
        isVisible.value = false
        _timeout = null
      }, autoHideMs)
    }
  }

  function _clearAutoHide() {
    if (_timeout) { clearTimeout(_timeout); _timeout = null }
  }

  function show(timeoutMs) {
    count.value += 1
    isVisible.value = count.value > 0
    console.debug('[useSpinner] show -> count=', count.value)
    // start or restart a fallback hide timer
    if (typeof timeoutMs === 'number') {
      if (_timeout) clearTimeout(_timeout)
      if (timeoutMs > 0) _timeout = setTimeout(() => { count.value = 0; isVisible.value = false; _timeout = null; console.warn('[useSpinner] auto-hide (per-call)') }, timeoutMs)
    } else {
      _startAutoHide()
    }
  }

  function hide() {
    count.value = Math.max(0, count.value - 1)
    isVisible.value = count.value > 0
    console.debug('[useSpinner] hide -> count=', count.value)
    if (count.value === 0) _clearAutoHide()
  }

  function reset() { count.value = 0; isVisible.value = false; _clearAutoHide() }

  return { show, hide, reset, isVisible }
}
