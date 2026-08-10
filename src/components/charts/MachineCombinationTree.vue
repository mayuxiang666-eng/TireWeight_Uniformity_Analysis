<template>
  <div class="combination-tree-container" style="width: 100%; height: 100%; display: flex; flex-direction: column; overflow: hidden; position: relative;">
    <!-- 头部参数筛选栏 -->
    <div v-show="!isAllControlsHidden" class="filter-bar" style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; padding: 10px; background: var(--el-fill-color-light); border-radius: 6px; flex-wrap: wrap;">
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <!-- 根节点 Level 1 -->
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 12px; color: var(--el-text-color-regular); font-weight: 500;">根节点 (L1):</span>
          <el-select v-model="level1" placeholder="选择根节点" size="small" style="width: 140px;" clearable @change="handleLevel1Change">
            <el-option
              v-for="item in level1Options"
              :key="item.value"
              :label="item.label"
              :value="item.value"
              :disabled="item.disabled"
            />
          </el-select>
        </div>

        <!-- 中间层 Level 2 -->
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 12px; color: var(--el-text-color-regular); font-weight: 500;">中间层 (L2):</span>
          <el-select v-model="level2" placeholder="选择中间层" size="small" style="width: 140px;" clearable @change="handleLevel2Change">
            <el-option
              v-for="item in level2Options"
              :key="item.value"
              :label="item.label"
              :value="item.value"
              :disabled="item.disabled"
            />
          </el-select>
        </div>

        <!-- 子层 Level 3 -->
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 12px; color: var(--el-text-color-regular); font-weight: 500;">子层 (L3):</span>
          <el-select v-model="level3" placeholder="选择子层" size="small" style="width: 140px;" clearable @change="handleLevel3Change">
            <el-option
              v-for="item in level3Options"
              :key="item.value"
              :label="item.label"
              :value="item.value"
              :disabled="item.disabled"
            />
          </el-select>
        </div>

        <!-- 末端层 Level 4 -->
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 12px; color: var(--el-text-color-regular); font-weight: 500;">末端层 (L4):</span>
          <el-select v-model="level4" placeholder="选择末端层" size="small" style="width: 140px;" clearable @change="handleLevel4Change">
            <el-option
              v-for="item in level4Options"
              :key="item.value"
              :label="item.label"
              :value="item.value"
              :disabled="item.disabled"
            />
          </el-select>
        </div>

        <!-- 快速反转 -->
        <el-button type="primary" size="small" plain @click="invertHierarchy">
          🔄 快速反转
        </el-button>
        
        <!-- 查看近三天数据 Checkbox -->
        <el-checkbox
          v-model="showLastThreeDays"
          size="small"
          style="margin-left: 16px; font-weight: 600;"
          @change="handleShowLastThreeDaysChange"
        >
          📅 查看近三天数据 ({{ props.targetDate }})
        </el-checkbox>

        <!-- 全部隐藏按钮 -->
        <el-button
          type="warning"
          size="small"
          plain
          style="margin-left: 12px; font-weight: 600;"
          @click="isAllControlsHidden = true"
        >
          🙈 全部隐藏
        </el-button>
      </div>

      <!-- 说明信息 -->
      <div style="font-size: 11px; color: var(--el-text-color-secondary); display: flex; align-items: center; gap: 6px;">
        <span style="display:inline-block; width: 8px; height: 8px; background: #ef4444; border-radius: 50%;"></span> CPK &lt; 1.0 (异常)
        <span style="display:inline-block; width: 8px; height: 8px; background: #f97316; border-radius: 50%;"></span> CPK &lt; 1.33 (警示)
        <span style="display:inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%;"></span> CPK &ge; 1.33 (良好)
      </div>
    </div>

    <!-- 图表展示区 -->
    <div style="flex: 1; min-height: 0; position: relative; display: flex; flex-direction: column;">
      <!-- 全部隐藏模式下的恢复悬浮按钮 -->
      <div v-if="isAllControlsHidden" style="position: absolute; top: 12px; right: 16px; z-index: 99;">
        <el-button 
          type="primary" 
          size="small" 
          effect="dark"
          style="font-weight: bold; box-shadow: 0 2px 8px rgba(0,0,0,0.15);"
          @click="isAllControlsHidden = false"
        >
          👁️ 恢复显示控制面板
        </el-button>
      </div>

      <div v-if="loading" class="loading-overlay" style="height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column;">
        <el-icon class="is-loading" size="24"><Loading /></el-icon>
        <span style="margin-left: 8px; font-size: 13px; color: var(--el-text-color-regular); margin-top: 8px;">正在实时加载排列组合路径数据...</span>
      </div>
      
      <div v-else-if="error" class="error-overlay" style="height: 100%; display: flex; align-items: center; justify-content: center; color: var(--el-color-danger); font-size: 13px;">
        <span>{{ error }}</span>
      </div>

      <div v-else-if="!paths || paths.length === 0 || studyColumns.length === 0" class="empty-overlay" style="height: 100%; display: flex; align-items: center; justify-content: center;">
        <el-empty :description="studyColumns.length === 0 ? '请至少选择一个层级工段进行分析' : '当前日期范围及规格下暂无工序流转组合数据'" :image-size="60" />
      </div>

      <template v-else>
        <!-- 决策树信息提示 -->
        <div v-show="!isAllControlsHidden" style="font-size: 11px; background: var(--el-color-primary-light-9); padding: 6px 12px; border-radius: 4px; border: 1px solid var(--el-color-primary-light-8); color: var(--el-color-primary); margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
          <span>
            🌳 <strong>排列组合路径分析：</strong> 
            包含工段从左到右依次为: <strong>{{ studyColumnsFriendly }}</strong>
            <span v-if="sortedTableData.length > 10" style="margin-left: 12px; color: var(--el-text-color-secondary);">
              💡 <strong>提示:</strong> 路径较多，可在右侧图表中【上下滚动】查看完整树结构。
            </span>
          </span>
          <div>
            <span>
              📊 决策树叶子路径数: <strong>{{ sortedTableData.length }}</strong> | 
              总记录数: <strong>{{ totalLotsCount }}</strong>
            </span>
          </div>
        </div>

        <!-- 决策图及其悬浮卡片容器 -->
        <div style="flex: 1; min-height: 0; position: relative; display: flex; flex-direction: column;">
          
          <!-- 智能诊断悬浮卡片 (可收起，可拖拽) -->
          <div 
            v-if="globalAnalysis && !isAllControlsHidden" 
            :style="{ 
              position: 'absolute', 
              top: cardPos.top + 'px', 
              left: cardPos.left + 'px', 
              zIndex: 10, 
              width: '185px', 
              background: 'rgba(255, 255, 255, 0.96)', 
              backdropFilter: 'blur(4px)', 
              border: '1px solid var(--el-border-color-light)', 
              borderRadius: '6px', 
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)', 
              padding: '12px', 
              fontFamily: 'sans-serif',
              cursor: isDragging ? 'grabbing' : 'grab',
              userSelect: 'none'
            }"
            @mousedown="startDrag"
          >
            <div style="font-size: 12px; font-weight: 700; color: var(--el-text-color-primary); margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 6px;">
              <div style="display: flex; align-items: center; gap: 4px;">
                <span>机台贡献度</span>
                <el-tooltip placement="top" raw-content>
                  <template #content>
                    <div style="max-width: 320px; font-size: 12px; line-height: 1.6; padding: 4px;">
                      <strong>计算逻辑：</strong><br/>
                      通过控制变量法（消除其他工序机台的干扰），评估单个机台在相同工序搭配下，相比其他替代机台对 CPK 的提升 or降低程度（贡献度），结合该机台的产量占比得到全局影响分。负值越大，说明对全局质量拖累越严重。<br/><br/>
                      <strong>核心计算公式：</strong><br/>
                      <code>影响分 (Impact Score) = 贡献度 × 产量占比</code><br/>
                      <code>贡献度 (Contribution) = 机台平均 CPK - 对照基准 CPK</code><br/>
                      <code>产量占比 (Volume) = 机台产量 / 全局总产量</code><br/>
                      <span style="font-size: 11px; color: #94a3b8;">* 对照基准 CPK 是将相同搭配下其他替代机台的 CPK 按产量二次加权计算得出。</span>
                    </div>
                  </template>
                  <el-icon class="help-icon" style="cursor: pointer; color: var(--c-text-muted);"><QuestionFilled /></el-icon>
                </el-tooltip>
              </div>
              <el-button 
                type="text" 
                size="small" 
                style="padding: 0; min-height: unset; color: var(--el-text-color-secondary); font-size: 10px; font-weight: bold;" 
                @click.stop="isCardCollapsed = !isCardCollapsed"
              >
                {{ isCardCollapsed ? '展开' : '收起' }}
              </el-button>
            </div>

            <div v-show="!isCardCollapsed" style="font-size: 11px; display: flex; flex-direction: column; gap: 8px;">
              <!-- 表现最差机台 -->
              <div style="display: flex; flex-direction: column; gap: 2px;">
                <span style="color: var(--el-text-color-secondary);">表现最差机台 (Worst Machine):</span>
                <div v-if="globalAnalysis.worstMachine" style="display: flex; align-items: center; gap: 6px; margin-top: 2px;">
                  <el-tag size="small" type="danger" effect="plain" style="font-weight: bold;">{{ globalAnalysis.worstMachine.machine }}</el-tag>
                  <span style="color: #ef4444; font-weight: 600;">(CPK: {{ globalAnalysis.worstMachine.avgCpk.toFixed(2) }})</span>
                </div>
                <span v-else style="color: var(--el-text-color-placeholder);">-</span>
              </div>

              <!-- 最大全局影响机台 -->
              <div style="display: flex; flex-direction: column; gap: 2px; border-top: 1px dashed var(--el-border-color-lighter); padding-top: 6px;">
                <span style="color: var(--el-text-color-secondary);">最大全局影响机台 (Critical):</span>
                <div v-if="globalAnalysis.criticalMachine" style="display: flex; align-items: center; gap: 6px; margin-top: 2px;">
                  <el-tag size="small" type="danger" style="font-weight: bold;">{{ globalAnalysis.criticalMachine.machine }}</el-tag>
                  <span style="color: #ef4444; font-weight: 600;">(影响分: {{ globalAnalysis.criticalMachine.impactScore.toFixed(3) }})</span>
                </div>
                <span v-else style="color: var(--el-text-color-placeholder);">-</span>
              </div>

              <!-- Top 5 核心负贡献机台 -->
              <div style="display: flex; flex-direction: column; gap: 4px; border-top: 1px dashed var(--el-border-color-lighter); padding-top: 6px;">
                <span style="color: var(--el-text-color-secondary);">Top 负贡献机台 (按 Impact Score):</span>
                <div v-if="globalAnalysis.machineList && globalAnalysis.machineList.length > 0" style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px; margin-top: 4px;">
                  <span v-for="(m, idx) in globalAnalysis.machineList.slice(0, 5)" :key="m.machine">
                    <el-tooltip placement="top" raw-content>
                      <template #content>
                        <div style="font-size: 11px; line-height: 1.5;">
                          <div style="font-weight:bold;margin-bottom:2px">机台: {{ m.machine }}</div>
                          <div>控制变量后负面贡献度: <strong style="color:#ef4444">{{ m.contribution.toFixed(2) }}</strong></div>
                          <div>流量占比 (Volume): <strong>{{ (m.volume * 100).toFixed(1) }}%</strong></div>
                          <div>影响指数 (Impact): <strong style="color:#ef4444">{{ m.impactScore.toFixed(3) }}</strong></div>
                        </div>
                      </template>
                      <el-tag 
                        size="small" 
                        :color="idx === 0 ? '#fee2e2' : (idx < 3 ? '#ffedd5' : '#fef9c3')" 
                        :style="{ 
                          color: idx === 0 ? '#ef4444' : (idx < 3 ? '#f97316' : '#a16207'), 
                          border: '1px solid ' + (idx === 0 ? '#fecaca' : (idx < 3 ? '#fed7aa' : '#fef08a')),
                          fontWeight: 'bold'
                        }"
                      >
                        {{ m.machine }} ({{ m.impactScore.toFixed(2) }})
                      </el-tag>
                    </el-tooltip>
                  </span>
                </div>
                <span v-else style="color: var(--el-text-color-placeholder);">-</span>
              </div>
            </div>
          </div>

          <!-- 缩放控制浮动面板 -->
          <div 
            v-if="globalAnalysis && !isAllControlsHidden"
            style="position: absolute; top: 12px; right: 12px; z-index: 10; display: flex; align-items: center; gap: 4px; background: rgba(255, 255, 255, 0.96); backdrop-filter: blur(4px); border: 1px solid var(--el-border-color-light); border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); padding: 4px 8px; user-select: none;"
          >
            <span style="font-size: 11px; font-weight: bold; color: var(--el-text-color-regular); margin-right: 6px;">缩放: {{ Math.round(zoomScale * 100) }}%</span>
            <el-button 
              type="text" 
              size="small" 
              style="padding: 2px 6px; min-height: unset; font-weight: bold; font-size: 12px;" 
              :disabled="zoomScale <= 0.5"
              @click="zoomScale = Math.max(0.5, Number((zoomScale - 0.1).toFixed(1)))"
            >
              ➖
            </el-button>
            <el-button 
              type="text" 
              size="small" 
              style="padding: 2px 6px; min-height: unset; font-weight: bold; font-size: 10px;" 
              @click="zoomScale = 1.0"
            >
              重置
            </el-button>
            <el-button 
              type="text" 
              size="small" 
              style="padding: 2px 6px; min-height: unset; font-weight: bold; font-size: 12px;" 
              :disabled="zoomScale >= 2.0"
              @click="zoomScale = Math.min(2.0, Number((zoomScale + 0.1).toFixed(1)))"
            >
              ➕
            </el-button>
          </div>

          <!-- 视图展示区域 (设置 X、Y 轴滚动条溢出) -->
          <div style="flex: 1; min-height: 0; overflow-y: auto; overflow-x: auto; border: 1px solid var(--el-border-color-lighter); border-radius: 4px; background: #ffffff;">
            <!-- 树状决策图 (高度自适应树叶子数，且绑定 ref 容器获取实时宽高) -->
            <div ref="chartWrapperRef" :style="{ width: (100 * zoomScale) + '%', minWidth: (1200 * zoomScale) + 'px', height: '100%', minHeight: '200px' }">
              <v-chart
                :option="chartOption"
                autoresize
                :style="{ width: '100%', height: treeChartHeight + 'px' }"
              />
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Loading } from '@element-plus/icons-vue'
import { api } from '../../api/index.js'

use([GraphChart, TooltipComponent, CanvasRenderer])

const props = defineProps({
  selectedArticle: { type: String, default: null },
  startDate: { type: String, default: null },
  endDate: { type: String, default: null },
  targetDate: { type: String, default: null },
  indicator: { type: String, default: 'rfpp' },
  minSamples: { type: Number, default: 10 },
  tolerance: { type: Number, default: 0.8 }
})

// 展示视图与高亮状态
const showLastThreeDays = ref(false)
const isAllControlsHidden = ref(false)

// 悬浮卡片拖动及收缩逻辑
const isCardCollapsed = ref(false)
const cardPos = ref({ top: 12, left: 12 })
const isDragging = ref(false)
let dragOffset = { x: 0, y: 0 }

// 整体树图缩放比例
const zoomScale = ref(1.0)

function startDrag(e) {
  if (e.button !== 0) return
  if (e.target.closest('button') || e.target.closest('.el-tooltip') || e.target.closest('.el-icon')) {
    return
  }
  isDragging.value = true
  dragOffset = {
    x: e.clientX - cardPos.value.left,
    y: e.clientY - cardPos.value.top
  }
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(e) {
  if (!isDragging.value) return
  cardPos.value = {
    left: e.clientX - dragOffset.x,
    top: e.clientY - dragOffset.y
  }
}

function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

function handleShowLastThreeDaysChange() {
  loadCombinationTree()
}

// 响应式画布容器物理宽度与高度 (用于等比例宽高比计算)
const chartWrapperRef = ref(null)
const wrapperWidth = ref(1200)
const wrapperHeight = ref(600)
let resizeObserver = null

// 工段备选项选项，对应后台列名与中文映射
const workcenterOptions = [
  { value: 'gt_workcenter', label: '生胎成型 (GT)' },
  { value: 'ct_workcenter', label: '硫化 (CT)' },
  { value: 'tu_first_workcenter', label: '终检 TU' },
  { value: 'tb_first_workcenter', label: '动平衡 TB' }
]

const level1 = ref('gt_workcenter')
const level2 = ref('ct_workcenter')
const level3 = ref('tu_first_workcenter')
const level4 = ref('tb_first_workcenter')

const level1Options = computed(() => {
  return workcenterOptions.map(item => ({
    ...item,
    disabled: item.value === level2.value || item.value === level3.value || item.value === level4.value
  }))
})

const level2Options = computed(() => {
  return workcenterOptions.map(item => ({
    ...item,
    disabled: item.value === level1.value || item.value === level3.value || item.value === level4.value
  }))
})

const level3Options = computed(() => {
  return workcenterOptions.map(item => ({
    ...item,
    disabled: item.value === level1.value || item.value === level2.value || item.value === level4.value
  }))
})

const level4Options = computed(() => {
  return workcenterOptions.map(item => ({
    ...item,
    disabled: item.value === level1.value || item.value === level2.value || item.value === level3.value
  }))
})

function resolveConflicts(changedLevel) {
  const options = ['gt_workcenter', 'ct_workcenter', 'tu_first_workcenter', 'tb_first_workcenter']
  
  if (changedLevel === 1) {
    if (!level1.value) return
    if (level2.value === level1.value) {
      level2.value = options.find(o => o !== level1.value && o !== level3.value && o !== level4.value)
    } else if (level3.value === level1.value) {
      level3.value = options.find(o => o !== level1.value && o !== level2.value && o !== level4.value)
    } else if (level4.value === level1.value) {
      level4.value = options.find(o => o !== level1.value && o !== level2.value && o !== level3.value)
    }
  } else if (changedLevel === 2) {
    if (!level2.value) return
    if (level1.value === level2.value) {
      level1.value = options.find(o => o !== level2.value && o !== level3.value && o !== level4.value)
    } else if (level3.value === level2.value) {
      level3.value = options.find(o => o !== level1.value && o !== level2.value && o !== level4.value)
    } else if (level4.value === level2.value) {
      level4.value = options.find(o => o !== level1.value && o !== level2.value && o !== level3.value)
    }
  } else if (changedLevel === 3) {
    if (!level3.value) return
    if (level1.value === level3.value) {
      level1.value = options.find(o => o !== level2.value && o !== level3.value && o !== level4.value)
    } else if (level2.value === level3.value) {
      level2.value = options.find(o => o !== level1.value && o !== level3.value && o !== level4.value)
    } else if (level4.value === level3.value) {
      level4.value = options.find(o => o !== level1.value && o !== level2.value && o !== level3.value)
    }
  } else if (changedLevel === 4) {
    if (!level4.value) return
    if (level1.value === level4.value) {
      level1.value = options.find(o => o !== level2.value && o !== level3.value && o !== level4.value)
    } else if (level2.value === level4.value) {
      level2.value = options.find(o => o !== level1.value && o !== level3.value && o !== level4.value)
    } else if (level3.value === level4.value) {
      level3.value = options.find(o => o !== level1.value && o !== level2.value && o !== level4.value)
    }
  }
}

function normalizeHierarchy() {
  const levels = [level1.value, level2.value, level3.value, level4.value].filter(Boolean)
  level1.value = levels[0] || null
  level2.value = levels[1] || null
  level3.value = levels[2] || null
  level4.value = levels[3] || null
}

function handleLevel1Change() {
  resolveConflicts(1)
  normalizeHierarchy()
}

function handleLevel2Change() {
  resolveConflicts(2)
  normalizeHierarchy()
}

function handleLevel3Change() {
  resolveConflicts(3)
  normalizeHierarchy()
}

function handleLevel4Change() {
  resolveConflicts(4)
  normalizeHierarchy()
}

function invertHierarchy() {
  const temp1 = level1.value
  const temp2 = level2.value
  level1.value = level4.value
  level2.value = level3.value
  level3.value = temp2
  level4.value = temp1
  normalizeHierarchy()
}

const loading = ref(false)
const error = ref(null)
const paths = ref([])
const uslVal = ref(100.0)

const studyColumns = computed(() => {
  return [level1.value, level2.value, level3.value, level4.value].filter(Boolean)
})

const studyColumnsFriendly = computed(() => {
  return studyColumns.value.map(col => wcFriendlyName(col)).join(' ➔ ')
})

const totalLotsCount = computed(() => {
  if (!paths.value) return 0
  return paths.value.reduce((acc, p) => acc + (p.lot_cnt || 0), 0)
})

// 工序列友情中文名字
const wcFriendlyName = (colName) => {
  const found = workcenterOptions.find(o => o.value === colName)
  return found ? found.label.split(' ')[0] : colName
}

// ── 方案一：全局机台贡献分析 (Global Contribution Analysis with Controlled Baseline) ──
const globalAnalysis = computed(() => {
  const data = sortedTableData.value || []
  const cols = studyColumns.value || []
  if (data.length === 0 || cols.length === 0) return null

  // 1. 全局加权 CPK (改用合并方差公式，计算总体综合 CPK)
  const globalAvgCpk = aggregateNodeStats(data).cpk

  // 计算全局总产量 (作为分量占比的分母)
  const totalTires = data.reduce((acc, p) => acc + p.lot_cnt, 0)

  // 2. 查找所有出现在活跃层级中的唯一机台
  const machinesSet = new Set()
  data.forEach(p => {
    cols.forEach(col => {
      if (p[col]) {
        machinesSet.add(p[col])
      }
    })
  })

  // 3. 计算每个机台的 Avg CPK, Controlled Baseline, Contribution, Volume, Impact Score
  const machineList = []
  machinesSet.forEach(mach => {
    let machTires = 0
    const matchingRows = []

    // 按搭档组合分组，用于消除搭档混淆变量
    const partnerGroups = {}

    data.forEach(p => {
      const matchedCols = cols.filter(col => p[col] === mach)
      if (matchedCols.length > 0) {
        machTires += p.lot_cnt
        matchingRows.push(p)

        // 针对当前机台出现的每一个工段，提取其搭档组合 Key
        matchedCols.forEach(mCol => {
          const partnerParts = cols.map(c => c === mCol ? '*' : (p[c] || '*'))
          const partnerKey = partnerParts.join('_')

          if (!partnerGroups[partnerKey]) {
            partnerGroups[partnerKey] = {
              mCol: mCol,
              partnerParts: partnerParts,
              machTires: 0
            }
          }
          partnerGroups[partnerKey].machTires += p.lot_cnt
        })
      }
    })

    // 用合并方差公式计算该机台总体的综合 CPK (这与树图节点的值完全相同)
    const machAvgCpk = matchingRows.length > 0 ? aggregateNodeStats(matchingRows).cpk : 0

    // 计算控制变量后的对照基准：对每个搭档组合求一次加权对照基准，再按 M 自己在该组合的产量做二次加权
    let controlledBaselineNumerator = 0
    let controlledBaselineDenominator = 0

    Object.values(partnerGroups).forEach(group => {
      const { mCol, partnerParts, machTires: groupMachTires } = group
      
      // 一次加权：寻找拥有相同搭档组合，但该工段不是 mach 的替代路径列表
      const otherRows = []

      data.forEach(p => {
        if (p[mCol] !== mach) {
          const isMatch = cols.every((c, idx) => {
            if (c === mCol) return true
            return p[c] === partnerParts[idx]
          })
          if (isMatch) {
            otherRows.push(p)
          }
        }
      })

      // 用合并方差公式计算该替代路径下的联合对照基准 CPK (若缺失则默认回退全局均值)
      const partnerBaseline = otherRows.length > 0 ? aggregateNodeStats(otherRows).cpk : globalAvgCpk

      // 二次加权累加：以机台 M 在该搭档组合中的实际产量为权重
      controlledBaselineNumerator += partnerBaseline * groupMachTires
      controlledBaselineDenominator += groupMachTires
    })

    const controlledBaseline = controlledBaselineDenominator > 0 
      ? (controlledBaselineNumerator / controlledBaselineDenominator) 
      : globalAvgCpk

    const contribution = machAvgCpk - controlledBaseline
    const volume = totalTires > 0 ? (machTires / totalTires) : 0
    const impactScore = contribution * volume

    if (machTires >= props.minSamples) {
      machineList.push({
        machine: mach,
        avgCpk: machAvgCpk,
        controlledBaseline: controlledBaseline,
        contribution: contribution,
        volume: volume,
        impactScore: impactScore
      })
    }
  })

  // 排序与最差机台提取 (胎重下, 影响分越正代表恶化越严重, 偏差绝对值越大代表越差)
  if (props.indicator === 'weight') {
    machineList.sort((a, b) => b.impactScore - a.impactScore)
  } else {
    machineList.sort((a, b) => a.impactScore - b.impactScore)
  }

  // Worst Machine: 平均 CPK 最低 (非胎重) 或 绝对偏差最高 (胎重) 的机台
  let worstMachine = null
  if (machineList.length > 0) {
    if (props.indicator === 'weight') {
      worstMachine = [...machineList].sort((a, b) => b.avgCpk - a.avgCpk)[0]
    } else {
      worstMachine = [...machineList].sort((a, b) => a.avgCpk - b.avgCpk)[0]
    }
  }

  // Critical Machine: 影响最坏的机台
  const criticalMachine = machineList[0] || null

  return {
    globalAvgCpk,
    machineList,
    worstMachine,
    criticalMachine
  }
})

// ── 全局高亮染色规则映射 ──
const machineHighlightMap = computed(() => {
  const highlight = {}

  // 仅对最坏影响机台进行高亮
  const global = globalAnalysis.value
  if (global && global.machineList && global.machineList.length > 0) {
    const first = global.machineList[0]
    const isBad = props.indicator === 'weight' ? (first.impactScore > 0) : (first.impactScore < 0)
    if (isBad) {
      highlight[first.machine] = { color: '#ef4444', rule: '全局贡献', rank: 1, type: 'global' }
    }
  }

  return highlight
})

// 格式化 CPK Tag 类型
const getCpkTagType = (cpk) => {
  if (cpk === null || cpk === undefined) return 'info'
  if (cpk < 1.0) return 'danger'    // 红
  if (cpk < 1.33) return 'warning'  // 橙
  if (cpk < 1.67) return 'primary'  // 蓝
  return 'success'                  // 绿
}

// 请求后台机台组合树数据
async function loadCombinationTree() {
  const spec = props.selectedArticle
  if (!spec) {
    paths.value = []
    return
  }

  loading.value = true
  error.value = null
  try {
    let start_date = null
    let end_date = null
    if (showLastThreeDays.value) {
      if (props.targetDate) {
        const tDate = new Date(props.targetDate)
        if (!isNaN(tDate.getTime())) {
          const sDate = new Date(tDate.getTime() - 2 * 24 * 60 * 60 * 1000)
          const fmt = (d) => {
            const y = d.getFullYear()
            const m = String(d.getMonth() + 1).padStart(2, '0')
            const dd = String(d.getDate()).padStart(2, '0')
            return `${y}-${m}-${dd}`
          }
          start_date = fmt(sDate)
          end_date = props.targetDate
        }
      } else {
        start_date = props.startDate
        end_date = props.endDate
      }
    } else {
      // 默认当天数据
      start_date = null
      end_date = null
    }

    const params = {
      spec: spec,
      indicator: props.indicator,
      start_date: start_date,
      end_date: end_date,
      target_date: props.targetDate,
      min_samples: props.minSamples
    }

    const res = await api.getMachineCombinationTree(params)
    if (res.data.status === 'success') {
      paths.value = res.data.paths || []
      uslVal.value = res.data.usl || 100.0
    } else {
      error.value = res.data.message || '加载组合数据失败'
    }
  } catch (err) {
    console.error(err)
    error.value = '请求接口异常'
  } finally {
    loading.value = false
  }
}

watch(() => props.selectedArticle, loadCombinationTree)
watch(() => props.startDate, loadCombinationTree)
watch(() => props.endDate, loadCombinationTree)
watch(() => props.targetDate, loadCombinationTree)
watch(() => props.indicator, loadCombinationTree)
watch(() => props.minSamples, loadCombinationTree)

// 监听容器大小，用于动态 Aspect Ratio 计算
onMounted(() => {
  loadCombinationTree()
  if (chartWrapperRef.value) {
    wrapperWidth.value = chartWrapperRef.value.clientWidth || 1200
    // 监听容器大小变更
    if (window.ResizeObserver) {
      resizeObserver = new ResizeObserver((entries) => {
        for (let entry of entries) {
          wrapperWidth.value = entry.contentRect.width || 1200
        }
      })
      resizeObserver.observe(chartWrapperRef.value)
    }
  }
})

onUnmounted(() => {
  if (resizeObserver && chartWrapperRef.value) {
    resizeObserver.unobserve(chartWrapperRef.value)
  }
})

// spanMethod and calculateSpans deleted as decision table view has been removed

// ── 数据预处理：归并排序 ───────────────────────────────────────────
const sortedTableData = computed(() => {
  const studyCols = studyColumns.value
  const pathList = paths.value || []
  if (studyCols.length === 0 || pathList.length === 0) return []

  const mapped = pathList.map(p => {
    // Calculate CPK/deviation for the leaf combination directly
    const std = p.std_val
    const avg = p.avg_val
    const usl = uslVal.value
    let cpk = 1.33
    if (props.indicator === 'weight') {
      cpk = avg
    } else {
      cpk = std > 0.0 ? (usl - avg) / (3.0 * std) : 1.33
      cpk = Math.max(0.0, Math.min(5.0, cpk))
    }

    const item = {
      lot_cnt: p.lot_cnt,
      cpk: cpk,
      avg_val: avg,
      std_val: std,
      // Map properties for table rendering
      gt_workcenter: p.gt,
      ct_workcenter: p.ct,
      tu_first_workcenter: p.tu,
      tb_first_workcenter: p.tb
    }
    return item
  })

  // Sort by the current order of columns so that identical cells stack together for row-span merging!
  mapped.sort((a, b) => {
    for (let col of studyCols) {
      const valA = String(a[col] || '')
      const valB = String(b[col] || '')
      const cmp = valA.localeCompare(valB)
      if (cmp !== 0) return cmp
    }
    return 0
  })

  return mapped
})

// 动态高度计算属性：叶子路径节点数量乘以动态 Y 轴间距（多少取夹 MIN=55px MAX=100px）
const MIN_Y_GAP = 55
const MAX_Y_GAP = 100

const treeYGap = computed(() => {
  const dataList = sortedTableData.value || []
  const visibleCount = dataList.filter(p => p.lot_cnt >= props.minSamples).length || 1
  // 可视区域高度预设 600px，尝试大致地匹配容器
  const targetH = Math.max(500, wrapperWidth.value * 0.5)
  const raw = targetH / visibleCount
  return Math.max(MIN_Y_GAP, Math.min(MAX_Y_GAP, raw)) * zoomScale.value
})

const treeChartHeight = computed(() => {
  const dataList = sortedTableData.value || []
  const visibleCount = dataList.filter(p => p.lot_cnt >= props.minSamples).length || 1
  return Math.max(500 * zoomScale.value, visibleCount * treeYGap.value + 80 * zoomScale.value)
})

// sortedTableData watcher removed


// ── 合并方差 (Merged Variance) 聚合辅助函数 ────────────────────
function aggregateNodeStats(rows) {
  if (!rows || rows.length === 0) return { lot_cnt: 0, avg: 0, std: 0, cpk: 1.33 }
  if (rows.length === 1) {
    return {
      lot_cnt: rows[0].lot_cnt,
      avg: rows[0].avg_val,
      std: rows[0].std_val,
      cpk: rows[0].cpk
    }
  }

  const totalN = rows.reduce((acc, r) => acc + r.lot_cnt, 0)
  if (totalN <= 0) return { lot_cnt: 0, avg: 0, std: 0, cpk: 1.33 }

  // Combined Mean: sum(n_i * avg_i) / sum(n_i)
  const combinedMean = rows.reduce((acc, r) => acc + r.lot_cnt * r.avg_val, 0) / totalN

  // Combined Variance: sum(n_i * (std_i^2 + (avg_i - combinedMean)^2)) / sum(n_i)
  const combinedVar = rows.reduce((acc, r) => {
    const diff = r.avg_val - combinedMean
    const variance = r.std_val * r.std_val
    return acc + r.lot_cnt * (variance + diff * diff)
  }, 0) / totalN

  const combinedStd = Math.sqrt(combinedVar)
  
  // CPK / 绝对偏差率 Calculation
  let cpk = 1.33
  if (props.indicator === 'weight') {
    cpk = combinedMean
  } else {
    const usl = uslVal.value
    cpk = combinedStd > 0.0 ? (usl - combinedMean) / (3.0 * combinedStd) : 1.33
    cpk = Math.max(0.0, Math.min(5.0, cpk))
  }

  return {
    lot_cnt: totalN,
    avg: combinedMean,
    std: combinedStd,
    cpk: cpk
  }
}


const chartOption = computed(() => {
  const studyCols = studyColumns.value || []
  const dataList = sortedTableData.value || []
  const numLayers = studyCols.length

  if (numLayers === 0 || dataList.length === 0) return {}

  // 1. 构建树节点映射
  const treeNodes = {}
  
  treeNodes['root'] = {
    id: 'root',
    label: props.selectedArticle || 'ROOT',
    layerIdx: -1,
    children: [],
    matchingRows: []
  }

  dataList.forEach(p => {
    treeNodes['root'].matchingRows.push(p)
    
    let parentKey = 'root'
    let pathParts = ['root']
    
    studyCols.forEach((colName, layerIdx) => {
      const mach = p[colName]
      pathParts.push(mach)
      const key = pathParts.join('_')
      
      if (!treeNodes[key]) {
        treeNodes[key] = {
          id: key,
          label: mach,
          layerIdx: layerIdx,
          colName: colName,
          children: [],
          matchingRows: []
        }
        treeNodes[parentKey].children.push(key)
      }
      
      treeNodes[key].matchingRows.push(p)
      parentKey = key
    })
  })

  // 2. 自底向上对每一层节点的均值、方差及 CPK 运行合并方差公式聚合
  Object.keys(treeNodes).forEach(key => {
    const node = treeNodes[key]
    const stats = aggregateNodeStats(node.matchingRows)
    node.lot_cnt = stats.lot_cnt
    node.avg_val = stats.avg
    node.std_val = stats.std
    node.cpk = stats.cpk
  })

  // 2.5 树节点按样本量进行前端修剪，找出所有可见的节点 (满足 >= minSamples 且其所有祖先节点也都满足)
  const visibleNodeIds = new Set(['root'])
  const queue = ['root']
  while (queue.length > 0) {
    const parentId = queue.shift()
    const parentNode = treeNodes[parentId]
    if (!parentNode) continue
    
    const visibleChildren = []
    parentNode.children.forEach(childKey => {
      const childNode = treeNodes[childKey]
      if (childNode && childNode.lot_cnt >= props.minSamples) {
        visibleChildren.push(childKey)
        visibleNodeIds.add(childKey)
        queue.push(childKey)
      }
    })
    parentNode.children = visibleChildren
  }

  // 3. 计算节点 X 和 Y 坐标 (自底向上叶子中心对齐布局)
  // 将所有没有可见子节点的节点统一视为“叶子节点”进行纵向空间分配
  const leaves = Object.values(treeNodes).filter(n => visibleNodeIds.has(n.id) && n.children.length === 0)
  leaves.sort((a, b) => a.id.localeCompare(b.id))

  const containerW = (wrapperWidth.value || 1200) * zoomScale.value
  const containerH = treeChartHeight.value || 500
  
  // 动态考虑 ECharts 边距配置的有效比例
  const leftMarginPx = isAllControlsHidden.value ? 120 : 250
  const rightMarginPx = 200
  const topMargin = isAllControlsHidden.value ? 0.08 : 0.12
  const bottomMargin = isAllControlsHidden.value ? 0.08 : 0.12

  const W_eff = containerW - leftMarginPx - rightMarginPx
  const H_eff = containerH * (1 - topMargin - bottomMargin)
  const targetAspect = W_eff / H_eff
  
  // 节点多少取天 Y 轴间距（已 clamp 至 55~100px）
  const ySpacing = treeYGap.value
  const leafCenterOffset = ((leaves.length - 1) * ySpacing) / 2
  const actualYHalfSpan = leafCenterOffset + 30
  const actualYRange = 2 * actualYHalfSpan

  // 计算动态 dx 横向总跨度，使数据比例精确匹配容器物理比率
  const minDx = numLayers * 150
  const dx = Math.max(minDx, actualYRange * targetAspect - 40)
  const layerSpacing = numLayers > 0 ? dx / numLayers : 150

  // 计算自适应调整后的 Y 轴半跨度，确保即使 dx 被 minDx 限制，数据的 X/Y 比例也与容器完全契合，防止圆形拉伸变形为椭圆
  const adjustedYHalfSpan = (dx + 40) / (2 * targetAspect)
  
  // 采用从上到下按 Y 轴减少排布，保持字母自然序从上到下展示
  leaves.forEach((n, idx) => {
    n.y = leafCenterOffset - idx * ySpacing
    n.x = dx
  })

  // 递归计算中间父节点的 Y 轴位置与动态 X 位置
  for (let layerIdx = numLayers - 2; layerIdx >= -1; layerIdx--) {
    const layerNodes = Object.values(treeNodes).filter(n => visibleNodeIds.has(n.id) && n.layerIdx === layerIdx)
    layerNodes.forEach(n => {
      n.x = (layerIdx + 1) * layerSpacing
      
      if (n.children && n.children.length > 0) {
        const childYVals = n.children.map(cKey => treeNodes[cKey].y)
        const sum = childYVals.reduce((acc, v) => acc + v, 0)
        n.y = sum / childYVals.length
      } else {
        // 如果是提前结束的中间末梢节点，保留其在 leaves 初始分配中的纵向高度
        if (n.y === undefined) {
          n.y = 0
        }
      }
    })
  }

  // 4. 构建 ECharts Nodes 和 Links 数组
  const nodes = []
  const links = []

  Object.values(treeNodes).forEach(n => {
    if (!visibleNodeIds.has(n.id)) return // 仅处理可见的节点

    const avgCpk = n.cpk
    
    let color = '#10b981' 
    if (n.id === 'root') color = '#64748b' 
    else if (props.indicator === 'weight') {
      color = avgCpk > props.tolerance ? '#ef4444' : '#10b981'
    } else {
      if (avgCpk < 1.0) color = '#ef4444' 
      else if (avgCpk < 1.33) color = '#f97316' 
    }

    const machHighlight = machineHighlightMap.value[n.label]
    const hasHighlight = !!machHighlight

    nodes.push({
      id: n.id,
      name: n.label,
      x: n.x,
      y: n.y,
      symbol: 'circle',
      symbolSize: 24, // 锁定像素大小为 24px 圆圈
      value: { 
        avgCpk: avgCpk, 
        avgVal: n.avg_val,
        lotSum: n.lot_cnt, 
        layerName: n.colName || '分析根节点'
      },
      itemStyle: {
        color: color,
        borderWidth: 0, // 去掉边框
        shadowBlur: hasHighlight ? 15 : 0, // 仅对最差机台发光
        shadowColor: hasHighlight ? '#ef4444' : 'transparent',
        shadowOffsetX: 0,
        shadowOffsetY: 0
      },
      label: {
        show: true,
        // 叶子节点文字在右侧显示，中间节点在上方，根节点在左侧
        position: n.id === 'root' ? 'left' : (n.children.length === 0 ? 'right' : 'top'),
        color: 'var(--el-text-color-primary)',
        fontSize: 12,
        fontWeight: '600',
        formatter: (params) => {
          if (n.id === 'root') return `{root|规格: ${params.name}}`
          const cpkStr = avgCpk.toFixed(2)
          if (props.indicator === 'weight') {
            if (n.children.length === 0) {
              return `{mach|${params.name}} {info|(偏离: ${cpkStr}%)}`
            }
            return `{mach|${params.name}}\n{info|(偏离: ${cpkStr}%)}`
          }
          const avgValStr = n.avg_val !== undefined && n.avg_val !== null ? n.avg_val.toFixed(2) : '0.00'
          
          if (n.children.length === 0) {
            // 叶子节点：单行排布
            return `{mach|${params.name}} {info|(μ: ${avgValStr}, CPK: ${cpkStr})}`
          }
          // 中间节点：折行排布
          return `{mach|${params.name}}\n{info|(μ: ${avgValStr}, CPK: ${cpkStr})}`
        },
        rich: {
          root: {
            fontSize: 12,
            fontWeight: 'bold',
            color: 'var(--el-text-color-primary)'
          },
          mach: {
            fontSize: 12,
            fontWeight: 'bold',
            color: 'var(--el-text-color-primary)'
          },
          info: {
            fontSize: 10,
            fontWeight: '500',
            color: '#7f8c8d' // 用灰色与机台名做视觉区分，提高可读性
          }
        }
      }
    })

    n.children.forEach(cKey => {
      const childNode = treeNodes[cKey]
      const childCpk = childNode.cpk
      
      let linkColor = 'rgba(16, 185, 129, 0.5)' 
      if (props.indicator === 'weight') {
        linkColor = childCpk > props.tolerance ? 'rgba(239, 68, 68, 0.5)' : 'rgba(16, 185, 129, 0.5)'
      } else {
        if (childCpk < 1.0) linkColor = 'rgba(239, 68, 68, 0.5)' 
        else if (childCpk < 1.33) linkColor = 'rgba(249, 115, 22, 0.5)' 
      } 

      const ratio = childNode.lot_cnt / (n.lot_cnt || 1)
      const width = Math.max(1.2, Math.min(8, ratio * 7))

      links.push({
        source: n.id,
        target: cKey,
        value: childNode.lot_cnt,
        avgCpk: childCpk,
        lineStyle: {
          color: linkColor,
          width: width,
          curveness: 0
        }
      })
    })
  })

  // 添加隐形锚点来限定 ECharts graph 容器在二维空间中的映射比例，强行锁定 circles 为完美正圆形
  nodes.push({
    id: '__anchor_top_left',
    name: '',
    x: -20,
    y: adjustedYHalfSpan,
    symbolSize: 0.1,
    itemStyle: { opacity: 0 },
    lineStyle: { opacity: 0 },
    label: { show: false },
    tooltip: { show: false }
  })

  nodes.push({
    id: '__anchor_bottom_right',
    name: '',
    x: dx + 20,
    y: -adjustedYHalfSpan,
    symbolSize: 0.1,
    itemStyle: { opacity: 0 },
    lineStyle: { opacity: 0 },
    label: { show: false },
    tooltip: { show: false }
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      backgroundColor: '#ffffff',
      borderColor: '#e5e8ef',
      borderWidth: 1,
      textStyle: {
        fontSize: 12
      },
      formatter(params) {
        if (params.dataType === 'node') {
          const val = params.data.value
          if (params.data.id === 'root' || params.data.id.startsWith('__anchor')) {
            return params.data.id.startsWith('__anchor') ? '' : `<div style="font-weight:bold;">分析起始规格: ${params.name}</div>`
          }
          const wcFriendly = wcFriendlyName(val.layerName)
          if (props.indicator === 'weight') {
            return `
              <div style="font-weight:bold;margin-bottom:4px;color:var(--el-color-primary);">${wcFriendly}: ${params.name}</div>
              <div style="font-size:11px;">经此节点轮胎数 (N): <strong style="color:#2563eb">${val.lotSum}</strong></div>
              <div style="font-size:11px;">此分支累计平均偏离度: <strong style="color:${val.avgCpk > props.tolerance ? '#ef4444' : '#10b981'}">${val.avgCpk.toFixed(2)}%</strong></div>
            `
          }
          return `
            <div style="font-weight:bold;margin-bottom:4px;color:var(--el-color-primary);">${wcFriendly}: ${params.name}</div>
            <div style="font-size:11px;">经此节点轮胎数 (N): <strong style="color:#2563eb">${val.lotSum}</strong></div>
            <div style="font-size:11px;">此分支累计平均 CPK: <strong style="color:${val.avgCpk < 1.33 ? '#ef4444' : '#10b981'}">${val.avgCpk.toFixed(2)}</strong></div>
          `
        } else if (params.dataType === 'edge') {
          const link = params.data
          const sourceNode = nodes.find(n => n.id === link.source)
          const targetNode = nodes.find(n => n.id === link.target)
          const sourceLabel = sourceNode ? `${wcFriendlyName(sourceNode.value.layerName)}_${sourceNode.name}` : link.source
          const targetLabel = targetNode ? `${wcFriendlyName(targetNode.value.layerName)}_${targetNode.name}` : link.target
          if (props.indicator === 'weight') {
            return `
              <div style="font-weight:bold;margin-bottom:4px;color:#3b82f6;">${sourceLabel} ➔ ${targetLabel}</div>
              <div style="font-size:11px;">流转轮胎数 (N): <strong style="color:#2563eb">${link.value}</strong></div>
              <div style="font-size:11px;">该连线平均偏离度: <strong style="color:${link.avgCpk > props.tolerance ? '#ef4444' : '#10b981'}">${link.avgCpk.toFixed(2)}%</strong></div>
            `
          }
          return `
            <div style="font-weight:bold;margin-bottom:4px;color:#3b82f6;">${sourceLabel} ➔ ${targetLabel}</div>
            <div style="font-size:11px;">流转轮胎数 (N): <strong style="color:#2563eb">${link.value}</strong></div>
            <div style="font-size:11px;">该连线平均 CPK: <strong style="color:${link.avgCpk < 1.33 ? '#ef4444' : '#10b981'}">${link.avgCpk.toFixed(2)}</strong></div>
          `
        }
      }
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        left: (isAllControlsHidden.value ? 120 : 250) * zoomScale.value,
        right: 200 * zoomScale.value,
        top: isAllControlsHidden.value ? '8%' : '12%',
        bottom: isAllControlsHidden.value ? '8%' : '12%',
        data: nodes,
        links: links,
        roam: false, // 禁用内部缩放，由外层 DOM 自适应滚动条管理
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 5],
        label: {
          show: true,
          position: 'inside',
          color: '#ffffff',
          fontSize: 8,
          fontWeight: 'bold',
          formatter: (params) => {
            if (params.data.id === 'root') return 'START'
            return params.name
          }
        },
        lineStyle: {
          color: 'source',
          curveness: 0
        }
      }
    ]
  }
})
</script>

<style scoped>
.combination-tree-container {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
</style>
