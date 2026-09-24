<template>
  <div class="production-anomaly-chart-wrap">
    <div v-if="loading" class="chart-loading-state">
      <el-skeleton :rows="5" animated />
    </div>
    <div v-else-if="error" class="chart-error-state">
      <el-icon size="28" color="#ef4444"><WarningFilled /></el-icon>
      <span>{{ error }}</span>
    </div>
    <div v-else-if="!data || data.length === 0" class="chart-empty-state">
      <el-empty description="当前筛选条件下暂无生产异常记录" :image-size="70" />
    </div>
    <div v-else class="chart-body-container">
      <v-chart 
        ref="chartRef" 
        :option="chartOption" 
        autoresize 
        style="width: 100%; height: 100%;" 
        @click="handleChartClick" 
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { WarningFilled } from '@element-plus/icons-vue'

use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  CanvasRenderer
])

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: null
  },
  selectedDate: {
    type: String,
    default: null
  },
  alarmModes: {
    type: Array,
    default: () => ['consecutive', 'top5']
  }
})

const emit = defineEmits(['date-select'])
const chartRef = ref(null)

// 采用用户指定优雅四色配色 (高明度暖橙 FBB07A, FFF0AB, D0F2CF, EEA5AC)
const COLOR_TU = '#FBB07A'     // 高明度透亮暖橙 (TU 均匀性异常)
const COLOR_TG = '#FFF0AB'     // 浅黄奶油色 (TG 几何尺寸异常)
const COLOR_TB = '#D0F2CF'     // 薄荷淡浅绿 (TB 动平衡异常)
const COLOR_MULTI = '#EEA5AC'  // 优雅浅玫瑰粉 (多工段复合异常)
const COLOR_LINE = '#0ea5e9'   // 清爽浅天蓝 (相较昨日增长比例折线)

const chartOption = computed(() => {
  const rawList = props.data || []
  if (rawList.length === 0) return {}

  const dates = rawList.map(item => item.date)
  
  // 计算各工序占当日总生产胎数的百分比 (%) 作为堆叠柱的值
  const tuRateList = rawList.map(item => {
    const total = item.total_tires || 1
    const count = item.tu_only_anomalies !== undefined ? item.tu_only_anomalies : (item.tu_anomalies || 0)
    return Number(((count / total) * 100).toFixed(2))
  })
  const tgRateList = rawList.map(item => {
    const total = item.total_tires || 1
    const count = item.tg_only_anomalies !== undefined ? item.tg_only_anomalies : (item.tg_anomalies || 0)
    return Number(((count / total) * 100).toFixed(2))
  })
  const tbRateList = rawList.map(item => {
    const total = item.total_tires || 1
    const count = item.tb_only_anomalies !== undefined ? item.tb_only_anomalies : (item.tb_anomalies || 0)
    return Number(((count / total) * 100).toFixed(2))
  })
  const multiList = rawList.map(item => item.multi_anomalies || 0)
  const multiRateList = rawList.map(item => {
    const total = item.total_tires || 1
    const count = item.multi_anomalies || 0
    return Number(((count / total) * 100).toFixed(2))
  })
  
  // 相较于前一天的异常率增长比例 (%) 数据
  const growthRateList = rawList.map(item => item.anomaly_growth_rate)

  const hasMulti = multiList.some(v => v > 0)

  // 1. 报警模式开启判定与算法计算
  const activeAlarmModes = props.alarmModes || []
  const enableConsecutive = activeAlarmModes.includes('consecutive')
  const enableTop5 = activeAlarmModes.includes('top5')

  // 逻辑 B: 极值点 Top 5 判定 (整个周期内日增长比例最高的 5 个恶化极值点)
  const top5Map = new Map() // index -> rank (1 ~ 5)
  if (enableTop5) {
    const validRatePoints = rawList
      .map((item, idx) => ({ idx, date: item.date, rate: item.anomaly_growth_rate }))
      .filter(p => typeof p.rate === 'number' && !isNaN(p.rate))
    
    validRatePoints.sort((a, b) => b.rate - a.rate)
    validRatePoints.slice(0, 5).forEach((p, rank) => {
      top5Map.set(p.idx, rank + 1)
    })
  }

  // 逻辑 A: 连续两天上涨判定 (当前日增长率 > 0 且前一日增长率 > 0)
  const consecutiveSet = new Set()
  if (enableConsecutive) {
    for (let i = 1; i < rawList.length; i++) {
      const curr = rawList[i].anomaly_growth_rate
      const prev = rawList[i - 1].anomaly_growth_rate
      if (typeof curr === 'number' && curr > 0 && typeof prev === 'number' && prev > 0) {
        consecutiveSet.add(i)
      }
    }
  }

  // 构建高亮折线点数据
  const linePointsData = rawList.map((item, idx) => {
    const val = item.anomaly_growth_rate
    if (val === null || val === undefined || isNaN(val)) {
      return null
    }

    const isTop5 = enableTop5 && top5Map.has(idx)
    const isConsecutive = enableConsecutive && consecutiveSet.has(idx)

    if (isTop5 && isConsecutive) {
      const rank = top5Map.get(idx)
      return {
        value: val,
        symbol: 'circle',
        symbolSize: 12,
        itemStyle: {
          color: '#dc2626',
          borderColor: '#ffffff',
          borderWidth: 2.5,
          shadowBlur: 10,
          shadowColor: 'rgba(220, 38, 38, 0.65)'
        },
        alarmType: 'both',
        alarmRank: rank
      }
    } else if (isTop5) {
      const rank = top5Map.get(idx)
      return {
        value: val,
        symbol: 'circle',
        symbolSize: 11,
        itemStyle: {
          color: '#ef4444',
          borderColor: '#ffffff',
          borderWidth: 2,
          shadowBlur: 8,
          shadowColor: 'rgba(239, 68, 68, 0.55)'
        },
        alarmType: 'top5',
        alarmRank: rank
      }
    } else if (isConsecutive) {
      return {
        value: val,
        symbol: 'circle',
        symbolSize: 10,
        itemStyle: {
          color: '#f97316',
          borderColor: '#ffffff',
          borderWidth: 2,
          shadowBlur: 8,
          shadowColor: 'rgba(249, 115, 22, 0.55)'
        },
        alarmType: 'consecutive'
      }
    }

    return {
      value: val,
      symbol: 'circle',
      symbolSize: 5,
      itemStyle: {
        color: COLOR_LINE,
        borderColor: '#ffffff',
        borderWidth: 1.5
      }
    }
  })

  // 选中日期的标线高亮
  const markLineData = []
  if (props.selectedDate && dates.includes(props.selectedDate)) {
    markLineData.push({
      xAxis: props.selectedDate,
      lineStyle: {
        color: '#2563eb',
        width: 2,
        type: 'dashed'
      },
      label: {
        show: true,
        position: 'end',
        formatter: '当前选定: ' + props.selectedDate,
        fontSize: 11,
        color: '#2563eb',
        fontWeight: 'bold',
        backgroundColor: 'rgba(239, 246, 255, 0.95)',
        borderColor: '#93c5fd',
        borderWidth: 1,
        borderRadius: 4,
        padding: [3, 6]
      }
    })
  }

  // 组装系列 series: 纯异常分布 (TU, TG, TB, 跨工段多异常) + 环比增长折线
  const series = []

  // 1. TU 异常 (不良率 %)
  series.push({
    name: 'TU',
    type: 'bar',
    stack: 'production',
    barMaxWidth: 32,
    itemStyle: {
      color: COLOR_TU
    },
    data: tuRateList,
    markLine: markLineData.length > 0 ? {
      silent: true,
      symbol: ['none', 'none'],
      data: markLineData
    } : undefined
  })

  // 2. TG 异常 (不良率 %)
  series.push({
    name: 'TG',
    type: 'bar',
    stack: 'production',
    barMaxWidth: 32,
    itemStyle: {
      color: COLOR_TG,
      borderColor: '#fef08a',
      borderWidth: 0.5
    },
    data: tgRateList
  })

  // 3. TB 异常 (不良率 %)
  series.push({
    name: 'TB',
    type: 'bar',
    stack: 'production',
    barMaxWidth: 32,
    itemStyle: {
      color: COLOR_TB,
      borderColor: '#bbf7d0',
      borderWidth: 0.5,
      borderRadius: hasMulti ? [0, 0, 0, 0] : [2, 2, 0, 0]
    },
    data: tbRateList
  })

  // 4. 多工段复合异常 (不良率 %)
  if (hasMulti) {
    series.push({
      name: '多工段复合',
      type: 'bar',
      stack: 'production',
      barMaxWidth: 32,
      itemStyle: {
        color: COLOR_MULTI,
        borderRadius: [2, 2, 0, 0]
      },
      data: multiRateList
    })
  }

  // 5. 相较于前一天的异常率增长比例折线 (次 Y 轴)
  series.push({
    name: '相较昨日增长比例 (%)',
    type: 'line',
    yAxisIndex: 1,
    data: linePointsData,
    showSymbol: true,
    connectNulls: true,
    smooth: 0.2,
    lineStyle: {
      color: COLOR_LINE,
      width: 2
    },
    itemStyle: {
      color: COLOR_LINE
    },
    emphasis: {
      scale: 1.4,
      itemStyle: {
        borderColor: COLOR_LINE,
        borderWidth: 2.5,
        shadowBlur: 8,
        shadowColor: 'rgba(14, 165, 233, 0.45)'
      }
    },
    markLine: {
      silent: true,
      symbol: ['none', 'none'],
      data: [
        {
          yAxis: 0,
          lineStyle: {
            color: '#475569',
            type: 'dashed',
            width: 1.8
          },
          label: {
            show: true,
            position: 'end',
            formatter: '0%',
            fontSize: 10,
            fontWeight: 'bold',
            color: '#475569',
            distance: 4
          }
        }
      ]
    }
  })

  // 图例设置
  const legendSelected = {
    'TU': true,
    'TG': true,
    'TB': true,
    '相较昨日增长比例 (%)': true
  }
  if (hasMulti) {
    legendSelected['多工段复合'] = true
  }

  // 次 Y 轴范围自适应与 0 轴对称微调
  const validGrowth = growthRateList.filter(v => typeof v === 'number' && !isNaN(v))
  let y2Min = -20
  let y2Max = 20
  if (validGrowth.length > 0) {
    const minG = Math.min(...validGrowth)
    const maxG = Math.max(...validGrowth)
    const maxAbs = Math.max(Math.abs(minG), Math.abs(maxG), 10)
    const bound = Math.ceil((maxAbs * 1.25) / 5) * 5
    y2Min = -bound
    y2Max = bound
  }

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
        shadowStyle: {
          color: 'rgba(59, 130, 246, 0.05)'
        }
      },
      padding: [10, 14],
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: {
        color: '#1e293b',
        fontSize: 12
      },
      extraCssText: 'box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1); border-radius: 8px;',
      formatter: (params) => {
        if (!params || params.length === 0) return ''
        const dateStr = params[0].axisValue
        const itemIdx = rawList.findIndex(d => d.date === dateStr)
        const item = rawList[itemIdx]
        if (!item) return ''

        // 仅保留 TB, TU, TG，去掉中文解释
        const processItems = [
          {
            name: 'TB',
            color: COLOR_TB,
            borderColor: '#86efac',
            count: item.tb_anomalies,
            rate: item.tb_anomaly_rate,
            growth: item.tb_growth_rate
          },
          {
            name: 'TU',
            color: COLOR_TU,
            borderColor: 'transparent',
            count: item.tu_anomalies,
            rate: item.tu_anomaly_rate,
            growth: item.tu_growth_rate
          },
          {
            name: 'TG',
            color: COLOR_TG,
            borderColor: '#fde047',
            count: item.tg_anomalies,
            rate: item.tg_anomaly_rate,
            growth: item.tg_growth_rate
          }
        ]

        if (item.multi_anomalies && item.multi_anomalies > 0) {
          const multiRate = Number(((item.multi_anomalies / (item.total_tires || 1)) * 100).toFixed(2))
          processItems.push({
            name: '复合异常',
            color: COLOR_MULTI,
            borderColor: '#f472b6',
            count: item.multi_anomalies,
            rate: multiRate,
            growth: null
          })
        }

        // 按日环比增长比例由高到低 (降序) 排序
        processItems.sort((a, b) => {
          const gA = (a.growth !== null && a.growth !== undefined) ? a.growth : -99999
          const gB = (b.growth !== null && b.growth !== undefined) ? b.growth : -99999
          if (gA !== gB) return gB - gA
          return (b.rate || 0) - (a.rate || 0)
        })

        const processRows = processItems.map(p => {
          let pGrowthText = '-'
          let pGrowthColor = '#94a3b8'
          if (p.growth !== null && p.growth !== undefined) {
            if (p.growth > 0) {
              pGrowthText = `+${p.growth}%`
              pGrowthColor = '#dc2626'
            } else if (p.growth < 0) {
              pGrowthText = `${p.growth}%`
              pGrowthColor = '#16a34a'
            } else {
              pGrowthText = '0.00%'
              pGrowthColor = '#64748b'
            }
          }

          return `
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 5px;">
              <div style="display: flex; align-items: center; min-width: 45px;">
                <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${p.color}; ${p.borderColor ? `border: 1px solid ${p.borderColor};` : ''} margin-right: 7px;"></span>
                <span style="color: #0f172a; font-weight: 700; font-family: 'JetBrains Mono', monospace;">${p.name}</span>
              </div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #0f172a;">${p.count.toLocaleString()} 胎 (${p.rate}%)</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600; min-width: 52px; text-align: right; color: ${pGrowthColor};">${pGrowthText}</span>
              </div>
            </div>`
        }).join('')

        return `
          <div style="padding: 4px 6px; min-width: 245px;">
            <div style="font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid #f1f5f9;">
              ${item.date} 生产数据
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 5px;">
              <span style="color: #64748b;">总生产条数</span>
              <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #0f172a;">${item.total_tires.toLocaleString()} 胎</span>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 8px;">
              <span style="color: #64748b;">异常比例</span>
              <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #e11d48;">${item.anomaly_rate}% (${item.anomaly_tires.toLocaleString()} 胎)</span>
            </div>

            <div style="border-top: 1px solid #f1f5f9; padding-top: 7px; margin-top: 4px;">
              <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; font-weight: 600; color: #94a3b8; margin-bottom: 6px;">
                <span>工序分布</span>
                <span>日环比</span>
              </div>
              ${processRows}
            </div>
          </div>
        `
      }
    },
    legend: {
      top: 0,
      left: 'center',
      itemWidth: 12,
      itemHeight: 10,
      itemGap: 14,
      textStyle: {
        fontSize: 11,
        color: '#64748b'
      },
      selected: legendSelected
    },
    grid: {
      top: 36,
      left: 16,
      right: 28,
      bottom: dates.length > 25 ? 40 : 16,
      containLabel: true
    },

    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { alignWithLabel: true, lineStyle: { color: '#cbd5e1' } },
      axisLabel: {
        fontSize: 11,
        color: '#64748b',
        interval: 'auto',
        formatter: (val) => {
          if (!val) return ''
          const parts = val.split('-')
          return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : val
        }
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '不良率 (%)',
        min: 0,
        nameTextStyle: {
          fontSize: 11,
          color: '#64748b',
          padding: [0, 0, 0, -10]
        },
        axisLabel: {
          fontSize: 11,
          color: '#64748b',
          formatter: (val) => `${val}%`
        },
        splitLine: {
          lineStyle: {
            color: '#f1f5f9',
            type: 'dashed'
          }
        }
      },
      {
        type: 'value',
        name: '日环比增幅',
        min: y2Min,
        max: y2Max,
        nameTextStyle: {
          fontSize: 11,
          color: '#0ea5e9',
          fontWeight: 600,
          padding: [0, -10, 0, 0]
        },
        axisLabel: {
          fontSize: 11,
          color: '#0ea5e9',
          formatter: (val) => (val > 0 ? `+${val}` : val) + '%'
        },
        splitLine: {
          show: false
        }
      }
    ],
    dataZoom: dates.length > 25 ? [
      {
        type: 'inside',
        start: Math.max(0, 100 - Math.round(3000 / dates.length)),
        end: 100
      },
      {
        type: 'slider',
        height: 16,
        bottom: 4,
        handleStyle: { color: '#3b82f6' },
        textStyle: { color: '#8c959f', fontSize: 10 },
        borderColor: '#e2e8f0',
        start: Math.max(0, 100 - Math.round(3000 / dates.length)),
        end: 100
      }
    ] : [],
    series: series
  }
})

function handleChartClick(params) {
  if (params.componentType === 'series' && params.name) {
    emit('date-select', params.name)
  } else if (params.componentType === 'xAxis' && params.value) {
    emit('date-select', params.value)
  }
}
</script>

<style scoped>
.production-anomaly-chart-wrap {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
}

.chart-body-container {
  flex: 1;
  width: 100%;
  min-height: 0;
  position: relative;
}

.chart-loading-state,
.chart-error-state,
.chart-empty-state {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.chart-error-state {
  color: #ef4444;
  font-size: 13px;
  font-weight: 500;
}
</style>
