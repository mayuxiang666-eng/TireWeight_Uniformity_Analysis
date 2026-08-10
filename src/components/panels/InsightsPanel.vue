<template>
  <div class="insights-panel">
    <div v-if="loading" class="insights-loading">
      <div v-for="i in 4" :key="i" class="skeleton alert-skeleton" />
    </div>
    <div v-else class="alerts-grid">
      <div
        v-for="(alert, idx) in computedAlerts"
        :key="idx"
        :class="['alert-card', alert.level, { 'is-clickable': isAlertClickable(alert) }]"
        @click="isAlertClickable(alert) && openDetail(alert)"
      >
        <div class="alert-icon-wrap">
          <div class="icon-circle">
            <el-icon size="18">
              <WarningFilled v-if="alert.level === 'high' || alert.level === 'medium'" />
              <Checked v-else />
            </el-icon>
          </div>
        </div>
        <div class="alert-content">
          <h4 class="alert-title">{{ alert.title }}</h4>
          <div class="alert-detail-wrapper">
            <div class="alert-detail" @click="handleHtmlClick($event, alert)" v-html="formatDetail(alert.detail, alert.level, false)"></div>
          </div>
        </div>
        <div class="alert-zoom-btn" v-if="isAlertClickable(alert)">
          <el-icon size="14"><ZoomIn /></el-icon>
        </div>
      </div>
    </div>

    <!-- 详情放大对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="activeAlert ? activeAlert.title + ' - 详细分析报告' : '详细分析报告'"
      width="720px"
      destroy-on-close
      align-center
      class="alert-detail-dialog"
    >
      <div v-if="activeAlert" :class="['dialog-alert-content', activeAlert.level]">
        <div class="dialog-icon-header">
          <div class="dialog-icon-circle">
            <el-icon size="28">
              <WarningFilled v-if="activeAlert.level === 'high' || activeAlert.level === 'medium'" />
              <Checked v-else />
            </el-icon>
          </div>
          <div class="dialog-status-title">
            <span class="dialog-title-text">{{ activeAlert.title }}</span>
            <span :class="['dialog-status-badge', activeAlert.level]">
              {{ activeAlert.level === 'high' || activeAlert.level === 'medium' ? '异常警告' : '状态正常' }}
            </span>
          </div>
        </div>

        <div class="dialog-details-list">
          <div 
            v-for="(item, idx) in parseAlertDetail(activeAlert)" 
            :key="idx"
            class="dialog-detail-item-new"
          >
            <!-- 整体文本渲染（如整体分析报告） -->
            <div v-if="item.type === 'text'" class="text-alert-item" v-html="formatDetail(item.content, activeAlert.level, true)">
            </div>
            
            <!-- 规格缺陷渲染 -->
            <div v-else-if="item.type === 'article'" class="article-alert-item">
              <div class="spec-header-row">
                <span class="verdict-label red-verdict" style="font-size: 12px; padding: 4px 10px; border-radius: 6px;">规格本身工艺缺陷</span>
              </div>
              <div class="spec-badges-grid" style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px;">
                <span class="spec-title-badge is-interactive" v-for="spec in item.specs" :key="spec" @click="selectSpec(spec)">{{ spec }}</span>
              </div>
              <div class="article-body-desc" style="background-color: rgba(239, 68, 68, 0.015); border-left: 3px solid #fca5a5; padding: 10px 14px; border-radius: 0 6px 6px 0; font-size: 13px; color: #475569; line-height: 1.6;">
                {{ item.message }}
              </div>
            </div>

            <!-- 机台异常网格渲染 (A 方案仪表盘) -->
            <div v-else-if="item.type === 'machine'" class="machine-alert-item">
              <div class="spec-header-row">
                <span class="spec-title-badge is-interactive" @click="selectSpec(item.spec)">{{ item.spec }}</span>
                <span class="verdict-label red-verdict">工序机台异常富集</span>
              </div>
              <div class="heatmap-grid">
                <div 
                  v-for="(m, mIdx) in item.items" 
                  :key="mIdx"
                  :class="['heatmap-card', 'is-interactive', getLiftClass(m.liftVal)]"
                  @click="handleMachineClick(item.spec, m)"
                >
                  <div class="card-wc">{{ m.workcenter }}</div>
                  <div class="card-mach">{{ m.machine }}</div>
                  <div class="card-lift-badge">
                    <span class="lift-label">提升度</span>
                    <span class="lift-value">{{ m.liftStr }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 物料异常网格渲染 (A 方案仪表盘) -->
            <div v-else-if="item.type === 'material'" class="material-alert-item">
              <div class="spec-header-row">
                <span class="spec-title-badge is-interactive" @click="selectSpec(item.spec)">{{ item.spec }}</span>
                <span class="verdict-label red-verdict">物料批次异常警告</span>
              </div>
              <div class="material-groups-container">
                <div 
                  v-for="(g, gIdx) in item.groups" 
                  :key="gIdx" 
                  class="mach-group-box is-interactive-box"
                  @click="handleMaterialClick(item.spec, g.machineLabel)"
                >
                  <div class="mach-group-title">
                    <el-icon size="14"><Monitor /></el-icon>
                    <span>加工机台：<strong class="group-mach-name">{{ g.machineLabel }}</strong></span>
                  </div>
                  <div class="heatmap-grid">
                    <div 
                      v-for="(lot, lIdx) in g.items" 
                      :key="lIdx"
                      :class="['heatmap-card', getLiftClass(lot.liftVal)]"
                    >
                      <div class="card-wc">异常批次</div>
                      <div class="card-mach lot-value-text" :title="lot.lotVal">{{ lot.lotVal }}</div>
                      <div class="card-lift-badge">
                        <span class="lift-label">局部提升</span>
                        <span class="lift-value">{{ lot.liftStr }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { WarningFilled, Checked, ZoomIn, Monitor } from '@element-plus/icons-vue'

const props = defineProps({
  alerts:  { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['selectArticle', 'selectMachine'])

const dialogVisible = ref(false)
const activeAlert = ref(null)

const defaultAlerts = [
  { category: 'overall', title: '生产期整体质量分析报告', level: 'info', detail: '暂无数据' },
  { category: 'article', title: '规格预警', level: 'info', detail: '未检测到异常规格' },
  { category: 'machine', title: '机台预警', level: 'info', detail: '未检测到异常机台' },
  { category: 'material', title: '物料预警', level: 'info', detail: '未检测到异常物料' },
]

const computedAlerts = computed(() => {
  const list = []
  const categories = ['overall', 'article', 'machine', 'material']
  for (const cat of categories) {
    const found = props.alerts.find(a => a.category === cat)
    if (found) {
      list.push(found)
    } else {
      list.push(defaultAlerts.find(d => d.category === cat))
    }
  }
  return list
})

function isAlertClickable(alert) {
  if (!alert || !alert.detail) return false
  const defaultDetails = ['暂无数据', '未检测到异常规格', '未检测到异常机台', '未检测到异常物料']
  return !defaultDetails.includes(alert.detail)
}

function openDetail(alert) {
  activeAlert.value = alert
  dialogVisible.value = true
}

function handleHtmlClick(e, alert) {
  const specTag = e.target.closest('.inline-spec-tag')
  if (specTag) {
    e.stopPropagation()
    const specText = specTag.textContent.replace(/[\[\]]/g, '').trim()
    emit('selectArticle', specText)
  }
}

function selectSpec(specText) {
  const cleanSpec = specText.replace(/[\[\]]/g, '').trim()
  emit('selectArticle', cleanSpec)
  dialogVisible.value = false
}

function handleMachineClick(spec, m) {
  const cleanSpec = spec.replace(/[\[\]]/g, '').trim()
  const wc = m.workcenter.toLowerCase() + '_workcenter'
  emit('selectMachine', {
    machine: m.machine,
    workcenter_col: wc,
    article10: cleanSpec
  })
  dialogVisible.value = false
}

function handleMaterialClick(spec, machineLabel) {
  const cleanSpec = spec.replace(/[\[\]]/g, '').trim()
  const parts = machineLabel.split(':')
  if (parts.length === 2) {
    const wc = parts[0].trim().toLowerCase() + '_workcenter'
    const mach = parts[1].trim()
    emit('selectMachine', {
      machine: mach,
      workcenter_col: wc,
      article10: cleanSpec
    })
    dialogVisible.value = false
  }
}

/**
 * 获取基于提升度的卡片颜色类别
 */
function getLiftClass(liftVal) {
  if (liftVal >= 2.0) return 'lift-critical'
  if (liftVal >= 1.5) return 'lift-warning'
  if (liftVal >= 1.0) return 'lift-attention'
  return 'lift-normal'
}

/**
 * 状态化解析预警详情文本为结构化数据结构 (方案 A)
 */
function parseAlertDetail(alert) {
  if (!alert || !alert.detail) return []
  const category = alert.category
  const detail = alert.detail

  if (category === 'overall') {
    return [{ type: 'text', content: detail }]
  }

  if (category === 'article') {
    const specs = detail.match(/\[[^\]]+\]/g) || []
    return [{
      type: 'article',
      specs,
      message: '该核心规格在研究期内异常贡献度或异常率过高，判定为规格本身设计/配方漂移，非外部机台或批次所致。'
    }]
  }

  // 针对机台预警和物料预警，按全角分号分割
  const lines = detail.split('；').map(s => s.trim()).filter(Boolean)
  const parsedSpecs = []
  let lastSpec = null

  for (const line of lines) {
    // 提取规格前缀
    const specMatch = line.match(/^(\[[^\]]+\])\s*[:：]?\s*/)
    let spec = lastSpec
    let rest = line
    if (specMatch) {
      spec = specMatch[1]
      rest = line.substring(specMatch[0].length).trim()
      lastSpec = spec
    }

    if (!spec) {
      parsedSpecs.push({ type: 'text', content: line })
      continue
    }

    if (category === 'machine') {
      // 格式: "CT:CUL02(2.37x), FIRST_PLY:CX103(1.0x)"
      const items = []
      const parts = rest.split(',').map(s => s.trim()).filter(Boolean)
      for (const part of parts) {
        const colonIndex = part.indexOf(':')
        if (colonIndex === -1) continue
        const workcenter = part.substring(0, colonIndex).trim()
        const machineAndLift = part.substring(colonIndex + 1).trim()

        const liftMatch = machineAndLift.match(/\(([^)]+)\)/)
        let machine = machineAndLift
        let liftStr = '1.0x'
        let liftVal = 1.0
        if (liftMatch) {
          liftStr = liftMatch[1].trim()
          liftVal = parseFloat(liftStr) || 1.0
          machine = machineAndLift.substring(0, liftMatch.index).trim()
        }
        items.push({ workcenter, machine, liftStr, liftVal })
      }

      // 合并到已有的同一个规格项中
      const existing = parsedSpecs.find(p => p.spec === spec && p.type === 'machine')
      if (existing) {
        existing.items.push(...items)
      } else {
        parsedSpecs.push({ type: 'machine', spec, items })
      }

    } else if (category === 'material') {
      // 格式: "在机台 SIDEWALL:EX 108 上 批次 992(1.40x), 批次 992(1.47x)"
      const machMatch = rest.match(/在机台\s+([^上]+?)\s+上/)
      let machineLabel = '未知机台'
      let lotRest = rest
      if (machMatch) {
        machineLabel = machMatch[1].trim()
        lotRest = rest.substring(machMatch[0].length).trim()
      }

      const lotParts = lotRest.split(',').map(s => s.trim()).filter(Boolean)
      const items = []
      for (const lotPart of lotParts) {
        const liftMatch = lotPart.match(/\(([^)]+)\)/)
        let lotVal = lotPart
        let liftStr = '1.0x'
        let liftVal = 1.0
        if (liftMatch) {
          liftStr = liftMatch[1].trim()
          liftVal = parseFloat(liftStr) || 1.0
          lotVal = lotPart.substring(0, liftMatch.index).trim()
        }
        // 清理前缀“批次”字样
        lotVal = lotVal.replace(/^批次\s*/, '').trim()
        items.push({ lotVal, liftStr, liftVal })
      }

      const existing = parsedSpecs.find(p => p.spec === spec && p.type === 'material')
      if (existing) {
        const machGroup = existing.groups.find(g => g.machineLabel === machineLabel)
        if (machGroup) {
          machGroup.items.push(...items)
        } else {
          existing.groups.push({ machineLabel, items })
        }
      } else {
        parsedSpecs.push({
          type: 'material',
          spec,
          groups: [{ machineLabel, items }]
        })
      }
    }
  }

  return parsedSpecs
}

/**
 * 格式化外层预览描述的 HTML
 */
function formatDetail(detail, level, isInDialog) {
  if (!detail) return ''
  
  let formatted = detail

  // 1. 规格格式化 [0315508000]
  const isHigh = level === 'high' || level === 'medium'
  const specClass = isHigh ? 'spec-badge-high' : 'spec-badge-normal'
  formatted = formatted.replace(/(\[[^\]]+\])/g, `<span class="inline-spec-tag ${specClass}">$1</span>`)

  // 2. 工段与机台号显著隔离格式化
  // 匹配 WORKCENTER:MACHINE (例如 CT:CUL02, FIRST_PLY:CX 103 等)
  const machineWcRegex = /\b([A-Z_]+(?:\s+\d+)?)\s*:\s*([A-Z0-9\s-]+)\b/g
  formatted = formatted.replace(machineWcRegex, 
    '<span class="inline-wc-tag">$1</span><span class="inline-mach-separator">:</span><span class="inline-mach-tag">$2</span>'
  )

  // 3. 提升度格式化 (数字 + x)
  const liftRegex = /(\d+(?:\.\d+)?\s*x)/g
  formatted = formatted.replace(liftRegex, '<strong class="highlight-lift">$1</strong>')

  // 4. 百分比、天数、排产条数
  const numRegex = /(\d{1,3}(?:,\d{3})*(?:\.\d+)?%|\d+\s*天|\d{1,3}(?:,\d{3})+(?=\s*条))/g
  formatted = formatted.replace(numRegex, '<strong class="highlight-num">$1</strong>')

  return formatted
}
</script>

<style scoped>
.insights-panel {
  width: 100%;
}

.insights-loading {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-skeleton {
  height: 120px;
  border-radius: 12px;
}

.alerts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}

.alert-card {
  display: flex;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid transparent;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
  height: 120px; /* 固定卡片高度，保持统一 */
  position: relative;
  box-sizing: border-box;
  background-color: #fff;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 可点击卡片悬浮样式 */
.alert-card.is-clickable {
  cursor: pointer;
}
.alert-card.is-clickable:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}

/* 放大图标 styles */
.alert-zoom-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  color: #9ca3af;
  opacity: 0;
  transition: opacity 0.2s, color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.03);
  padding: 4px;
  border-radius: 50%;
}
.alert-card:hover .alert-zoom-btn {
  opacity: 1;
}
.alert-zoom-btn:hover {
  color: #111827;
  background-color: rgba(0, 0, 0, 0.08);
}

/* 图标容器圆形化 */
.icon-circle {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.3s;
}

/* 高风险 alert 🔴 */
.alert-card.high, .alert-card.medium {
  border-left: 5px solid #ef4444;
  border-top-color: #fee2e2;
  border-right-color: #fee2e2;
  border-bottom-color: #fee2e2;
  background-color: #fffafb;
}
.alert-card.high .icon-circle, .alert-card.medium .icon-circle {
  background-color: #fee2e2;
  color: #ef4444;
}
.alert-card.high .alert-title, .alert-card.medium .alert-title {
  color: #991b1b;
}
.alert-card.is-clickable.high:hover, .alert-card.is-clickable.medium:hover {
  border-color: #fca5a5;
  border-left-color: #dc2626;
  background-color: #fff5f6;
}

/* 一般消息/正常 alert 🟢 */
.alert-card.info, .alert-card.success {
  border-left: 5px solid #10b981;
  border-top-color: #e6fcf5;
  border-right-color: #e6fcf5;
  border-bottom-color: #e6fcf5;
  background-color: #fafdfc;
}
.alert-card.info .icon-circle, .alert-card.success .icon-circle {
  background-color: #d1fae5;
  color: #10b981;
}
.alert-card.info .alert-title, .alert-card.success .alert-title {
  color: #065f46;
}
.alert-card.is-clickable.info:hover, .alert-card.is-clickable.success:hover {
  border-color: #a7f3d0;
  border-left-color: #059669;
  background-color: #f0fdf4;
}

.alert-icon-wrap {
  display: flex;
  align-items: flex-start;
}

.alert-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 0;
  height: 100%;
}

.alert-title {
  margin: 0;
  font-size: 14.5px;
  font-weight: 700;
  line-height: 1.2;
}

/* 卡片内容滚动区域 */
.alert-detail-wrapper {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
  margin-bottom: 2px;
}

/* 自定义细滚动条 */
.alert-detail-wrapper::-webkit-scrollbar {
  width: 4px;
}
.alert-detail-wrapper::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.08);
  border-radius: 2px;
}
.alert-detail-wrapper::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.18);
}

.alert-detail {
  margin: 0;
  font-size: 12.5px;
  color: #4b5563;
  line-height: 1.6;
}

/* 规格内联样式 */
:deep(.inline-spec-tag) {
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11.5px;
  display: inline-block;
  margin: 1px 3px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}
:deep(.inline-spec-tag:hover) {
  transform: scale(1.05);
  filter: brightness(0.92);
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
:deep(.inline-spec-tag.spec-badge-high) {
  background-color: #fee2e2;
  color: #b91c1c;
  border-color: #fecaca;
}
:deep(.inline-spec-tag.spec-badge-normal) {
  background-color: #e0f2fe;
  color: #0369a1;
  border-color: #bae6fd;
}

/* ── 强调工段 vs 机台的卡片内样式 ── */
:deep(.inline-wc-tag) {
  font-weight: 600;
  background-color: #e0e7ff;
  color: #4338ca;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 10px;
  display: inline-block;
  margin: 1px 2px;
  text-transform: uppercase;
}
:deep(.inline-mach-separator) {
  color: #9ca3af;
  font-weight: 600;
  margin: 0 1px;
}
:deep(.inline-mach-tag) {
  font-family: 'JetBrains Mono', monospace;
  background-color: #f3f4f6;
  color: #1f2937;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid #d1d5db;
  display: inline-block;
  margin: 1px 2px;
}

/* 提升度值 */
:deep(.highlight-lift) {
  color: #ef4444;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}

/* 常规数字高亮 */
:deep(.highlight-num) {
  font-weight: 700;
  color: #111827;
}

/* ── Dialog Details Style ── */
.dialog-alert-content {
  padding: 5px 0;
}
.dialog-icon-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 16px;
}

.dialog-icon-circle {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-alert-content.high .dialog-icon-circle,
.dialog-alert-content.medium .dialog-icon-circle {
  background-color: #fef2f2;
  color: #ef4444;
  border: 1px solid #fee2e2;
}
.dialog-alert-content.info .dialog-icon-circle,
.dialog-alert-content.success .dialog-icon-circle {
  background-color: #f0fdf4;
  color: #10b981;
  border: 1px solid #dcfce7;
}

.dialog-status-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dialog-title-text {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
}
.dialog-status-badge {
  display: inline-block;
  align-self: flex-start;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 9999px;
}
.dialog-status-badge.high, .dialog-status-badge.medium {
  background-color: #fee2e2;
  color: #dc2626;
}
.dialog-status-badge.info, .dialog-status-badge.success {
  background-color: #d1fae5;
  color: #065f46;
}

.dialog-details-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 480px;
  overflow-y: auto;
  padding-right: 6px;
}
.dialog-details-list::-webkit-scrollbar {
  width: 5px;
}
.dialog-details-list::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 3px;
}

.dialog-detail-item-new {
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  padding: 18px;
  background-color: #f8fafc;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.dialog-alert-content.high .dialog-detail-item-new,
.dialog-alert-content.medium .dialog-detail-item-new {
  background-color: #fffbfa;
  border-color: #fee2e2;
}

/* 规格与缺陷标题行 */
.spec-header-row, .article-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  border-bottom: 1px dashed #f1f5f9;
  padding-bottom: 8px;
}

.spec-title-badge {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 13px;
  color: #b91c1c;
  background-color: #fee2e2;
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid #fca5a5;
}

.verdict-label {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}
.red-verdict {
  background-color: #fecaca;
  color: #991b1b;
}

/* 方案 A: 仪表盘热力网格布局 */
.heatmap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.heatmap-card {
  border-radius: 8px;
  padding: 10px 12px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid transparent;
  transition: transform 0.2s;
}
.heatmap-card:hover {
  transform: translateY(-2px);
}

.card-wc {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  color: #64748b;
}

.card-mach {
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 800;
  color: #1e293b;
  word-break: break-all;
}

.lot-value-text {
  font-size: 11.5px;
  min-height: 18px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-lift-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed rgba(0, 0, 0, 0.05);
}

.lift-label {
  font-size: 8.5px;
  color: #64748b;
  transform: scale(0.9);
}

.lift-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
  font-weight: 700;
}

/* 热力严重程度级别样式 (A方案颜色标尺) */
/* 严重级 🔴 */
.heatmap-card.lift-critical {
  background-color: #fef2f2;
  border-color: #fca5a5;
}
.heatmap-card.lift-critical .card-mach {
  color: #991b1b;
}
.heatmap-card.lift-critical .lift-value {
  color: #ef4444;
}

/* 警告级 🟠 */
.heatmap-card.lift-warning {
  background-color: #fff7ed;
  border-color: #ffedd5;
}
.heatmap-card.lift-warning .card-mach {
  color: #c2410c;
}
.heatmap-card.lift-warning .lift-value {
  color: #f97316;
}

/* 关注级 🟡 */
.heatmap-card.lift-attention {
  background-color: #fefce8;
  border-color: #fef08a;
}
.heatmap-card.lift-attention .card-mach {
  color: #854d0e;
}
.heatmap-card.lift-attention .lift-value {
  color: #ca8a04;
}

/* 正常级 🟢 */
.heatmap-card.lift-normal {
  background-color: #f0fdf4;
  border-color: #bbf7d0;
}
.heatmap-card.lift-normal .card-mach {
  color: #166534;
}
.heatmap-card.lift-normal .lift-value {
  color: #10b981;
}

/* 物料群组箱 */
.material-groups-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mach-group-box {
  background-color: rgba(0, 0, 0, 0.015);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
}

.mach-group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #475569;
  font-weight: 500;
  margin-bottom: 8px;
}

.group-mach-name {
  font-family: 'JetBrains Mono', monospace;
  color: #0f172a;
}

.article-body-desc {
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
}

.is-interactive {
  cursor: pointer;
  transition: all 0.2s ease;
}
.is-interactive:hover {
  transform: translateY(-2px);
  filter: brightness(0.95);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
}
.is-interactive-box {
  cursor: pointer;
  transition: all 0.2s ease;
}
.is-interactive-box:hover {
  border-color: #cbd5e1;
  background-color: rgba(0, 0, 0, 0.03);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);
}
.spec-title-badge.is-interactive:hover {
  background-color: #fca5a5;
  border-color: #ef4444;
  color: #7f1d1d;
}
</style>
