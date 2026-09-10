<template>
  <div class="barcode-measurements-container">
    <!-- 顶部核心指标摘要看板 -->
    <div v-if="summary" class="summary-cards">
      <div class="stat-card">
        <div class="stat-label">单日生产条数 (N)</div>
        <div class="stat-value">{{ summary.total_tires || 0 }} <span class="stat-unit">条</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">实测物理均值 (μ)</div>
        <div class="stat-value primary">{{ summary.mean_val !== null ? summary.mean_val : '-' }} <span class="stat-unit">{{ summary.unit }}</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">实测标准差 (σ)</div>
        <div class="stat-value">{{ summary.std_val !== null ? summary.std_val : '-' }} <span class="stat-unit">{{ summary.unit }}</span></div>
      </div>
      <div class="stat-card" v-if="summary.cpk !== null">
        <div class="stat-label">过程能力 (CPK)</div>
        <div class="stat-value" :class="summary.cpk >= 1.33 ? 'success' : (summary.cpk >= 1.0 ? 'warning' : 'danger')">
          {{ summary.cpk }}
        </div>
      </div>

      <!-- 异常值 (Q3 + 1.5 IQR) 统计卡片 -->
      <div v-if="iqrStats" class="stat-card iqr-card">
        <div class="stat-label">异常值 (Rate)</div>
        <div class="stat-value" :class="iqrStats.outlierCount > 0 ? 'purple-text' : 'success'">
          {{ iqrStats.outlierCount }} <span class="stat-unit">条</span>
          <span class="rate-badge" :class="iqrStats.outlierCount > 0 ? 'purple-badge' : 'good'">
            ({{ iqrStats.outlierRate }})
          </span>
        </div>
      </div>
    </div>

    <!-- 操作工具栏 -->
    <div class="chart-toolbar">
      <div class="left-tools">
        <span class="toolbar-tip">
          💡 <strong>操作指南</strong>：X 轴按实际生产时间时序排列；紫色虚线与紫光节点标记为<strong>异常值 (Q3 + 1.5 IQR)</strong>。
        </span>
      </div>
      <div class="right-tools">
        <el-checkbox v-model="showIqrLine" @change="renderChart">显示异常值界线</el-checkbox>
        <el-checkbox v-model="onlyUpperIqrOutliers" @change="renderChart">仅看异常值 ({{ iqrStats?.outlierCount || 0 }})</el-checkbox>
      </div>
    </div>

    <!-- ECharts 图表主容器 -->
    <div class="chart-wrapper">
      <div v-if="loading" class="chart-loading">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>正在载入单胎实测时序数据...</span>
      </div>
      <div v-else-if="error" class="chart-error">
        <el-result icon="error" title="加载异常" :sub-title="error">
          <template #extra>
            <el-button type="primary" size="small" @click="$emit('reload')">重新加载</el-button>
          </template>
        </el-result>
      </div>
      <div v-else-if="!chartData || chartData.length === 0" class="chart-empty">
        <el-empty description="暂无该规格当日单胎实测数据" :image-size="80" />
      </div>
      <div ref="chartRef" class="chart-canvas" :style="{ opacity: loading ? 0.3 : 1 }"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { Loading } from '@element-plus/icons-vue'

const props = defineProps({
  chartData: {
    type: Array,
    default: () => []
  },
  summary: {
    type: Object,
    default: () => null
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: null
  },
  indicator: {
    type: String,
    default: 'rfpp'
  }
})

defineEmits(['reload'])

const chartRef = ref(null)
let chartInstance = null
const onlyUpperIqrOutliers = ref(false)
const showIqrLine = ref(true)

// 动态计算异常值界线 (Q3 + 1.5 * IQR) 离群参数
const iqrStats = computed(() => {
  if (!props.chartData || props.chartData.length === 0) return null
  const validVals = props.chartData
    .map(d => d.value)
    .filter(v => v !== null && v !== undefined && !isNaN(v))
  if (validVals.length === 0) return null

  const sorted = [...validVals].sort((a, b) => a - b)
  const n = sorted.length

  function quantile(q) {
    const pos = (n - 1) * q
    const base = Math.floor(pos)
    const rest = pos - base
    if (sorted[base + 1] !== undefined) {
      return sorted[base] + rest * (sorted[base + 1] - sorted[base])
    }
    return sorted[base]
  }

  const q1 = Number(quantile(0.25).toFixed(2))
  const q3 = Number(quantile(0.75).toFixed(2))
  const iqr = Number((q3 - q1).toFixed(2))
  const upperBoundary = Number((q3 + 1.5 * iqr).toFixed(2))

  const outliers = validVals.filter(v => v > upperBoundary)
  const count = outliers.length
  const rate = ((count / validVals.length) * 100).toFixed(2) + '%'

  return {
    q1,
    q3,
    iqr,
    upperBoundary,
    outlierCount: count,
    outlierRate: rate
  }
})

function initChart() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
    window.addEventListener('resize', handleResize)
  }
  renderChart()
}

function handleResize() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

function renderChart() {
  if (!chartInstance || !props.chartData || props.chartData.length === 0) return

  const rawData = props.chartData
  let displayData = rawData
  if (onlyUpperIqrOutliers.value && iqrStats.value) {
    displayData = displayData.filter(d => d.value > iqrStats.value.upperBoundary)
  }

  const xCategories = displayData.map(d => d.barcode)
  const yValues = displayData.map(d => d.value)
  const unit = props.summary?.unit || 'N'
  const meanVal = props.summary?.mean_val
  const stdVal = props.summary?.std_val

  // 标线配置
  const markLineData = []

  // 异常值界线参考线 (Q3 + 1.5 * IQR)
  if (showIqrLine.value && iqrStats.value && iqrStats.value.upperBoundary !== null && !isNaN(iqrStats.value.upperBoundary)) {
    markLineData.push({
      yAxis: iqrStats.value.upperBoundary,
      name: '异常值界线 (Q3+1.5IQR)',
      lineStyle: { color: '#a855f7', width: 2, type: 'dashed' },
      label: {
        formatter: `异常值界线 (Q3+1.5IQR): ${iqrStats.value.upperBoundary} ${unit}`,
        position: 'insideEndTop',
        color: '#9333ea',
        fontWeight: 'bold',
        fontSize: 11
      }
    })
  }

  if (meanVal !== undefined && meanVal !== null && !isNaN(meanVal)) {
    markLineData.push({
      yAxis: meanVal,
      name: '均值 (Mean)',
      lineStyle: { color: '#10b981', width: 1.5, type: 'solid' },
      label: {
        formatter: `Mean (μ): ${meanVal} ${unit}`,
        position: 'insideEndBottom',
        color: '#059669',
        fontSize: 11
      }
    })
  }
  if (meanVal !== undefined && stdVal !== undefined && stdVal > 0) {
    const ucl = Number((meanVal + 3 * stdVal).toFixed(2))
    const lcl = Number((meanVal - 3 * stdVal).toFixed(2))
    markLineData.push({
      yAxis: ucl,
      name: '+3σ 控制上限',
      lineStyle: { color: '#f59e0b', width: 1, type: 'dashed' },
      label: { formatter: `+3σ: ${ucl}`, position: 'end', color: '#d97706', fontSize: 10 }
    })
    if (lcl > 0 || props.indicator === 'cony') {
      markLineData.push({
        yAxis: lcl,
        name: '-3σ 控制下限',
        lineStyle: { color: '#f59e0b', width: 1, type: 'dashed' },
        label: { formatter: `-3σ: ${lcl}`, position: 'end', color: '#d97706', fontSize: 10 }
      })
    }
  }

  const option = {
    backgroundColor: '#ffffff',
    grid: {
      left: '4%',
      right: '8%',
      top: '12%',
      bottom: '18%',
      containLabel: true
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      borderColor: '#334155',
      borderWidth: 1,
      textStyle: { color: '#ffffff', fontSize: 12 },
      formatter: function(params) {
        if (!params || params.length === 0) return ''
        const idx = params[0].dataIndex
        const item = displayData[idx]
        if (!item) return ''

        const isUpperOutlier = iqrStats.value && item.value > iqrStats.value.upperBoundary
        const iqrTag = isUpperOutlier
          ? '<span style="color:#a855f7;font-weight:bold;background:rgba(168,85,247,0.25);padding:1px 6px;border-radius:4px;margin-left:6px;">🟣 异常值</span>'
          : ''

        let extraWeightInfo = ''
        if (item.diff_pct !== undefined) {
          extraWeightInfo = `<div style="margin-top:4px;">偏差百分比: <strong style="color:${Math.abs(item.diff_pct) > 0.8 ? '#ef4444' : '#60a5fa'}">${item.diff_pct > 0 ? '+' : ''}${item.diff_pct}%</strong> (目标: ${item.target_val} kg)</div>`
        }

        return `
          <div style="padding: 2px 4px; line-height: 1.6;">
            <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,0.15);padding-bottom:4px;margin-bottom:6px;">
              <strong style="color:#38bdf8;font-size:13px;">条码: ${item.barcode}</strong>
              <div>${iqrTag}</div>
            </div>
            <div>测量实测值: <strong style="font-size:14px;color:#ffffff;">${item.value} ${unit}</strong></div>
            ${extraWeightInfo}
            <div style="color:#cbd5e1;font-size:11px;margin-top:4px;">
              <span>成型工段: <strong style="color:#f8fafc;">${item.gt_workcenter}</strong></span> | 
              <span>终检工段: <strong style="color:#f8fafc;">${item.tu_workcenter}</strong></span>
            </div>
            <div style="color:#94a3b8;font-size:11px;margin-top:2px;">
              生产/成型时间: ${item.prod_time || '未知'}
            </div>
          </div>
        `
      }
    },
    toolbox: {
      feature: {
        dataZoom: { yAxisIndex: 'none', title: { zoom: '区域缩放', back: '还原' } },
        restore: { title: '重置' },
        saveAsImage: { title: '保存图片', pixelRatio: 2 }
      },
      right: '4%',
      top: '2%'
    },
    xAxis: {
      type: 'category',
      data: xCategories,
      boundaryGap: false,
      axisLabel: {
        rotate: 35,
        fontSize: 10,
        color: '#64748b',
        interval: Math.max(0, Math.floor(xCategories.length / 25))
      },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisTick: { alignWithLabel: true }
    },
    yAxis: {
      type: 'value',
      name: `实测值 (${unit})`,
      nameTextStyle: { color: '#475569', fontSize: 12, padding: [0, 0, 0, 10] },
      scale: true,
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
      axisLabel: { color: '#64748b', fontSize: 11 }
    },
    dataZoom: [
      {
        type: 'slider',
        show: true,
        xAxisIndex: [0],
        start: 0,
        end: 100,
        height: 24,
        bottom: '2%',
        borderColor: '#e2e8f0',
        fillerColor: 'rgba(59, 130, 246, 0.12)',
        handleStyle: { color: '#3b82f6' },
        textStyle: { color: '#64748b', fontSize: 10 }
      },
      {
        type: 'inside',
        xAxisIndex: [0],
        start: 0,
        end: 100
      }
    ],
    series: [
      {
        name: '实测值',
        type: 'line',
        data: yValues,
        smooth: false,
        symbol: 'circle',
        symbolSize: function(val, params) {
          const item = displayData[params.dataIndex]
          if (!item) return 5
          const isUpperOutlier = iqrStats.value && item.value > iqrStats.value.upperBoundary
          if (isUpperOutlier) return 10
          return 5
        },
        itemStyle: {
          color: function(params) {
            const item = displayData[params.dataIndex]
            if (!item) return '#3b82f6'
            const isUpperOutlier = iqrStats.value && item.value > iqrStats.value.upperBoundary
            if (isUpperOutlier) return '#a855f7'
            return '#3b82f6'
          },
          borderWidth: 1.5,
          borderColor: '#ffffff',
          shadowBlur: 6,
          shadowColor: 'rgba(0,0,0,0.15)'
        },
        lineStyle: {
          color: '#3b82f6',
          width: 1.8
        },
        markLine: {
          symbol: 'none',
          data: markLineData
        }
      }
    ]
  }

  chartInstance.setOption(option, true)
}

watch(
  () => [props.chartData, props.summary, props.indicator],
  () => {
    nextTick(() => {
      renderChart()
    })
  },
  { deep: true }
)

onMounted(() => {
  nextTick(() => {
    initChart()
  })
})

onBeforeUnmount(() => {
  if (chartInstance) {
    window.removeEventListener('resize', handleResize)
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.barcode-measurements-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: #ffffff;
  gap: 12px;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 12px;
  padding: 4px 0;
}

.stat-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-card.iqr-card {
  background: #fcf5ff;
  border-color: #f3e8ff;
}

.stat-label {
  font-size: 11.5px;
  color: #64748b;
  font-weight: 500;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat-value.primary {
  color: #2563eb;
}

.stat-value.success {
  color: #16a34a;
}

.stat-value.warning {
  color: #d97706;
}

.stat-value.danger {
  color: #dc2626;
}

.stat-value.purple, .purple-text {
  color: #9333ea;
}

.stat-unit {
  font-size: 11px;
  color: #94a3b8;
  font-weight: normal;
}

.rate-badge {
  font-size: 11px;
  padding: 1px 5px;
  border-radius: 4px;
  margin-left: 4px;
}

.rate-badge.good {
  background: #dcfce7;
  color: #166534;
}

.rate-badge.bad {
  background: #fee2e2;
  color: #991b1b;
}

.purple-badge {
  background: #f3e8ff;
  color: #7e22ce;
  font-weight: 700;
}

.chart-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 6px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 12px;
}

.toolbar-tip {
  color: #475569;
  font-size: 11.5px;
}

.right-tools {
  display: flex;
  align-items: center;
  gap: 16px;
}

.chart-wrapper {
  position: relative;
  flex: 1;
  min-height: 440px;
  width: 100%;
}

.chart-canvas {
  width: 100%;
  height: 100%;
  min-height: 440px;
}

.chart-loading, .chart-error, .chart-empty {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  z-index: 10;
  gap: 8px;
  color: #64748b;
  font-size: 13px;
}
</style>
