import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useFilterStore = defineStore('filter', () => {
  // 当前选中的规格型号（仅限 Tab 1 本地趋势下钻过滤，已与 Tab 2 & 3 诊断解耦）
  const selectedArticle = ref(null)

  // 全局日期范围 [dateFrom, dateTo]
  const dateRange = ref(null)

  // 趋势粒度：'daily' | 'weekly'
  const trendGranularity = ref('daily')

  // 全局 CPK 指标切换状态：'rfpp' | 'rfh1'
  const cpkIndicator = ref('rfpp')

  // 胎重指标的偏差公差限 (%)，默认为 0.8
  const weightTolerance = ref(0.8)

  // 是否处于下钻状态
  const isDrillDown = ref(false)
  const drillDownTarget = ref(null)

  // 基准期日期范围 [dateFrom, dateTo]
  const baselineRange = ref(null)

  // 研究期日期范围 [dateFrom, dateTo]
  const studyRange = ref(null)

  // 当前激活的 Tab 页: 'overview' | 'rootcase' | 'diagnose'
  const activeTab = ref('overview')

  // 样本量过滤门槛（用户自定义输入，默认 50，取代原硬编码 50/0 布尔值）
  const minYieldThreshold = ref(50)
  
  // 保留原有变量兼容性：当门槛值大于 0 时，即视为启用了过滤，且支持 v-model 修改
  const filterLowYield = computed({
    get: () => minYieldThreshold.value > 0,
    set: (val) => {
      minYieldThreshold.value = val ? 50 : 0
    }
  })

  // ── 跳转交互状态：Tab 2 联动至 Tab 3 深度诊断 ─────────────────────
  const selectedMachineName = ref(null)
  const selectedMachineWorkcenter = ref(null)
  const selectedMachineCluster = ref(0)

  // 计算属性：是否设置了分析周期（基准期与研究期都设置完整）
  const hasAnalysisPeriod = computed(() => {
    return !!(
      baselineRange.value &&
      baselineRange.value.length === 2 &&
      studyRange.value &&
      studyRange.value.length === 2
    )
  })

  function setArticle(article) {
    selectedArticle.value = article
  }

  function setDateRange(range) {
    dateRange.value = range
  }

  function setGranularity(g) {
    trendGranularity.value = g
  }

  function setCpkIndicator(val) {
    cpkIndicator.value = val
  }

  function drillDown(article) {
    isDrillDown.value = true
    drillDownTarget.value = article
    selectedArticle.value = article
  }

  function resetDrillDown() {
    isDrillDown.value = false
    drillDownTarget.value = null
    selectedArticle.value = null
  }

  function setBaselineRange(range) {
    baselineRange.value = range
  }

  function setStudyRange(range) {
    studyRange.value = range
  }

  function setActiveTab(tab) {
    activeTab.value = tab
  }

  function setMinYieldThreshold(val) {
    minYieldThreshold.value = Number(val) || 0
  }

  function setDiagnosticMachine(machine, workcenter, cluster = 0) {
    selectedMachineName.value = machine
    selectedMachineWorkcenter.value = workcenter
    selectedMachineCluster.value = Number(cluster) || 0
  }

  function reset() {
    selectedArticle.value = null
    dateRange.value = null
    trendGranularity.value = 'daily'
    isDrillDown.value = false
    drillDownTarget.value = null
    baselineRange.value = null
    studyRange.value = null
    activeTab.value = 'overview'
    minYieldThreshold.value = 50
    selectedMachineName.value = null
    selectedMachineWorkcenter.value = null
    selectedMachineCluster.value = 0
  }

  return {
    selectedArticle,
    dateRange,
    trendGranularity,
    isDrillDown,
    drillDownTarget,
    baselineRange,
    studyRange,
    activeTab,
    minYieldThreshold,
    filterLowYield,
    selectedMachineName,
    selectedMachineWorkcenter,
    selectedMachineCluster,
    hasAnalysisPeriod,
    cpkIndicator,
    weightTolerance,
    setArticle,
    setDateRange,
    setGranularity,
    setCpkIndicator,
    drillDown,
    resetDrillDown,
    setBaselineRange,
    setStudyRange,
    setActiveTab,
    setMinYieldThreshold,
    setDiagnosticMachine,
    reset,
  }
})
