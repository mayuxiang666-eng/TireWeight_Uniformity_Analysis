<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="850px"
    destroy-on-close
    append-to-body
  >
    <div style="margin-bottom: 12px; font-size: 13px; color: var(--el-text-color-secondary); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
      <div style="display: flex; gap: 16px; align-items: center;">
        <span><strong>机台：</strong>{{ machine }}</span>
        <span><strong>工位：</strong>{{ workcenterCol }}</span>
        <span><strong>规格类型：</strong>{{ article10 ? `单规格 (${article10})` : '全体规格 (All Specs)' }}</span>
      </div>
      <!-- 复选按钮控制 3 条曲线显隐 -->
      <div style="display: flex; gap: 12px; align-items: center; background: #f8fafc; padding: 4px 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
        <span style="font-size: 12px; font-weight: 600; color: #475569;">曲线控制:</span>
        <el-checkbox v-model="showAvg" size="small"><span style="color:#2563eb; font-weight:600;">{{ labelAvg }}</span></el-checkbox>
        <el-checkbox v-model="showStd" size="small"><span style="color:#d97706; font-weight:600;">{{ labelStd }}</span></el-checkbox>
        <el-checkbox v-model="showCpk" size="small"><span style="color:#059669; font-weight:600;">{{ labelCpk }}</span></el-checkbox>
      </div>
    </div>

    <div style="height: 400px; position: relative;">
      <div v-if="loading" style="height: 100%; display: flex; align-items: center; justify-content: center;">
        <el-icon class="is-loading" size="28"><Loading /></el-icon>
        <span style="margin-left: 8px; font-size: 13px; color: #666;">正在检索全量历史走势...</span>
      </div>
      <div v-else-if="error" style="height: 100%; display: flex; align-items: center; justify-content: center; color: #ef4444;">
        <span>{{ error }}</span>
      </div>
      <div v-else-if="!trendData || trendData.length === 0" style="height: 100%; display: flex; align-items: center; justify-content: center; color: #8c959f;">
        <span>暂无该机台的历史参数走势数据</span>
      </div>
      <v-chart
        v-else
        :option="option"
        autoresize
        style="width: 100%; height: 100%;"
      />
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { Loading } from '@element-plus/icons-vue'
import { api } from '../../api'

const props = defineProps({
  visible:       { type: Boolean, default: false },
  machine:       { type: String, default: '' },
  workcenterCol: { type: String, default: '' },
  article10:     { type: String, default: null }, // Null -> all specs
  mode:          { type: String, default: null },
  indicator:     { type: String, default: 'rfpp' },
  selectedDate:  { type: String, default: null },
})

const emit = defineEmits(['update:visible'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const loading = ref(false)
const error = ref(null)
const trendData = ref([])
const controlLimits = ref(null)

// 曲线显隐控制变量
const showAvg = ref(true)
const showStd = ref(true)
const showCpk = ref(true)

// weight 模式下的动态标签
const isWeight = computed(() => props.indicator === 'weight')
const labelAvg = computed(() => isWeight.value ? '实际胎重均值 (kg)' : '均值 (avg)')
const labelStd = computed(() => isWeight.value ? '实际胎重标准差 (kg)' : '标准差 (σ)')
const labelCpk = computed(() => isWeight.value ? 'Diff 偏差率 (%)' : 'CPK 指数')

const dialogTitle = computed(() => {
  const modeText = props.mode === 'multi' ? '全规格产量加权' : `单规格: ${props.article10 || '选中规格'}`
  return `机台 ${props.machine} 走势分析 - [${modeText}]`
})

async function fetchTrend() {
  if (!props.machine || !props.workcenterCol) return
  loading.value = true
  error.value = null
  try {
    const params = {
      machine: props.machine,
      workcenter_col: props.workcenterCol,
      indicator: props.indicator
    }
    if (props.mode) {
      params.mode = props.mode
    }
    if (props.article10) {
      params.article10 = props.article10
    }
    const res = await api.getMachineCpkTrend(params)
    if (res.data.status === 'success') {
      trendData.value = res.data.data
      controlLimits.value = res.data.control_limits || null
    } else {
      error.value = res.data.message || '加载趋势失败'
    }
  } catch (e) {
    error.value = '请求趋势数据时发生网络或服务端错误'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      fetchTrend()
    }
  }
)

const option = computed(() => {
  const dates = trendData.value.map(d => d.date)
  const warnThreshold = controlLimits.value?.warning_threshold ?? null
  const weight = isWeight.value
  
  const markLineData = []
  if (props.selectedDate && dates.includes(props.selectedDate)) {
    markLineData.push({
      xAxis: props.selectedDate,
      lineStyle: { color: '#8b5cf6', type: 'dashed', width: 2 },
      label: {
        show: true,
        position: 'end',
        formatter: '选中分析点',
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

  const series = []

  // 1. 均值曲线 (weight 下: 实际胎重均值 kg)
  if (showAvg.value) {
    series.push({
      name: labelAvg.value,
      type: 'line',
      yAxisIndex: 0,
      data: trendData.value.map(d => d.mean_val),
      smooth: true,
      lineStyle: { width: 2.5, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
      markLine: { silent: true, symbol: 'none', data: markLineData }
    })
  }

  // 2. 标准差曲线 (weight 下: 实际胎重标准差 kg)
  if (showStd.value) {
    series.push({
      name: labelStd.value,
      type: 'line',
      yAxisIndex: weight ? 0 : 1,  // weight 模式与均值共享左轴（同为 kg）
      data: trendData.value.map(d => d.std_val),
      smooth: true,
      lineStyle: { width: 2, color: '#d97706', type: 'dashed' },
      itemStyle: { color: '#d97706' }
    })
  }

  // 3. CPK / Diff 偏差率曲线
  if (showCpk.value) {
    const cpkMarkLines = [...markLineData]
    if (warnThreshold !== null && warnThreshold !== undefined) {
      const warnLabel = weight
        ? `公差限: ±${warnThreshold}%`
        : `CPK预警线: ${warnThreshold}`
      cpkMarkLines.push({
        yAxis: weight ? warnThreshold : warnThreshold,
        lineStyle: { color: '#ef4444', type: 'dashed', width: 2 },
        label: {
          show: true,
          position: 'end',
          formatter: warnLabel,
          color: '#ef4444',
          fontSize: 10,
          fontWeight: 'bold'
        }
      })
      // weight 模式同时画负公差线
      if (weight) {
        cpkMarkLines.push({
          yAxis: -warnThreshold,
          lineStyle: { color: '#ef4444', type: 'dashed', width: 2 },
          label: {
            show: true,
            position: 'end',
            formatter: `-${warnThreshold}%`,
            color: '#ef4444',
            fontSize: 10,
            fontWeight: 'bold'
          }
        })
      }
    }

    const cpkPoints = trendData.value.map(d => {
      const val = d.cpk_val
      const isWarn = warnThreshold !== null && (
        weight ? Math.abs(val) >= warnThreshold : val <= warnThreshold
      )
      return {
        value: val,
        symbol: 'circle',
        symbolSize: isWarn ? 9 : 5,
        itemStyle: {
          color: isWarn ? '#ef4444' : '#059669',
          borderColor: isWarn ? '#fecaca' : '#fff',
          borderWidth: isWarn ? 3 : 1
        }
      }
    })

    series.push({
      name: labelCpk.value,
      type: 'line',
      yAxisIndex: weight ? 2 : 1,
      data: cpkPoints,
      smooth: true,
      lineStyle: { width: 2.5, color: '#059669' },
      markLine: { silent: true, symbol: 'none', data: cpkMarkLines }
    })
  }

  // Y轴配置
  const yAxes = weight
    ? [
        // 左轴: 实际胎重 (kg) - 均值与标准差共享
        {
          type: 'value',
          name: '实际胎重 (kg)',
          nameTextStyle: { fontSize: 11, color: '#2563eb' },
          axisLabel: { fontSize: 10, color: '#2563eb' },
          splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } }
        },
        // 占位（对齐非 weight 轴数量）
        { show: false },
        // 右轴: Diff 偏差率 (%)
        {
          type: 'value',
          name: 'Diff 偏差率 (%)',
          nameTextStyle: { fontSize: 11, color: '#059669' },
          axisLabel: {
            fontSize: 10,
            color: '#059669',
            formatter: v => (v > 0 ? '+' : '') + v.toFixed(2) + '%'
          },
          splitLine: { show: false }
        }
      ]
    : [
        {
          type: 'value',
          name: '均值 (avg)',
          nameTextStyle: { fontSize: 11, color: '#2563eb' },
          axisLabel: { fontSize: 10, color: '#2563eb' },
          splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } }
        },
        {
          type: 'value',
          name: '标准差(σ) / CPK',
          nameTextStyle: { fontSize: 11, color: '#059669' },
          axisLabel: { fontSize: 10, color: '#059669' },
          splitLine: { show: false }
        }
      ]

  return {
    backgroundColor: 'transparent',
    grid: { top: 40, right: 90, bottom: 45, left: 60 },
    legend: {
      show: false
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e5e8ef',
      borderWidth: 1,
      formatter(params) {
        const date = params[0]?.name || ''
        const idx = params[0]?.dataIndex ?? 0
        const item = trendData.value[idx] || {}
        const cpkVal = item.cpk_val
        const isWarn = warnThreshold !== null && (
          weight ? Math.abs(cpkVal) >= warnThreshold : cpkVal <= warnThreshold
        )
        const warnHtml = isWarn
          ? `<div style="color:#ef4444; font-weight:bold; margin-top:3px;">⚠️ ${weight ? `超出公差限 ±${warnThreshold}%` : `跌破 CPK 预警线 (${cpkVal} ≤ ${warnThreshold})`}</div>`
          : ''

        if (weight) {
          const diffSign = cpkVal >= 0 ? '+' : ''
          return `
            <div style="font-weight:bold;margin-bottom:4px">${date}</div>
            <div>实际胎重均值: <strong style="color:#2563eb">${item.mean_val?.toFixed(3) ?? '-'} kg</strong></div>
            <div>实际胎重标准差: <strong style="color:#d97706">${item.std_val?.toFixed(4) ?? '-'} kg</strong></div>
            <div>Diff 偏差率: <strong style="color:#059669">${diffSign}${cpkVal?.toFixed(3) ?? '-'}%</strong></div>
            <div>样本量 (N): <strong>${item.sample_size ?? 0}</strong></div>
            ${warnHtml}
          `
        }

        return `
          <div style="font-weight:bold;margin-bottom:4px">${date}</div>
          <div>均值 (avg): <strong style="color:#2563eb">${item.mean_val?.toFixed(2) ?? '-'}</strong></div>
          <div>标准差 (σ): <strong style="color:#d97706">${item.std_val?.toFixed(2) ?? '-'}</strong></div>
          <div>CPK 指数: <strong style="color:#059669">${cpkVal?.toFixed(2) ?? '-'}</strong></div>
          <div>样本量 (N): <strong>${item.sample_size ?? 0}</strong></div>
          ${warnHtml}
        `
      }
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        fontSize: 10,
        color: '#8c959f',
        rotate: dates.length > 20 ? 35 : 0
      }
    },
    yAxis: yAxes,
    series: series
  }
})
</script>


