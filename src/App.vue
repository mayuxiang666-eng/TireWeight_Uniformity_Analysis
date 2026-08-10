<template>
  <div class="app-shell">
    <!-- Top Navigation Bar -->
    <header class="app-header">
      <div class="header-left">
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
        <div class="brand-info">
          <span class="brand-name">轮胎质量看板</span>
          <span class="brand-sub">Quality Intelligence</span>
        </div>
        <!-- 当前选中分析规格显示与重置 (使用 Element Plus 官方 closable 标签组件，避免嵌套边框) -->
        <div v-if="filterStore.selectedArticle" style="margin-left: 20px;">
          <el-tag
            size="large"
            type="primary"
            effect="light"
            closable
            @close="filterStore.resetDrillDown()"
            style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; border-radius: 6px; padding: 6px 12px; height: 32px; display: inline-flex; align-items: center;"
          >
            当前规格: {{ filterStore.selectedArticle }}
          </el-tag>
        </div>
      </div>
      
      <div class="header-right" style="display: flex; align-items: center; gap: 20px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 13px; font-weight: 600; color: #475569;">全局指标研究切换：</span>
          <el-radio-group v-model="filterStore.cpkIndicator" size="small">
            <el-radio-button value="rfpp" label="rfpp">RFPP CPK</el-radio-button>
            <el-radio-button value="rfh1" label="rfh1">RFH1 CPK</el-radio-button>
            <el-radio-button value="cony" label="cony">CONY</el-radio-button>
            <el-radio-button value="weight" label="weight">胎重 Diff</el-radio-button>
          </el-radio-group>
        </div>
        <div v-if="filterStore.cpkIndicator === 'weight'" style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 12px; color: #475569; font-weight: 600;">公差限：</span>
          <el-input-number
            v-model="filterStore.weightTolerance"
            :precision="2"
            :step="0.05"
            :min="0.05"
            :max="5.0"
            size="small"
            style="width: 90px;"
          />
          <span style="font-size: 12px; color: #64748b;">%</span>
        </div>
        <div class="footer-capsule">
          <div :class="['api-status', apiOk ? 'ok' : 'err']">
            <span class="status-dot" />
            {{ apiOk ? '服务正常' : '后端离线' }}
          </div>
          <div class="footer-divider">|</div>
          <div class="time-display">{{ currentTime }}</div>
        </div>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="app-main-content">
      <Dashboard />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import Dashboard from './views/Dashboard.vue'
import axios from 'axios'
import { useFilterStore } from './store/filter.js'

const filterStore = useFilterStore()

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
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--c-bg);
}

.app-header {
  height: 60px;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 32px;
  height: 32px;
  background: var(--c-accent-light, #eff6ff);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.brand-info {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.brand-sub {
  font-size: 10px;
  color: var(--c-text-muted, #64748b);
  line-height: 1;
  margin-top: 1px;
}

.header-right {
  display: flex;
  align-items: center;
}

.footer-capsule {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 6px 16px;
  border-radius: 20px;
  box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.03);
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
.api-status.ok  { color: var(--c-success, #10b981); }
.api-status.err { color: var(--c-danger, #ef4444);  }

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
  color: var(--c-text-secondary, #475569);
  font-family: 'JetBrains Mono', monospace;
}

.app-main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px 24px;
}
</style>
