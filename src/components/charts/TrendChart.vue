<template>
  <div 
    class="chart-wrap"
    @mousedown="handleMouseDown"
    @mousemove="handleMouseMove"
    @mouseup="handleMouseUp"
    @mouseleave="handleMouseUp"
  >
    <div v-if="loading" class="skeleton" style="height:100%" />
    <div v-else-if="error" class="chart-error">
      <el-icon size="24"><WarningFilled /></el-icon>
      <span>{{ error }}</span>
    </div>
    <v-chart ref="chartRef" v-else :option="option" autoresize style="width:100%;height:100%" @click="onChartClick" />
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { useFilterStore } from '../../store/filter.js'
import {
  GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkLineComponent, MarkAreaComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { WarningFilled } from '@element-plus/icons-vue'

use([BarChart, LineChart, GridComponent, TooltipComponent,
     LegendComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent, CanvasRenderer])

const props = defineProps({
  data:            { type: Array, default: () => [] },
  cpkData:         { type: Object, default: () => ({}) },
  showCpk:         { type: Boolean, default: false },
  showAnomalyRate: { type: Boolean, default: true },
  loading:         { type: Boolean, default: false },
  error:           { type: String, default: null },
  xKey:            { type: String, default: 'date' },
  indicator:       { type: String, default: 'rfpp' }, // 'rfpp' | 'rfh1'
  selectedDate:    { type: String, default: null }
})

const filterStore = useFilterStore()

const chartRef = ref(null)
const isDragging = ref(false)
const draggedLine = ref(null) // 'b_from' | 'b_to' | 's_from' | 's_to'
const localBaselineRange = ref([null, null])
const localStudyRange = ref([null, null])

watch(
  () => filterStore.baselineRange,
  (val) => {
    if (val) {
      localBaselineRange.value = [...val]
    } else {
      localBaselineRange.value = [null, null]
    }
  },
  { immediate: true, deep: true }
)

watch(
  () => filterStore.studyRange,
  (val) => {
    if (val) {
      localStudyRange.value = [...val]
    } else {
      localStudyRange.value = [null, null]
    }
  },
  { immediate: true, deep: true }
)

function getXIndexFromEvent(e) {
  const chart = chartRef.value?.chart
  if (!chart) return -1
  const rect = e.currentTarget.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  const point = chart.convertFromPixel({ gridIndex: 0 }, [x, y])
  if (point) {
    return Math.round(point[0])
  }
  return -1
}

function handleMouseDown(e) {
  const labels = props.cpkData.dates || []
  if (labels.length === 0) return

  const b_from = localBaselineRange.value[0]
  const b_to = localBaselineRange.value[1]
  const s_from = localStudyRange.value[0]
  const s_to = localStudyRange.value[1]

  const xIndex = getXIndexFromEvent(e)
  if (xIndex === -1) return

  const bFromIdx = b_from ? labels.indexOf(b_from) : -1
  const bToIdx = b_to ? labels.indexOf(b_to) : -1
  const sFromIdx = s_from ? labels.indexOf(s_from) : -1
  const sToIdx = s_to ? labels.indexOf(s_to) : -1

  let nearLine = null
  if (bFromIdx !== -1 && Math.abs(xIndex - bFromIdx) <= 1) nearLine = 'b_from'
  else if (bToIdx !== -1 && Math.abs(xIndex - bToIdx) <= 1) nearLine = 'b_to'
  else if (sFromIdx !== -1 && Math.abs(xIndex - sFromIdx) <= 1) nearLine = 's_from'
  else if (sToIdx !== -1 && Math.abs(xIndex - sToIdx) <= 1) nearLine = 's_to'

  if (nearLine) {
    isDragging.value = true
    draggedLine.value = nearLine
    e.currentTarget.style.cursor = 'ew-resize'
  }
}

function handleMouseMove(e) {
  const labels = props.cpkData.dates || []
  if (labels.length === 0) return

  const b_from = localBaselineRange.value[0]
  const b_to = localBaselineRange.value[1]
  const s_from = localStudyRange.value[0]
  const s_to = localStudyRange.value[1]

  const xIndex = getXIndexFromEvent(e)
  if (xIndex === -1) return

  const bFromIdx = b_from ? labels.indexOf(b_from) : -1
  const bToIdx = b_to ? labels.indexOf(b_to) : -1
  const sFromIdx = s_from ? labels.indexOf(s_from) : -1
  const sToIdx = s_to ? labels.indexOf(s_to) : -1

  if (isDragging.value) {
    const target = draggedLine.value
    if (!target) return
    e.currentTarget.style.cursor = 'ew-resize'

    if (target === 'b_from') {
      const limit = bToIdx !== -1 ? bToIdx : labels.length - 1
      if (xIndex >= 0 && xIndex <= limit) {
        localBaselineRange.value = [labels[xIndex], b_to]
      }
    } else if (target === 'b_to') {
      const minLimit = bFromIdx !== -1 ? bFromIdx : 0
      const maxLimit = sFromIdx !== -1 ? sFromIdx : labels.length - 1
      if (xIndex >= minLimit && xIndex <= maxLimit) {
        localBaselineRange.value = [b_from, labels[xIndex]]
      }
    } else if (target === 's_from') {
      const minLimit = bToIdx !== -1 ? bToIdx : 0
      const maxLimit = sToIdx !== -1 ? sToIdx : labels.length - 1
      if (xIndex >= minLimit && xIndex <= maxLimit) {
        localStudyRange.value = [labels[xIndex], s_to]
      }
    } else if (target === 's_to') {
      const minLimit = sFromIdx !== -1 ? sFromIdx : 0
      if (xIndex >= minLimit && xIndex < labels.length) {
        localStudyRange.value = [s_from, labels[xIndex]]
      }
    }
  } else {
    let nearLine = null
    if (bFromIdx !== -1 && Math.abs(xIndex - bFromIdx) <= 1) nearLine = 'b_from'
    else if (bToIdx !== -1 && Math.abs(xIndex - bToIdx) <= 1) nearLine = 'b_to'
    else if (sFromIdx !== -1 && Math.abs(xIndex - sFromIdx) <= 1) nearLine = 's_from'
    else if (sToIdx !== -1 && Math.abs(xIndex - sToIdx) <= 1) nearLine = 's_to'

    if (nearLine) {
      e.currentTarget.style.cursor = 'ew-resize'
    } else {
      e.currentTarget.style.cursor = 'default'
    }
  }
}

function handleMouseUp(e) {
  if (isDragging.value) {
    isDragging.value = false
    const target = draggedLine.value
    draggedLine.value = null
    e.currentTarget.style.cursor = 'default'

    if (target === 'b_from' || target === 'b_to') {
      filterStore.setBaselineRange([...localBaselineRange.value])
    } else if (target === 's_from' || target === 's_to') {
      filterStore.setStudyRange([...localStudyRange.value])
    }
  }
}

const option = computed(() => {
  const activeKey = props.indicator === 'cony'
    ? 'CONY 综合 实际值'
    : (props.indicator === 'weight' ? '胎重 综合 偏差' : (props.indicator === 'rfpp' ? 'RFPP 综合 CPK' : 'RFH1 综合 CPK'))
  const labels = props.cpkData.dates || []
  const cpkValues = props.cpkData.cpk_trends?.[activeKey] || []

  // Calculate Mean and StdDev dynamically
  const validValues = cpkValues.filter(v => v !== null && !isNaN(v))
  const n = validValues.length
  const mean = n > 0 ? validValues.reduce((sum, v) => sum + v, 0) / n : 0
  const variance = n > 1 ? validValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / (n - 1) : 0
  const std = n > 1 ? Math.sqrt(variance) : 0

  const mlData = []
  const T = filterStore.weightTolerance || 0.8
  
  // Add control limit horizontal lines
  if (n > 0) {
    if (props.indicator === 'weight') {
      mlData.push(
        {
          yAxis: 0,
          lineStyle: { color: '#16a34a', type: 'solid', width: 2 },
          label: {
            show: true,
            position: 'start',
            formatter: '理想目标: 0.0%',
            color: '#16a34a',
            fontSize: 10,
            fontWeight: 'bold'
          }
        },
        {
          yAxis: T,
          lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
          label: {
            show: true,
            position: 'end',
            formatter: `上限: +${T}%`,
            color: '#ef4444',
            fontSize: 10,
            fontWeight: 'bold'
          }
        },
        {
          yAxis: -T,
          lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
          label: {
            show: true,
            position: 'end',
            formatter: `下限: -${T}%`,
            color: '#ef4444',
            fontSize: 10,
            fontWeight: 'bold'
          }
        }
      )
    } else if (props.indicator === 'cony') {
      mlData.push(
        {
          yAxis: mean,
          lineStyle: { color: '#16a34a', type: 'solid', width: 2 },
          label: {
            show: true,
            position: 'start',
            formatter: `Mean: ${mean.toFixed(3)}`,
            color: '#16a34a',
            fontSize: 10,
            fontWeight: 'bold'
          }
        },
        {
          yAxis: mean + std,
          lineStyle: { color: '#d97706', type: 'dotted', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ+1σ: ${(mean + std).toFixed(3)}`,
            color: '#d97706',
            fontSize: 10
          }
        },
        {
          yAxis: mean + 2 * std,
          lineStyle: { color: '#d97706', type: 'dotted', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ+2σ: ${(mean + 2 * std).toFixed(3)}`,
            color: '#d97706',
            fontSize: 10
          }
        },
        {
          yAxis: mean + 3 * std,
          lineStyle: { color: '#b91c1c', type: 'dashed', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ+3σ (UCL): ${(mean + 3 * std).toFixed(3)}`,
            color: '#b91c1c',
            fontSize: 10,
            fontWeight: 'bold'
          }
        },
        {
          yAxis: mean - std,
          lineStyle: { color: '#d97706', type: 'dotted', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ-1σ: ${(mean - std).toFixed(3)}`,
            color: '#d97706',
            fontSize: 10
          }
        },
        {
          yAxis: mean - 2 * std,
          lineStyle: { color: '#d97706', type: 'dotted', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ-2σ: ${(mean - 2 * std).toFixed(3)}`,
            color: '#d97706',
            fontSize: 10
          }
        },
        {
          yAxis: mean - 3 * std,
          lineStyle: { color: '#b91c1c', type: 'dashed', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ-3σ (LCL): ${(mean - 3 * std).toFixed(3)}`,
            color: '#b91c1c',
            fontSize: 10,
            fontWeight: 'bold'
          }
        }
      )
    } else {
      mlData.push(
        {
          yAxis: mean,
          lineStyle: { color: '#16a34a', type: 'solid', width: 2 },
          label: {
            show: true,
            position: 'start',
            formatter: `Mean: ${mean.toFixed(3)}`,
            color: '#16a34a',
            fontSize: 10,
            fontWeight: 'bold'
          }
        },
        {
          yAxis: mean - std,
          lineStyle: { color: '#d97706', type: 'dotted', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ-1σ: ${(mean - std).toFixed(3)}`,
            color: '#d97706',
            fontSize: 10
          }
        },
        {
          yAxis: mean - 2 * std,
          lineStyle: { color: '#d97706', type: 'dotted', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ-2σ: ${(mean - 2 * std).toFixed(3)}`,
            color: '#d97706',
            fontSize: 10
          }
        },
        {
          yAxis: mean - 3 * std,
          lineStyle: { color: '#b91c1c', type: 'dashed', width: 1.5 },
          label: {
            show: true,
            position: 'start',
            formatter: `μ-3σ (LCL): ${(mean - 3 * std).toFixed(3)}`,
            color: '#b91c1c',
            fontSize: 10,
            fontWeight: 'bold'
          }
        },
        {
          yAxis: 1.33,
          lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
          label: {
            show: true,
            position: 'end',
            formatter: 'Target: 1.33',
            color: '#ef4444',
            fontSize: 10,
            fontWeight: 'bold'
          }
        }
      )
    }
  }

  if (props.selectedDate && labels.includes(props.selectedDate)) {
    mlData.push({
      xAxis: props.selectedDate,
      lineStyle: { color: '#8b5cf6', type: 'dashed', width: 2 },
      label: {
        show: true,
        position: 'end',
        formatter: '已选分析点',
        fontSize: 9,
        color: '#4c1d95',
        backgroundColor: 'rgba(243, 232, 255, 0.95)',
        padding: [3, 5],
        borderRadius: 4,
        borderColor: '#ddd6fe',
        borderWidth: 1
      }
    })
  }

  // Highlight points: outside warning limits gets red, normal gets blue
  const alignedCpkData = cpkValues.map((val, idx) => {
    if (val === null || isNaN(val)) return null
    const isAnomaly = props.indicator === 'weight'
      ? (Math.abs(val) > T)
      : (props.indicator === 'cony'
         ? (n > 0 && (val < (mean - std) || val > (mean + std)))
         : (n > 0 && val < (mean - std)))

    if (isAnomaly) {
      return {
        value: val,
        symbol: 'circle',
        symbolSize: 10,
        itemStyle: {
          color: '#ef4444',
          borderColor: '#fecaca',
          borderWidth: 3,
          shadowBlur: 5,
          shadowColor: 'rgba(239, 68, 68, 0.4)'
        },
        label: {
          show: true,
          position: 'top',
          color: '#ef4444',
          fontWeight: 'bold',
          fontSize: 10,
          formatter: (p) => {
            const v = p.value
            if (props.indicator === 'weight' && typeof v === 'number') {
              const sign = v > 0 ? '+' : ''
              return `${sign}${v.toFixed(2)}%`
            }
            return v
          }
        }
      }
    } else {
      return {
        value: val,
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: {
          color: '#3b82f6',
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: props.indicator === 'weight',
          position: 'top',
          color: '#3b82f6',
          fontSize: 9,
          formatter: (p) => {
            const v = p.value
            if (typeof v === 'number') {
              const sign = v > 0 ? '+' : ''
              return `${sign}${v.toFixed(2)}%`
            }
            return v
          }
        }
      }
    }
  })

  // Control chart background zone markAreas
  const controlAreas = props.indicator === 'weight' ? [
    [
      {
        yAxis: T,
        itemStyle: { color: 'rgba(16, 185, 129, 0.06)' } // 正常稳定区间 (light green)
      },
      {
        yAxis: -T
      }
    ],
    [
      {
        yAxis: T,
        itemStyle: { color: 'rgba(239, 68, 68, 0.06)' } // 超正差 (light red)
      },
      {
        yAxis: 999999
      }
    ],
    [
      {
        yAxis: -999999,
        itemStyle: { color: 'rgba(239, 68, 68, 0.06)' } // 超负差 (light red)
      },
      {
        yAxis: -T
      }
    ]
  ] : (props.indicator === 'cony' ? [
    [
      {
        yAxis: mean + std,
        itemStyle: { color: 'rgba(16, 185, 129, 0.06)' }
      },
      {
        yAxis: mean - std
      }
    ],
    [
      {
        yAxis: mean + 2 * std,
        itemStyle: { color: 'rgba(245, 158, 11, 0.04)' }
      },
      {
        yAxis: mean + std
      }
    ],
    [
      {
        yAxis: mean + 3 * std,
        itemStyle: { color: 'rgba(245, 158, 11, 0.12)' }
      },
      {
        yAxis: mean + 2 * std
      }
    ],
    [
      {
        yAxis: mean - std,
        itemStyle: { color: 'rgba(245, 158, 11, 0.04)' }
      },
      {
        yAxis: mean - 2 * std
      }
    ],
    [
      {
        yAxis: mean - 2 * std,
        itemStyle: { color: 'rgba(245, 158, 11, 0.12)' }
      },
      {
        yAxis: mean - 3 * std
      }
    ],
    [
      {
        yAxis: mean + 3 * std,
        itemStyle: { color: 'rgba(239, 68, 68, 0.06)' }
      },
      {
        yAxis: 999999
      }
    ],
    [
      {
        yAxis: -999999,
        itemStyle: { color: 'rgba(239, 68, 68, 0.06)' }
      },
      {
        yAxis: mean - 3 * std
      }
    ]
  ] : [
    [
      {
        yAxis: mean - std,
        itemStyle: { color: 'rgba(16, 185, 129, 0.06)' }
      },
      {
        yAxis: 10.0 // high upper bound
      }
    ],
    [
      {
        yAxis: mean - 2 * std,
        itemStyle: { color: 'rgba(245, 158, 11, 0.04)' }
      },
      {
        yAxis: mean - std
      }
    ],
    [
      {
        yAxis: mean - 3 * std,
        itemStyle: { color: 'rgba(245, 158, 11, 0.12)' }
      },
      {
        yAxis: mean - 2 * std
      }
    ],
    [
      {
        yAxis: 0,
        itemStyle: { color: 'rgba(239, 68, 68, 0.06)' }
      },
      {
        yAxis: mean - 3 * std
      }
    ]
  ])

  // Merge period markAreas and control zone markAreas
  const finalMarkAreas = controlAreas

  const legendNames = props.indicator === 'weight' ? [
    activeKey,
    '理想目标: 0.0%',
    `偏差公差限 (±${T}%)`,
    '稳定区间',
    '超出公差区间'
  ] : (props.indicator === 'cony' ? [
    activeKey,
    `历史均值 (CL: ${mean.toFixed(3)})`,
    '[稳定] 均值±1σ 正常区间',
    '[预警] 1σ ~ 2σ 警戒区间',
    '[行动] 2σ ~ 3σ 严重预警',
    '[失控] 超出 3σ 控制限'
  ] : [
    activeKey,
    `历史均值 (CL: ${mean.toFixed(3)})`,
    '行业达标 Target (1.33)',
    '[优秀/稳定] 正常区间',
    '[预警] 1σ ~ 2σ 区间',
    '[行动] 2σ ~ 3σ 严重预警',
    '[失控] 低于 3σ 下限'
  ])

  const series = props.indicator === 'weight' ? [
    {
      name: activeKey,
      type: 'line',
      data: alignedCpkData,
      lineStyle: { width: 2.5, color: '#3b82f6' },
      markLine: { silent: true, symbol: 'none', data: mlData },
      markArea: { silent: true, data: finalMarkAreas }
    },
    {
      name: '理想目标: 0.0%',
      type: 'line',
      color: '#16a34a',
      lineStyle: { width: 2 },
      data: []
    },
    {
      name: `偏差公差限 (±${T}%)`,
      type: 'line',
      color: '#ef4444',
      lineStyle: { type: 'dashed', width: 1.5 },
      data: []
    },
    {
      name: '稳定区间',
      type: 'bar',
      color: 'rgba(16, 185, 129, 0.15)',
      data: []
    },
    {
      name: '超出公差区间',
      type: 'bar',
      color: 'rgba(239, 68, 68, 0.1)',
      data: []
    }
  ] : (props.indicator === 'cony' ? [
    {
      name: activeKey,
      type: 'line',
      data: alignedCpkData,
      lineStyle: { width: 2.5, color: '#3b82f6' },
      markLine: { silent: true, symbol: 'none', data: mlData },
      markArea: { silent: true, data: finalMarkAreas }
    },
    // Dummy series to draw legend items
    {
      name: `历史均值 (CL: ${mean.toFixed(3)})`,
      type: 'line',
      color: '#16a34a',
      lineStyle: { width: 2 },
      data: []
    },
    {
      name: '[稳定] 均值±1σ 正常区间',
      type: 'bar',
      color: 'rgba(16, 185, 129, 0.15)',
      data: []
    },
    {
      name: '[预警] 1σ ~ 2σ 警戒区间',
      type: 'bar',
      color: 'rgba(245, 158, 11, 0.08)',
      data: []
    },
    {
      name: '[行动] 2σ ~ 3σ 严重预警',
      type: 'bar',
      color: 'rgba(245, 158, 11, 0.18)',
      data: []
    },
    {
      name: '[失控] 超出 3σ 控制限',
      type: 'bar',
      color: 'rgba(239, 68, 68, 0.1)',
      data: []
    }
  ] : [
    {
      name: activeKey,
      type: 'line',
      data: alignedCpkData,
      lineStyle: { width: 2.5, color: '#3b82f6' },
      markLine: { silent: true, symbol: 'none', data: mlData },
      markArea: { silent: true, data: finalMarkAreas }
    },
    // Dummy series to draw legend items
    {
      name: `历史均值 (CL: ${mean.toFixed(3)})`,
      type: 'line',
      color: '#16a34a',
      lineStyle: { width: 2 },
      data: []
    },
    {
      name: '行业达标 Target (1.33)',
      type: 'line',
      color: '#ef4444',
      lineStyle: { type: 'dashed', width: 1.5 },
      data: []
    },
    {
      name: '[优秀/稳定] 正常区间',
      type: 'bar',
      color: 'rgba(16, 185, 129, 0.15)',
      data: []
    },
    {
      name: '[预警] 1σ ~ 2σ 区间',
      type: 'bar',
      color: 'rgba(245, 158, 11, 0.08)',
      data: []
    },
    {
      name: '[行动] 2σ ~ 3σ 严重预警',
      type: 'bar',
      color: 'rgba(245, 158, 11, 0.18)',
      data: []
    },
    {
      name: '[失控] 低于 3σ 下限',
      type: 'bar',
      color: 'rgba(239, 68, 68, 0.1)',
      data: []
    }
  ])

  return {
    backgroundColor: 'transparent',
    grid: { top: 72, right: 40, bottom: 56, left: 60, containLabel: true },
    legend: {
      top: 8,
      left: 'center',
      orient: 'horizontal',
      itemWidth: 12,
      itemHeight: 12,
      icon: 'roundRect',
      textStyle: { fontSize: 11, color: '#57606a' },
      data: legendNames,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#fff',
      borderColor: '#e5e8ef',
      borderWidth: 1,
      textStyle: { color: '#0d1117', fontSize: 12 },
      formatter(params) {
        const date = params[0]?.axisValue ?? ''
        let html = `<div style="font-weight:600;margin-bottom:6px">${date}</div>`
        params.forEach(p => {
          if (p.seriesName.includes('正常区间') || p.seriesName.includes('稳定区间') || p.seriesName.includes('超出公差') || p.seriesName.includes('区间') || p.seriesName.includes('下限')) return
          if (p.value === undefined || p.value === null || (Array.isArray(p.value) && p.value.length === 0)) return
          
          const color = p.color?.colorStops?.[0]?.color ?? p.color
          const valueText = typeof p.value === 'number' ? (props.indicator === 'weight' ? p.value.toFixed(4) + '%' : p.value.toFixed(4)) : p.value
          html += `<div style="display:flex;justify-content:space-between;gap:16px">
            <span><span style="display:inline-block;width:8px;height:8px;background:${color};border-radius:2px;margin-right:5px"></span>${p.seriesName}</span>
            <span style="font-weight:600;font-variant-numeric:tabular-nums">${valueText}</span>
          </div>`
        })
        return html
      },
    },
    xAxis: {
      type: 'category',
      data: labels,
      triggerEvent: true,
      axisLabel: {
        fontSize: 10,
        color: '#8c959f',
        rotate: 35,
        interval: 0,
        formatter: (val) => {
          if (props.selectedDate && val === props.selectedDate) {
            return `{selected|${val}}`
          }
          return val
        },
        rich: {
          selected: {
            color: '#fff',
            backgroundColor: '#8b5cf6',
            padding: [2, 5],
            borderRadius: 3,
            fontWeight: 'bold'
          }
        }
      },
      axisLine: { lineStyle: { color: '#e5e8ef' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: props.indicator === 'weight' ? '生产偏差比率' : (props.indicator === 'cony' ? '实际值' : '加权 CPK'),
      nameTextStyle: { fontSize: 11, color: '#8c959f', padding: [0, 0, 0, -20] },
      axisLabel: { 
        fontSize: 11, 
        color: '#8c959f', 
        formatter: props.indicator === 'weight' ? '{value}%' : '{value}'
      },
      min: value => {
        if (props.indicator === 'weight') {
          const localMin = value.min !== undefined ? value.min : -1.0
          const baseline = Math.min(-T, localMin)
          return +(baseline - 0.2).toFixed(2)
        }
        if (props.indicator === 'cony') {
          const minLcl = mean - 3 * std
          const localMin = value.min !== undefined ? value.min : -10
          const baseline = Math.min(minLcl, localMin)
          return +(baseline - Math.max(0.1, Math.abs(std))).toFixed(2)
        }
        const minLcl = mean - 3 * std
        const localMin = value.min !== undefined ? value.min : 0
        const baseline = Math.min(minLcl, localMin, 1.2)
        return Math.max(0, +(baseline - 0.05).toFixed(2))
      },
      max: value => {
        if (props.indicator === 'weight') {
          const localMax = value.max !== undefined ? value.max : 1.0
          const baseline = Math.max(T, localMax)
          return +(baseline + 0.2).toFixed(2)
        }
        if (props.indicator === 'cony') {
          const maxUcl = mean + 3 * std
          const localMax = value.max !== undefined ? value.max : 0
          const baseline = Math.max(maxUcl, localMax)
          return +(baseline + Math.max(0.1, Math.abs(std))).toFixed(2)
        }
        const localMax = value.max !== undefined ? value.max : 1.5
        const baseline = Math.max(mean + std, localMax, 1.5)
        return +(baseline + 0.05).toFixed(2)
      },
      splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: series,
    dataZoom: labels.length > 30 ? [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', height: 18, bottom: 0,
        handleStyle: { color: '#2563eb' },
        textStyle: { color: '#8c959f', fontSize: 10 },
        borderColor: '#e5e8ef' },
    ] : [],
  }
})

const emit = defineEmits(['date-select'])

function onChartClick(params) {
  if (params.componentType === 'series' && params.name) {
    emit('date-select', params.name)
  } else if (params.componentType === 'xAxis' && params.value) {
    emit('date-select', params.value)
  }
}
</script>

<style scoped>
.chart-wrap { width: 100%; height: 100%; position: relative; }
.chart-error {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--c-text-muted);
  font-size: 13px;
}
</style>
