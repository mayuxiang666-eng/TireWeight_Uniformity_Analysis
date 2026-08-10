<template>
  <div class="chart-wrap">
    <div v-if="loading" class="skeleton" style="height:100%" />
    <div v-else-if="error" class="chart-error">
      <el-icon size="24"><WarningFilled /></el-icon>
      <span>{{ error }}</span>
    </div>
    <div v-else-if="!data.length" class="chart-empty">
      <span>暂无大排产物料批次对照数据</span>
    </div>
    <v-chart
      v-else
      :option="option"
      autoresize
      style="width:100%;height:100%"
    />
  </div>
</template>

<script setup>
/**
 * 组件描述: 物料批次双向提升度对比柱状图 (Local Lift vs Cross-Machine Lift)
 * ===================================================================
 * 渲染被点击机台下的各物料批次表现。
 * 本地提升度高且全场提升度低 -> 属于适配性故障 (单边蓝色柱起峰)。
 * 本地提升度高且全场提升度也高 -> 属于全局物料缺陷 (双色柱对称起峰)。
 * ===================================================================
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { WarningFilled } from '@element-plus/icons-vue'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps({
  data:    { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error:   { type: String, default: null }
})

const option = computed(() => {
  const d = props.data
  const labels = d.map(r => r.lot_val)
  const localLifts = d.map(r => r.local_lift)
  const crossLifts = d.map(r => r.cross_machine_lift)

  return {
    backgroundColor: 'transparent',
    legend: {
      data: ['本机局部提升 (Local Lift)', '全厂交叉对照 (Cross-Machine Lift)'],
      bottom: 0,
      textStyle: { fontSize: 11, color: '#4b5563' }
    },
    grid: { top: 32, right: 16, bottom: 48, left: 16, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e5e8ef',
      borderWidth: 1,
      textStyle: { color: '#0d1117', fontSize: 12 },
      formatter(params) {
        const idx = params[0]?.dataIndex ?? 0
        const row = d[idx] ?? {}
        return `
          <div style="font-weight:600;margin-bottom:6px">物料批次: ${row.lot_val}</div>
          <div style="display:flex;justify-content:space-between;gap:24px">
            <span>批次总数 / 异常数</span>
            <span style="font-weight:600">${row.lot_total} / ${row.lot_anomaly}</span>
          </div>
          <div style="display:flex;justify-content:space-between;gap:24px">
            <span>当前机台局部提升度</span>
            <span style="font-weight:600;color:#2563eb">${row.local_lift}x</span>
          </div>
          <div style="display:flex;justify-content:space-between;gap:24px;border-bottom:1px solid #f3f4f6;padding-bottom:4px;margin-bottom:4px">
            <span>全厂交叉对照提升度</span>
            <span style="font-weight:600;color:#9ca3af">${row.cross_machine_lift}x</span>
          </div>
          <div style="color:#d97706;font-weight:500">诊断建议: ${row.suggestion}</div>
        `
      }
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        fontSize: 10,
        color: '#4b5563',
        rotate: 20
      },
      axisLine: { lineStyle: { color: '#e5e7eb' } }
    },
    yAxis: {
      type: 'value',
      name: '提升度 (Lift)',
      axisLabel: { formatter: '{value}x', fontSize: 10, color: '#4b5563' },
      splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }
    },
    series: [
      {
        name: '本机局部提升 (Local Lift)',
        type: 'bar',
        barGap: '20%',
        barMaxWidth: 16,
        data: localLifts,
        itemStyle: { color: '#3b82f6', borderRadius: [2, 2, 0, 0] },
        markLine: {
          symbol: 'none',
          data: [{ yAxis: 1.5, lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 } }],
          label: { formatter: '告警线 1.5x', position: 'end', fontSize: 9, color: '#ef4444' }
        }
      },
      {
        name: '全厂交叉对照 (Cross-Machine Lift)',
        type: 'bar',
        barMaxWidth: 16,
        data: crossLifts,
        itemStyle: { color: '#9ca3af', borderRadius: [2, 2, 0, 0] }
      }
    ]
  }
})
</script>

<style scoped>
.chart-wrap { width: 100%; height: 100%; position: relative; }
.chart-error, .chart-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--c-text-muted);
  font-size: 13px;
}
.skeleton {
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 37%, #f3f4f6 63%);
  background-size: 400% 100%;
  animation: loading 1.4s ease infinite;
}
@keyframes loading {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
</style>
