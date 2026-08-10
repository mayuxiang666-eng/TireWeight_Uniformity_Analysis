<template>
  <aside class="app-sidebar">
    <!-- Brand Info -->
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="#2563eb" stroke-width="2"/>
          <circle cx="12" cy="12" r="4" fill="#2563eb"/>
          <line x1="12" y1="2" x2="12" y2="6" stroke="#2563eb" stroke-width="2"/>
          <line x1="12" y1="18" x2="12" y2="22" stroke="#2563eb" stroke-width="2"/>
          <line x1="2" y1="12" x2="6" y2="12" stroke="#2563eb" stroke-width="2"/>
          <line x1="18" y1="12" x2="22" y2="12" stroke="#2563eb" stroke-width="2"/>
        </svg>
      </div>
      <div>
        <div class="brand-name">轮胎质量看板</div>
        <div class="brand-sub">Quality Intelligence</div>
      </div>
    </div>

    <!-- Navigation Filters Area -->
    <div class="sidebar-filters-container">
      <GlobalFilter />
    </div>

    <!-- Sidebar Footer (Status & Time Capsule) -->
    <div class="sidebar-footer">
      <div class="footer-capsule">
        <div :class="['api-status', apiOk ? 'ok' : 'err']">
          <span class="status-dot" />
          {{ apiOk ? '服务正常' : '后端离线' }}
        </div>
        <div class="footer-divider">|</div>
        <div class="time-display">{{ currentTime }}</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import GlobalFilter from '../filters/GlobalFilter.vue'
import axios from 'axios'

const apiOk = ref(false)
const currentTime = ref('')
let timer = null
let clockTimer = null

async function checkApi() {
  try {
    await axios.get('http://127.0.0.1:8000/', { timeout: 3000 })
    apiOk.value = true
  } catch {
    apiOk.value = false
  }
}

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  checkApi()
  updateClock()
  timer = setInterval(checkApi, 15000)
  clockTimer = setInterval(updateClock, 1000)
})

onUnmounted(() => {
  clearInterval(timer)
  clearInterval(clockTimer)
})
</script>

<style scoped>
.app-sidebar {
  width: var(--sidebar-w, 290px);
  background: #f8fafc; /* 💡 莫兰迪灰蓝背景 */
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
  flex-shrink: 0;
  box-shadow: 1px 0 0 rgba(15, 23, 42, 0.05);
}

.sidebar-brand {
  padding: 24px 24px 16px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 36px;
  height: 36px;
  background: var(--c-accent-light);
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--c-text-primary);
  letter-spacing: -0.01em;
}

.brand-sub {
  font-size: 11px;
  color: var(--c-text-muted);
  margin-top: 1px;
}

.sidebar-filters-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 20px 20px;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
}

.footer-capsule {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  padding: 8px 14px;
  border-radius: 20px;
  box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.05);
}

.footer-divider {
  color: #cbd5e1;
  font-size: 12px;
  user-select: none;
}

.api-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
}
.api-status.ok  { color: var(--c-success); }
.api-status.err { color: var(--c-danger);  }

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}

.time-display {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary);
  font-family: 'JetBrains Mono', monospace;
}
</style>
