<template>
  <div class="app-shell">
    <!-- Top Navigation Bar -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand-logo-wrap">
          <img :src="logoImg" alt="Logo" class="brand-logo-img" />
        </div>
        <div class="brand-info">
          <span class="brand-name">均匀性AI智能分析系统</span>
          <span class="brand-sub">Uniformity AI Intelligence</span>
        </div>
        <!-- 当前选中分析规格显示与重置 (使用 Element Plus 官方 closable 标签组件，避免嵌套边框) -->
        <!-- 当前选中分析规格显示与重置 (带三期/四期期别标签) -->
        <div v-if="filterStore.selectedArticle" style="margin-left: 20px;">
          <el-tag
            size="large"
            type="warning"
            effect="light"
            closable
            @close="filterStore.resetDrillDown()"
            style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; border-radius: 20px; padding: 6px 14px; height: 34px; display: inline-flex; align-items: center; background: #fffbeb; border: 1px solid #fde68a; color: #b45309;"
          >
            <span>当前规格: {{ filterStore.selectedArticle }}</span>
            <span v-if="currentArticlePhase" class="phase-tag-badge">{{ currentArticlePhase }}</span>
          </el-tag>
        </div>
      </div>
      
      <div class="header-right" style="display: flex; align-items: center; gap: 8px;">
        <!-- 全局分析维度与指标控制组 (新手引导目标 1) -->
        <div id="tour-header-filters" style="display: flex; align-items: center; gap: 8px;">
          <!-- 全局分析规格选择胶囊 -->
          <div class="nav-control-group stripe-pill">
            <div class="nav-label-badge">
              <el-icon class="nav-badge-icon"><Search /></el-icon>
              <span class="nav-control-label">规格</span>
            </div>
            <el-select
              v-model="filterStore.selectedArticle"
              filterable
              clearable
              placeholder="可手动输入查询规格"
              size="small"
              :class="['header-nav-select', 'article-select', { 'is-selected': !!filterStore.selectedArticle }]"
              popper-class="header-select-popper"
            >
              <el-option
                v-for="item in allArticles"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </div>

          <!-- 时间维度一体化选择胶囊 -->
          <div class="nav-control-group stripe-pill">
            <div class="nav-label-badge">
              <el-icon class="nav-badge-icon"><Clock /></el-icon>
              <span class="nav-control-label">时间</span>
            </div>
            <el-select
              v-model="filterStore.selectedTimeCol"
              size="small"
              class="header-nav-select time-select"
              popper-class="header-select-popper"
              placeholder="选择时间字段"
              @change="filterStore.setSelectedTimeCol"
            >
              <el-option
                v-for="item in filterStore.timeColOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>

          <!-- 班组一体化选择胶囊 -->
          <div class="nav-control-group stripe-pill">
            <div class="nav-label-badge">
              <el-icon class="nav-badge-icon"><User /></el-icon>
              <span class="nav-control-label">班组</span>
            </div>
            <el-select
              v-model="filterStore.selectedShift"
              size="small"
              class="header-nav-select shift-select"
              popper-class="header-select-popper"
              placeholder="选择班组"
              @change="filterStore.setSelectedShift"
            >
              <el-option
                v-for="item in filterStore.shiftOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>

          <!-- 全局指标一体化选择胶囊 -->
          <div class="nav-control-group stripe-pill">
            <div class="nav-label-badge">
              <el-icon class="nav-badge-icon"><DataAnalysis /></el-icon>
              <span class="nav-control-label">指标</span>
            </div>
            <el-select
              v-model="filterStore.cpkIndicator"
              size="small"
              class="header-nav-select indicator-select"
              popper-class="header-select-popper indicator-select-popper"
              placeholder="选择指标"
            >
              <el-option-group
                v-for="grp in filterStore.indicatorGroups"
                :key="grp.group"
                :label="grp.label"
              >
                <el-option
                  v-for="opt in grp.options"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                >
                  <el-tooltip
                    placement="right"
                    :show-after="120"
                    :hide-after="50"
                    popper-class="indicator-day-tooltip-popper"
                    :disabled="opt.count === undefined || opt.count === null"
                  >
                    <template #content>
                      <div class="ind-tip-box">
                        <div class="ind-tip-header">
                          <span class="ind-tip-title">{{ opt.label }} 异常数对比</span>
                          <span class="ind-tip-date">{{ opt.currDate || '' }}</span>
                        </div>
                        <div class="ind-tip-divider"></div>
                        <div class="ind-tip-list">
                          <div class="ind-tip-row">
                            <span class="ind-tip-label">前一日 {{ opt.prevDate ? `(${formatShortDate(opt.prevDate)})` : '(无前日)' }}</span>
                            <span class="ind-tip-val">
                              {{ opt.prevCount !== null && opt.prevCount !== undefined ? opt.prevCount + ' 胎' : '-' }}
                            </span>
                          </div>
                          <div class="ind-tip-row current">
                            <span class="ind-tip-label">当　日 {{ opt.currDate ? `(${formatShortDate(opt.currDate)})` : '' }}</span>
                            <span class="ind-tip-val highlight">
                              {{ opt.count !== null && opt.count !== undefined ? opt.count + ' 胎' : '-' }}
                              <span v-if="opt.growthText && opt.growthText !== '-'" :class="['ind-tip-badge', opt.growthClass]">
                                {{ opt.growthText }}
                              </span>
                            </span>
                          </div>
                          <div class="ind-tip-row">
                            <span class="ind-tip-label">后一日 {{ opt.nextDate ? `(${formatShortDate(opt.nextDate)})` : '(无次日)' }}</span>
                            <span class="ind-tip-val">
                              {{ opt.nextCount !== null && opt.nextCount !== undefined ? opt.nextCount + ' 胎' : '-' }}
                            </span>
                          </div>
                        </div>
                      </div>
                    </template>
                    <div class="indicator-option-row">
                      <span class="indicator-opt-name" :class="{ 'is-max': opt.isMax }">
                        {{ opt.label }}
                      </span>
                      <span
                        v-if="opt.growthText && opt.growthText !== '-'"
                        :class="['indicator-opt-growth', opt.growthClass, { 'is-max-growth': opt.isMax }]"
                      >
                        {{ opt.growthText }}
                      </span>
                    </div>
                  </el-tooltip>
                </el-option>
              </el-option-group>
            </el-select>
          </div>
        </div>

        <!-- 状态与时钟胶囊 -->
        <div class="footer-capsule">
          <div :class="['api-status', apiOk ? 'ok' : 'err']">
            <span class="status-dot" />
            {{ apiOk ? '服务正常' : '后端离线' }}
          </div>
          <div class="footer-divider">|</div>
          <div class="time-display">{{ currentTime }}</div>
        </div>

        <!-- 新手交互教程引导按钮 (新手引导目标 5) -->
        <div id="tour-help-trigger" class="tour-trigger-pill" @click="handleStartTour" title="点击重新播放看板动态新手引导">
          <el-icon class="tour-trigger-icon"><QuestionFilled /></el-icon>
          <span>新手引导</span>
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
import { ref, watch, onMounted, onUnmounted } from 'vue'
import Dashboard from './views/Dashboard.vue'
import axios from 'axios'
import { useFilterStore } from './store/filter.js'
import { api } from './api/index.js'
import { Search, Clock, DataAnalysis, Operation, User, QuestionFilled } from '@element-plus/icons-vue'
import { useDashboardTour } from './composables/useDashboardTour.js'
import logoImg from './logo.png'

const filterStore = useFilterStore()
const { startTour } = useDashboardTour()

function handleStartTour() {
  startTour(true)
}

function formatShortDate(d) {
  if (!d) return '-'
  const parts = String(d).split('-')
  return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : d
}

const apiOk = ref(false)
const currentTime = ref('')
const allArticles = ref([])
const currentArticlePhase = ref('')

watch(() => filterStore.selectedArticle, async (newVal) => {
  if (!newVal) {
    currentArticlePhase.value = ''
    return
  }
  try {
    const res = await api.getArticlePhase(newVal)
    if (res.data && res.data.status === 'success') {
      currentArticlePhase.value = res.data.data.phase_label || ''
    } else {
      currentArticlePhase.value = ''
    }
  } catch (e) {
    currentArticlePhase.value = ''
  }
}, { immediate: true })
let timer = null
let clockTimer = null
let failureCount = 0

async function checkApi() {
  try {
    const res = await axios.get('/api/etl/status', { timeout: 10000 })
    failureCount = 0
    apiOk.value = true
    if (res.data && res.data.status === 'success' && res.data.data?.last_modified) {
      filterStore.setDataUpdateTime(res.data.data.last_modified)
    }
  } catch {
    failureCount++
    if (failureCount >= 2) {
      apiOk.value = false
    }
  }
}

async function loadAllArticles() {
  try {
    const res = await api.getAllArticles()
    if (res.data && res.data.status === 'success') {
      allArticles.value = res.data.data || []
    }
  } catch (e) {
    console.error('加载全量规格列表失败:', e)
  }
}

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  checkApi()
  loadAllArticles()
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
  height: 64px;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px 0 0;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  height: 64px;
}

.brand-logo-wrap {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.brand-logo-img {
  height: 64px;
  width: auto;
  object-fit: cover;
  display: block;
}

.brand-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.2px;
  color: var(--c-text-primary, #0f172a);
  line-height: 1.2;
}

.brand-sub {
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.4px;
  color: var(--c-text-muted, #64748b);
  line-height: 1.2;
  margin-top: 2px;
}

.header-right {
  display: flex;
  align-items: center;
}

/* ── 导航栏组件专属尺寸配置 (继承全局 main.css 标准胶囊样式) ── */
.article-select {
  width: 155px;
  transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.article-select.is-selected {
  width: 122px;
}

.time-select {
  width: 145px;
}

.shift-select {
  width: 140px;
}

.indicator-select {
  width: 104px;
}

/* 嵌入式 InputNumber 尺寸与单位 */
:deep(.header-nav-input-num .el-input__wrapper) {
  background-color: transparent !important;
  box-shadow: none !important;
  border: none !important;
  padding: 0 2px !important;
  height: 26px !important;
  min-height: 26px !important;
}
:deep(.header-nav-input-num) {
  width: 75px;
}

.nav-unit-label {
  font-size: 12px;
  font-weight: 700;
  color: #b45309;
  padding-right: 4px;
}

.footer-capsule {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 34px !important;
  box-sizing: border-box !important;
  background: #fffbeb;
  border: 1px solid #fde68a;
  padding: 0 16px;
  border-radius: 20px;
  box-shadow: 0 1px 2px 0 rgba(245, 158, 11, 0.08);
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

.data-time-display {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.data-time-label {
  color: var(--c-text-muted, #64748b);
  font-weight: 500;
}

.data-time-val {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  color: #334155;
}

.time-display {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary, #475569);
  font-family: 'JetBrains Mono', monospace;
}

.phase-tag-badge {
  font-size: 11px;
  background: #f59e0b;
  color: #ffffff;
  padding: 1.5px 8px;
  border-radius: 10px;
  margin-left: 8px;
  font-weight: 700;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  letter-spacing: 0.2px;
  box-shadow: 0 1px 3px rgba(245, 158, 11, 0.3);
}

.app-main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px 24px;
}
</style>
