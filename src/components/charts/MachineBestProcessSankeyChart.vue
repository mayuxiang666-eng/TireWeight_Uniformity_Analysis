<template>
  <div class="sankey-container" style="width: 100%; height: 100%; position: relative;">
    <div v-if="loading" class="sankey-loading" style="height: 100%; display: flex; align-items: center; justify-content: center;">
      <el-icon class="is-loading" size="24"><Loading /></el-icon>
      <span style="margin-left: 8px; font-size: 13px; color: #666;">正在生成全量最佳工序流转路径图...</span>
    </div>
    <div v-else-if="error" class="sankey-error" style="height: 100%; display: flex; align-items: center; justify-content: center; color: #ef4444; font-size: 13px;">
      <span>{{ error }}</span>
    </div>
    <div v-else-if="!sankeyData || !sankeyData.nodes || sankeyData.nodes.length === 0" class="sankey-empty" style="height: 100%; display: flex; align-items: center; justify-content: center; color: #8c959f; font-size: 13px;">
      <el-empty description="该规格暂无全量最佳工序流转数据" :image-size="60" />
    </div>
    <template v-else>
      <div style="display: flex; flex-direction: column; height: 100%;">
        <div v-if="sankeyData.best_tu_machine" class="path-notice" style="flex-shrink: 0; margin-bottom: 8px; font-size: 12px; background: #ecfdf5; padding: 6px 12px; border-radius: 4px; border: 1px solid #a7f3d0; color: #047857; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <span>👑 基于过去30天数据计算出最佳检测机台 <strong>{{ sankeyData.best_tu_machine }}</strong></span>
          <div style="display: flex; gap: 12px; align-items: center;">
            <span style="font-weight: 600; color: #059669;">🟢 绿色标注：全量最佳生产路径</span>
            <el-button size="small" class="zoom-btn" :icon="ZoomIn" style="margin-left: 8px;" @click="dialogVisible = true">
              放大查看
            </el-button>
          </div>
        </div>
        <div v-else style="display: flex; justify-content: flex-end; margin-bottom: 6px; flex-shrink: 0;">
          <el-button size="small" class="zoom-btn" :icon="ZoomIn" @click="dialogVisible = true">
            放大查看图表
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
      title="👑 全量最佳生产工序路径桑基图 - 放大全屏分析"
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

  const nodes = props.sankeyData.nodes.map(n => {
    const prefix = n.name.split("_")[0]
    const adjustedDepth = (prefix === '动平衡TB') ? n.depth + 1 : n.depth
    let nodeColor = '#64748b' // 普通节点：蓝灰
    
    // 全量最佳路径上的节点使用翡翠绿标记
    if (n.is_best_path) {
      nodeColor = '#10b981'
    }

    return {
      name: n.name,
      depth: adjustedDepth,
      is_best_path: n.is_best_path,
      is_best_tu: n.is_best_tu,
      avg_val: n.avg_val,
      itemStyle: {
        color: nodeColor,
        borderColor: nodeColor,
        borderWidth: 0
      }
    }
  })

  const links = props.sankeyData.links.map(l => {
    return {
      source: l.source,
      target: l.target,
      value: l.value,
      avg_3sigma: l.avg_3sigma,
      lineStyle: l.is_best_path ? {
        color: 'rgba(16, 185, 129, 0.75)',
        curveness: 0.5,
        width: 3
      } : {
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
          const isBest = params.data.is_best_path
          const isBestTu = params.data.is_best_tu
          const avgVal = params.data.avg_val
          let avgStr = ''
          if (avgVal !== undefined && avgVal !== null) {
            if (props.indicator === 'weight') {
              const sign = avgVal > 0 ? '+' : ''
              avgStr = `<br/>偏差率: <strong style="color:#10b981">${sign}${avgVal.toFixed(2)}%</strong>`
            } else {
              avgStr = `<br/>均值 (μ): <strong style="color:#10b981">${avgVal.toFixed(2)}</strong>`
            }
          }
          let badge = ''
          if (isBestTu) {
            badge = `<div style="color:#059669;font-weight:bold;margin-top:4px">👑 最佳 TU 终检机台（全量波动最小/能力最高）</div>`
          } else if (isBest) {
            badge = `<div style="color:#059669;font-weight:bold;margin-top:4px">🟢 最佳生产路径上的推荐节点</div>`
          }
          return `<div style="font-weight:bold;margin-bottom:2px">${params.name}</div>
                  <div>工序节点关联数据${avgStr}</div>
                  ${badge}`
        } else if (params.dataType === 'edge') {
          const l = params.data
          return `
            <div style="font-weight:bold;margin-bottom:4px">${l.source} ➔ ${l.target}</div>
            <div>全量历史轮胎数 (N): <strong style="color:#2563eb">${l.value}</strong></div>
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
        nodeWidth: 16,
        nodeGap: 24,
        nodeAlign: 'justify',
        layoutIterations: 64,
        orient: 'horizontal',
        draggable: true,
        data: nodes,
        links: links,
        label: {
          position: 'right',
          fontSize: 10,
          color: '#334155',
          formatter: (params) => {
            const parts = params.name.split('_')
            const avgVal = params.data?.avg_val
            let suffix = ''
            if (avgVal !== undefined && avgVal !== null) {
              if (props.indicator === 'weight') {
                const sign = avgVal > 0 ? '+' : ''
                suffix = ` (${sign}${avgVal.toFixed(2)}%)`
              } else {
                suffix = ` (μ: ${avgVal.toFixed(2)})`
              }
            }
            return parts.length > 1 ? `${parts[1]}${suffix}` : `${params.name}${suffix}`
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
  s.left = 50
  s.right = 160
  s.top = 25
  s.bottom = 25
  s.nodeGap = 18
  s.nodeWidth = 22
  s.label.fontSize = 11
  s.label.color = '#1e293b'
  s.label.formatter = baseOpt.series[0].label.formatter
  deep.tooltip.formatter = baseOpt.tooltip.formatter

  return deep
})
</script>

<style scoped>
.path-notice {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.zoom-btn {
  background-color: #fff !important;
  border-color: #a7f3d0 !important;
  color: #047857 !important;
  transition: all 0.2s ease-in-out !important;
  font-weight: 600 !important;
}
.zoom-btn:hover {
  background-color: #a7f3d0 !important;
  border-color: #86efac !important;
  color: #065f46 !important;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(4, 120, 87, 0.08);
}
.zoom-btn:active {
  transform: translateY(0);
}
</style>
