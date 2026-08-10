<template>
  <div class="diagnostics-panel-inner">
    
    <!-- 1. 顶部机台快速切换选择器 (取代原有左侧设备列表表格，实现防图表横向压缩) -->
    <div class="diagnostics-selector-header">
      <span class="selector-label">🔬 当前诊断机台：</span>
      <el-select
        v-model="selectedMachineKey"
        placeholder="请选择需要追溯诊断的嫌疑设备"
        style="width: 280px;"
        size="small"
        @change="onDropdownMachineChange"
      >
        <el-option
          v-for="item in suspects"
          :key="item.machine + '|' + item.workcenter_col + '|' + item.cluster"
          :label="item.machine + ' (' + item.workcenter_col.replace('_workcenter', '') + ') - Step Lift: ' + item.step_lift + 'x'"
          :value="item.machine + '|' + item.workcenter_col + '|' + item.cluster"
        />
      </el-select>
      <span class="text-muted" style="margin-left: auto;" v-if="selectedMachine">
        故障簇 Cluster {{ selectedMachine.cluster }} (基于门槛: {{ filterStore.minYieldThreshold }} 条)
      </span>
    </div>

    <!-- 下方内容滚动区域 -->
    <div class="diagnostics-scroll-body">
      <!-- 2. 物料批次提升对照直方图 -->
      <div class="compare-chart-wrap" v-if="selectedMachine">
        <div class="chart-title-sub">📈 物料批次提升对照直方图 (Local Lift vs Cross-Machine Lift)</div>
        <div style="height: 380px; width: 100%;">
          <LotCompareChart
            :data="lots"
            :loading="lotsLoading"
            :error="lotsError"
          />
        </div>
      </div>

      <!-- 3. 未选择或无数据时的占位提示 -->
      <div v-else class="empty-period-card">
        <el-empty description="暂未选定深度归因诊断设备" :image-size="60">
          <div class="text-muted mt-8">请在顶部下拉选择框中挑选一台嫌疑设备，或在上方“工位机台异常排行”或“工艺路径对比表”中点击设备名直接开始诊断</div>
        </el-empty>
      </div>
    </div>

  </div>
</template>

<script setup>
/**
 * 模块描述: Tab 3 深度诊断面板 (DiagnosticsPanel.vue)
 * ===================================================================
 * 1. 顶部以 Select 选择框挂接当前追溯机台，替换原左侧重复的 Suspect 设备列表以防图表压缩。
 * 2. 对接 Tab 2 可配置的 minYieldThreshold，透传作为 min_total 参与 Lot 对照数据拉取。
 * 3. 监听 store.selectedMachineName 的外部跳转更新，达成 Tab 2 -> Tab 3 的跨页无感导航。
 * ===================================================================
 */
import { ref, watch, computed, onMounted } from 'vue'
import { api } from '../../api/index.js'
import { useFilterStore } from '../../store/filter.js'
import LotCompareChart from '../charts/LotCompareChart.vue'

const props = defineProps({
  baselineRange: { type: Array, default: null },
  studyRange:    { type: Array, default: null },
})

const filterStore = useFilterStore()

// 嫌疑机台下拉候选列表
const suspects = ref([])
const suspectsLoading = ref(false)

// 当前在诊断的机台元数据
const selectedMachine = ref(null)
const selectedMachineKey = ref('')

// 物料批次状态
const lots = ref([])
const lotsLoading = ref(false)
const lotsError = ref(null)

// 1. 获取动态 KMeans 嫌疑机台
async function loadSuspects() {
  if (!props.studyRange) return
  suspectsLoading.value = true
  try {
    const res = await api.getSuspects({
      study_from: props.studyRange[0],
      study_to:   props.studyRange[1],
      min_yield:  filterStore.minYieldThreshold,
      lift_threshold: 1.5
    })
    suspects.value = res.data.status === 'success' ? res.data.data : []
    

  } finally {
    suspectsLoading.value = false
  }
}

// 2. 根据选中的机台拉取批次诊断 (接入 minYieldThreshold 过滤稀疏物料)
async function loadLotDiagnosis(m) {
  if (!props.studyRange || !m) return
  lotsLoading.value = true
  lotsError.value = null
  try {
    const res = await api.getLotDiagnosis({
      study_from:     props.studyRange[0],
      study_to:       props.studyRange[1],
      machine:        m.machine,
      workcenter_col: m.workcenter_col,
      cluster_id:     m.cluster,
      min_total:      filterStore.minYieldThreshold, // 用户自定义过滤门槛传入 min_total
      min_anomaly:    3
    })
    lots.value = res.data.status === 'success' ? res.data.data : []
    if (res.data.status === 'error') lotsError.value = res.data.message
  } catch (e) {
    lotsError.value = '加载物料批次诊断失败'
  } finally {
    lotsLoading.value = false
  }
}

// 3. 响应下拉框的选中变动，同步通知全局 store
function onDropdownMachineChange(val) {
  if (!val) {
    selectedMachine.value = null
    lots.value = []
    return
  }
  const [m, wc, cl] = val.split('|')
  filterStore.setDiagnosticMachine(m, wc, Number(cl))
}

// 4. 监听全局 Store 中的嫌疑机台选中变动 (支持 Tab 2 页面的下钻点击跳转)
watch(
  [
    () => filterStore.selectedMachineName,
    () => filterStore.selectedMachineWorkcenter,
    () => filterStore.selectedMachineCluster
  ],
  ([m, wc, cl]) => {
    if (m && wc) {
      selectedMachine.value = { machine: m, workcenter_col: wc, cluster: cl }
      selectedMachineKey.value = `${m}|${wc}|${cl}`
      loadLotDiagnosis(selectedMachine.value)
    } else {
      selectedMachine.value = null
      selectedMachineKey.value = ''
      lots.value = []
    }
  },
  { immediate: true }
)

// 5. 自动无偏病因诊断逻辑
const machineDiagnosis = computed(() => {
  if (!selectedMachine.value) return {}
  if (!lots.value || !lots.value.length) {
    return {
      title: '设备系统性工艺漂移',
      suggestion: '当前嫌疑设备下各物料批次的坏损率表现非常均匀，均没有发生局部的显著起峰。判定为设备自身张力、温度、模具对位等出现物理精度漂移。建议立即通知钳工/维保组停机点检。'
    }
  }
  
  // 后端返回已经按 local_lift 降序排列，取局部提升度最显著的第一批次
  const primary = lots.value[0]
  if (primary.local_lift > 1.5) {
    return {
      title: primary.diagnosis,
      suggestion: primary.suggestion
    }
  }
  
  return {
    title: '设备系统性工艺漂移',
    suggestion: '各批次在该机台上的坏损率分布平缓，没有单一批次缺陷拉动，判定为设备自身精度漂移。建议停机维护。'
  }
})

// 监听刷新条件
watch(
  [() => props.studyRange, () => filterStore.minYieldThreshold],
  () => {
    // 日期或门槛调整时重新初始化加载嫌疑机台
    filterStore.setDiagnosticMachine(null, null, 0)
    loadSuspects()
  }
)

function getVerdictClass(title) {
  if (title === '设备系统性工艺漂移') return 'orange'
  if (title === '全局物料批次缺陷') return 'red'
  if (title === '机台-批次适配性故障') return 'purple'
  return ''
}

onMounted(() => {
  loadSuspects()
})
</script>

<style scoped>
.diagnostics-panel-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
}
.diagnostics-selector-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border-light);
  min-height: 57px;
  box-sizing: border-box;
}
.diagnostics-scroll-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.selector-label {
  font-weight: 700;
  font-size: 13px;
  color: #374151;
}
.text-muted {
  font-size: 12px;
  color: #6b7280;
}
.font-mono { font-family: 'JetBrains Mono', monospace; }
.text-bold { font-weight: 600; }
.text-danger { color: #dc2626; }

.empty-period-card {
  padding: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.chart-title-sub {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #374151;
}
.mt-8 { margin-top: 8px; }
.mt-16 { margin-top: 16px; }
</style>
