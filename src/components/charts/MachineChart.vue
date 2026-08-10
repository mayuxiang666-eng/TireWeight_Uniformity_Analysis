<template>
  <div class="chart-wrap">
    <div v-if="loading" class="skeleton" style="height:100%" />
    <div v-else-if="error" class="chart-error">
      <el-icon size="24"><WarningFilled /></el-icon>
      <span>{{ error }}</span>
    </div>
    <v-chart v-else :option="option" autoresize style="width:100%;height:100%" @click="onBarClick" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { WarningFilled } from '@element-plus/icons-vue'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const props = defineProps({
  data:    { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error:   { type: String, default: null },
})

const emit = defineEmits(['select-machine'])

function onBarClick(params) {
  if (params.componentType === 'series') {
    const row = props.data[params.dataIndex]
    if (row) {
      emit('select-machine', row)
    }
  }
}

// 颜色映射：不同工序用不同色
const wc_colors = [
  '#2563eb','#7c3aed','#db2777','#ea580c',
  '#d97706','#16a34a','#0891b2','#65a30d',
  '#4f46e5','#be123c','#b45309','#047857',
]

const option = computed(() => {
  const d = props.data
  const labels   = d.map(r => {
    const m = r.machine ?? ''
    return m.length > 20 ? m.slice(0, 19) + '…' : m
  })
  
  const chartValues = d.map(r => r.step_lift ?? 0)
  const maxVal = Math.max(...chartValues, 1)

  // 按 workcenter_col 分组着色（使用名称哈希固定颜色，避免顺序变化导致颜色漂移）
  const wcList = [...new Set(d.map(r => r.workcenter_col))]
  const colorMap = {}
  wcList.forEach(wc => {
    let hash = 0
    for (let c of String(wc)) hash = (hash * 31 + c.charCodeAt(0)) & 0xffff
    colorMap[wc] = wc_colors[hash % wc_colors.length]
  })

  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 80, bottom: 4, left: 4, containLabel: true },
    dataZoom: [
      {
        type: 'slider',
        yAxisIndex: 0,
        start: 0,
        end: 100,
        width: 12,
        right: 15,
        textStyle: { fontSize: 8 }
      },
      {
        type: 'inside',
        yAxisIndex: 0
      }
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'none' },
      backgroundColor: '#fff',
      borderColor: '#e5e8ef',
      borderWidth: 1,
      textStyle: { color: '#0d1117', fontSize: 12 },
      formatter(params) {
        const idx   = params[0]?.dataIndex ?? 0
        const row   = d[idx] ?? {}
        let html = `
          <div style="font-weight:600;margin-bottom:6px">${row.machine ?? ''}</div>
          <div style="font-size:11px;color:#8c959f;margin-bottom:8px">工序：${row.workcenter_col ?? ''}</div>
        `
        if (row.step_lift !== undefined) {
          html += `<div style="display:flex;justify-content:space-between;gap:16px">
            <span>异常提升度 (Step Lift)</span><span style="font-weight:600;color:#7c3aed">${row.step_lift}x</span>
          </div>`
        }
        return html
      },
    },
    xAxis: {
      type: 'value',
      axisLabel: { 
        fontSize: 10, 
        color: '#8c959f',
        formatter: v => v + 'x'
      },
      splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'category',
      data: labels,
      axisLabel: { fontSize: 10, color: '#0d1117' },
      axisLine: { show: false },
      axisTick: { show: false },
      inverse: true,
    },
    series: [
      {
        name: 'Step Lift',
        type: 'bar',
        data: chartValues.map((v, i) => {
          const baseColor = colorMap[d[i]?.workcenter_col] ?? '#2563eb'
          const opacity = 0.5 + 0.5 * (v / maxVal)

          return {
            value: v,
            itemStyle: {
              color: baseColor,
              borderRadius: [0, 4, 4, 0],
              opacity: opacity,
            },
          }
        }),
        barMaxWidth: 18,
        label: {
          show: true,
          position: 'right',
          formatter: (p) => {
            const idx = p.dataIndex
            const row = d[idx] ?? {}
            return `{rate|${row.step_lift}x}`
          },
          rich: {
            rate: { fontSize: 10, color: '#f59e0b', fontFamily: 'JetBrains Mono,monospace', fontWeight: '500' },
          },
        },
        emphasis: {
          focus: 'self',
          itemStyle: { opacity: 1, shadowBlur: 6, shadowColor: 'rgba(0,0,0,.2)' },
        },
      },
    ],
  }
})
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
