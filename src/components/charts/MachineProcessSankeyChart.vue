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
      <el-empty :description="sankeyEmptyDescription" :image-size="60" />
    </div>
    <template v-else>
      <div style="display: flex; flex-direction: column; height: 100%;">
        <div class="path-notice" style="flex-shrink: 0; margin-bottom: 6px; font-size: 12px; background: #fff7ed; padding: 6px 12px; border-radius: 4px; border: 1px solid #ffedd5; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div style="display: flex; gap: 14px; align-items: center; flex-wrap: wrap;">
            <span style="font-weight: 600; color: #475569;">灰色节点：正常流转机台</span>
            <span style="font-weight: 600; color: #dc2626; display: inline-flex; align-items: center; gap: 4px;">
              红色发光节点：全局核心负贡献报警机台（依据全局影响度判定：影响度 = 贡献度 × 产量平方根平滑占比，负向绝对值越大拉低越严重）
              <el-tooltip placement="top" raw-content>
                <template #content>
                  <div style="max-width: 330px; font-size: 12px; line-height: 1.6; padding: 4px;">
                    <strong style="color: #ef4444;">全局核心负贡献机台判定机理：</strong><br/>
                    1. <strong>对照基准设定</strong>：控制上下游其他工序机台不变，提取流经该工序其他机台的替代路径综合 CPK 作为对照基准；<br/>
                    2. <strong>机台独立偏离</strong>：<code>贡献度 = 机台实际CPK - 替代对照基准CPK</code>；<br/>
                    3. <strong>全局影响度</strong>：<code>全局影响度 = 贡献度 × 产量平方根平滑占比 (sqrt(N)/sum(sqrt(N)))</code>；<br/>
                    4. <strong>预警判定</strong>：影响度为负且绝对值最大的机台即为全场拉低质量的核心瓶颈设备，系统自动触发红色发光投影高亮。
                  </div>
                </template>
                <el-icon style="cursor: pointer; color: #dc2626; font-size: 13px;"><QuestionFilled /></el-icon>
              </el-tooltip>
            </span>
          </div>
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
      title="生产工序流转桑基图 - 放大全屏分析"
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
  article:    { type: String, default: '' }
})

const emit = defineEmits(['open-cgrs'])

const dialogVisible = ref(false)

const sankeyEmptyDescription = computed(() => {
  if (props.sankeyData && props.sankeyData.empty_message) {
    return props.sankeyData.empty_message
  }
  return '当前规格无工序流转路径数据'
})

const sankeyPrefixToCol = {
  "胎面": "tread_workcenter",
  "胎侧": "sidewall_workcenter",
  "内衬": "inner_liner_workcenter",
  "胎圈": "bead_workcenter",
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
    
    // 成型工段 (GT) 或 硫化工段 (CT) 触发 CGRS 弹窗
    if (
      prefix.includes('成型') || prefix.includes('GT') || prefix.includes('硫化') || prefix.includes('CT') ||
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

  function getNodeColor(prefix, cpk) {
    if (prefixMachineCounts[prefix] === 1) {
      return '#cbd5e1'
    }

    const baseHues = {
      "胎面": 217,
      "胎侧": 190,
      "内衬": 174,
      "胎圈": 45,
      "帘布层1": 262,
      "带束层1": 239,
      "带束层2": 205,
      "冠带层1": 280,
      "冠带层2": 220,
      "生胎成型GT": 250,
      "硫化CT": 35,
      "终检TU": 228,
      "动平衡TB": 30
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

    const s = 85
    const l = Math.round(80 - ratio * 35)
    return `hsl(${h}, ${s}%, ${l}%)`
  }

  const nodes = props.sankeyData.nodes.map(n => {
    const prefix = n.name.split("_")[0]
    const adjustedDepth = (prefix === '动平衡TB') ? n.depth + 1 : n.depth
    const nodeColor = n.is_warning_machine ? '#ef4444' : '#94a3b8'
    
    const itemStyle = {
      color: nodeColor,
      borderColor: nodeColor,
      borderWidth: 0
    }

    if (n.is_warning_machine) {
      itemStyle.shadowColor = 'rgba(239, 68, 68, 0.95)'
      itemStyle.shadowBlur = 14
      itemStyle.shadowOffsetX = 0
      itemStyle.shadowOffsetY = 0
    }

    return {
      name: n.name,
      depth: adjustedDepth,
      is_warning_machine: n.is_warning_machine,
      spec_cpk: n.spec_cpk,
      spec_std: n.spec_std,
      spec_ratio: n.spec_ratio,
      spec_avg: n.spec_avg,
      cgrs_comparison: n.cgrs_comparison,
      itemStyle: itemStyle
    }
  })

  const sortedNodes = [...nodes].sort((a, b) => {
    if (a.depth !== b.depth) return a.depth - b.depth
    
    const wcOrder = {
      "胎面": 1, "胎侧": 2, "内衬": 3, "胎圈": 4,
      "带束层1": 1, "带束层2": 2, "帘布层1": 3, "冠带层1": 4, "冠带层2": 5,
      "生胎成型GT": 1,
      "硫化CT": 1,
      "终检TU": 1,
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
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      extraCssText: 'box-shadow: 0 6px 16px rgba(0,0,0,0.1); border-radius: 8px; max-width: 380px;',
      formatter(params) {
        if (params.dataType === 'node') {
          const cpk = params.data.spec_cpk
          const std = params.data.spec_std
          const avg = params.data.spec_avg
          const cgrs = params.data.cgrs_comparison
          const warnText = params.data.is_warning_machine ? ' <span style="color:#ef4444;font-weight:bold;margin-left:6px;">[全局核心负贡献]</span>' : ''
          
          let cgrsHtml = ''
          if (cgrs && cgrs.has_cgrs) {
            const evList = cgrs.events_summary || []
            let evItemsHtml = ''
            if (evList.length > 0) {
              evItemsHtml = evList.map(ev => {
                const timeOnly = ev.time_str ? (ev.time_str.split(' ')[1] || ev.time_str) : ''
                if (ev.is_disabled || ev.valid_paths_count === 0) {
                  return `
                    <div style="background: #f8fafc; border-radius: 5px; padding: 6px 8px; margin-bottom: 5px; border: 1px solid #e2e8f0; opacity: 0.85;">
                      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; margin-bottom: 3px;">
                        <span style="font-weight: 700; color: #64748b;">第 ${ev.event_num} 次修改 <span style="font-weight: normal; color: #94a3b8; font-size: 10px;">(${timeOnly})</span></span>
                        <span style="font-weight: 600; color: #94a3b8; font-size: 10px;">无有效对比路径</span>
                      </div>
                      <div style="color: #94a3b8; font-size: 10.5px; margin-bottom: 3px;">
                        变更参数: <span style="color:#64748b;">${ev.params}</span>
                      </div>
                      <div style="color: #94a3b8; font-size: 10px; background: #f1f5f9; padding: 3px 6px; border-radius: 4px; text-align: center;">
                        单侧样本 &lt; 5 胎 或 路径样本差 &gt; 2.5 倍
                      </div>
                    </div>
                  `
                }
                const isPos = (ev.yoy_pct || 0) >= 0
                const yoyColor = isPos ? '#059669' : '#dc2626'
                const yoySign = isPos ? '+' : ''
                return `
                  <div style="background: #ffffff; border-radius: 5px; padding: 6px 8px; margin-bottom: 5px; border: 1px solid #fed7aa;">
                    <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; margin-bottom: 3px;">
                      <span style="font-weight: 700; color: #78350f;">第 ${ev.event_num} 次修改 <span style="font-weight: normal; color: #94a3b8; font-size: 10px;">(${timeOnly})</span></span>
                      <span style="font-weight: 700; color: ${yoyColor};">CPK 增幅: ${yoySign}${Number(ev.yoy_pct || 0).toFixed(2)}%</span>
                    </div>
                    <div style="color: #475569; font-size: 10.5px; margin-bottom: 3px;">
                      变更参数: <span style="color:#0369a1; font-weight: 600;">${ev.params}</span>
                    </div>
                    <div style="display: flex; align-items: center; justify-content: space-between; color: #334155; font-size: 10.5px; background: #f8fafc; padding: 3px 6px; border-radius: 4px;">
                      <span>改前 CPK: <strong>${ev.cpk_before}</strong> (N=${ev.n_before})</span>
                      <span style="color:#f59e0b; font-weight: bold;">➔</span>
                      <span>改后 CPK: <strong>${ev.cpk_after}</strong> (N=${ev.n_after})</span>
                    </div>
                  </div>
                `
              }).join('')
            } else {
              const isPos = cgrs.latest_yoy_pct >= 0
              const yoyColor = isPos ? '#059669' : '#dc2626'
              const yoySign = isPos ? '+' : ''
              const paramListStr = (cgrs.latest_params && cgrs.latest_params.length > 0) ? cgrs.latest_params.slice(0, 3).join(', ') + (cgrs.latest_params.length > 3 ? '...' : '') : '参数调整'
              evItemsHtml = `
                <div style="background: #ffffff; border-radius: 5px; padding: 6px 8px; margin-bottom: 5px; border: 1px solid #fed7aa;">
                  <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; margin-bottom: 3px;">
                    <span style="font-weight: 700; color: #78350f;">最新修改 (${cgrs.latest_event_time})</span>
                    <span style="font-weight: 700; color: ${yoyColor};">CPK 增幅: ${yoySign}${cgrs.latest_yoy_pct.toFixed(2)}%</span>
                  </div>
                  <div style="color: #475569; font-size: 10.5px; margin-bottom: 3px;">
                    变更参数: <span style="color:#0369a1; font-weight: 600;">${paramListStr}</span>
                  </div>
                  <div style="display: flex; align-items: center; justify-content: space-between; color: #334155; font-size: 10.5px; background: #f8fafc; padding: 3px 6px; border-radius: 4px;">
                    <span>改前 CPK: <strong>${cgrs.latest_cpk_before}</strong> (N=${cgrs.latest_n_before})</span>
                    <span style="color:#f59e0b; font-weight: bold;">➔</span>
                    <span>改后 CPK: <strong>${cgrs.latest_cpk_after}</strong> (N=${cgrs.latest_n_after})</span>
                  </div>
                </div>
              `
            }

            cgrsHtml = `
              <div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed #cbd5e1;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                  <span style="font-weight: 700; color: #b45309; font-size: 11.5px; display: inline-flex; align-items: center; gap: 3px;">
                    ⚙️ CGRS 调参前后对比
                  </span>
                  <span style="font-size: 10.5px; color: #64748b;">当天共 ${cgrs.events_count || 1} 次调参</span>
                </div>
                <div style="background: #fffbeb; border-radius: 6px; padding: 6px 8px; border: 1px solid #fef3c7;">
                  ${evItemsHtml}
                </div>
              </div>
            `
          }

          if (props.indicator === 'weight') {
            const avgPct = params.data.spec_ratio ?? cpk
            const meanVal = avg
            const avgPctStr = avgPct !== undefined && avgPct !== null ? (avgPct > 0 ? '+' : '') + avgPct.toFixed(2) + '%' : '暂无数据'
            const stdStr = std !== undefined && std !== null ? std.toFixed(2) + '%' : '暂无数据'
            const meanStr = meanVal !== undefined && meanVal !== null ? (meanVal > 0 ? '+' : '') + meanVal.toFixed(3) + ' kg' : '暂无数据'
            return `
              <div style="font-weight:bold;font-size:13px;margin-bottom:6px;color:#1e293b;border-bottom:1px solid #f1f5f9;padding-bottom:4px;">${params.name}${warnText}</div>
              <div style="display:flex;flex-direction:column;gap:3px;font-size:12px;color:#475569;">
                <div>偏差率: <strong style="color:#2563eb;">${avgPctStr}</strong></div>
                <div>标准差 (σ): <strong style="color:#10b981;">${stdStr}</strong></div>
                <div>物理均值差: <strong style="color:#0f172a;">${meanStr}</strong></div>
              </div>
              ${cgrsHtml}
            `
          }
          const cpkStr = (cpk !== undefined && cpk !== null) ? cpk.toFixed(2) : '暂无数据'
          const stdStr = (std !== undefined && std !== null) ? std.toFixed(2) : '暂无数据'
          const avgStr = (avg !== undefined && avg !== null) ? avg.toFixed(2) : '暂无数据'
          return `
            <div style="font-weight:bold;font-size:13px;margin-bottom:6px;color:#1e293b;border-bottom:1px solid #f1f5f9;padding-bottom:4px;">${params.name}${warnText}</div>
            <div style="display:flex;flex-direction:column;gap:3px;font-size:12px;color:#475569;">
              <div>单规格 CPK: <strong style="color:#2563eb;">${cpkStr}</strong></div>
              <div>标准差 (σ): <strong style="color:#10b981;">${stdStr}</strong></div>
              <div>均值 (μ): <strong style="color:#0f172a;">${avgStr}</strong></div>
            </div>
            ${cgrsHtml}
          `
        } else if (params.dataType === 'edge') {
          const l = params.data
          if (props.indicator === 'weight') {
            const avgPct = l.avg_3sigma
            const meanVal = l.avg_diff_abs
            const avgPctStr = avgPct !== undefined && avgPct !== null ? (avgPct > 0 ? '+' : '') + avgPct.toFixed(2) + '%' : '暂无数据'
            const meanStr = meanVal !== undefined && meanVal !== null ? (meanVal > 0 ? '+' : '') + meanVal.toFixed(3) + ' kg' : '暂无数据'
            return `
              <div style="font-weight:bold;font-size:13px;margin-bottom:6px;color:#1e293b;border-bottom:1px solid #f1f5f9;padding-bottom:4px;">${l.source} ➔ ${l.target}</div>
              <div style="display:flex;flex-direction:column;gap:3px;font-size:12px;color:#475569;">
                <div>流转轮胎数 (N): <strong style="color:#2563eb;">${l.value}</strong></div>
                <div>流转偏差率: <strong style="color:#2563eb;">${avgPctStr}</strong></div>
                <div>物理均值差: <strong style="color:#10b981;">${meanStr}</strong></div>
              </div>
            `
          }
          return `
            <div style="font-weight:bold;font-size:13px;margin-bottom:6px;color:#1e293b;border-bottom:1px solid #f1f5f9;padding-bottom:4px;">${l.source} ➔ ${l.target}</div>
            <div style="font-size:12px;color:#475569;">流转轮胎条数 (N): <strong style="color:#2563eb;">${l.value}</strong></div>
          `
        }
      }
    },
    series: [
      {
        type: 'sankey',
        left: 10,
        top: 10,
        right: 140,
        bottom: 10,
        nodeGap: 24,
        nodeWidth: 16,
        layoutIterations: 0,
        data: sortedNodes,
        links: links,
        orient: 'horizontal',
        label: {
          fontSize: 10,
          color: '#334155',
          formatter(params) {
            const parts = params.name.split('_')
            const displayName = (parts.length > 1 ? parts[1] : params.name).toUpperCase()
            const cpk = params.data?.spec_cpk
            const std = params.data?.spec_std
            const avg = params.data?.spec_avg
            const cgrs = params.data?.cgrs_comparison

            let cgrsBadge = ''
            if (cgrs && cgrs.has_cgrs) {
              cgrsBadge = ` {cgrsNotice|⚙ 调参记录}`
            }

            let suffix = ''
            if (props.indicator === 'weight') {
              const avgPct = params.data?.spec_ratio ?? cpk
              if (avgPct !== undefined && avgPct !== null) {
                const sign = avgPct > 0 ? '+' : ''
                const meanText = (avg !== undefined && avg !== null) ? ` μ: ${(avg > 0 ? '+' : '')}${avg.toFixed(2)}` : ''
                const stdText = (std !== undefined && std !== null) ? ` σ: ${std.toFixed(2)}` : ''
                suffix = `  {info|[ 偏离: ${sign}${avgPct.toFixed(2)}%${meanText}${stdText} ]}`
              }
            } else {
              if (cpk !== undefined && cpk !== null) {
                const avgText = (avg !== undefined && avg !== null) ? ` μ: ${avg.toFixed(2)}` : ''
                const stdText = (std !== undefined && std !== null) ? ` σ: ${std.toFixed(2)}` : ''
                suffix = `  {info|[ CPK: ${cpk.toFixed(2)}${avgText}${stdText} ]}`
              } else if (avg !== undefined && avg !== null) {
                const stdText = (std !== undefined && std !== null) ? ` σ: ${std.toFixed(2)}` : ''
                suffix = `  {info|[ μ: ${avg.toFixed(2)}${stdText} ]}`
              }
            }
            return `{mach|${displayName}}${cgrsBadge}${suffix}`
          },
          rich: {
            mach: {
              fontWeight: '900',
              fontSize: 11,
              color: '#0f172a'
            },
            cgrsNotice: {
              fontWeight: '700',
              fontSize: 9.5,
              color: '#b45309',
              backgroundColor: '#fef3c7',
              borderColor: '#fde68a',
              borderWidth: 1,
              borderRadius: 3,
              padding: [1, 4]
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

const zoomedOption = computed(() => {
  const baseOpt = option.value
  if (!baseOpt || !baseOpt.series) return {}

  const deep = JSON.parse(JSON.stringify(baseOpt))
  const s = deep.series[0]
  s.left = 40
  s.right = 180
  s.top = 20
  s.bottom = 20
  s.nodeGap = 36
  s.nodeWidth = 20
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
