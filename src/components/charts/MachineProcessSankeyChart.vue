<template>
  <div class="sankey-container" style="width: 100%; height: 100%; position: relative;">
    <div v-if="loading" class="sankey-loading" style="height: 100%; display: flex; align-items: center; justify-content: center;">
      <el-icon class="is-loading" size="24"><Loading /></el-icon>
      <span style="margin-left: 8px; font-size: 13px; color: #666;">正在生成工序流转桑基图...</span>
    </div>
    <div v-else-if="error" class="sankey-error" style="height: 100%; display: flex; align-items: center; justify-content: center; color: #ef4444; font-size: 13px;">
      <span>{{ error }}</span>
    </div>
    <div v-else-if="!sankeyData || !sankeyData.nodes || sankeyData.nodes.length === 0" class="sankey-empty" style="height: 100%; display: flex; align-items: center; justify-content: center; color: #8c959f; font-size: 13px;">
      <el-empty description="当前规格无工序流转路径数据" :image-size="60" />
    </div>
    <template v-else>
      <div style="display: flex; flex-direction: column; height: 100%;">
        <div class="path-notice" style="flex-shrink: 0; margin-bottom: 6px; font-size: 12px; background: #fff7ed; padding: 6px 12px; border-radius: 4px; border: 1px solid #ffedd5; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <span style="font-weight: 600; color: #475569;">🎨 节点颜色对应不同工段，{{ props.indicator === 'weight' ? '色深代表偏差严重程度' : '色深代表 CPK 严重程度' }}</span>
            <span style="font-weight: 600; color: #dc2626;">🔴 红色发光节点：全局核心负贡献机台</span>
          </div>
          <el-button size="small" class="zoom-btn" :icon="ZoomIn" style="margin-left: 8px;" @click="dialogVisible = true">
            放大查看
          </el-button>
        </div>
        <v-chart
          :option="option"
          autoresize
          style="width: 100%; flex: 1; min-height: 0; cursor: pointer;"
          @click="onChartClick"
        />
      </div>
    </template>

    <!-- 放大全屏查看弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      title="🔍 5列生产工序流转桑基图 - 放大全屏分析"
      width="92%"
      top="4vh"
      destroy-on-close
      append-to-body
    >
      <div style="height: 650px; width: 100%;">
        <v-chart
          :option="zoomedOption"
          autoresize
          style="width: 100%; height: 100%; cursor: pointer;"
          @click="onChartClick"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { SankeyChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Loading, ZoomIn } from '@element-plus/icons-vue'

use([SankeyChart, TooltipComponent, CanvasRenderer])

const props = defineProps({
  sankeyData: { type: Object, default: () => ({ nodes: [], links: [] }) },
  loading:    { type: Boolean, default: false },
  error:      { type: String, default: null },
  indicator:  { type: String, default: 'rfpp' },
  tolerance:  { type: Number, default: 0.8 }
})

const emit = defineEmits(['click-node'])

const dialogVisible = ref(false)

const sankeyPrefixToCol = {
  "胎面": "tread_workcenter",
  "胎圈": "bead_workcenter",
  "内衬": "inner_liner_workcenter",
  "胎侧": "sidewall_workcenter",
  "带束层1": "first_breaker_workcenter",
  "带束层2": "second_breaker_workcenter",
  "帘布层1": "first_ply_workcenter",
  "帘布层2": "second_ply_workcenter",
  "冠带层1": "wound_cap_ply1_workcenter",
  "冠带层2": "wound_cap_ply2_workcenter",
  "生胎成型GT": "gt_workcenter",
  "硫化CT": "ct_workcenter",
  "终检TU": "tu_first_workcenter",
  "动平衡TB": "tb_first_workcenter"
}

function onChartClick(params) {
  if (params && params.dataType === 'node') {
    const parts = params.name.split('_')
    const prefix = parts[0]
    const machine = parts[1]
    const workcenterCol = sankeyPrefixToCol[prefix]
    if (machine && workcenterCol) {
      emit('click-node', { machine, workcenterCol })
      dialogVisible.value = false
    }
  }
}

const option = computed(() => {
  if (!props.sankeyData || !props.sankeyData.nodes) return {}

  // 1. 计算每个工段下出现的机台节点总数，用于区分“单机台”与“多机台”工段
  const prefixMachineCounts = {}
  props.sankeyData.nodes.forEach(n => {
    const prefix = n.name.split("_")[0]
    prefixMachineCounts[prefix] = (prefixMachineCounts[prefix] || 0) + 1
  })

  // 2. 按工段提取所有机台的有效 CPK 指标值，并计算各工段的自适应映射极值
  const prefixCpkBounds = {}
  props.sankeyData.nodes.forEach(n => {
    const prefix = n.name.split("_")[0]
    if (!prefixCpkBounds[prefix]) {
      prefixCpkBounds[prefix] = []
    }
    if (n.spec_cpk !== undefined && n.spec_cpk !== null) {
      prefixCpkBounds[prefix].push(n.spec_cpk)
    }
  })

  const prefixCpkExtremes = {}
  for (const prefix in prefixCpkBounds) {
    const vals = prefixCpkBounds[prefix]
    if (vals.length > 0) {
      prefixCpkExtremes[prefix] = {
        min: Math.min(...vals),
        max: Math.max(...vals)
      }
    } else {
      prefixCpkExtremes[prefix] = { min: 1.33, max: 1.33 }
    }
  }

  // 节点颜色生成函数：
  // 1. 如果该 workcenter 只有一台机器，则使用统一的灰色 (#cbd5e1)
  // 2. 如果有多个机台，则使用明亮鲜艳的高饱和度配色，根据 CPK 局域相对位置自适应映射深浅
  function getNodeColor(prefix, cpk) {
    // 单机台工段，统一使用中灰色标记
    if (prefixMachineCounts[prefix] === 1) {
      return '#cbd5e1'
    }

    // 各多机台工段基础色相 Hue (H) - 对应一组高明度亮色系 (完全排除 310-360 以及 0-20 的红粉色范围)
    const baseHues = {
      "胎面": 217,        // 亮蓝
      "胎侧": 190,        // 湖蓝/青绿
      "内衬": 174,        // 亮青
      "胎圈": 45,         // 金黄
      "帘布层1": 262,      // 亮紫
      "带束层1": 239,      // 靛蓝
      "带束层2": 205,      // 天蓝
      "冠带层1": 280,      // 罗兰紫
      "冠带层2": 220,      // 灰蓝
      "生胎成型GT": 250,    // 蓝紫
      "硫化CT": 35,        // 暖橙
      "终检TU": 228,       // 皇家蓝
      "动平衡TB": 30        // 浅橙褐/古铜
    }

    const h = baseHues[prefix] ?? 217
    const cpkVal = (cpk !== undefined && cpk !== null && cpk >= 0) ? cpk : 1.33
    const extremes = prefixCpkExtremes[prefix] || { min: 1.33, max: 1.33 }
    
    let ratio = 0.5
    if (extremes.max > extremes.min) {
      if (props.indicator === 'weight') {
        ratio = (cpkVal - extremes.min) / (extremes.max - extremes.min)
      } else {
        ratio = (extremes.max - cpkVal) / (extremes.max - extremes.min)
      }
    }

    // 采用高饱和度 (80% - 90%)，亮度在 45% 到 80% 之间映射
    const s = 85
    const l = Math.round(80 - ratio * 35)
    return `hsl(${h}, ${s}%, ${l}%)`
  }

  const nodes = props.sankeyData.nodes.map(n => {
    const prefix = n.name.split("_")[0]
    // 动平衡TB 需要在 TU 之后单独一层深度展示
    const adjustedDepth = (prefix === '动平衡TB') ? n.depth + 1 : n.depth
    const nodeColor = getNodeColor(prefix, n.spec_cpk)
    
    const itemStyle = {
      color: nodeColor,
      borderColor: nodeColor,
      borderWidth: 0
    }

    // 全局核心负贡献节点，添加红色霓虹外发光投影特效
    if (n.is_warning_machine) {
      itemStyle.shadowColor = 'rgba(239, 68, 68, 0.95)'
      itemStyle.shadowBlur = 12
      itemStyle.shadowOffsetX = 0
      itemStyle.shadowOffsetY = 0
    }

    return {
      name: n.name,
      depth: adjustedDepth,
      is_warning_machine: n.is_warning_machine,
      spec_cpk: n.spec_cpk,
      spec_ratio: n.spec_ratio,
      spec_avg: n.spec_avg,
      itemStyle: itemStyle
    }
  })

  // 根据 depth 和自定义的工段顺序进行排序，使相同 workcenter 的节点聚集排列在一起
  const sortedNodes = [...nodes].sort((a, b) => {
    if (a.depth !== b.depth) return a.depth - b.depth
    
    const wcOrder = {
      // Depth 0
      "胎面": 1, "胎侧": 2, "内衬": 3, "胎圈": 4,
      // Depth 1
      "带束层1": 1, "带束层2": 2, "帘布层1": 3, "冠带层1": 4, "冠带层2": 5,
      // Depth 2
      "生胎成型GT": 1,
      // Depth 3
      "硫化CT": 1,
      // Depth 4
      "终检TU": 1,
      // Depth 5 (动平衡TB placed after TU)
      "动平衡TB": 1
    }
    
    const aOrder = wcOrder[a.name.split("_")[0]] ?? 99
    const bOrder = wcOrder[b.name.split("_")[0]] ?? 99
    if (aOrder !== bOrder) return aOrder - bOrder
    
    return a.name.localeCompare(b.name)
  })

  const links = props.sankeyData.links.map(l => {
    return {
      source: l.source,
      target: l.target,
      value: l.value,
      avg_3sigma: l.avg_3sigma,
      avg_diff_abs: l.avg_diff_abs,
      lineStyle: {
        color: 'rgba(148, 163, 184, 0.35)',
        curveness: 0.5,
        width: 1.5
      }
    }
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      backgroundColor: '#fff',
      borderColor: '#e5e8ef',
      borderWidth: 1,
      formatter(params) {
        if (params.dataType === 'node') {
          const cpk = params.data.spec_cpk
          const warnText = params.data.is_warning_machine ? ' <span style="color:#ef4444;font-weight:bold;">[全局核心负贡献]</span>' : ''
          if (props.indicator === 'weight') {
            const avgPct = params.data.spec_ratio
            const meanVal = params.data.spec_avg
            const avgPctStr = avgPct !== undefined && avgPct !== null ? (avgPct > 0 ? '+' : '') + avgPct.toFixed(2) + '%' : '暂无数据'
            const meanStr = meanVal !== undefined && meanVal !== null ? (meanVal > 0 ? '+' : '') + meanVal.toFixed(3) + ' kg' : '暂无数据'
            return `
              <div style="font-weight:bold;margin-bottom:4px">${params.name}${warnText}</div>
              <div style="font-size:11px;color:#64748b;">偏差率: <strong style="color:#2563eb">${avgPctStr}</strong></div>
              <div style="font-size:11px;color:#64748b;">物理均值差: <strong style="color:#10b981">${meanStr}</strong></div>
            `
          }
          const cpkStr = (cpk !== undefined && cpk !== null) ? cpk.toFixed(2) : '暂无数据'
          return `
            <div style="font-weight:bold;margin-bottom:4px">${params.name}${warnText}</div>
            <div style="font-size:11px;color:#64748b;">单规格 CPK: <strong style="color:#2563eb">${cpkStr}</strong></div>
          `
        } else if (params.dataType === 'edge') {
          const l = params.data
          if (props.indicator === 'weight') {
            const avgPct = l.avg_3sigma
            const meanVal = l.avg_diff_abs
            const avgPctStr = avgPct !== undefined && avgPct !== null ? (avgPct > 0 ? '+' : '') + avgPct.toFixed(2) + '%' : '暂无数据'
            const meanStr = meanVal !== undefined && meanVal !== null ? (meanVal > 0 ? '+' : '') + meanVal.toFixed(3) + ' kg' : '暂无数据'
            return `
              <div style="font-weight:bold;margin-bottom:4px">${l.source} ➔ ${l.target}</div>
              <div style="font-size:11px;color:#64748b;">流转轮胎数 (N): <strong style="color:#2563eb">${l.value}</strong></div>
              <div style="font-size:11px;color:#64748b;">流转偏差率: <strong style="color:#2563eb">${avgPctStr}</strong></div>
              <div style="font-size:11px;color:#64748b;">物理均值差: <strong style="color:#10b981">${meanStr}</strong></div>
            `
          }
          return `
            <div style="font-weight:bold;margin-bottom:4px">${l.source} ➔ ${l.target}</div>
            <div>流转轮胎条数 (N): <strong style="color:#2563eb">${l.value}</strong></div>
          `
        }
      }
    },
    series: [
      {
        type: 'sankey',
        left: 10,
        top: 10,
        right: 120,
        bottom: 10,
        nodeGap: 24, // 增加垂直间距使布局宽松
        nodeWidth: 16,
        layoutIterations: 0, // 设为 0 以保证尊重我们自定义的排序（相同 workcenter 的节点聚在一起）
        data: sortedNodes,
        links: links,
        orient: 'horizontal',
        label: {
          fontSize: 10,
          color: '#334155',
          formatter(params) {
            const parts = params.name.split('_')
            const displayName = parts.length > 1 ? parts[1] : params.name
            const cpk = params.data.spec_cpk
            if (cpk !== undefined && cpk !== null) {
              if (props.indicator === 'weight') {
                const avgPct = params.data.spec_ratio
                const sign = avgPct > 0 ? '+' : ''
                return `${displayName} (${sign}${avgPct.toFixed(2)}%)`
              }
              return `${displayName} (CPK: ${cpk.toFixed(2)})`
            }
            return displayName
          }
        },
        lineStyle: {
          color: 'gradient',
          curveness: 0.5
        }
      }
    ]
  }
})

// 放大全屏模式配置（增强字号与节点间距）
const zoomedOption = computed(() => {
  const baseOpt = option.value
  if (!baseOpt || !baseOpt.series) return {}

  const deep = JSON.parse(JSON.stringify(baseOpt))
  const s = deep.series[0]
  s.left = 40
  s.right = 160
  s.top = 20
  s.bottom = 20
  s.nodeGap = 36 // 放大模式下给予更充足的间距
  s.nodeWidth = 20
  s.label.fontSize = 11
  s.label.color = '#1e293b'
  s.label.formatter = function(params) {
    const parts = params.name.split('_')
    const displayName = parts.length > 1 ? parts[1] : params.name
    const cpk = params.data.spec_cpk
    if (cpk !== undefined && cpk !== null) {
      if (props.indicator === 'weight') {
        const avgPct = params.data.spec_ratio
        const sign = avgPct > 0 ? '+' : ''
        return `${displayName} (${sign}${avgPct.toFixed(2)}%)`
      }
      return `${displayName} (CPK: ${cpk.toFixed(2)})`
    }
    return displayName
  }

  return deep
})
</script>

<style scoped>
.sankey-container {
  overflow: hidden;
}
.zoom-btn {
  background-color: #fff !important;
  border-color: #ffedd5 !important;
  color: #c2410c !important;
  transition: all 0.2s ease-in-out !important;
  font-weight: 600 !important;
}
.zoom-btn:hover {
  background-color: #ffedd5 !important;
  border-color: #ffdbb5 !important;
  color: #9a3412 !important;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(194, 65, 12, 0.08);
}
.zoom-btn:active {
  transform: translateY(0);
}
</style>
