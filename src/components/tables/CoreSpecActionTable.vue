<template>
  <div class="core-spec-table-wrap">
    <!-- Loading State -->
    <div v-if="loading" class="state-container">
      <el-icon class="is-loading" size="28" style="color: #f59e0b;"><Loading /></el-icon>
      <span class="state-text">正在分析核心预警规格与责任机台…</span>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="state-container state-error">
      <el-icon size="26"><WarningFilled /></el-icon>
      <span class="state-text">{{ error }}</span>
    </div>

    <!-- Empty State -->
    <div v-else-if="tableData.length === 0" class="state-container">
      <el-empty description="当前所选日期无符合条件的预警规格" :image-size="60" />
    </div>

    <!-- Main Table with Fixed Height and Smooth Scrolling -->
    <div v-else class="table-scroll-container">
      <el-table
        :data="tableData"
        border
        size="small"
        height="100%"
        class="core-spec-action-table"
        :span-method="arraySpanMethod"
        :row-class-name="getRowClassName"
        @row-click="handleRowClick"
      >
        <!-- 1. 预警规格 (仅显示规格代码，悬浮呈现完整诊断卡片) -->
        <el-table-column
          label="预警规格"
          prop="article10"
          min-width="115"
          align="center"
        >
          <template #default="{ row }">
            <el-tooltip
              placement="right"
              :show-after="80"
              raw-content
              popper-class="spec-diagnostic-popper"
            >
              <template #content>
                <div class="spec-tooltip-box">
                  <div class="spec-tooltip-header">
                    <span class="spec-title">规格：{{ row.article10 }}</span>
                    <span v-if="row.phase_label" class="phase-tag">{{ row.phase_label }}</span>
                  </div>
                  <div class="spec-tooltip-body">
                    <div class="metric-row">
                      <span class="m-label">{{ isWeight ? '单日规格偏差率' : '单规格 CPK' }}</span>
                      <span class="m-val highlight">{{ formatSingleVal(row.single_cpk) }}</span>
                    </div>
                    <div class="metric-row">
                      <span class="m-label">{{ isWeight ? '全厂整体偏差率' : '全厂综合 CPK' }}</span>
                      <span class="m-val">{{ formatAvgVal(row.avg_cpk) }}</span>
                    </div>
                    <div class="metric-row">
                      <span class="m-label">单日排产条数 (N)</span>
                      <span class="m-val font-mono">{{ row.sample_size || 0 }}</span>
                    </div>
                    <div class="metric-row">
                      <span class="m-label">主要责任机台</span>
                      <span class="m-val" style="color: #ef4444; font-weight: 700;">{{ row.warning_machine || '无' }}</span>
                    </div>
                    <div class="metric-row score-row">
                      <span class="m-label">{{ isWeight ? '生产偏差贡献' : 'CPK 负向贡献' }}</span>
                      <span class="m-val font-mono score-val">{{ formatScore(row.stable_score) }}</span>
                    </div>
                  </div>
                  <div class="spec-tooltip-footer">
                    {{ isWeight ? '数值越大，拉大整体偏差越严重。点击该行可同步联动全屏分析。' : '数值越大，拉低全厂质量越严重。点击该行可同步联动全屏分析。' }}
                  </div>
                </div>
              </template>
              <div class="spec-code-cell">
                <span class="spec-code-text">{{ row.article10 }}</span>
              </div>
            </el-tooltip>
          </template>
        </el-table-column>

        <!-- 2. 预警机台 (严格以小球进行基准对齐，保持在同一垂直列上) -->
        <el-table-column
          label="预警机台"
          min-width="120"
          align="center"
        >
          <template #default="{ row }">
            <el-tooltip
              placement="top"
              :show-after="80"
              popper-class="machine-diagnostic-popper"
            >
              <template #content>
                <div class="machine-tooltip-box">
                  <div class="machine-tooltip-header">
                    机台 [{{ row.warning_machine || '-' }}] 诊断分析：
                  </div>
                  <template v-if="row.status_badges && row.status_badges.length > 0">
                    <div
                      v-for="(b, idx) in row.status_badges"
                      :key="idx"
                      class="badge-detail-item"
                    >
                      <strong class="b-text">{{ b.text }}</strong>：{{ b.tooltip }}
                    </div>
                  </template>
                  <div v-else class="badge-detail-item">
                    {{ getFallbackMachineTooltip(row) }}
                  </div>
                </div>
              </template>
              <div class="machine-cell-content">
                <span class="status-ball" :class="`ball-${row.warning_level || 'yellow'}`"></span>
                <span class="machine-name">{{ row.warning_machine || '-' }}</span>
              </div>
            </el-tooltip>
          </template>
        </el-table-column>

        <!-- 3. CPK 变化率 (低饱和度优雅胶囊徽标) -->
        <el-table-column
          label="CPK 变化率"
          min-width="110"
          align="center"
        >
          <template #default="{ row }">
            <el-tooltip
              v-if="row.cpk_pct_change !== null && row.cpk_pct_change !== undefined"
              :content="`当班 CPK 相比前 3 天均值变化率: ${row.cpk_pct_change > 0 ? '+' : ''}${row.cpk_pct_change}%`"
              placement="top"
            >
              <span
                class="pct-pill"
                :class="row.cpk_pct_change < 0 ? 'pct-drop' : 'pct-rise'"
              >
                {{ row.cpk_pct_change > 0 ? '+' : '' }}{{ Number(row.cpk_pct_change).toFixed(1) }}%
              </span>
            </el-tooltip>
            <el-tooltip
              v-else-if="row.is_new_online || (row.status_badges && row.status_badges.some(b => b.text && b.text.includes('新上线')))"
              content="该机台前 3 天未生产该规格，今日新换型上线排产，处于试产磨合阶段，暂无历史对比基准"
              placement="top"
            >
              <span class="pct-pill pct-new">新上线</span>
            </el-tooltip>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>

        <!-- 4. 行动措施 (去图标低饱和度优雅胶囊按钮/标签) -->
        <el-table-column
          label="行动措施"
          min-width="145"
          align="center"
        >
          <template #default="{ row }">
            <template v-if="isRecommendButton(row)">
              <el-tooltip :content="row.action_tooltip || '点击查看该规格历史最优工艺参数推荐与基准对比'" placement="top">
                <button
                  type="button"
                  class="action-btn"
                  @click.stop="handleOpenRecommend(row)"
                >
                  {{ cleanActionText(row.action_text || '查看推荐参数') }}
                </button>
              </el-tooltip>
            </template>
            <template v-else-if="row.action_text && row.action_text !== '-'">
              <el-tooltip :content="row.action_tooltip || '机台行动建议'" placement="top">
                <span class="action-tag">
                  {{ cleanActionText(row.action_text) }}
                </span>
              </el-tooltip>
            </template>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
  selectedArticle: { type: String, default: null },
  indicator: { type: String, default: 'rfpp' },
  targetDate: { type: String, default: '' },
  isLatestDate: { type: Boolean, default: false }
})

const emit = defineEmits(['drill-down', 'open-recommend'])

const isWeight = computed(() => props.indicator === 'weight')

function isRecommendButton(row) {
  if (!row) return false
  if (row.can_click_recommend) return true
  const txt = String(row.action_text || '')
  return txt.includes('推荐参数') || txt.includes('查看')
}

// 规格行合并与明细行数据结构
const tableData = computed(() => {
  const list = props.data || []
  if (list.length === 0) return []

  // 按连续同规格计算合并行跨度与分组标记
  const result = []
  let i = 0
  let specIndex = 0
  while (i < list.length) {
    const currSpec = list[i].article10
    let j = i
    while (j < list.length && list[j].article10 === currSpec) {
      j++
    }
    const count = j - i
    for (let k = i; k < j; k++) {
      result.push({
        ...list[k],
        row_span: k === i ? count : 0,
        is_first_of_spec: k === i,
        is_last_of_spec: k === j - 1,
        spec_group_index: specIndex
      })
    }
    specIndex++
    i = j
  }
  return result
})

function arraySpanMethod({ row, column, rowIndex, columnIndex }) {
  if (columnIndex === 0) { // 预警规格列：同规格多机台纵向合并
    const span = row.row_span ?? 1
    if (span > 0) {
      return { rowspan: span, colspan: 1 }
    } else {
      return { rowspan: 0, colspan: 0 }
    }
  }
  return { rowspan: 1, colspan: 1 }
}

function getRowClassName({ row }) {
  const classes = []
  if (props.selectedArticle && props.selectedArticle === row.article10) {
    classes.push('row-selected')
  } else {
    classes.push('clickable-row')
  }
  if (row.is_last_of_spec) {
    classes.push('spec-group-last')
  }
  classes.push(row.spec_group_index % 2 === 0 ? 'spec-group-even' : 'spec-group-odd')
  return classes.join(' ')
}

function handleRowClick(row) {
  if (!row || !row.article10) return
  emit('drill-down', row.article10)
}

function handleOpenRecommend(row) {
  console.log('[CoreSpecActionTable] 点击查看推荐参数:', row)
  emit('open-recommend', row)
}

function formatSingleVal(val) {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  if (isWeight.value) {
    return (num > 0 ? '+' : '') + num.toFixed(2) + '%'
  }
  return num.toFixed(2)
}

function formatAvgVal(val) {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  if (isWeight.value) {
    return (num > 0 ? '+' : '') + num.toFixed(2) + '%'
  }
  return num.toFixed(2)
}

function formatScore(val) {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  return isWeight.value ? num.toFixed(4) : num.toFixed(1)
}

function getFallbackMachineTooltip(row) {
  if (row.warning_level === 'red') {
    return '该机台为核心恶化机台，建议重点排查'
  }
  if (row.warning_level === 'orange') {
    return '该机台 CPK 降幅显著或持续在榜，存在质量隐患'
  }
  if (row.warning_level === 'yellow') {
    return '该机台位列当日负贡献在榜机台'
  }
  return '机台运行状态正常'
}

function cleanActionText(text) {
  if (!text) return ''
  return text.replace(/^[💡\s]+/, '').trim()
}
</script>

<style scoped>
.core-spec-table-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: var(--el-bg-color, #ffffff);
}

.state-container {
  height: 100%;
  min-height: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--el-text-color-secondary, #64748b);
  font-size: 14px;
}

.state-error {
  color: #ef4444;
}

.table-scroll-container {
  width: 100%;
  height: 100%;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

/* 优化表格垂直与水平滚动条外观 */
:deep(.el-table__body-wrapper::-webkit-scrollbar),
:deep(.el-scrollbar__wrap::-webkit-scrollbar) {
  height: 6px;
  width: 6px;
}
:deep(.el-table__body-wrapper::-webkit-scrollbar-track),
:deep(.el-scrollbar__wrap::-webkit-scrollbar-track) {
  background: #f8fafc;
  border-radius: 3px;
}
:deep(.el-table__body-wrapper::-webkit-scrollbar-thumb),
:deep(.el-scrollbar__wrap::-webkit-scrollbar-thumb) {
  background: #cbd5e1;
  border-radius: 3px;
}
:deep(.el-table__body-wrapper::-webkit-scrollbar-thumb:hover),
:deep(.el-scrollbar__wrap::-webkit-scrollbar-thumb:hover) {
  background: #94a3b8;
}

.core-spec-action-table {
  width: 100%;
  height: 100%;
  min-width: 440px;
}

:deep(.el-table .clickable-row) {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

/* 规格分组交替底色与规格间粗分隔线 (低饱和度、柔和轻量) */
:deep(.el-table tr.spec-group-even td) {
  background-color: #ffffff;
}

:deep(.el-table tr.spec-group-odd td) {
  background-color: #fafbfc;
}

:deep(.el-table tr.spec-group-last td) {
  border-bottom: 2px solid #cbd5e1 !important; /* 低饱和灰蓝精致分割线 */
}

:deep(.el-table .row-selected) {
  background-color: #fffbeb !important;
  font-weight: 600;
  cursor: pointer;
}

:deep(.el-table .row-selected td) {
  background-color: #fffbeb !important;
  color: #92400e !important;
}

:deep(.el-table .row-selected td:first-child) {
  position: relative;
  box-shadow: inset 4px 0 0 #f59e0b;
}

/* 表头：字体放大 20% (14.5px)，低饱和灰，加粗 */
:deep(.el-table th.el-table__cell) {
  background-color: #f8fafc !important;
  color: #475569 !important;
  font-size: 14.5px !important;
  font-weight: 700 !important;
  border-bottom: 1px solid #e2e8f0 !important;
  padding: 8px 0 !important;
}

:deep(.el-table td.el-table__cell) {
  padding: 6px 0 !important;
  font-weight: 600;
}

/* 预警规格列：无外边框设计，纯净现代数字排版 (字号 15.5px，超粗体 800) */
.spec-code-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 4px;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  cursor: pointer;
}

.spec-code-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 15.5px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: 0.5px;
  transition: color 0.15s ease;
}

.spec-code-cell:hover .spec-code-text {
  color: #d97706;
}

/* 机台列：严格以小球进行基准对齐 (小球放大 20% 至 12px，机台字体放大 20% 至 18px，加粗 700) */
.machine-cell-content {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 98px;
  margin: 0 auto;
  gap: 9px;
  cursor: help;
}

/* 优雅低饱和质感小球 (放大 20% 至 12px) */
.status-ball {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
  border: none;
}

.ball-red {
  background: radial-gradient(circle at 35% 35%, #b91c1c 0%, #881337 65%, #4c0519 100%);
  box-shadow: none;
}

.ball-orange {
  background: radial-gradient(circle at 35% 35%, #ffa600 0%, #ff6600 65%, #d84315 100%);
  box-shadow: none;
}

.ball-yellow {
  background: radial-gradient(circle at 35% 35%, #fef08a 0%, #eab308 65%, #a16207 100%);
  box-shadow: none;
}

.ball-none {
  background: #cbd5e1;
}

.machine-name {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  letter-spacing: 0.2px;
  text-align: left;
}

/* CPK 变化率列：低饱和度优雅胶囊徽标 (字体加粗 700) */
.pct-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 26px;
  line-height: 24px;
  padding: 0 10px;
  border-radius: 13px;
  font-size: 14.5px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  letter-spacing: -0.2px;
}

.pct-drop {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
}

.pct-rise {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #16a34a;
}

.pct-new {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #b45309;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

/* 行动措施列：优雅暖金琥珀胶囊按钮 (全局黄调统一) */
.action-btn {
  font-size: 13px;
  padding: 0 12px;
  height: 26px;
  line-height: 24px;
  border-radius: 13px;
  font-weight: 700;
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #b45309;
  box-shadow: 0 1px 2px rgba(245, 158, 11, 0.08);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
}

.action-btn:hover {
  background: #fef3c7;
  border-color: #f59e0b;
  color: #92400e;
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(245, 158, 11, 0.22);
}

.action-tag {
  display: inline-flex;
  align-items: center;
  font-size: 13.5px;
  font-weight: 700;
  padding: 0 12px;
  height: 27px;
  line-height: 25px;
  border-radius: 13px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #15803d;
  box-shadow: 0 1px 2px rgba(22, 101, 52, 0.06);
  white-space: nowrap;
}

.text-muted {
  color: #94a3b8;
  font-size: 15.5px;
  font-weight: 700;
}
</style>

<style>
/* 全局 Tooltip 卡片美化 */
.spec-diagnostic-popper {
  max-width: 320px !important;
  padding: 10px 14px !important;
  border-radius: 8px !important;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2) !important;
}

.spec-tooltip-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  line-height: 1.5;
}

.spec-tooltip-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding-bottom: 5px;
  margin-bottom: 2px;
}

.spec-title {
  font-weight: 700;
  font-size: 13px;
}

.phase-tag {
  background: rgba(56, 189, 248, 0.25);
  color: #38bdf8;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.spec-tooltip-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
}

.m-label {
  color: #cbd5e1;
}

.m-val {
  font-weight: 600;
  color: #ffffff;
}

.m-val.highlight {
  color: #f87171;
  font-weight: 700;
}

.score-row {
  border-top: 1px dashed rgba(255, 255, 255, 0.15);
  padding-top: 4px;
  margin-top: 2px;
}

.score-val {
  color: #fbbf24;
  font-weight: 700;
}

.spec-tooltip-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.15);
  padding-top: 5px;
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.4;
}

.machine-diagnostic-popper {
  max-width: 330px !important;
  padding: 10px 14px !important;
  border-radius: 8px !important;
}

.machine-tooltip-box {
  font-size: 12px;
  line-height: 1.6;
}

.machine-tooltip-header {
  font-weight: 700;
  font-size: 13px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding-bottom: 4px;
  margin-bottom: 6px;
}

.badge-detail-item {
  margin-bottom: 4px;
}

.b-text {
  font-weight: 700;
}
</style>
