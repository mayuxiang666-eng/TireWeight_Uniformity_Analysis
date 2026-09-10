<template>
  <el-dialog
    v-model="dialogVisible"
    width="760px"
    top="10vh"
    destroy-on-close
    append-to-body
    class="rec-param-dialog"
  >
    <!-- 自定义弹窗头部：机台名称 + 同机台/跨机台胶囊标签 -->
    <template #header>
      <div class="rec-dialog-header">
        <span class="dialog-title-text">{{ machine }} 机台参数推荐</span>
        <span
          v-if="recData?.has_recommendation"
          class="rec-header-badge"
          :class="isSameMachine ? 'badge-same' : 'badge-cross'"
        >
          {{ isSameMachine ? '🟢 同机台参数推荐' : `🟠 跨机台参数推荐 (来源: ${recData.source_machine})` }}
        </span>
      </div>
    </template>

    <!-- 头部统一风格元信息标签栏 (规格与检索范围保持高度统一) -->
    <div class="rec-meta-bar">
      <div class="meta-pill">
        <span class="meta-pill-label">选定规格</span>
        <span class="meta-pill-val font-mono">{{ article }}</span>
      </div>
      <div class="meta-pill">
        <span class="meta-pill-label">检索范围</span>
        <span class="meta-pill-val font-mono">基准日前 30 天历史数据</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="rec-state-box">
      <el-icon class="is-loading" size="26" style="color: #f59e0b;"><Loading /></el-icon>
      <span style="margin-left: 10px; font-size: 13.5px; color: #64748b; font-weight: 500;">
        正在回溯 {{ targetDate }} 前 30 天历史生产调参记录，筛选最优工艺参数...
      </span>
    </div>

    <!-- 错误 / 无数据 -->
    <div v-else-if="error || !recData || !recData.has_recommendation" class="rec-state-box state-empty">
      <el-icon size="26" style="color: #94a3b8;"><InfoFilled /></el-icon>
      <div class="empty-msg">
        <div class="msg-title">{{ recData?.recommend_title || '暂无历史参考调参数据' }}</div>
        <div class="msg-desc">{{ error || recData?.message || `在基准日 [${targetDate}] 前 30 天内，未查询到该规格带来质量改善的调参记录。` }}</div>
      </div>
    </div>

    <!-- 极简 3 列表格内容主体 -->
    <div v-else class="rec-content-wrap">
      <el-table
        :data="recData.params || []"
        border
        stripe
        size="default"
        class="rec-params-table"
      >
        <!-- 1. 调参时间 -->
        <el-table-column label="调参时间" width="180" align="center">
          <template #default="{ row }">
            <span class="font-mono time-val">{{ row.event_time || recData.best_event_time }}</span>
          </template>
        </el-table-column>

        <!-- 2. 参数名称 -->
        <el-table-column label="参数名称" min-width="260">
          <template #default="{ row }">
            <div class="param-name-cell">
              <div class="param-title-row">
                <span class="local-name">{{ row.param_local_name }}</span>
                <span class="priority-tag">
                  P{{ row.priority || 1 }}
                </span>
              </div>
              <span v-if="row.param_name && row.param_name !== row.param_local_name" class="sys-name font-mono">
                {{ row.param_name }}
              </span>
            </div>
          </template>
        </el-table-column>

        <!-- 3. 参数变更轨迹 (纯设定值轨迹) -->
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
import { Loading, InfoFilled } from '@element-plus/icons-vue'

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

const dialogVisible = ref(false)
const loading = ref(false)
const error = ref(null)
const recData = ref(null)

const isCu = computed(() => {
  const m = String(props.machine || '').toUpperCase()
  return m.startsWith('CU') || m.startsWith('CT') || String(props.workcenterType).toLowerCase() in { ct: 1, cu: 1 }
})

const isSameMachine = computed(() => {
  if (!recData.value) return true
  return recData.value.recommend_category === 'same_machine' || recData.value.source_type === 'same_machine_best'
})

watch(() => props.visible, (v) => {
  dialogVisible.value = v
  if (v && props.machine) {
    fetchRecommendedParams()
  }
})

watch(dialogVisible, (v) => emit('update:visible', v))

async function fetchRecommendedParams() {
  loading.value = true
  error.value = null
  recData.value = null

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

/* 弹窗头部：标题 + 胶囊徽标 */
.rec-dialog-header {
  display: flex;
  align-items: center;
  gap: 12px;
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

/* 头部统一风格元信息标签栏 */
.rec-meta-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
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

/* 状态框 */
.rec-state-box {
  height: 180px;
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
  padding: 12px 14px;
  border-bottom: 1px solid #f1f5f9;
}

.time-val {
  font-size: 12px;
  color: #334155;
}

.param-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.local-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #0f172a;
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

.sys-name {
  font-size: 10.5px;
  color: #64748b;
}

/* 设定值变更轨迹单元格 */
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

.unit-text {
  font-size: 12px;
  color: #64748b;
}

.font-mono {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
</style>


