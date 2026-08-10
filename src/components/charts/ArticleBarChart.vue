<template>
  <div class="chart-wrap">
    <div v-if="loading" class="skeleton" style="height:100%" />
    <div v-else-if="error" class="chart-error">
      <el-icon size="24"><WarningFilled /></el-icon>
      <span>{{ error }}</span>
    </div>
    <v-chart
      v-else
      :option="option"
      autoresize
      style="width:100%;height:100%"
      @click="onBarClick"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { WarningFilled } from '@element-plus/icons-vue'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  data:            { type: Array, default: () => [] },
  loading:         { type: Boolean, default: false },
  error:           { type: String, default: null },
  selectedArticle: { type: String, default: null },
  indicator:       { type: String, default: 'rfpp' }
})

const emit = defineEmits(['drill-down'])

const option = computed(() => {
  const d = props.data
  const labels = d.map(r => r.article10)
  
  const chartValues = d.map(r => r.stable_score ?? 0)
  const hasSelection = props.selectedArticle !== null && props.selectedArticle !== undefined && props.selectedArticle !== ''
  const isWeight = props.indicator === 'weight'

  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 125, bottom: 4, left: 4, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'none' },
      backgroundColor: '#fff',
      borderColor: '#e5e8ef',
      borderWidth: 1,
      textStyle: { color: '#0d1117', fontSize: 12 },
      formatter(params) {
        const idx = params[0]?.dataIndex ?? 0
        const row = d[idx] ?? {}
        let html = `<div style="font-weight:600;margin-bottom:8px;max-width:220px;word-break:break-all">${row.article10}</div>`
        
        if (row.stable_score !== undefined) {
          if (isWeight) {
            const singlePct = row.single_cpk !== undefined && row.single_cpk !== null ? (row.single_cpk > 0 ? '+' : '') + row.single_cpk.toFixed(2) + '%' : '暂无数据'
            const avgPct = row.avg_cpk !== undefined && row.avg_cpk !== null ? (row.avg_cpk > 0 ? '+' : '') + row.avg_cpk.toFixed(2) + '%' : '暂无数据'
            const scoreStr = (row.stable_score > 0 ? '+' : '') + row.stable_score.toFixed(4)
            html += `
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>单日规格偏差率</span>
                <span style="font-weight:bold;color:#ef4444">${singlePct}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>全厂整体偏差率</span>
                <span style="font-weight:600">${avgPct}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>单日排产条数 (N)</span>
                <span style="font-weight:600">${row.sample_size}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>主要责任机台</span>
                <span style="font-weight:600;color:#ef4444">🔴 ${row.warning_machine || '无'}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>偏差贡献度</span>
                <span style="font-weight:bold;color:#ef4444">${scoreStr}</span>
              </div>
            `
          } else {
            html += `
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>单日规格 CPK</span>
                <span style="font-weight:bold;color:#ef4444">${row.single_cpk.toFixed(4)}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>系统 CPK 均值 (加权)</span>
                <span style="font-weight:600">${row.avg_cpk.toFixed(4)}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>单日排产条数 (N)</span>
                <span style="font-weight:600">${row.sample_size}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>主要责任机台</span>
                <span style="font-weight:600;color:#ef4444">🔴 ${row.warning_machine || '无'}</span>
              </div>
              <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:3px">
                <span>CPK 负向贡献</span>
                <span style="font-weight:bold;color:#ef4444">${row.stable_score.toFixed(2)}</span>
              </div>
            `
          }
        }
        
        html += `<div style="margin-top:8px;font-size:11px;color:#8c959f">点击可下钻或取消下钻该规格趋势 →</div>`
        return html
      },
    },
    xAxis: {
      type: 'value',
      name: isWeight ? '生产偏差贡献' : 'CPK 负向贡献',
      nameTextStyle: { fontSize: 10, color: '#9ca3af' },
      axisLabel: { 
        fontSize: 10, 
        color: '#9ca3af',
        formatter: v => v
      },
      splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        fontSize: 11,
        color: '#4b5563',
        width: 140,
        overflow: 'truncate',
        formatter: v => v.length > 18 ? v.slice(0, 17) + '…' : v,
      },
      axisLine: { show: false },
      axisTick: { show: false },
      inverse: true,
    },
    series: [
      {
        name: isWeight ? '生产偏差贡献' : 'CPK 负向贡献',
        type: 'bar',
        data: chartValues.map((v, i) => {
          const row = d[i] ?? {}
          const isSelected = props.selectedArticle === row.article10
          
          let baseColor = '#ef4444' // 统一为警告红
          let color = baseColor
          let opacity = 1.0
          if (hasSelection) {
            if (isSelected) {
              color = baseColor
              opacity = 1.0
            } else {
              color = '#e5e7eb'
              opacity = 0.6
            }
          }

          return {
            value: v,
            itemStyle: {
              color: color,
              borderRadius: [0, 8, 8, 0],
              opacity: opacity,
            },
          }
        }),
        barMaxWidth: 18,
        cursor: 'pointer',
        label: {
          show: true,
          position: 'right',
          formatter: (p) => {
            const idx = p.dataIndex
            const row = d[idx] ?? {}
            const isSelected = props.selectedArticle === row.article10
            const score = row.stable_score !== undefined && row.stable_score !== null ? row.stable_score : 0
            const scoreText = isWeight ? (score > 0 ? '+' : '') + score.toFixed(4) : score.toFixed(1)
            const hasMachine = row.warning_machine && row.warning_machine !== '无'
            
            if (hasSelection && !isSelected) {
              const mText = hasMachine ? ` (${row.warning_machine})` : ''
              return `{dim|${scoreText}${mText}}`
            }
            
            if (hasMachine) {
              return `{score|${scoreText}} {light|●} {mach|${row.warning_machine}}`
            } else {
              return `{score|${scoreText}}`
            }
          },
          rich: {
            score: { fontSize: 10, color: '#64748b', fontFamily: 'JetBrains Mono,monospace', fontWeight: '500', padding: [0, 6, 0, 8] },
            light: { fontSize: 16, color: '#ef4444', fontWeight: 'bold', padding: [0, 3, 0, 3] },
            mach: { 
              fontSize: 12, 
              color: '#ef4444', 
              fontFamily: 'JetBrains Mono,monospace', 
              fontWeight: '700',
              backgroundColor: 'rgba(239, 68, 68, 0.08)',
              borderColor: 'rgba(239, 68, 68, 0.2)',
              borderWidth: 1,
              borderRadius: 4,
              padding: [3, 8, 3, 8]
            },
            dim: { fontSize: 10, color: '#9ca3af', fontFamily: 'JetBrains Mono,monospace', fontWeight: '500', padding: [0, 0, 0, 8] },
          },
        },
        emphasis: {
          focus: 'self',
          itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.05)' },
        },
      },
    ],
  }
})


function onBarClick(params) {
  if (params.componentType === 'series') {
    const article = props.data[params.dataIndex]?.article10
    if (article) emit('drill-down', article)
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
