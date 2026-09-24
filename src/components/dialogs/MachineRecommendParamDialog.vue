<template>
  <el-dialog
    v-model="dialogVisible"
    :width="hasStatusComparison ? '1040px' : '760px'"
    top="9vh"
    destroy-on-close
    append-to-body
    class="rec-param-dialog"
  >
    <!-- 自定义弹窗头部：机台名称 + 推荐属性标签 -->
    <template #header>
      <div class="rec-dialog-header">
        <div class="header-left">
          <span class="dialog-title-text">{{ machine }} 机台参数推荐</span>
          <span
            v-if="recData?.has_recommendation"
            class="rec-header-badge"
            :class="isSameMachine ? 'badge-same' : 'badge-cross'"
          >
            {{ isSameMachine ? '🟢 同机台参数推荐' : `🟠 跨机台参数推荐 (来源: ${recData.source_machine})` }}
          </span>
          <span v-else-if="recData && !recData.has_recommendation" class="rec-header-badge badge-neutral">
            ⚪ 暂无推荐参数
          </span>
        </div>

        <!-- 控制区：默认只展示结果，点击展开/隐藏推荐修改前状态列 -->
        <div v-if="recData?.has_recommendation && hasStatusComparison" class="header-controls">
          <el-button
            size="small"
            :type="showPreState ? 'primary' : 'default'"
            :class="['btn-toggle-pre-state', { 'is-active': showPreState }]"
            @click="showPreState = !showPreState"
          >
            <el-icon style="margin-right: 4px;">
              <Hide v-if="showPreState" />
              <View v-else />
            </el-icon>
            {{ showPreState ? '只看结果' : '展示修改前状态' }}
          </el-button>
        </div>
      </div>
    </template>

    <!-- 头部统一风格元信息标签栏 (精简为三个核心标签: 规格、当前日期、推荐参数日期) -->
    <div class="rec-meta-bar">
      <div class="meta-pill">
        <span class="meta-pill-label">规格</span>
        <span class="meta-pill-val font-mono">{{ article }}</span>
      </div>
      <!-- 当前日期 -->
      <div v-if="recData?.has_recommendation" class="meta-pill meta-pill-highlight">
        <span class="meta-pill-label">当前日期</span>
        <span class="meta-pill-val font-mono">{{ recData.current_base_date || recData.baseline_status_date || targetDate }}</span>
      </div>
      <!-- 推荐参数日期 (点击可展开/收起生产表现对比) -->
      <div
        v-if="recData?.has_recommendation && (recData.recommend_event_date || recData.best_event_time)"
        class="meta-pill meta-pill-rec-date is-clickable-pill"
        :class="{ 'is-active-pill': showCgrsPanel }"
        @click="onTopDatePillClick"
        :title="showCgrsPanel ? '点击收起生产表现与调参趋势对比' : '点击展开生产表现与调参趋势对比'"
      >
        <span class="meta-pill-label">推荐参数日期</span>
        <span class="meta-pill-val font-mono">{{ selectedEventTime || recData.recommend_event_date || recData.best_event_time }}</span>
        <el-icon class="pill-expand-icon" :class="{ 'is-rotated': showCgrsPanel }">
          <ArrowDown />
        </el-icon>
      </div>
    </div>

    <!-- 推荐调参对应的 CGRS 生产表现与趋势分析折叠面板 (点击顶端推荐调参选取日期展开) -->
    <el-collapse-transition>
      <div v-if="showCgrsPanel" class="cgrs-embedded-panel-card">
        <div class="embedded-panel-header">
          <div class="embedded-panel-title">
            <span class="pulse-indicator"></span>
            <span><strong>{{ isCu ? '硫化机' : '成型机' }} [{{ recData?.source_machine || recData?.recommend_machine || machine }}]</strong> CGRS 调参生产表现与全工序实测趋势</span>
            <span v-if="selectedEventTime || recData?.recommend_event_date" class="panel-event-tag">
              调参事件: {{ selectedEventTime || recData?.recommend_event_date || recData?.best_event_time }}
            </span>
          </div>
          <button type="button" class="embedded-close-btn" @click="showCgrsPanel = false">
            收起面板 ✕
          </button>
        </div>
        <div class="embedded-panel-body">
          <CgrsRecordPanel
            :machine="recData?.source_machine || recData?.recommend_machine || machine"
            :date="formatShortDate(selectedEventTime || recData?.recommend_event_date || recData?.best_event_time)"
            :event-time="selectedEventTime || recData?.best_event_time || recData?.recommend_event_date"
            :article="article"
            :indicator="indicator"
            :recommend-reason="reason"
            :hide-recommend-btn="true"
          />
        </div>
      </div>
    </el-collapse-transition>

    <!-- Loading 状态 -->
    <div v-if="loading" class="rec-state-box">
      <el-icon class="is-loading" size="26" style="color: #f59e0b;"><Loading /></el-icon>
      <span style="margin-left: 10px; font-size: 13.5px; color: #64748b; font-weight: 500;">
        正在读取机台工艺参数底表并对齐历史优质调参推荐...
      </span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="rec-state-box state-empty">
      <el-icon size="26" style="color: #ef4444;"><CircleCloseFilled /></el-icon>
      <div class="empty-msg">
        <div class="msg-title">参数数据加载失败</div>
        <div class="msg-desc">{{ error }}</div>
      </div>
    </div>

    <!-- 无推荐调参记录状态 (明确提示未查询到修改记录，绝不强行展示表格) -->
    <div v-else-if="!recData || !recData.has_recommendation" class="rec-state-box state-empty">
      <el-icon size="28" style="color: #94a3b8;"><InfoFilled /></el-icon>
      <div class="empty-msg">
        <div class="msg-title">未匹配到推荐调参记录</div>
        <div class="msg-desc">
          历史生产数据中未查询到针对规格 [{{ article }}] 且质量优于该机台的正向调参记录
        </div>
      </div>
    </div>

    <!-- 内容展示区 -->
    <div v-else class="rec-content-wrap">
      <!-- 模式 A: 成功匹配到工艺底表快照，四列状态全息对比表格 -->
      <el-table
        v-if="hasStatusComparison"
        :data="filteredStatusParams"
        class="rec-params-table status-comp-table"
        size="small"
        style="width: 100%"
        max-height="540"
        :row-class-name="tableRowClassName"
      >
        <!-- 1. 参数名称与工步 -->
        <el-table-column label="工序参数名称" min-width="220">
          <template #default="{ row }">
            <div class="param-name-cell">
              <div class="param-top-line">
                <span class="param-cn" :class="{ 'param-cn-highlight': row.is_changed }">{{ row.param_name }}</span>
                <span v-if="row.is_changed" class="changed-tag">★ 推荐调整</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 2. 【第一列】当前参数状态 -->
        <el-table-column min-width="150" align="right">
          <template #header>
            <div class="col-header-wrap">
              <span class="col-header-strong">当前参数状态</span>
            </div>
          </template>
          <template #default="{ row }">
            <div class="val-cell-container">
              <div class="val-cell current-val-cell font-mono">
                <span class="val-num">{{ getRowVal(row, 'current') }}</span>
                <span v-if="row.unit && hasVal(getRowVal(row, 'current'))" class="unit-text">{{ row.unit }}</span>
              </div>
              <!-- 每一个参数具体的最后修改生效时间 -->
              <div v-if="row.current_offset_date" class="param-date-caption">
                <el-tooltip :content="`该参数最近一次现场调参时间: ${row.current_offset_date}`" placement="top">
                  <span class="date-chip font-mono">
                    {{ formatDisplayDate(row.current_offset_date) }}
                  </span>
                </el-tooltip>
              </div>
              <div v-else-if="getRowVal(row, 'current') === '-'" class="param-date-caption">
                <span class="text-muted-sub">未调过 (无记录)</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 3. 【第二列】推荐修改前状态 (默认隐藏，点击按钮后展示) -->
        <el-table-column v-if="showPreState" min-width="150" align="right">
          <template #header>
            <div class="col-header-wrap">
              <span class="col-header-muted">推荐修改前状态</span>
            </div>
          </template>
          <template #default="{ row }">
            <div class="val-cell-container">
              <div class="val-cell pre-rec-val-cell font-mono">
                <span class="val-num">{{ getRowVal(row, 'pre') }}</span>
                <span v-if="row.unit && hasVal(getRowVal(row, 'pre'))" class="unit-text">{{ row.unit }}</span>
              </div>
              <div v-if="row.recommend_event_date && hasVal(getRowVal(row, 'pre'))" class="param-date-caption">
                <el-tooltip :content="`点击在上方查看该调参事件生产表现: ${row.recommend_event_date}`" placement="top">
                  <span
                    class="date-chip font-mono is-clickable-tag"
                    @click.stop="onDateChipClick(row.recommend_event_date)"
                  >
                    {{ formatDisplayDate(row.recommend_event_date) }}
                  </span>
                </el-tooltip>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 4. 【第三列】推荐修改后状态 -->
        <el-table-column min-width="160" align="right">
          <template #header>
            <div class="col-header-wrap">
              <span class="col-header-highlight">推荐修改后状态</span>
            </div>
          </template>
          <template #default="{ row }">
            <div class="val-cell-container">
              <div class="val-cell rec-after-cell font-mono" :class="{ 'rec-val-changed': row.is_changed }">
                <span class="val-num">{{ getRowVal(row, 'post') }}</span>
                <span v-if="row.unit && hasVal(getRowVal(row, 'post'))" class="unit-text">{{ row.unit }}</span>
              </div>
              <!-- 推荐方案日期标记 (保持与当前参数状态时间标签完全相同的标准样式) -->
              <div v-if="row.recommend_event_date && hasVal(getRowVal(row, 'post'))" class="param-date-caption">
                <el-tooltip :content="`本次推荐参数源于调参事件: ${row.recommend_event_date}（点击在上方查看生产表现与全工序趋势）`" placement="top">
                  <span
                    class="date-chip font-mono is-clickable-tag"
                    @click.stop="onDateChipClick(row.recommend_event_date)"
                  >
                    {{ formatDisplayDate(row.recommend_event_date) }}
                  </span>
                </el-tooltip>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 5. 【第四列】修改变化 -->
        <el-table-column label="修改变化" min-width="110" align="center">
          <template #default="{ row }">
            <template v-if="row.is_changed && getRowChange(row)">
              <span class="change-diff-pill font-mono" :class="getChangeBadgeClass(row.change_value ?? row.change_delta_value)">
                {{ getRowChange(row) }}
              </span>
            </template>
            <template v-else-if="!row.is_changed && getRowChange(row)">
              <el-tooltip content="当前参数与历史最优工况设定的标杆差异 (Gap)" placement="top">
                <span class="change-diff-pill font-mono badge-diff-gap">
                  {{ getRowChange(row) }}
                </span>
              </el-tooltip>
            </template>
            <span v-else class="val-empty-dash">-</span>
          </template>
        </el-table-column>
      </el-table>

      <!-- 模式 B: 硫化机或当期无原始底表快照时，仅展示真实调参记录明细 -->
      <el-table
        v-else
        :data="recData.params"
        size="small"
        style="width: 100%"
        max-height="540"
      >
        <!-- 1. 参数项信息 -->
        <el-table-column label="推荐调整工艺参数" min-width="220">
          <template #default="{ row }">
            <div class="param-name-cell">
              <span class="param-cn">{{ row.param_name }}</span>
            </div>
          </template>
        </el-table-column>

        <!-- 2. 工段类型 -->
        <el-table-column label="工序工段" width="110" align="center">
          <template #default="{ row }">
            <span class="stage-tag font-mono">{{ row.stage }}</span>
          </template>
        </el-table-column>

        <!-- 3. 参数变更轨迹 -->
        <el-table-column label="参数变更轨迹" min-width="200">
          <template #default="{ row }">
            <div class="trajectory-cell font-mono">
              <span class="from-num">{{ row.setting_from }}</span>
              <span class="arrow-symbol">➔</span>
              <span class="to-pill">{{ row.setting_to }}</span>
              <span v-if="row.unit" class="unit-text">{{ row.unit }}</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Loading, InfoFilled, CircleCloseFilled, View, Hide, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import CgrsRecordPanel from './CgrsRecordPanel.vue'

const props = defineProps({
  visible:        { type: Boolean, default: false },
  machine:        { type: String, default: '' },
  article:        { type: String, default: '' },
  targetDate:     { type: String, default: '' },
  workcenterType: { type: String, default: 'gt' },
  indicator:      { type: String, default: 'rfpp' },
  reason:         { type: String, default: 'degradation' }
})

const emit = defineEmits(['update:visible'])

// 双向绑定弹窗显示状态，采用官方 computed get/set 消除 watch 滞后与状态竞争
const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const loading = ref(false)
const error = ref(null)
const recData = ref(null)
const selectedEventTime = ref('') // 当前选中的具体调参事件时间戳
const showPreState = ref(false) // 默认只展示结果（不展示推荐修改前状态列）
const showCgrsPanel = ref(false) // 默认收起 CGRS 面板，点击日期胶囊可展开

const isCu = computed(() => {
  const m = String(props.machine || '').toUpperCase()
  return m.startsWith('CU') || m.startsWith('CT') || String(props.workcenterType).toLowerCase() in { ct: 1, cu: 1 }
})

const isSameMachine = computed(() => {
  if (!recData.value) return true
  return recData.value.recommend_category === 'same_machine' || recData.value.source_type === 'same_machine_best'
})

// 是否包含多工序工艺参数状态对比表 (只要包含 status_comparison 数据即渲染四列全息看板)
const hasStatusComparison = computed(() => {
  return Boolean(
    recData.value?.status_comparison &&
    Array.isArray(recData.value.status_comparison) &&
    recData.value.status_comparison.length > 0
  )
})

// 表格参数列表（直接输出状态对比全量数据）
const filteredStatusParams = computed(() => {
  if (!hasStatusComparison.value) return []
  return recData.value.status_comparison
})

function tableRowClassName({ row }) {
  if (row.is_changed) {
    return 'row-highlight-changed'
  }
  return ''
}

function getChangeBadgeClass(val) {
  if (val === null || val === undefined) return ''
  const num = Number(val)
  if (!isNaN(num) && Math.abs(num) < 0.0001) return 'badge-diff-zero'
  return num > 0 ? 'badge-diff-pos' : 'badge-diff-neg'
}

function getRowVal(row, type) {
  if (!row) return '-'
  if (type === 'current') {
    return row.current_value_formatted || row.current_status_display || (row.current_value !== null && row.current_value !== undefined ? String(row.current_value) : '-')
  }
  if (type === 'pre') {
    return row.pre_recommended_value_formatted || row.recommend_before_display || (row.pre_recommended_value !== null && row.pre_recommended_value !== undefined ? String(row.pre_recommended_value) : '-')
  }
  if (type === 'post') {
    return row.recommended_value_formatted || row.recommend_after_display || (row.recommended_value !== null && row.recommended_value !== undefined ? String(row.recommended_value) : '-')
  }
  return '-'
}

function hasVal(v) {
  return Boolean(v && v !== '-' && v !== '')
}

function getRowChange(row) {
  if (!row) return ''
  return row.change || row.change_delta_display || ''
}

function formatShortDate(d) {
  if (!d) return ''
  const str = String(d).trim()
  return str.slice(0, 10)
}

function formatDisplayDate(d) {
  if (!d) return ''
  const str = String(d).trim()
  // 去除 4 位年份前缀，呈现更紧凑美观的 MM-DD HH:mm 或 MM-DD
  return str.replace(/^\d{4}-/, '')
}

function formatInheritedTag(d) {
  if (!d) return ''
  const str = String(d).trim().slice(0, 10)
  return str.replace(/^\d{4}-/, '')
}

function onTopDatePillClick() {
  showCgrsPanel.value = !showCgrsPanel.value
  if (showCgrsPanel.value && !selectedEventTime.value) {
    selectedEventTime.value = recData.value?.best_event_time || recData.value?.recommend_event_date || ''
  }
}

function onDateChipClick(dtStr) {
  if (!dtStr) return
  selectedEventTime.value = String(dtStr).trim()
  showCgrsPanel.value = true
}

watch(() => props.visible, (v) => {
  if (v && props.machine) {
    showPreState.value = false // 每次打开弹窗默认只展示结果
    showCgrsPanel.value = false // 每次打开弹窗默认收起面板
    selectedEventTime.value = ''
    fetchRecommendedParams()
  }
})

async function fetchRecommendedParams() {
  loading.value = true
  error.value = null
  recData.value = null
  selectedEventTime.value = ''

  try {
    const params = new URLSearchParams({
      machine: props.machine,
      article10: props.article,
      workcenter_type: isCu.value ? 'ct' : 'gt',
      indicator: props.indicator || 'rfpp',
      target_date: props.targetDate || '',
      reason: props.reason || 'degradation'
    })
    const res = await fetch(`/api/cgrs/recommended-params?${params.toString()}`)
    const json = await res.json()
    if (json.status === 'success') {
      recData.value = json
      selectedEventTime.value = json.best_event_time || json.recommend_event_date || ''
    } else {
      error.value = json.message || '获取推荐数据失败'
    }
  } catch (e) {
    console.error('fetchRecommendedParams error:', e)
    error.value = '网络请求异常，无法加载推荐参数'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.rec-param-dialog :deep(.el-dialog__body) {
  padding: 14px 20px 18px;
  background: #ffffff;
}

/* 弹窗头部：标题 + 胶囊徽标 + 筛选控制区 */
.rec-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-right: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-toggle-pre-state {
  font-weight: 500;
  border-radius: 6px;
  font-size: 12.5px;
  padding: 6px 12px;
  border-color: #cbd5e1;
  color: #334155;
  transition: all 0.2s ease;
}

.btn-toggle-pre-state:hover {
  border-color: #3b82f6;
  color: #2563eb;
  background-color: #eff6ff;
}

.btn-toggle-pre-state.is-active {
  background-color: #2563eb !important;
  border-color: #2563eb !important;
  color: #ffffff !important;
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.25);
}

.dialog-title-text {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.rec-header-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  line-height: 1.5;
}

.badge-same {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #a7f3d0;
}

.badge-cross {
  background: #fff7ed;
  color: #c2410c;
  border: 1px solid #fed7aa;
}

.badge-neutral {
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #e2e8f0;
}

/* 头部元信息栏 */
.rec-meta-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 4px 11px;
  font-size: 12px;
  line-height: 1.4;
  gap: 6px;
}

.meta-pill-label {
  color: #64748b;
  font-weight: 500;
}

.meta-pill-val {
  color: #0f172a;
  font-weight: 600;
}

.meta-pill-highlight {
  background: #eff6ff;
  border-color: #bfdbfe;
}
.meta-pill-highlight .meta-pill-label {
  color: #1d4ed8;
}
.meta-pill-highlight .meta-pill-val {
  color: #1e40af;
}

.meta-pill-changed {
  background: #fef3c7;
  border-color: #fde68a;
}

.meta-pill-rec-date {
  background: #fffbeb;
  border-color: #fde68a;
}

.meta-pill-rec-date .meta-pill-label {
  color: #b45309;
}

.meta-pill-rec-date .meta-pill-val {
  color: #92400e;
}

.is-clickable-pill {
  cursor: pointer;
  user-select: none;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.is-clickable-pill:hover {
  background: #fef3c7;
  border-color: #f59e0b;
  box-shadow: 0 2px 6px rgba(245, 158, 11, 0.15);
  transform: translateY(-1px);
}

.is-clickable-pill.is-active-pill {
  background: #fef3c7;
  border-color: #d97706;
  box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.2);
}

.pill-expand-icon {
  font-size: 12px;
  color: #d97706;
  margin-left: 2px;
  transition: transform 0.25s ease;
}

.pill-expand-icon.is-rotated {
  transform: rotate(180deg);
}

/* 嵌入式 CGRS 生产表现与趋势折叠面板 */
.cgrs-embedded-panel-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 16px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.embedded-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
}

.embedded-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #334155;
}

.pulse-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.25);
}

.embedded-close-btn {
  background: transparent;
  border: none;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.embedded-close-btn:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.embedded-panel-body {
  padding: 12px 14px;
  max-height: 580px;
  overflow-y: auto;
}

/* 说明条 */
.table-sub-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 11.5px;
  color: #64748b;
}

.sub-header-tip {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tip-icon {
  font-size: 13px;
}

.sub-header-counts {
  font-weight: 600;
  color: #475569;
}

/* 状态框 */
.rec-state-box {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px dashed #cbd5e1;
}

.state-empty {
  flex-direction: column;
  gap: 8px;
}

.empty-msg {
  text-align: center;
}

.msg-title {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 4px;
}

.msg-desc {
  font-size: 12px;
  color: #64748b;
}

/* 表格主体 */
.rec-content-wrap {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.rec-params-table {
  width: 100%;
}

.rec-params-table :deep(th.el-table__cell) {
  background: #f8fafc;
  color: #475569;
  font-weight: 600;
  font-size: 12.5px;
  padding: 9px 0;
  border-bottom: 1px solid #e2e8f0;
}

.rec-params-table :deep(td.el-table__cell) {
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
}

/* 修改项整行高亮 */
.status-comp-table :deep(.row-highlight-changed) {
  background-color: #fffbeb !important;
}

.status-comp-table :deep(.row-highlight-changed:hover > td.el-table__cell) {
  background-color: #fef3c7 !important;
}

.param-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.local-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #0f172a;
}

.text-bold-changed {
  color: #92400e;
  font-weight: 700;
}

.changed-tag {
  font-size: 10.5px;
  font-weight: 700;
  color: #b45309;
  background: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 4px;
  padding: 1px 6px;
  line-height: 1.4;
}

.param-name-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.param-top-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.param-cn {
  font-size: 13.5px;
  font-weight: 600;
  color: #0f172a;
}

.param-cn-highlight {
  font-weight: 700;
  color: #92400e;
}

.param-en {
  font-size: 11px;
  color: #64748b;
  line-height: 1.2;
}

.step-pill {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #e2e8f0;
  line-height: 1.4;
  white-space: nowrap;
}

.step-cu {
  background: #eff6ff;
  color: #2563eb;
  border-color: #bfdbfe;
}

.step-gt {
  background: #f0fdf4;
  color: #15803d;
  border-color: #bbf7d0;
}

.changed-tag {
  font-size: 11px;
  font-weight: 700;
  color: #b45309;
  background: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 4px;
  padding: 1px 7px;
  line-height: 1.4;
  white-space: nowrap;
}

/* 单元格数值与表头 */
.col-header-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.col-header-strong {
  font-weight: 700;
  color: #0f172a;
}

.col-header-muted {
  font-weight: 600;
  color: #64748b;
}

.col-header-highlight {
  font-weight: 700;
  color: #b45309;
}

.col-header-date-badge {
  font-size: 10px;
  font-weight: 600;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 3px;
  padding: 0 4px;
  line-height: 1.4;
  letter-spacing: -0.2px;
}

.badge-rec-date {
  color: #b45309;
  background: #fffbeb;
  border-color: #fde68a;
}

.meta-pill-rec-date {
  background: #fffbeb;
  border-color: #fde68a;
}
.meta-pill-rec-date .meta-pill-label {
  color: #b45309;
}
.meta-pill-rec-date .meta-pill-val {
  color: #92400e;
}

.val-cell-container {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.val-cell {
  display: inline-flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 4px;
}

.val-num {
  font-size: 13.5px;
  font-weight: 700;
  color: #1e293b;
}

.unit-text {
  font-size: 11px;
  color: #64748b;
  font-weight: 500;
}

.param-date-caption {
  font-size: 10px;
  line-height: 1.3;
}

.date-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  color: #475569;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 3px;
  padding: 0 4px;
  cursor: help;
  transition: all 0.15s ease;
}

.date-chip:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.date-chip-rec {
  color: #b45309;
  background: #fffbeb;
  border-color: #fde68a;
}

.date-chip-rec:hover {
  background: #fef3c7;
  color: #78350f;
}

.is-clickable-tag {
  cursor: pointer !important;
  user-select: none;
}

.is-clickable-tag:hover {
  background-color: #e2e8f0;
  color: #0f172a;
}

.panel-event-tag {
  display: inline-flex;
  align-items: center;
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 11.5px;
  font-weight: 600;
  margin-left: 8px;
}

.date-chip-inherited {
  color: #0369a1;
  background: #f0f9ff;
  border-color: #bae6fd;
}

.date-chip-inherited:hover {
  background: #e0f2fe;
}

.inherited-tag {
  color: #0284c7;
  font-weight: 600;
  margin-left: 2px;
}

.text-muted-sub {
  color: #94a3b8;
  font-size: 10px;
}

.val-empty-dash {
  color: #94a3b8;
  font-size: 13px;
}

.rec-val-changed {
  background: transparent;
  padding: 0;
  border: none;
}

.rec-val-changed .val-num {
  color: #b45309;
  font-weight: 700;
}

.change-diff-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  height: 22px;
  padding: 0 8px;
  border-radius: 11px;
  font-size: 12px;
  font-weight: 700;
}

.badge-diff-pos {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #a7f3d0;
}

.badge-diff-neg {
  background: #fff7ed;
  color: #c2410c;
  border: 1px solid #fed7aa;
}

.badge-diff-zero {
  background: #f8fafc;
  color: #475569;
  border: 1px solid #cbd5e1;
}

.badge-diff-gap {
  background: #f8fafc;
  color: #334155;
  border: 1px dashed #94a3b8;
  cursor: help;
}

.date-chip-empty {
  color: #94a3b8;
  background: #f8fafc;
  border-color: #e2e8f0;
  font-style: italic;
}

.date-chip-bench {
  color: #0369a1;
  background: #f0f9ff;
  border-color: #bae6fd;
}

.empty-placeholder {
  display: inline-block;
  width: 20px;
}

/* 硫化机旧视图轨迹 */
.trajectory-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.from-num {
  color: #64748b;
  font-weight: 500;
}

.arrow-symbol {
  color: #94a3b8;
  font-size: 12px;
}

.to-pill {
  background: #e0f2fe;
  color: #0369a1;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: 4px;
  border: 1px solid #bae6fd;
  font-size: 13.5px;
}

.priority-tag {
  height: 18px;
  line-height: 16px;
  padding: 0 5px;
  font-size: 10.5px;
  font-weight: 700;
  border-radius: 4px;
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
  display: inline-flex;
  align-items: center;
}

.time-val {
  font-size: 12px;
  color: #334155;
}

.font-mono {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
</style>
