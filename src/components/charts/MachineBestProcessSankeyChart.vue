<template>
  <div ref="sankeyContainerRef" class="sankey-container" style="width: 100%; height: 100%; position: relative;">
    <div v-if="loading" class="sankey-loading" style="height: 100%; display: flex; align-items: center; justify-content: center;">
      <el-icon class="is-loading" size="24"><Loading /></el-icon>
      <span style="margin-left: 8px; font-size: 13px; color: #666;">正在生成全量最佳工序流转路径图...</span>
    </div>
    <div v-else-if="error" class="sankey-error" style="height: 100%; display: flex; align-items: center; justify-content: center; color: #ef4444; font-size: 13px;">
      <span>{{ error }}</span>
    </div>
    <div v-else-if="!sankeyData || !sankeyData.nodes || sankeyData.nodes.length === 0" class="sankey-empty" style="height: 100%; display: flex; align-items: center; justify-content: center; color: #8c959f; font-size: 13px;">
      <el-empty :description="sankeyEmptyDescription" :image-size="60" />
    </div>
    <template v-else>
      <div style="display: flex; flex-direction: column; height: 100%;">
        <!-- 可拖拽悬浮注水/发光球 (Draggable Floating Orb) -->
        <div
          class="rec-floating-orb-wrapper"
          :style="orbWrapperStyle"
          @pointerdown="onOrbPointerDown"
        >
          <el-tooltip placement="left" raw-content>
            <template #content>
              <div style="font-size: 12px; padding: 2px;">
                <span v-if="recommendationLoading">正在检索近 7 天同规格 CGRS 参数推荐...</span>
                <span v-else-if="recommendationData && recommendationData.has_recommendation">
                  <strong>点击查看同规格 CGRS 参数推荐 (按住可拖拽移动)</strong><br/>
                  <span style="color: #6ee7b7; font-size: 11px;">(已整合生胎成型 GT 与 硫化 CU 调参明细)</span>
                </span>
                <span v-else>近 7 天同规格暂无符合条件的正向参数推荐</span>
              </div>
            </template>
            <div
              class="rec-floating-orb"
              :class="{
                'is-loading': recommendationLoading,
                'is-success': !recommendationLoading && recommendationData && recBadgeCount > 0,
                'is-empty': !recommendationLoading && (!recommendationData || !recommendationData.has_recommendation || recBadgeCount === 0),
                'is-active': isRecExpanded,
                'is-dragging': isDragging
              }"
              @click="toggleRecPanel"
            >
              <div v-if="recommendationLoading" class="orb-water-fill">
                <el-icon class="is-loading" style="font-size: 16px; color: #ffffff;"><Loading /></el-icon>
              </div>
              <div v-else-if="recommendationData && recommendationData.has_recommendation && recBadgeCount > 0" class="orb-content">
                <svg class="ai-sparkle-icon" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z"/>
                  <path d="M20 2L20.8 4.2L23 5L20.8 5.8L20 8L19.2 5.8L17 5L19.2 4.2L20 2Z" opacity="0.85"/>
                </svg>
                <span v-if="recBadgeCount > 0" class="orb-badge">{{ recBadgeCount }}</span>
              </div>
              <div v-else class="orb-content">
                <svg class="ai-sparkle-icon" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="opacity: 0.75;">
                  <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z"/>
                </svg>
              </div>
            </div>
          </el-tooltip>
        </div>

        <!-- 悬浮展开的 CGRS 调参推荐卡片 (跟随悬浮球或原位渲染) -->
        <transition name="el-zoom-in-top">
          <div
            v-if="isRecExpanded && recommendationData"
            class="recommendation-floating-panel"
            :style="panelStyle"
          >
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 12px;">
              <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-weight: 800; color: #047857; font-size: 13.5px; display: inline-flex; align-items: center; gap: 4px;">
                  参数推荐
                </span>
                <el-radio-group v-model="activeTab" size="small">
                  <el-radio-button label="gt">生胎成型 (GT)</el-radio-button>
                  <el-radio-button label="cu">硫化工段 (CU)</el-radio-button>
                </el-radio-group>
              </div>
              <el-button type="info" link size="small" @click="isRecExpanded = false" style="font-weight: 700; font-size: 16px; color: #94a3b8;">✕</el-button>
            </div>

            <!-- 成型 (GT) 推荐卡片 -->
            <template v-if="activeTab === 'gt'">
              <div v-if="recommendationData.gt_recommendation" class="rec-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                  <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #047857; font-size: 12.5px;">
                    <span>来源机台: <strong style="color: #065f46; font-size: 13px;">{{ recommendationData.gt_recommendation.workcenter }}</strong></span>
                    <span style="font-size: 11px; color: #64748b; font-weight: normal;">
                      ({{ recommendationData.gt_recommendation.timestamp || recommendationData.gt_recommendation.date }})
                    </span>
                  </div>
                  <div style="display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-size: 12px;">
                    <span>改后 CPK: <strong style="color: #047857;">{{ recommendationData.gt_recommendation.cpk_before }}</strong> ➔ <strong style="color: #059669; font-size: 13.5px;">{{ recommendationData.gt_recommendation.cpk_after }}</strong></span>
                    <el-tag size="small" type="success" effect="dark" style="font-weight: bold;">
                      +{{ recommendationData.gt_recommendation.yoy_pct }}%
                    </el-tag>
                  </div>
                </div>

                <div v-if="recommendationData.gt_recommendation.params_changed && recommendationData.gt_recommendation.params_changed.length > 0" style="display: flex; flex-wrap: wrap; gap: 8px; background: #f0fdf4; padding: 10px 12px; border-radius: 8px; border: 1px dashed #a7f3d0; align-items: center; max-height: 220px; overflow-y: auto;">
                  <span style="font-weight: 700; color: #047857; font-size: 11.5px; width: 100%; margin-bottom: 2px;">建议成型参数调整:</span>
                  <div
                    v-for="(p, pIdx) in recommendationData.gt_recommendation.params_changed"
                    :key="pIdx"
                    style="font-size: 11.5px; color: #1e293b; background: #ffffff; padding: 4px 10px; border-radius: 6px; border: 1px solid #cbd5e1; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);"
                  >
                    <strong style="color: #0369a1;">{{ p.param_local || p.param_code || p.ParameterName || '参数' }}</strong>:
                    <span style="color: #64748b; font-family: monospace;">{{ p.from_val ?? p.ParameterValue ?? '-' }}</span>
                    <span style="color: #059669; font-weight: bold;">➔</span>
                    <strong style="color: #15803d; font-family: monospace; font-size: 12px;">{{ p.to_val ?? p.ParameterValue ?? '-' }}</strong>
                  </div>
                </div>
              </div>
              <div v-else style="font-size: 12px; color: #94a3b8; padding: 16px 0; text-align: center; background: #f8fafc; border-radius: 8px; border: 1px dashed #e2e8f0;">
                近 7 天生胎成型 (GT) 工段暂无该规格符合条件的正向调参记录
              </div>
            </template>

            <!-- 硫化 (CU) 推荐卡片 -->
            <template v-if="activeTab === 'cu'">
              <div v-if="recommendationData.cu_recommendation" class="rec-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                  <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #b45309; font-size: 12.5px;">
                    <span>来源机台: <strong style="color: #92400e; font-size: 13px;">{{ recommendationData.cu_recommendation.workcenter }}</strong></span>
                    <span style="font-size: 11px; color: #64748b; font-weight: normal;">
                      ({{ recommendationData.cu_recommendation.timestamp || recommendationData.cu_recommendation.date }})
                    </span>
                  </div>
                  <div style="display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-size: 12px;">
                    <span>改后 CPK: <strong style="color: #b45309;">{{ recommendationData.cu_recommendation.cpk_before }}</strong> ➔ <strong style="color: #d97706; font-size: 13.5px;">{{ recommendationData.cu_recommendation.cpk_after }}</strong></span>
                    <el-tag size="small" type="warning" effect="dark" style="font-weight: bold;">
                      +{{ recommendationData.cu_recommendation.yoy_pct }}%
                    </el-tag>
                  </div>
                </div>

                <div v-if="recommendationData.cu_recommendation.params_changed && recommendationData.cu_recommendation.params_changed.length > 0" style="display: flex; flex-wrap: wrap; gap: 8px; background: #fffbeb; padding: 10px 12px; border-radius: 8px; border: 1px dashed #fde68a; align-items: center; max-height: 220px; overflow-y: auto;">
                  <span style="font-weight: 700; color: #b45309; font-size: 11.5px; width: 100%; margin-bottom: 2px;">建议硫化参数调整:</span>
                  <div
                    v-for="(p, pIdx) in recommendationData.cu_recommendation.params_changed"
                    :key="pIdx"
                    style="font-size: 11.5px; color: #1e293b; background: #ffffff; padding: 4px 10px; border-radius: 6px; border: 1px solid #fde68a; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);"
                  >
                    <strong style="color: #b45309;">{{ p.param_local || p.param_code || p.ParameterName || '参数' }}</strong>:
                    <span style="color: #64748b; font-family: monospace;">{{ p.from_val ?? p.ParameterValue ?? '-' }}</span>
                    <span style="color: #d97706; font-weight: bold;">➔</span>
                    <strong style="color: #b45309; font-family: monospace; font-size: 12px;">{{ p.to_val ?? p.ParameterValue ?? '-' }}</strong>
                  </div>
                </div>
              </div>
              <div v-else style="font-size: 12px; color: #94a3b8; padding: 16px 0; text-align: center; background: #f8fafc; border-radius: 8px; border: 1px dashed #e2e8f0;">
                近 7 天硫化工段 (CU) 暂无该规格符合条件的正向调参记录
              </div>
            </template>
          </div>
        </transition>

        <div v-if="sankeyData.best_tu_machine" class="path-notice" style="flex-shrink: 0; margin-bottom: 8px; font-size: 12px; background: #ecfdf5; padding: 6px 12px; padding-right: 54px; border-radius: 4px; border: 1px solid #a7f3d0; color: #047857; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span>基于过去30天数据计算出{{ bestTuCriterionText }} <strong>{{ sankeyData.best_tu_machine }}</strong></span>
            <el-tooltip placement="top" raw-content>
              <template #content>
                <div style="max-width: 330px; font-size: 12px; line-height: 1.6; padding: 4px;">
                  <strong style="color: #10b981;">最佳生产路径推导算法逻辑：</strong><br/>
                  1. <strong>定位最优终检机台（锚点）</strong>：<br/>
                  • <strong>RFPP / RFH1 指标</strong>：筛选过去 30 天样本充足（N ≥ 门槛）的数据，选取<strong>过程能力指数 CPK 表现最高</strong>的 TU 机台（如 {{ sankeyData.best_tu_machine }}）；<br/>
                  • <strong>CONY 指标</strong>：选取<strong>标准差 (σ) 最小、离散波动最稳定</strong>的 TU 机台；<br/>
                  • <strong>胎重偏差指标</strong>：选取<strong>实际胎重与目标标准偏差绝对值最小</strong>的 TU 机台。<br/>
                  2. <strong>反向追溯主导工艺链路</strong>：以该最佳 TU 机台为基准向前逆向回溯全量流转数据，提取各工段（生胎成型 GT、硫化 CT、胎面、带束层等）排产占比最高且工序质量最稳定的匹配机台；<br/>
                  3. <strong>全链路推荐</strong>：将整条生产路径高亮为绿色推荐链路。
                </div>
              </template>
              <el-icon style="cursor: pointer; color: #047857; font-size: 13px;"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <span style="font-weight: 600; color: #059669;">绿色标注：全量最佳生产路径</span>
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
      title="全量最佳生产工序路径桑基图 - 放大全屏分析"
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
import { Loading, ZoomIn, QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

use([SankeyChart, TooltipComponent, CanvasRenderer])

const props = defineProps({
  sankeyData: { type: Object, default: () => ({ nodes: [], links: [] }) },
  loading:    { type: Boolean, default: false },
  error:      { type: String, default: null },
  indicator:  { type: String, default: 'rfpp' },
  tolerance:  { type: Number, default: 0.8 },
  article:    { type: String, default: '' },
  recommendationData: { type: Object, default: null },
  recommendationLoading: { type: Boolean, default: false }
})


const emit = defineEmits(['open-cgrs'])

const sankeyContainerRef = ref(null)
const dialogVisible = ref(false)
const isRecExpanded = ref(false)
const activeTab = ref('gt')

// 悬浮球可拖拽 (Draggable Orb State)
const orbPos = ref({ x: null, y: null })
const isDragging = ref(false)
let startPointerX = 0
let startPointerY = 0
let startOrbX = 0
let startOrbY = 0
let hasDraggedMoved = false

const orbWrapperStyle = computed(() => {
  if (orbPos.value.x !== null && orbPos.value.y !== null) {
    return {
      position: 'absolute',
      left: `${orbPos.value.x}px`,
      top: `${orbPos.value.y}px`,
      zIndex: 100,
      cursor: isDragging.value ? 'grabbing' : 'grab',
      touchAction: 'none'
    }
  }
  return {
    position: 'absolute',
    top: '4px',
    right: '10px',
    zIndex: 100,
    cursor: 'grab',
    touchAction: 'none'
  }
})

const panelStyle = computed(() => {
  const base = {
    position: 'absolute',
    zIndex: 40,
    width: '500px',
    maxWidth: '92vw',
    background: 'rgba(255, 255, 255, 0.96)',
    backdropFilter: 'blur(16px)',
    border: '1px solid rgba(16, 185, 129, 0.35)',
    borderRadius: '12px',
    padding: '14px',
    boxShadow: '0 12px 32px -4px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(16, 185, 129, 0.1)'
  }

  if (orbPos.value.x !== null && orbPos.value.y !== null) {
    const containerWidth = sankeyContainerRef.value ? sankeyContainerRef.value.clientWidth : 800
    let panelLeft = orbPos.value.x - 230
    if (panelLeft < 12) panelLeft = 12
    if (panelLeft + 510 > containerWidth) panelLeft = Math.max(12, containerWidth - 512)

    return {
      ...base,
      top: `${orbPos.value.y + 48}px`,
      left: `${panelLeft}px`,
      right: 'auto'
    }
  }

  return {
    ...base,
    top: '52px',
    right: '16px'
  }
})

function onOrbPointerDown(e) {
  if (e.button !== undefined && e.button !== 0) return
  const container = sankeyContainerRef.value
  if (!container) return

  const containerRect = container.getBoundingClientRect()
  const wrapperEl = e.currentTarget
  const wrapperRect = wrapperEl.getBoundingClientRect()

  startPointerX = e.clientX
  startPointerY = e.clientY
  startOrbX = wrapperRect.left - containerRect.left
  startOrbY = wrapperRect.top - containerRect.top
  hasDraggedMoved = false

  isDragging.value = true

  window.addEventListener('pointermove', onOrbPointerMove)
  window.addEventListener('pointerup', onOrbPointerUp)
  window.addEventListener('pointercancel', onOrbPointerUp)
}

function onOrbPointerMove(e) {
  if (!isDragging.value) return
  const dx = e.clientX - startPointerX
  const dy = e.clientY - startPointerY

  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
    hasDraggedMoved = true
  }

  const container = sankeyContainerRef.value
  if (!container) return
  const containerRect = container.getBoundingClientRect()

  const orbWidth = 42
  const orbHeight = 42

  let newX = startOrbX + dx
  let newY = startOrbY + dy

  newX = Math.max(8, Math.min(containerRect.width - orbWidth - 8, newX))
  newY = Math.max(8, Math.min(containerRect.height - orbHeight - 8, newY))

  orbPos.value = { x: newX, y: newY }
}

function onOrbPointerUp() {
  isDragging.value = false
  window.removeEventListener('pointermove', onOrbPointerMove)
  window.removeEventListener('pointerup', onOrbPointerUp)
  window.removeEventListener('pointercancel', onOrbPointerUp)
}

const recBadgeCount = computed(() => {
  if (!props.recommendationData || !props.recommendationData.has_recommendation) return 0
  let count = 0
  const gt = props.recommendationData.gt_recommendation
  const cu = props.recommendationData.cu_recommendation
  if (gt && (gt.workcenter || (gt.params_changed && gt.params_changed.length > 0))) count++
  if (cu && (cu.workcenter || (cu.params_changed && cu.params_changed.length > 0))) count++
  return count
})

function toggleRecPanel() {
  if (props.recommendationLoading) return
  if (hasDraggedMoved) {
    hasDraggedMoved = false
    return
  }
  isRecExpanded.value = !isRecExpanded.value
  if (isRecExpanded.value && props.recommendationData) {
    const gt = props.recommendationData.gt_recommendation
    const cu = props.recommendationData.cu_recommendation
    const hasGt = !!(gt && (gt.workcenter || (gt.params_changed && gt.params_changed.length > 0)))
    const hasCu = !!(cu && (cu.workcenter || (cu.params_changed && cu.params_changed.length > 0)))
    if (!hasGt && hasCu) {
      activeTab.value = 'cu'
    } else {
      activeTab.value = 'gt'
    }
  }
}

const sankeyEmptyDescription = computed(() => {
  if (props.sankeyData && props.sankeyData.empty_message) {
    return props.sankeyData.empty_message
  }
  return '该规格暂无全量最佳工序流转数据'
})

const bestTuCriterionText = computed(() => {
  if (props.indicator === 'cony') {
    return '最佳标准差终检机台'
  } else if (props.indicator === 'weight') {
    return '最佳胎重偏差终检机台'
  } else {
    return '最佳 CPK 终检机台'
  }
})

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
    const machine = parts.length > 1 ? parts.slice(1).join('_') : parts[0]
    const workcenterCol = sankeyPrefixToCol[prefix]
    
    // 成型工段 (生胎成型GT) 或 硫化工段 (硫化CT) 触发 CGRS 弹窗
    if (
      prefix.includes('成型') || prefix.includes('GT') || prefix.includes('硫化') || prefix.includes('CT') || prefix.includes('CU') ||
      (workcenterCol && (workcenterCol.includes('gt_workcenter') || workcenterCol.includes('ct_workcenter')))
    ) {
      emit('open-cgrs', {
        machine,
        stage: prefix,
        article: props.article,
        indicator: props.indicator,
        topWarningMachines: props.sankeyData?.top_warning_machines || []
      })
      dialogVisible.value = false
    } else {
      ElMessage.info(`CGRS 参数修改记录仅支持成型与硫化工段设备 (当前点击: ${prefix} - ${machine})`)
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
      std_val: n.std_val,
      cpk_val: n.cpk_val,
      ratio_val: n.ratio_val,
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
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [8, 12],
      extraCssText: 'box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-radius: 6px;',
      formatter(params) {
        if (params.dataType === 'node') {
          const isBest = params.data.is_best_path
          const isBestTu = params.data.is_best_tu
          const avgVal = params.data.avg_val
          const stdVal = params.data.std_val
          const cpkVal = params.data.cpk_val

          let badge = ''
          if (isBestTu) {
            badge = `<div style="color:#059669;font-weight:600;font-size:11px;margin-top:6px;padding-top:4px;border-top:1px dashed #e2e8f0;">[最佳 TU 终检机台] 全量波动最小 / 能力最高</div>`
          } else if (isBest) {
            badge = `<div style="color:#059669;font-weight:600;font-size:11px;margin-top:6px;padding-top:4px;border-top:1px dashed #e2e8f0;">[最佳推荐节点] 全量最佳生产路径推荐</div>`
          }

          if (props.indicator === 'weight') {
            const ratioVal = params.data.ratio_val ?? cpkVal
            const ratioStr = ratioVal !== undefined && ratioVal !== null ? (ratioVal > 0 ? '+' : '') + ratioVal.toFixed(2) + '%' : '暂无数据'
            const stdStr = stdVal !== undefined && stdVal !== null ? stdVal.toFixed(2) + '%' : '暂无数据'
            const meanStr = avgVal !== undefined && avgVal !== null ? (avgVal > 0 ? '+' : '') + avgVal.toFixed(3) + ' kg' : '暂无数据'
            return `
              <div style="font-weight:bold;font-size:13px;margin-bottom:6px;color:#1e293b;border-bottom:1px solid #f1f5f9;padding-bottom:4px;">${params.name}</div>
              <div style="display:flex;flex-direction:column;gap:3px;font-size:12px;color:#475569;">
                <div>偏差率: <strong style="color:#2563eb;">${ratioStr}</strong></div>
                <div>标准差 (σ): <strong style="color:#10b981;">${stdStr}</strong></div>
                <div>物理均值差: <strong style="color:#0f172a;">${meanStr}</strong></div>
              </div>
              ${badge}
            `
          }

          const cpkStr = (cpkVal !== undefined && cpkVal !== null) ? cpkVal.toFixed(2) : '暂无数据'
          const stdStr = (stdVal !== undefined && stdVal !== null) ? stdVal.toFixed(2) : '暂无数据'
          const avgStr = (avgVal !== undefined && avgVal !== null) ? avgVal.toFixed(2) : '暂无数据'

          return `
            <div style="font-weight:bold;font-size:13px;margin-bottom:6px;color:#1e293b;border-bottom:1px solid #f1f5f9;padding-bottom:4px;">${params.name}</div>
            <div style="display:flex;flex-direction:column;gap:3px;font-size:12px;color:#475569;">
              <div>全量 CPK: <strong style="color:#2563eb;">${cpkStr}</strong></div>
              <div>标准差 (σ): <strong style="color:#10b981;">${stdStr}</strong></div>
              <div>均值 (μ): <strong style="color:#0f172a;">${avgStr}</strong></div>
            </div>
            ${badge}
          `
        } else if (params.dataType === 'edge') {
          const l = params.data
          const bestTag = l.is_best_path ? `<div style="color:#059669;font-weight:600;font-size:11px;margin-top:4px;">[最佳生产流转链路]</div>` : ''
          return `
            <div style="font-weight:bold;font-size:13px;margin-bottom:6px;color:#1e293b;border-bottom:1px solid #f1f5f9;padding-bottom:4px;">${l.source} ➔ ${l.target}</div>
            <div style="font-size:12px;color:#475569;">全量历史轮胎数 (N): <strong style="color:#2563eb;">${l.value}</strong></div>
            ${bestTag}
          `
        }
      }
    },
    series: [
      {
        type: 'sankey',
        left: 10,
        top: 10,
        right: 180,
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
            const displayName = (parts.length > 1 ? parts[1] : params.name).toUpperCase()
            const avgVal = params.data?.avg_val
            const stdVal = params.data?.std_val
            const cpkVal = params.data?.cpk_val
            let suffix = ''
            if (props.indicator === 'weight') {
              const ratioVal = params.data?.ratio_val ?? cpkVal
              if (ratioVal !== undefined && ratioVal !== null) {
                const sign = ratioVal > 0 ? '+' : ''
                const avgText = (avgVal !== undefined && avgVal !== null) ? ` μ: ${(avgVal > 0 ? '+' : '')}${avgVal.toFixed(2)}` : ''
                const stdText = (stdVal !== undefined && stdVal !== null) ? ` σ: ${stdVal.toFixed(2)}` : ''
                suffix = `  {info|[ 偏离: ${sign}${ratioVal.toFixed(2)}%${avgText}${stdText} ]}`
              }
            } else {
              if (cpkVal !== undefined && cpkVal !== null) {
                const avgText = (avgVal !== undefined && avgVal !== null) ? ` μ: ${avgVal.toFixed(2)}` : ''
                const stdText = (stdVal !== undefined && stdVal !== null) ? ` σ: ${stdVal.toFixed(2)}` : ''
                suffix = `  {info|[ CPK: ${cpkVal.toFixed(2)}${avgText}${stdText} ]}`
              } else if (avgVal !== undefined && avgVal !== null) {
                const stdText = (stdVal !== undefined && stdVal !== null) ? ` σ: ${stdVal.toFixed(2)}` : ''
                suffix = `  {info|[ μ: ${avgVal.toFixed(2)}${stdText} ]}`
              }
            }
            return `{mach|${displayName}}${suffix}`
          },
          rich: {
            mach: {
              fontWeight: '900',
              fontSize: 11,
              color: '#0f172a'
            },
            info: {
              fontWeight: '400',
              fontSize: 9,
              color: '#64748b'
            }
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
  s.right = 200
  s.top = 25
  s.bottom = 25
  s.nodeGap = 18
  s.nodeWidth = 22
  s.label.fontSize = 11
  s.label.color = '#1e293b'
  s.label.formatter = baseOpt.series[0].label.formatter
  s.label.rich = baseOpt.series[0].label.rich
  if (deep.tooltip) {
    deep.tooltip.formatter = baseOpt.tooltip.formatter
  }

  return deep
})

function openZoomDialog() {
  dialogVisible.value = true
}

defineExpose({
  openZoomDialog
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

/* 悬浮发光球 Floating Liquid Orb Styling */
.rec-floating-orb {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  user-select: none;
}

.rec-floating-orb:hover {
  transform: scale(1.12) translateY(-2px);
}

/* 加载中：蓝色波浪脉冲 */
.rec-floating-orb.is-loading {
  background: radial-gradient(circle at 35% 35%, #60a5fa 0%, #3b82f6 60%, #1d4ed8 100%);
  box-shadow: 0 0 14px rgba(59, 130, 246, 0.6);
  animation: orbLoadingPulse 1.6s infinite ease-in-out;
}

/* 完成：翡翠绿微光气泡 */
.rec-floating-orb.is-success {
  background: radial-gradient(circle at 35% 35%, #34d399 0%, #10b981 60%, #047857 100%);
  box-shadow: 0 0 16px rgba(16, 185, 129, 0.6), inset 0 2px 4px rgba(255, 255, 255, 0.5);
  animation: orbSuccessGlow 3s infinite ease-in-out;
}

.rec-floating-orb.is-empty {
  background: radial-gradient(circle at 35% 35%, #cbd5e1 0%, #94a3b8 60%, #64748b 100%);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}

.rec-floating-orb.is-active {
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.4), 0 8px 20px rgba(16, 185, 129, 0.4);
}

.orb-content {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 100%;
  height: 100%;
}

.ai-sparkle-icon {
  color: #ffffff;
  filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.25));
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.rec-floating-orb:hover .ai-sparkle-icon {
  transform: rotate(15deg) scale(1.12);
}

.orb-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  background: #ef4444;
  color: #ffffff;
  font-size: 9.5px;
  font-weight: 800;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid #ffffff;
}

@keyframes orbLoadingPulse {
  0%, 100% { transform: scale(1); box-shadow: 0 0 10px rgba(59, 130, 246, 0.4); }
  50% { transform: scale(1.08); box-shadow: 0 0 20px rgba(59, 130, 246, 0.85); }
}

@keyframes orbSuccessGlow {
  0%, 100% { box-shadow: 0 0 12px rgba(16, 185, 129, 0.5), inset 0 2px 4px rgba(255, 255, 255, 0.5); }
  50% { box-shadow: 0 0 22px rgba(16, 185, 129, 0.85), inset 0 2px 4px rgba(255, 255, 255, 0.75); }
}
</style>
