<template>
  <div class="global-filter-vertical">
    <!-- Card 1: 规格型号 Selection -->
    <div class="filter-card">
      <div class="filter-card-title">规格型号</div>
      <el-select
        v-model="filterStore.selectedArticle"
        placeholder="全部规格"
        clearable
        filterable
        size="small"
        style="width: 100%"
        @change="onArticleChange"
      >
        <el-option
          v-for="item in articles"
          :key="item.article10"
          :label="item.article10"
          :value="item.article10"
        >
          <span>{{ item.article10 }}</span>
          <span class="option-count">{{ fmtNum(item.cnt) }}</span>
        </el-option>
      </el-select>
    </div>

    <!-- Card 2: 分析时间段 (基准期 + 研究期) -->
    <div class="filter-card">
      <div class="filter-card-title">基准对比分析期</div>
      
      <div class="sub-filter-item">
        <div class="sub-label">基准期间 (Baseline)</div>
        <el-date-picker
          v-model="filterStore.baselineRange"
          type="daterange"
          range-separator="→"
          start-placeholder="开始"
          end-placeholder="结束"
          size="small"
          style="width: 100%"
          value-format="YYYY-MM-DD"
          :disabled-date="disabledDate"
          :clearable="false"
        />
      </div>

      <div class="sub-filter-item mt-8">
        <div class="sub-label">研究期间 (Study)</div>
        <el-date-picker
          v-model="filterStore.studyRange"
          type="daterange"
          range-separator="→"
          start-placeholder="开始"
          end-placeholder="结束"
          size="small"
          style="width: 100%"
          value-format="YYYY-MM-DD"
          :disabled-date="disabledDate"
          :clearable="false"
        />
      </div>
    </div>

    <!-- Card 3: 样本量过滤门槛 (Min Yield) -->
    <div class="filter-card">
      <div class="filter-card-title" style="display: inline-flex; align-items: center; justify-content: space-between; width: 100%">
        <span>样本过滤门槛</span>
        <el-tooltip content="设定最小排产件数。系统将过滤产量低于此数值的设备、路径以及配对，消除小样本干扰。">
          <el-icon class="info-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
      <el-input-number
        v-model="filterStore.minYieldThreshold"
        :min="0"
        :step="10"
        size="small"
        style="width: 100%"
        controls-position="right"
      />
    </div>



    <!-- 下钻提示 Badge -->
    <transition name="fade">
      <div v-if="filterStore.isDrillDown" class="drill-badge-vertical">
        <el-icon><ZoomIn /></el-icon>
        <span class="truncate">下钻：{{ filterStore.drillDownTarget }}</span>
        <el-button
          size="small"
          text
          :icon="Close"
          @click="filterStore.resetDrillDown()"
          style="margin-top: 6px; color: var(--c-danger); width: 100%;"
        >返回全局总览</el-button>
      </div>
    </transition>

    <!-- Reset Buttons -->
    <div class="filter-actions">
      <el-button
        size="small"
        :icon="Refresh"
        class="reset-btn-flat"
        @click="filterStore.reset()"
      >
        重置所有筛选器
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useFilterStore } from '../../store/filter.js'
import { api } from '../../api/index.js'
import { Refresh, Close, ZoomIn, QuestionFilled } from '@element-plus/icons-vue'

const filterStore = useFilterStore()
const articles = ref([])
const dateRange = ref(null)

async function loadFilterArticles() {
  try {
    const res = await api.getFilterArticles({
      min_yield: filterStore.minYieldThreshold > 0 ? 50 : 0
    })
    if (res.data.status === 'success') {
      articles.value = res.data.data
    }
  } catch (e) {
    console.error('获取过滤规格列表失败', e)
  }
}

onMounted(async () => {
  try {
    const drRes = await api.getDateRange()
    if (drRes.data.status === 'success') {
      dateRange.value = drRes.data.data
      
      if (!filterStore.baselineRange && !filterStore.studyRange) {
        const dMin = new Date(dateRange.value.date_min)
        const dMax = new Date(dateRange.value.date_max)
        const diffTime = Math.abs(dMax - dMin)
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
        const midPoint = new Date(dMin.getTime() + (Math.floor(diffDays / 2)) * (1000 * 60 * 60 * 24))
        const midPointStr = midPoint.toISOString().slice(0, 10)
        const midPointPlus1 = new Date(midPoint.getTime() + (1000 * 60 * 60 * 24))
        const midPointPlus1Str = midPointPlus1.toISOString().slice(0, 10)

        filterStore.baselineRange = [dateRange.value.date_min, midPointStr]
        filterStore.studyRange = [midPointPlus1Str, dateRange.value.date_max]
      }
    }
  } catch (e) {
    console.error('过滤器初始化失败', e)
  }
  await loadFilterArticles()
})

watch(
  () => filterStore.minYieldThreshold,
  () => {
    loadFilterArticles()
  }
)

function disabledDate(t) {
  if (!dateRange.value) return false
  const d = t.toISOString().slice(0, 10)
  return d < dateRange.value.date_min || d > dateRange.value.date_max
}

function onArticleChange(val) {
  if (!val && filterStore.isDrillDown) {
    filterStore.resetDrillDown()
  }
}

function fmtNum(n) {
  return Number(n).toLocaleString()
}
</script>

<style scoped>
.global-filter-vertical {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

/* 过滤分组白色卡片样式 */
.filter-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: var(--radius-md);
  padding: 14px 16px;
  box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 小标题带左指示条 */
.filter-card-title {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  letter-spacing: 0.02em;
  display: flex;
  align-items: center;
  gap: 6px;
  padding-left: 6px;
  border-left: 2px solid var(--c-accent);
}

/* 子滤项标题 */
.sub-filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sub-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--c-text-secondary);
}

.info-icon {
  font-size: 13px;
  color: var(--c-text-muted);
  cursor: pointer;
  transition: color 0.15s ease;
}
.info-icon:hover {
  color: var(--c-accent);
}

.option-count {
  float: right;
  font-size: 11px;
  color: var(--c-text-muted);
  font-family: 'JetBrains Mono', monospace;
}

.drill-badge-vertical {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  background: var(--c-accent-light);
  border: 1px solid #bfdbfe;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  color: var(--c-accent);
  box-shadow: 0 1px 2px 0 rgba(37, 99, 235, 0.05);
}

.filter-actions {
  margin-top: 4px;
}

/* 扁平重置按钮 */
.reset-btn-flat {
  width: 100%;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #475569;
  font-weight: 600;
  transition: all 0.2s ease;
  height: 32px;
  border-radius: var(--radius-sm);
}
.reset-btn-flat:hover {
  background: #f1f5f9;
  color: var(--c-text-primary);
  border-color: #cbd5e1;
}

/* 穿透重绘 Element Plus 控件，打造扁平无缝质感 */
:deep(.el-input__wrapper),
:deep(.el-select .el-input__wrapper) {
  background-color: #f8fafc !important; /* 淡灰背景 */
  border: 1px solid #e2e8f0 !important;
  box-shadow: none !important;
  border-radius: var(--radius-sm) !important;
  transition: border-color 0.15s ease;
  padding: 0 8px !important;
}
:deep(.el-input__wrapper:hover),
:deep(.el-select .el-input__wrapper:hover) {
  border-color: #cbd5e1 !important;
}
:deep(.el-input__wrapper.is-focus),
:deep(.el-select .el-input__wrapper.is-focus) {
  border-color: var(--c-accent) !important;
}

/* 极简步进器加减号微调 */
:deep(.el-input-number.is-controls-right .el-input-number__decrease),
:deep(.el-input-number.is-controls-right .el-input-number__increase) {
  border-left: 1px solid #e2e8f0 !important;
  background: #f1f5f9 !important;
}

/* 胶囊单选 Radio-Group 重塑 */
.pill-radio-group :deep(.el-radio-button) {
  flex: 1;
}
.pill-radio-group :deep(.el-radio-button__inner) {
  width: 100%;
  text-align: center;
  border: 1px solid #e2e8f0 !important;
  background: #ffffff;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.2s ease;
}
.pill-radio-group :deep(.el-radio-button__orig-radio:checked + .el-radio-button__inner) {
  background-color: var(--c-accent-light) !important;
  color: var(--c-accent) !important;
  border-color: #bfdbfe !important;
  box-shadow: none !important;
}
.pill-radio-group :deep(.el-radio-button:first-child .el-radio-button__inner) {
  border-right: none !important;
}

/* 对齐双日期输入框 */
:deep(.el-range-editor.el-input__inner) {
  padding: 0 8px !important;
}
:deep(.el-range-input) {
  font-size: 11px !important;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 500;
  width: 42% !important;
}
:deep(.el-range-separator) {
  font-size: 11px !important;
  color: #94a3b8;
  padding: 0 !important;
  width: 10% !important;
}
</style>
