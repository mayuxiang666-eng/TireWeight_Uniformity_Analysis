<template>
  <div class="lot-chart-container" style="width: 100%; position: relative;">
    <!-- 顶部综合控制栏: 工段切换、分布模式、指标切换、时间维度排序、日期选择 -->
    <div class="lot-top-controls" style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
      <!-- 左侧: 视图分布模式 & 质量指标选择 -->
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <el-radio-group v-if="props.indicator !== 'weight'" v-model="displayMode" size="small">
          <el-radio-button value="cpk">CPK 分布</el-radio-button>
          <el-radio-button value="raw">实际值分布</el-radio-button>
        </el-radio-group>
        <span v-else style="font-size: 13px; font-weight: bold; color: #475569; display: flex; align-items: center; gap: 4px;">
          📦 胎重实际测量值分布 (单位: kg)
        </span>
      </div>

      <!-- 右侧: 时间维度选择器与日期范围选择器 -->
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 12px; color: #64748b; font-weight: 500;">⏱️ 排序维度:</span>
          <el-select v-model="selectedTimeCol" size="small" style="width: 165px;" @change="handleTimeColChange">
            <el-option label="成型 GT 时间 (默认)" value="gt_loc_timestamp" />
            <el-option label="硫化 CT 时间" value="ct_loc_timestamp" />
            <el-option label="胎面时间" value="tread_loc_timestamp" />
            <el-option label="胎圈时间" value="bead_loc_timestamp" />
            <el-option label="内衬时间" value="inner_liner_loc_timestamp" />
            <el-option label="胎侧时间" value="sidewall_loc_timestamp" />
            <el-option label="带束层1时间" value="first_breaker_loc_timestamp" />
            <el-option label="带束层2时间" value="second_breaker_loc_timestamp" />
            <el-option label="帘布层1时间" value="first_ply_loc_timestamp" />
            <el-option label="帘布层2时间" value="second_ply_loc_timestamp" />
            <el-option label="冠带层1时间" value="wound_cap_ply1_loc_timestamp" />
            <el-option label="冠带层2时间" value="wound_cap_ply2_loc_timestamp" />
          </el-select>
        </div>

        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 12px; color: #64748b; font-weight: 500;">📅 追溯日期:</span>
          <el-date-picker
            v-model="localDateRange"
            type="daterange"
            size="small"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 220px;"
            @change="handleDateRangeChange"
          />
        </div>
      </div>
    </div>

    <!-- 工段快速定位导航按钮组 (各工段独立单独展示) -->
    <div class="workcenter-nav-bar" style="margin-bottom: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
      <span style="font-size: 12px; font-weight: 600; color: #475569; margin-right: 2px;">⚡ 选择工段:</span>
      <button
        v-for="comp in allWorkcenters"
        :key="comp"
        class="wc-nav-btn"
        :class="{ active: activeComponent === comp }"
        @click="selectComponent(comp)"
      >
        {{ comp }}
      </button>
    </div>

    <!-- 图例与提示说明栏 -->
    <div class="lot-notice-bar" style="margin-bottom: 10px; font-size: 12px; background: #f8fafc; padding: 8px 14px; border-radius: 6px; border: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
      <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
        <span>📦 【{{ activeComponent || '工段' }}】有效批次: <strong>{{ currentCompLotCount }}</strong> 个</span>
        <template v-if="displayMode === 'cpk'">
          <span style="color: #334155; font-weight: 600;">● ── 单规格 CPK (点击数据点看 Barcode 明细)</span>
          <span style="color: #64748b; font-weight: 600;">◆ ┈┈ 其它规格加权 CPK (已排除当前单规格)</span>
        </template>
        <template v-else>
          <span style="color: #334155; font-weight: 600;">📦 实际测量值分布 (点击箱形图看 Barcode 明细)</span>
          <span style="color: #dc2626; font-weight: 600;">── 规格上限 (USL: {{ uslValue }})</span>
          <span style="color: #475569; font-weight: 500;">📉 按选定时间维度先后次序排列</span>
        </template>
      </div>
      
      <!-- 右侧图例组 -->
      <div style="display: flex; flex-direction: column; gap: 6px; align-items: flex-end;">
        <!-- 加工机台图例 -->
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          <span style="color: #64748b; font-weight: 500;">加工机台:</span>
          <span
            v-for="m in uniqueMachines"
            :key="m.code"
            style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: #ffffff; border: 1px solid #cbd5e1; font-weight: bold;"
            :style="{ color: m.color }"
          >
            ● {{ m.code }}
          </span>
        </div>
        <!-- 成型机台比例背景色图例 -->
        <div v-if="uniqueBuildingMachines.length > 0" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          <span style="color: #64748b; font-weight: 500;">成型分流 (背景色):</span>
          <span
            v-for="m in uniqueBuildingMachines"
            :key="m.code"
            style="font-size: 11px; padding: 2px 6px; border-radius: 4px; border: 1px solid #cbd5e1; font-weight: bold; cursor: pointer; transition: all 0.2s;"
            :style="{ 
              borderColor: selectedBuildingMachine === m.code ? m.color : '#cbd5e1', 
              backgroundColor: selectedBuildingMachine === m.code ? m.color : m.bgColor, 
              color: selectedBuildingMachine === m.code ? '#ffffff' : '#334155',
              boxShadow: selectedBuildingMachine === m.code ? '0 1px 3px rgba(0,0,0,0.15)' : 'none'
            }"
            @click="toggleBuildingMachineFilter(m.code)"
          >
            ■ {{ m.code }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="lot-loading" style="height: 350px; display: flex; align-items: center; justify-content: center;">
      <el-icon class="is-loading" size="24"><Loading /></el-icon>
      <span style="margin-left: 8px; font-size: 13px; color: #666;">正在加载物料批次追溯数据...</span>
    </div>
    <div v-else-if="error" class="lot-error" style="height: 350px; display: flex; align-items: center; justify-content: center; color: #ef4444; font-size: 13px;">
      <span>{{ error }}</span>
    </div>
    <div v-else-if="!filteredLotData || filteredLotData.length === 0" class="lot-empty" style="height: 350px; display: flex; align-items: center; justify-content: center; color: #8c959f; font-size: 13px;">
      <el-empty :description="`当前选中规格在 [${activeComponent}] 工段下暂无半成品物料批次记录`" :image-size="60" />
    </div>
    <template v-else>
      <v-chart
        ref="chartRef"
        :option="option"
        autoresize
        style="width: 100%; height: 350px; cursor: pointer;"
        @click="onChartClick"
      />
    </template>

    <!-- 点击箱形图/数据点后的 Barcode 级测量实际值明细弹窗 -->
    <el-dialog
      v-model="barcodeDialogVisible"
      :title="`${localIndicator.toUpperCase()} 实际值 (按 barcode 和 ${dialogLotInfo?.component || activeComponent || ''}_lot)`"
      width="84%"
      top="4vh"
      destroy-on-close
      append-to-body
    >
      <!-- 弹窗顶栏控制与元数据说明 -->
      <div style="margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; background: #f8fafc; padding: 10px 14px; border-radius: 6px; border: 1px solid #e2e8f0;">
        <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap; font-size: 12px; color: #334155;">
          <span>📦 规格: <strong>{{ selectedArticle || '未指定' }}</strong></span>
          <span>⚙️ 工段: <strong>{{ dialogLotInfo?.component || activeComponent }}</strong></span>
          <span>🏭 加工机台: <strong :style="{ color: getMachineColor(dialogLotInfo?.machine) }">● {{ dialogLotInfo?.machine }}</strong></span>
          <span>🏷️ 物料批次 Lot: <strong style="color: #2563eb;">{{ dialogLotInfo?.lot }}</strong></span>
          <span>📊 下属 Barcode 样本量: <strong>{{ dialogBarcodeList.length }}</strong> 条</span>
        </div>

        <!-- 机台分组连线切换 Radio -->
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 12px; font-weight: 600; color: #475569;">🔀 机台分组连线:</span>
          <el-radio-group v-model="barcodeGroupMode" size="small">
            <el-radio-button value="none">🌐 不分组 (全局顺序)</el-radio-button>
            <el-radio-button value="ct">🏭 按 CT 硫化机台分组</el-radio-button>
            <el-radio-button value="tu">🔍 按 TU 检测机台分组</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div v-if="dialogLoading" style="height: 400px; display: flex; align-items: center; justify-content: center;">
        <el-icon class="is-loading" size="28"><Loading /></el-icon>
        <span style="margin-left: 10px; color: #64748b; font-size: 13px;">正在加载选中物料批次关联的 Barcode 级测量数据...</span>
      </div>
      <div v-else-if="dialogError" style="height: 400px; display: flex; align-items: center; justify-content: center; color: #ef4444; font-size: 13px;">
        {{ dialogError }}
      </div>
      <div v-else-if="!dialogBarcodeList || dialogBarcodeList.length === 0" style="height: 400px; display: flex; align-items: center; justify-content: center;">
        <el-empty description="该物料批次暂无关联的 Barcode 级实际测量记录" :image-size="60" />
      </div>
      <template v-else>
        <v-chart
          :option="barcodeChartOption"
          autoresize
          style="width: 100%; height: 420px;"
        />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BoxplotChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent, MarkLineComponent, MarkAreaComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Loading } from '@element-plus/icons-vue'
import { api } from '@/api'

use([LineChart, BoxplotChart, TooltipComponent, GridComponent, LegendComponent, MarkLineComponent, MarkAreaComponent, DataZoomComponent, CanvasRenderer])

const props = defineProps({
  lotData:         { type: Array, default: () => [] },
  uslValue:        { type: Number, default: 100 },
  loading:         { type: Boolean, default: false },
  error:           { type: String, default: null },
  selectedArticle: { type: String, default: '' },
  targetDate:      { type: String, default: '' },
  indicator:       { type: String, default: 'rfpp' }
})

const emit = defineEmits(['reload'])

const chartRef = ref(null)
const displayMode = ref('cpk') // 'cpk' | 'raw'
const localIndicator = ref(props.indicator || 'rfpp')
const selectedTimeCol = ref('gt_loc_timestamp')
const localDateRange = ref([])
const activeComponent = ref('胎面')

// Barcode 明细弹窗管理与分组模式
const barcodeDialogVisible = ref(false)
const dialogLoading = ref(false)
const dialogError = ref(null)
const dialogLotInfo = ref(null)
const dialogBarcodeList = ref([])
const barcodeGroupMode = ref('none') // 'none' | 'ct' | 'tu'

// 固定的 9 大工段列表 (严格按生产顺序)
const allWorkcenters = [
  '胎面', '胎圈', '内衬', '胎侧', '帘布层1', '带束层1', '带束层2', '冠带层1', '冠带层2'
]

// 预定义机器调色板 (区分不同加工机台)
const machineColors = [
  '#2563eb', '#7c3aed', '#059669', '#d97706', '#db2777', 
  '#0284c7', '#9333ea', '#16a34a', '#ea580c', '#e11d48'
]

function hexToRgba(hex, alpha = 1.0) {
  if (!hex || typeof hex !== 'string' || !hex.startsWith('#')) return hex
  let c = hex.substring(1)
  if (c.length === 3) c = c.split('').map(x => x + x).join('')
  const num = parseInt(c, 16)
  return `rgba(${(num >> 16) & 255}, ${(num >> 8) & 255}, ${num & 255}, ${alpha})`
}

// 获取基于目标日期前推 7 天的默认日期范围
function getDefaultDateRange(dateStr) {
  if (!dateStr) return []
  const dObj = new Date(dateStr)
  const dStart = new Date(dObj.getTime() - 7 * 24 * 60 * 60 * 1000)
  const fmt = (d) => d.toISOString().split('T')[0]
  return [fmt(dStart), dateStr]
}

// 自动继承初始化日期与指标，并支持在规格/日期/指标变更时重置/同步追溯时间范围
watch(() => props.targetDate, (newVal) => {
  if (newVal) {
    localDateRange.value = getDefaultDateRange(newVal)
  }
}, { immediate: true })

watch(() => props.selectedArticle, () => {
  if (props.targetDate) {
    localDateRange.value = getDefaultDateRange(props.targetDate)
  }
})

watch(() => props.indicator, (newVal) => {
  if (newVal) {
    localIndicator.value = newVal
    if (newVal === 'weight') {
      displayMode.value = 'raw'
    }
    emitReload()
  }
}, { immediate: true })

// 当全局 lotData 加载更新时，校验当前选中的工段
watch(() => props.lotData, (newVal) => {
  if (newVal && newVal.length > 0) {
    const availableComps = allWorkcenters.filter(c => newVal.some(d => !d.is_break && d.component === c))
    if (availableComps.length > 0 && (!activeComponent.value || !availableComps.includes(activeComponent.value))) {
      activeComponent.value = availableComps[0]
    }
  }
}, { immediate: true })

function handleIndicatorChange() {
  emitReload()
}

function handleTimeColChange() {
  emitReload()
}

function handleDateRangeChange() {
  emitReload()
}

function emitReload() {
  emit('reload', {
    indicator: localIndicator.value,
    dateRange: localDateRange.value,
    component: activeComponent.value,
    time_col: selectedTimeCol.value
  })
}

const selectedBuildingMachine = ref(null)

function toggleBuildingMachineFilter(code) {
  if (selectedBuildingMachine.value === code) {
    selectedBuildingMachine.value = null
  } else {
    selectedBuildingMachine.value = code
  }
}

function selectComponent(comp) {
  activeComponent.value = comp
  selectedBuildingMachine.value = null // 切换工段时重置选中机台过滤器
  emitReload()
}

// 过滤当前选中工段的数据
const filteredLotData = computed(() => {
  if (!props.lotData) return []
  return props.lotData.filter(d => d.component === activeComponent.value)
})

// 当前工段的有效物料批次数量 (排除切断点)
const currentCompLotCount = computed(() => {
  if (!filteredLotData.value) return 0
  return filteredLotData.value.filter(d => !d.is_break).length
})

// 提取当前过滤工段涉及的所有唯一机台及其专属颜色
const uniqueMachines = computed(() => {
  if (!filteredLotData.value) return []
  const map = {}
  const result = []
  filteredLotData.value.forEach(d => {
    if (d.is_break) return
    const code = (d.machine || 'N/A').trim()
    if (code && !(code in map)) {
      const idx = Object.keys(map).length % machineColors.length
      const color = machineColors[idx]
      map[code] = color
      result.push({ code, color })
    }
  })
  return result
})

// 成型机台柔和配色板 (用于比例分段背景色)
const buildingMachineColors = [
  'rgba(59, 130, 246, 0.10)',   // Soft blue
  'rgba(16, 185, 129, 0.10)',   // Soft green
  'rgba(245, 158, 11, 0.10)',   // Soft orange
  'rgba(139, 92, 246, 0.10)',   // Soft purple
  'rgba(236, 72, 153, 0.10)',   // Soft pink
  'rgba(20, 184, 166, 0.10)',   // Soft teal
  'rgba(244, 63, 94, 0.10)',    // Soft rose
  'rgba(101, 163, 13, 0.10)'    // Soft lime
]

// 提取当前工段涉及的所有唯一成型机台及其专属柔和背景色
const uniqueBuildingMachines = computed(() => {
  if (!filteredLotData.value) return []
  const map = {}
  const result = []
  filteredLotData.value.forEach(d => {
    if (d.is_break || !d.building_machine || d.building_machine === 'N/A') return
    const code = d.building_machine.trim()
    if (code && !(code in map)) {
      const idx = Object.keys(map).length % buildingMachineColors.length
      const color = buildingMachineColors[idx]
      map[code] = color
      result.push({
        code,
        color: color.replace('0.10', '0.8'), // Border/legend color
        bgColor: color // BG color
      })
    }
  })
  return result
})

function getBuildingMachineColor(code) {
  const match = uniqueBuildingMachines.value.find(m => m.code === (code || '').trim())
  return match ? match.bgColor : 'transparent'
}

function getMachineColor(machineCode) {
  const match = uniqueMachines.value.find(m => m.code === (machineCode || '').trim())
  return match ? match.color : '#64748b'
}

// 点击箱形图/折线图节点时弹出 Barcode 弹窗
async function openBarcodeDialog(lotInfo) {
  if (!lotInfo || !lotInfo.lot) return
  dialogLotInfo.value = lotInfo
  barcodeDialogVisible.value = true
  dialogLoading.value = true
  dialogError.value = null
  dialogBarcodeList.value = []

  try {
    const res = await api.getLotBarcodeDetail({
      article10: props.selectedArticle || '',
      lot: lotInfo.lot,
      component: activeComponent.value || lotInfo.component || '',
      indicator: localIndicator.value
    })

    if (res.data && res.data.status === 'success') {
      const list = res.data.data || []
      // 默认按 Barcode 从小到大升序排列
      list.sort((a, b) => (a.barcode || '').localeCompare(b.barcode || '', undefined, { numeric: true }))
      dialogBarcodeList.value = list
    } else {
      dialogError.value = res.data?.message || '获取 Barcode 明细失败'
    }
  } catch (e) {
    dialogError.value = '加载 Barcode 测量数据异常'
  } finally {
    dialogLoading.value = false
  }
}

function onChartClick(params) {
  if (!params || !params.data) return
  const lotInfo = params.data.lotInfo
  if (lotInfo && !lotInfo.is_break && lotInfo.lot) {
    openBarcodeDialog(lotInfo)
  }
}

// 构建弹窗内的 Barcode 级折线图 Option (支持按 CT / TU 机台分组同机台同色隔断连线)
const barcodeChartOption = computed(() => {
  if (!dialogBarcodeList.value || dialogBarcodeList.value.length === 0) return {}

  const groupMode = barcodeGroupMode.value
  const targetUSL = props.uslValue || 100

  if (groupMode === 'none') {
    // ── 不分组连线 ─────────────────────────────────────────
    const list = [...dialogBarcodeList.value]
    list.sort((a, b) => (a.barcode || '').localeCompare(b.barcode || '', undefined, { numeric: true }))

    const mColor = getMachineColor(dialogLotInfo.value?.machine)
    const xCategories = list.map(b => b.barcode)
    const yValues = list.map(b => b.val)

    let yMin, yMax
    if (localIndicator.value === 'weight') {
      const nonZeroVals = yValues.filter(v => v > 1.0)
      const realMin = nonZeroVals.length > 0 ? Math.min(...nonZeroVals) : 10.0
      const realMax = nonZeroVals.length > 0 ? Math.max(...nonZeroVals) : 16.0
      const targetUSLVal = targetUSL && targetUSL > 1.0 ? targetUSL : realMax
      
      const minV = Math.min(realMin, targetUSLVal)
      const maxV = Math.max(realMax, targetUSLVal)
      yMin = Math.max(0.0, Math.floor((minV - 0.25) * 10) / 10)
      yMax = Math.ceil((maxV + 0.25) * 10) / 10
    } else {
      const minV = Math.min(...yValues)
      const maxV = Math.max(...yValues, targetUSL)
      yMin = Math.max(0, Math.floor((minV - 2.0) / 5) * 5)
      yMax = Math.ceil((maxV + 5.0) / 5) * 5
    }
    const zoomEnd = Math.min(100, Math.max(20, Math.round((28 / Math.max(1, yValues.length)) * 100)))

    return {
      backgroundColor: 'transparent',
      grid: { left: 55, right: 35, top: 45, bottom: 90 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#ffffff',
        borderColor: '#cbd5e1',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: '#0f172a', fontSize: 12 },
        formatter(params) {
          if (!params || params.length === 0) return ''
          const p = params[0]
          return `
            <div style="font-weight:bold; font-size:12px; margin-bottom:4px; color:#0f172a;">
              Barcode: ${p.name}
            </div>
            <div style="display:flex; justify-content:space-between; gap:12px;">
              <span style="color:#64748b;">${localIndicator.value.toUpperCase()} 实际值:</span>
              <strong style="color:${mColor}">${p.value}</strong>
            </div>
          `
        }
      },
      dataZoom: [
        { type: 'slider', show: true, orient: 'horizontal', start: 0, end: zoomEnd, height: 20, bottom: 8, borderColor: '#cbd5e1', fillerColor: 'rgba(51, 65, 85, 0.15)', handleStyle: { color: '#334155' } },
        { type: 'inside', orient: 'horizontal' },
        { type: 'slider', show: true, orient: 'vertical', right: 10, borderColor: '#cbd5e1', fillerColor: 'rgba(51, 65, 85, 0.15)', handleStyle: { color: '#334155' } },
        { type: 'inside', orient: 'vertical' }
      ],
      xAxis: {
        type: 'category',
        name: 'barcode',
        nameLocation: 'middle',
        nameGap: 65,
        nameTextStyle: { color: '#475569', fontSize: 12, fontWeight: 'bold' },
        data: xCategories,
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisTick: { alignWithLabel: true },
        axisLabel: { fontSize: 10, color: '#334155', interval: 0, rotate: 90 }
      },
      yAxis: {
        type: 'value',
        name: `${localIndicator.value.toUpperCase()} 实际测量值`,
        nameTextStyle: { color: '#64748b', fontSize: 11 },
        min: yMin,
        max: yMax,
        splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
        axisLabel: { color: '#64748b', fontSize: 11 }
      },
      series: [
        {
          name: `${dialogLotInfo.value?.lot} 实际测量值`,
          type: 'line',
          smooth: 0.2,
          symbol: 'circle',
          symbolSize: 7,
          lineStyle: { color: mColor, width: 2.2 },
          itemStyle: { color: mColor, borderColor: '#ffffff', borderWidth: 1 },
          label: { show: true, position: 'top', fontSize: 10, color: '#334155', formatter: '{c}' },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: targetUSL,
                name: '规格上限 USL',
                lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
                label: { formatter: `USL 上限 (${targetUSL})`, position: 'end', color: '#ef4444', fontSize: 10 }
              }
            ]
          },
          data: yValues
        }
      ]
    }
  } else {
    // ── 按 CT 硫化或 TU 检测机台分组连线 (同机台同色，异机台隔断) ──────────
    const keyField = groupMode === 'ct' ? 'ct_workcenter' : 'tu_workcenter'
    const groupName = groupMode === 'ct' ? 'CT 硫化机台' : 'TU 检测机台'

    // 按 机台, Barcode 二重排序
    const list = [...dialogBarcodeList.value]
    list.sort((a, b) => {
      const mA = a[keyField] || 'N/A'
      const mB = b[keyField] || 'N/A'
      if (mA !== mB) return mA.localeCompare(mB)
      return (a.barcode || '').localeCompare(b.barcode || '', undefined, { numeric: true })
    })

    // 插入隔断点并映射数据
    const processedList = []
    list.forEach((item, idx) => {
      if (idx > 0 && item[keyField] !== list[idx - 1][keyField]) {
        processedList.push({
          barcode: '',
          val: null,
          is_break: true,
          [keyField]: list[idx - 1][keyField]
        })
      }
      processedList.push({ ...item, is_break: false })
    })

    const xCategories = processedList.map(b => (b.is_break ? '' : b.barcode))
    const validVals = processedList.filter(b => !b.is_break && b.val !== null).map(b => b.val)

    const minV = validVals.length > 0 ? Math.min(...validVals) : 0
    const maxV = validVals.length > 0 ? Math.max(...validVals, targetUSL) : targetUSL
    let yMin, yMax
    if (localIndicator.value === 'weight') {
      yMin = Math.max(0.0, Math.floor((minV - 0.2) * 10) / 10)
      yMax = Math.ceil((maxV + 0.2) * 10) / 10
    } else {
      yMin = Math.max(0, Math.floor((minV - 2.0) / 5) * 5)
      yMax = Math.ceil((maxV + 5.0) / 5) * 5
    }
    const zoomEnd = Math.min(100, Math.max(20, Math.round((28 / Math.max(1, processedList.length)) * 100)))

    // 提取唯一机台并关联专属颜色
    const subUniqueMachines = []
    const subMap = {}
    processedList.forEach(b => {
      if (b.is_break) return
      const code = (b[keyField] || 'N/A').trim()
      if (code && !(code in subMap)) {
        const idx = Object.keys(subMap).length % machineColors.length
        const color = machineColors[idx]
        subMap[code] = color
        subUniqueMachines.push({ code, color })
      }
    })

    function getSubColor(code) {
      const match = subUniqueMachines.find(m => m.code === (code || '').trim())
      return match ? match.color : '#64748b'
    }

    const seriesList = []
    seriesList.push({
      name: '规格上限 USL',
      type: 'line',
      data: [],
      markLine: {
        symbol: 'none',
        data: [
          {
            yAxis: targetUSL,
            name: '规格上限 USL',
            lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
            label: { formatter: `USL 上限 (${targetUSL})`, position: 'end', color: '#ef4444', fontSize: 10 }
          }
        ]
      }
    })

    subUniqueMachines.forEach(mInfo => {
      const mCode = mInfo.code
      const mColor = mInfo.color

      const mData = processedList.map(b => {
        if (!b.is_break && (b[keyField] || '').trim() === mCode) {
          return {
            value: b.val,
            barcodeInfo: b
          }
        }
        return null
      })

      seriesList.push({
        name: `${mCode}`,
        type: 'line',
        smooth: 0.2,
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { color: mColor, width: 2.2 },
        itemStyle: { color: mColor, borderColor: '#ffffff', borderWidth: 1 },
        label: { show: true, position: 'top', fontSize: 10, color: '#334155', formatter: '{c}' },
        data: mData
      })
    })

    return {
      backgroundColor: 'transparent',
      grid: { left: 55, right: 35, top: 45, bottom: 95 },
      legend: {
        show: true,
        top: 5,
        right: 20,
        textStyle: { color: '#475569', fontSize: 11 }
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#ffffff',
        borderColor: '#cbd5e1',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: '#0f172a', fontSize: 12 },
        formatter(params) {
          if (!params || params.length === 0) return ''
          const validP = params.find(p => p.data && p.data.barcodeInfo)
          if (!validP) return ''
          const bInfo = validP.data.barcodeInfo
          const mColor = getSubColor(bInfo[keyField])
          return `
            <div style="font-weight:bold; font-size:12px; margin-bottom:4px; color:#0f172a;">
              Barcode: ${bInfo.barcode}
            </div>
            <div style="display:flex; justify-content:space-between; gap:12px; margin-bottom:2px;">
              <span style="color:#64748b;">${groupName}:</span>
              <strong style="color:${mColor}">● ${bInfo[keyField]}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:12px;">
              <span style="color:#64748b;">${localIndicator.value.toUpperCase()} 实际值:</span>
              <strong style="color:${mColor}">${bInfo.val}</strong>
            </div>
          `
        }
      },
      dataZoom: [
        { type: 'slider', show: true, orient: 'horizontal', start: 0, end: zoomEnd, height: 20, bottom: 8, borderColor: '#cbd5e1', fillerColor: 'rgba(51, 65, 85, 0.15)', handleStyle: { color: '#334155' } },
        { type: 'inside', orient: 'horizontal' },
        { type: 'slider', show: true, orient: 'vertical', right: 10, borderColor: '#cbd5e1', fillerColor: 'rgba(51, 65, 85, 0.15)', handleStyle: { color: '#334155' } },
        { type: 'inside', orient: 'vertical' }
      ],
      xAxis: {
        type: 'category',
        name: 'barcode',
        nameLocation: 'middle',
        nameGap: 65,
        nameTextStyle: { color: '#475569', fontSize: 12, fontWeight: 'bold' },
        data: xCategories,
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisTick: { alignWithLabel: true },
        axisLabel: { fontSize: 10, color: '#334155', interval: 0, rotate: 90 }
      },
      yAxis: {
        type: 'value',
        name: `${localIndicator.value.toUpperCase()} 实际测量值`,
        nameTextStyle: { color: '#64748b', fontSize: 11 },
        min: yMin,
        max: yMax,
        splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
        axisLabel: { color: '#64748b', fontSize: 11 }
      },
      series: seriesList
    }
  }
})

const option = computed(() => {
  if (!filteredLotData.value || filteredLotData.value.length === 0) return {}

  const currentData = filteredLotData.value
  const isBoxplotMode = displayMode.value === 'raw'

  // 1. 过滤出真正的有效物料数据
  const validLots = currentData.filter(d => !d.is_break && d.boxplot)
  
  // 2. X 轴标签 - 只保留物料批次 (Lot)，不用显示规格/机台信息
  const xCategories = isBoxplotMode
    ? validLots.map(d => d.lot)
    : currentData.map(d => (d.is_break ? '' : d.lot))

  // 3. 构建比例背景渐变色块 (markAreaData)
  const markAreaData = []
  const dataListForMarkArea = isBoxplotMode ? validLots : currentData

  for (let i = 0; i < dataListForMarkArea.length; i++) {
    const d = dataListForMarkArea[i]
    if (d.is_break || !d.gt_distribution || Object.keys(d.gt_distribution).length === 0) {
      continue
    }

    const dist = d.gt_distribution
    const sortedEntries = Object.entries(dist).sort((a, b) => b[1] - a[1]) // 按比例从大到小排序

    const stops = []
    let accum = 0
    sortedEntries.forEach(([machine, pct]) => {
      const color = getBuildingMachineColor(machine)
      stops.push({ offset: accum, color: color })
      accum += pct
      const clampedAccum = Math.min(1.0, accum)
      stops.push({ offset: clampedAccum, color: color })
    })

    // 如果选中了某成型机台，对于不含该机台分流的批次进行背景置灰弱化
    let finalItemStyle = {
      color: {
        type: 'linear',
        x: 0,
        y: 1,  // 从下往上渲染
        x2: 0,
        y2: 0,
        colorStops: stops
      }
    }

    if (selectedBuildingMachine.value) {
      const hasSelected = dist[selectedBuildingMachine.value] !== undefined && dist[selectedBuildingMachine.value] > 0
      if (!hasSelected) {
        const dimmedStops = stops.map(s => ({
          offset: s.offset,
          color: 'rgba(241, 245, 249, 0.01)' // 极淡底色
        }))
        finalItemStyle = {
          color: {
            type: 'linear',
            x: 0,
            y: 1,
            x2: 0,
            y2: 0,
            colorStops: dimmedStops
          }
        }
      }
    }

    markAreaData.push([
      {
        xAxis: i - 0.5,
        itemStyle: finalItemStyle
      },
      {
        xAxis: i + 0.5
      }
    ])
  }

  // 4. 动态自适应计算 Y 轴刻度范围
  let yMin = 0
  let yMax = 3.0

  if (isBoxplotMode) {
    const validRawVals = validLots
      .flatMap(d => d.boxplot)
      .filter(v => v !== null && v !== undefined && !isNaN(v))

    if (validRawVals.length > 0) {
      if (localIndicator.value === 'weight') {
        const nonZeroVals = validRawVals.filter(v => v > 1.0)
        const realMin = nonZeroVals.length > 0 ? Math.min(...nonZeroVals) : 10.0
        const realMax = nonZeroVals.length > 0 ? Math.max(...nonZeroVals) : 16.0
        const targetUSL = props.uslValue && props.uslValue > 1.0 ? props.uslValue : realMax
        
        const minVal = Math.min(realMin, targetUSL)
        const maxVal = Math.max(realMax, targetUSL)
        yMin = Math.max(0.0, Math.floor((minVal - 0.25) * 10) / 10)
        yMax = Math.ceil((maxVal + 0.25) * 10) / 10
      } else {
        const targetUSL = props.uslValue || 100
        const minVal = Math.min(...validRawVals)
        const maxVal = Math.max(...validRawVals, targetUSL)
        yMin = Math.max(0, Math.floor((minVal - 2.0) / 5) * 5)
        yMax = Math.ceil((maxVal + 5.0) / 5) * 5
      }
    } else {
      yMin = 0
      yMax = 120
    }
  } else {
    const validCpkValues = currentData
      .filter(d => !d.is_break)
      .flatMap(d => [d.spec_cpk, d.multi_cpk])
      .filter(v => v !== null && v !== undefined && !isNaN(v))

    if (validCpkValues.length > 0) {
      const minVal = Math.min(...validCpkValues, 1.33)
      const maxVal = Math.max(...validCpkValues, 1.33)
      yMin = Math.max(0, Math.floor((minVal - 0.1) * 10) / 10)
      yMax = Math.min(5.0, Math.ceil((maxVal + 0.15) * 10) / 10)
    }
  }

  // 5. 构建 Series List
  const seriesList = []

  if (isBoxplotMode) {
    // ── 箱线图实际值模式 ──────────────────────────────────────────
    seriesList.push({
      name: '规格上限 USL',
      type: 'line',
      data: [],
      markLine: {
        symbol: 'none',
        data: [
          {
            yAxis: props.uslValue || 100,
            name: '规格上限 USL',
            lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
            label: { formatter: `USL 上限 (${props.uslValue || 100})`, position: 'end', color: '#ef4444', fontSize: 10 }
          }
        ]
      }
    })

    // 1. 单条 Boxplot Series 填充所有有效物料 (保留矩形箱体，中间中线为均值 Mean)
    const boxData = validLots.map(d => {
      const mColor = getMachineColor(d.machine)
      
      let isDimmed = false
      if (selectedBuildingMachine.value) {
        const dist = d.gt_distribution || {}
        const hasSelected = dist[selectedBuildingMachine.value] !== undefined && dist[selectedBuildingMachine.value] > 0
        if (!hasSelected) {
          isDimmed = true
        }
      }

      return {
        value: d.boxplot, // [min_v, q1_v, mean_v, q3_v, max_v]
        lotInfo: d,
        itemStyle: {
          color: isDimmed ? 'rgba(241, 245, 249, 0.03)' : hexToRgba(mColor, 0.25),
          borderColor: isDimmed ? 'rgba(203, 213, 225, 0.2)' : mColor,
          borderWidth: isDimmed ? 0.5 : 1.5
        }
      }
    })

    seriesList.push({
      name: '实际测量值箱线图',
      type: 'boxplot',
      boxWidth: [6, 26],
      data: boxData,
      markArea: {
        silent: true,
        data: markAreaData
      }
    })

    // 2. 增加按机台分组的【均值连接折线】(Mean Line)
    uniqueMachines.value.forEach(mInfo => {
      const mCode = mInfo.code
      const mColor = mInfo.color

      const meanData = validLots.map(d => {
        if (d.machine === mCode) {
          const val = d.mean_v !== undefined && d.mean_v !== null ? d.mean_v : (d.boxplot ? d.boxplot[2] : null)
          return {
            value: val,
            lotInfo: d
          }
        }
        return null
      })

      seriesList.push({
        name: `${mCode} 均值连线`,
        type: 'line',
        smooth: 0.2,
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: mColor, width: 2.0 },
        itemStyle: { color: mColor, borderColor: mColor },
        data: meanData
      })
    })

  } else {
    // ── CPK 模式 (按机台生成专属折线) ──────────────────────────────
    seriesList.push({
      name: 'CPK 预警线',
      type: 'line',
      data: [],
      markLine: {
        symbol: 'none',
        data: [
          {
            yAxis: 1.33,
            name: 'CPK 预警线',
            lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
            label: { formatter: 'CPK 预警线 (1.33)', position: 'end', color: '#ef4444', fontSize: 10 }
          }
        ]
      }
    })

    uniqueMachines.value.forEach((mInfo, idx) => {
      const mCode = mInfo.code
      const mColor = mInfo.color

      const specData = []
      const multiData = []

      currentData.forEach(d => {
        let isDimmed = false
        if (selectedBuildingMachine.value && !d.is_break) {
          const dist = d.gt_distribution || {}
          const hasSelected = dist[selectedBuildingMachine.value] !== undefined && dist[selectedBuildingMachine.value] > 0
          if (!hasSelected) {
            isDimmed = true
          }
        }

        if (!d.is_break && d.machine === mCode) {
          specData.push({
            value: d.spec_cpk,
            lotInfo: d,
            symbolSize: isDimmed ? 3 : 9,
            itemStyle: {
              opacity: isDimmed ? 0.15 : 1.0
            }
          })
          multiData.push({
            value: d.multi_cpk,
            lotInfo: d,
            symbolSize: isDimmed ? 3 : 9,
            itemStyle: {
              opacity: isDimmed ? 0.15 : 1.0
            }
          })
        } else {
          specData.push(null)
          multiData.push(null)
        }
      })

      const specSeries = {
        name: `${mCode} 单规格`,
        type: 'line',
        smooth: 0.25,
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 9,
        lineStyle: { color: mColor, width: 2.5 },
        itemStyle: { color: mColor, borderColor: mColor },
        data: specData
      }

      if (idx === 0) {
        specSeries.markArea = {
          silent: true,
          data: markAreaData
        }
      }

      seriesList.push(specSeries)

      seriesList.push({
        name: `${mCode} 其它规格加权`,
        type: 'line',
        smooth: 0.25,
        connectNulls: false,
        symbol: 'diamond',
        symbolSize: 9,
        lineStyle: { color: mColor, width: 2.0, type: 'dashed', opacity: 0.65 },
        itemStyle: { color: hexToRgba(mColor, 0.65), borderColor: mColor },
        data: multiData
      })
    })
  }

  const totalCount = isBoxplotMode ? validLots.length : currentData.length
  const zoomEnd = Math.min(100, Math.max(25, Math.round((22 / Math.max(1, totalCount)) * 100)))

  return {
    backgroundColor: 'transparent',
    grid: {
      left: 50,
      right: 30,
      top: 35,
      bottom: 95
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#1e293b', fontSize: 12 },
      formatter(params) {
        if (!params || params.length === 0) return ''
        const validParam = params.find(p => p.data && p.data.lotInfo)
        if (!validParam) return ''

        const lotInfo = validParam.data.lotInfo
        if (!lotInfo || lotInfo.is_break) return ''

        const mColor = getMachineColor(lotInfo.machine)

        let gtDistStr = 'N/A'
        if (lotInfo.gt_distribution && Object.keys(lotInfo.gt_distribution).length > 0) {
          gtDistStr = Object.entries(lotInfo.gt_distribution)
            .sort((a, b) => b[1] - a[1])
            .map(([mac, pct]) => `${mac} (${Math.round(pct * 100)}%)`)
            .join(' | ')
        }

        if (isBoxplotMode) {
          const bp = lotInfo.boxplot || [0, 0, 0, 0, 0]
          const meanV = lotInfo.mean_v !== undefined && lotInfo.mean_v !== null ? lotInfo.mean_v : bp[2]
          return `
            <div style="font-weight:bold; font-size:13px; margin-bottom:6px; color:#0f172a; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">
              【${lotInfo.component}】批次: ${lotInfo.lot}
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:3px;">
              <span style="color:#64748b;">加工机台:</span>
              <strong style="color:${mColor}">● ${lotInfo.machine}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:3px;">
              <span style="color:#64748b;">成型机台:</span>
              <strong>${gtDistStr}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:2px;">
              <span style="color:#64748b;">样本条数:</span>
              <strong>N = ${lotInfo.spec_n}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:2px;">
              <span style="color:#64748b;">最大值 (Max):</span>
              <strong style="color:#dc2626">${bp[4]}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:2px;">
              <span style="color:#64748b;">均值 (Mean):</span>
              <strong style="color:#2563eb">${meanV}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px;">
              <span style="color:#64748b;">最小值 (Min):</span>
              <strong style="color:#059669">${bp[0]}</strong>
            </div>
            <div style="margin-top:6px; font-size:10px; color:#94a3b8; text-align:right; border-top:1px dashed #e2e8f0; padding-top:4px;">
              💡 点击图形查看 Barcode 级明细
            </div>
          `
        } else {
          return `
            <div style="font-weight:bold; font-size:13px; margin-bottom:6px; color:#0f172a; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">
              【${lotInfo.component}】批次: ${lotInfo.lot}
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:3px;">
              <span style="color:#64748b;">加工机台:</span>
              <strong style="color:${mColor}">● ${lotInfo.machine}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:3px;">
              <span style="color:#64748b;">成型机台:</span>
              <strong>${gtDistStr}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:3px;">
              <span style="color:#64748b;">单规格 CPK (${props.selectedArticle || '当前'}):</span>
              <strong style="color:${lotInfo.spec_cpk < 1.33 ? '#dc2626' : '#16a34a'}">${lotInfo.spec_cpk} (N=${lotInfo.spec_n})</strong>
            </div>
            <div style="display:flex; justify-content:space-between; gap:16px;">
              <span style="color:#64748b;">其它规格加权 CPK (已排除单规格):</span>
              <strong style="color:${lotInfo.multi_cpk < 1.33 ? '#dc2626' : '#d97706'}">${lotInfo.multi_cpk} (N=${lotInfo.multi_n})</strong>
            </div>
            <div style="margin-top:6px; font-size:10px; color:#94a3b8; text-align:right; border-top:1px dashed #e2e8f0; padding-top:4px;">
              💡 点击图形查看 Barcode 级明细
            </div>
          `
        }
      }
    },
    dataZoom: [
      {
        type: 'slider',
        show: true,
        orient: 'horizontal',
        start: 0,
        end: zoomEnd,
        height: 20,
        bottom: 10,
        borderColor: '#cbd5e1',
        fillerColor: 'rgba(51, 65, 85, 0.15)',
        handleStyle: { color: '#334155' }
      },
      { type: 'inside', orient: 'horizontal' },
      {
        type: 'slider',
        show: true,
        orient: 'vertical',
        right: 40,
        borderColor: '#cbd5e1',
        fillerColor: 'rgba(51, 65, 85, 0.15)',
        handleStyle: { color: '#334155' }
      },
      { type: 'inside', orient: 'vertical' }
    ],
    xAxis: {
      type: 'category',
      data: xCategories,
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisTick: { alignWithLabel: true },
      axisLabel: {
        fontSize: 10,
        color: '#334155',
        interval: 0,
        rotate: 45,
        lineHeight: 13
      }
    },
    yAxis: {
      type: 'value',
      name: isBoxplotMode ? (localIndicator.value === 'weight' ? '实测胎重 (kg)' : `测量实际值 (${(localIndicator.value || 'rfpp').toUpperCase()})`) : 'CPK 指数',
      nameTextStyle: { color: '#64748b', fontSize: 11 },
      min: yMin,
      max: yMax,
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
      axisLabel: { color: '#64748b', fontSize: 11 }
    },
    series: seriesList
  }
})
</script>

<style scoped>
.lot-chart-container {
  overflow: hidden;
}

.wc-nav-btn {
  background: var(--c-surface-2);
  border: none;
  color: var(--c-text-secondary);
  font-size: 11px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--dur-normal) var(--ease);
}

.wc-nav-btn:hover {
  background: var(--c-accent-light);
  color: var(--c-accent);
  transform: translateY(-1px);
}

.wc-nav-btn.active {
  background: var(--c-accent);
  color: #ffffff;
  font-weight: 600;
}
</style>
