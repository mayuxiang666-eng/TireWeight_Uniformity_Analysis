<template>
  <div class="app-container">
    
    <!-- Row 1: 加权 CPK 控制区间分析 (全宽) -->
    <section class="section-row">
      <div id="tour-cpk-trend" class="card full-width">
        <div class="card-header">
          <div>
            <div class="card-title" style="display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span>{{ tab1SelectedArticle ? tab1SelectedArticle + ' · ' : '' }}整体指标预览 (CPK指标)</span>
              <el-tooltip placement="top" raw-content>
                <template #content>
                  <div v-if="cpkIndicator === 'cony'" style="max-width: 290px; font-size: 12px; line-height: 1.6; padding: 4px;">
                    <strong style="color: #10b981;">过程能力指数 (CONY 双侧 CPK)：</strong><br/>
                    以规格 (Article10) 为基本单元计算单日双侧 CPK：<br/>
                    <code>CPK = min((USL - μ)/(3σ), (μ - LSL)/(3σ))</code><br/>
                    系统使用配方表对应的 conny_usl 与 conny_lsl 双侧公差，全厂 CPK 为所有合格规格按排产条数加权平均。<br/><br/>
                    <strong style="color: #f59e0b;">控制限标准 (SPC)：</strong><br/>
                    绘制 1.33 目标基准线，低于 1.33 的点自动判定为预警/失控并高亮标红。
                  </div>
                  <div v-else style="max-width: 290px; font-size: 12px; line-height: 1.6; padding: 4px;">
                    <strong style="color: #10b981;">过程能力指数 (CPK)：</strong><br/>
                    以规格 (Article10) 为基本单元计算单日单侧上限 CPK：<br/>
                    <code>CPK = (USL - Mean) / (3 * StdDev)</code><br/>
                    系统自动剔除单规格日样本量 &lt; 5 的波动数据。厂区 CPK 为所有合格规格按排产条数加权平均后，分别绘制 of RFPP 综合 CPK 和 RFH1 综合 CPK 曲线。<br/><br/>
                    <strong style="color: #f59e0b;">控制限标准 (SPC)：</strong><br/>
                    基于当前数据动态计算均值 (Mean) 和标准差 (σ)，定义正常区间、1σ~2σ 预警区间、2σ~3σ 严重预警区间，低于 3σ (LCL) 则判定为失控。低于 1σ 的点将自动高亮标识。
                  </div>
                </template>
                <el-icon class="help-icon"><QuestionFilled /></el-icon>
              </el-tooltip>
              <div v-if="filterStore.dataUpdateTime" class="data-update-capsule">
                <span class="capsule-dot" />
                <span class="capsule-label">数据最近刷新时间:</span>
                <span class="capsule-val">{{ filterStore.dataUpdateTime }}</span>
              </div>
            </div>
            <div class="breadcrumb mt-4" v-if="tab1SelectedArticle" style="display: flex; align-items: center; gap: 8px;">
              <el-button size="small" type="primary" plain :icon="RefreshLeft" @click="resetTab1Article()">全部规格 (重置)</el-button>
              <span class="breadcrumb-sep">›</span>
              <span class="breadcrumb-current" style="font-weight: 600; color: #1e293b; font-family: 'JetBrains Mono', monospace; font-size: 13px;">{{ tab1SelectedArticle }}</span>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 16px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 12px; color: var(--el-text-color-regular); font-weight: 600;">Main Hall:</span>
              <el-radio-group
                v-model="filterStore.selectedPhase"
                size="small"
                @change="handlePhaseChange"
              >
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="p3">三期</el-radio-button>
                <el-radio-button value="p4">四期</el-radio-button>
              </el-radio-group>
            </div>
            
            <el-checkbox
              v-if="!tab1SelectedArticle"
              v-model="excludeTop10"
              size="small"
              style="margin-left: 10px; font-weight: 500;"
              @change="handleExcludeTop10Change"
            >
              剔除 Top 10 预警规格
            </el-checkbox>

            <el-button
              v-if="tab1SelectedArticle"
              size="small"
              :class="['exclude-outliers-btn', { 'is-active': excludeOutliers }]"
              @click="excludeOutliers = !excludeOutliers; loadCpkTrend()"
            >
              <el-icon v-if="excludeOutliers" style="margin-right: 4px; font-weight: bold;"><Select /></el-icon>
              <span>{{ excludeOutliers ? '已剔除异常值 (Q3+1.5IQR)' : '剔除异常值 (Q3+1.5IQR)' }}</span>
            </el-button>
          </div>
        </div>
        <div class="card-body" style="min-height:380px; height:380px;">
          <TrendChart
            :cpk-data="cpkData"
            :indicator="cpkIndicator"
            :loading="cpkLoading"
            :error="cpkError"
            :x-key="filterStore.trendGranularity === 'daily' ? 'date' : 'week_start'"
            :selected-date="selectedTrendDate"
            @date-select="handleDateSelect"
          />
        </div>
      </div>
    </section>


    <!-- Row 3: 规格排行与机台排行并排 -->
    <section class="section-row two-col">
      <!-- 左侧: 核心规格行动表 (占 40%) -->
      <div id="tour-spec-action-table" class="card" style="min-width:0; flex: 4; display: flex; flex-direction: column; overflow: hidden; height: 650px;">
        <div v-if="!selectedTrendDate" class="empty-period-card" style="height: 100%; display: flex; align-items: center; justify-content: center;">
          <el-empty description="请点击上方 CPK 趋势图的任意数据点以载入该天的规格预警分析" :image-size="60" />
        </div>
        <template v-else>
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; gap: 8px; padding-bottom: 8px; flex-shrink: 0;">
            <div class="card-title" style="display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0;">
              <span style="white-space: nowrap; font-weight: 600; font-size: 13px;">
                核心规格行动表
              </span>
              <span
                v-if="tab1SelectedArticle"
                class="spec-focus-badge"
              >
                已聚焦: {{ tab1SelectedArticle }}
              </span>
              <el-tooltip placement="top" raw-content>
                <template #content>
                  <div style="max-width: 280px; font-size: 12px; line-height: 1.5;">
                    <template v-if="cpkIndicator === 'weight'">
                      <strong>偏差贡献排行逻辑：</strong><br/>
                      计算当日规格对全厂整体偏差率的拉低贡献度：<br/>
                      <code>贡献度 = (单规格偏差率 - 全厂整体偏差率) × 规格产量占比</code><br/><br/>
                      预警分级：🔴 红色预警 > 🟠 橙色预警 > 🟡 黄色预警。同级别内按负向拉低贡献降序排列。
                    </template>
                    <template v-else>
                      <strong>负向贡献排行逻辑 (方案 B)：</strong><br/>
                      计算当日规格对全区加权综合 CPK 的负向拉低贡献度：<br/>
                      <code>CPK 负向贡献 = (当日系统综合 CPK - 单规格 CPK) × 规格产量 (N)</code><br/><br/>
                      预警分级：🔴 红色预警 > 🟠 橙色预警 > 🟡 黄色预警。同级别内按负向拉低贡献降序排列。
                    </template>
                  </div>
                </template>
                <el-icon class="help-icon"><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0; white-space: nowrap;">
              <template v-if="tab1SelectedArticle">
                <el-button
                  size="small"
                  class="btn-warm-outline"
                  :icon="RefreshLeft"
                  @click="resetTab1Article"
                >
                  查看全量
                </el-button>
                <el-button
                  size="small"
                  class="btn-warm-primary"
                  :icon="TrendCharts"
                  @click="handleOpenBarcodeMeasurements(tab1SelectedArticle)"
                >
                  单规格折线图
                </el-button>
              </template>
              <template v-else>
                <template v-if="cpkIndicator !== 'weight'">
                  <span style="font-size: 12px; color: var(--el-text-color-regular);">CPK:</span>
                  <el-input-number
                    v-model="warningMaxCpk"
                    :min="0.01"
                    :max="5.0"
                    :step="0.05"
                    :precision="2"
                    size="small"
                    style="width: 80px;"
                    @change="loadWarningArticles"
                  />
                </template>
                <span style="font-size: 12px; color: var(--el-text-color-regular); margin-left: 2px;">产量:</span>
                <el-input-number v-model="warningMinSamples" :min="1" :max="1000" size="small" style="width: 75px;" @change="loadWarningArticles" />
              </template>
            </div>
          </div>
          
          <!-- 公式的警示说明框 (象牙暖金全局统一风格) -->
          <div style="padding: 0 16px 8px 16px; flex-shrink: 0;">
            <div
              :style="{
                padding: '7px 12px',
                borderRadius: '8px',
                width: '100%',
                backgroundColor: tab1SelectedArticle ? '#fffbeb' : '#fafaf9',
                backgroundImage: tab1SelectedArticle ? 'linear-gradient(135deg, #fffdf5 0%, #fffbeb 100%)' : 'none',
                border: tab1SelectedArticle ? '1px solid #fde68a' : '1px solid #e7e5e4',
                borderLeft: tab1SelectedArticle ? '3px solid #f59e0b' : '3px solid #cbd5e1',
                boxShadow: tab1SelectedArticle ? '0 1px 3px rgba(245, 158, 11, 0.08)' : 'none',
                transition: 'all 0.25s ease'
              }"
            >
              <div style="font-size: 12px; line-height: 1.5; display: flex; flex-direction: column; gap: 3px;">
                <template v-if="tab1SelectedArticle">
                  <div style="color: #92400e; font-weight: 700; display: flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #f59e0b;"></span>
                    已聚焦规格：{{ tab1SelectedArticle }}（{{ selectedTrendDate }} 质量追溯联动中）
                  </div>
                  <div style="color: #78350f; font-size: 11px; font-weight: 500;">
                    下方表格已高亮标示该规格；右侧工序流转与批次数据已同步联动。点击上方“查看全量”按钮可清除聚焦。
                  </div>
                </template>
                <template v-else>
                  <div style="color: #44403c; font-weight: 600;">
                    预警规则：🔴 红色预警（调参恶化 / 持续霸榜）> 🟠 橙色预警（降幅超 35% / 持续在榜）> 🟡 黄色预警
                  </div>
                  <div style="color: #78716c; font-size: 11px; font-weight: normal;">
                    说明：同预警等级内严格按负向拉低贡献由重到轻排列。悬浮规格可查看完整指标卡片，点击任意行可下钻联动右侧流转图。
                  </div>
                </template>
              </div>
            </div>
          </div>
          
          <div class="card-body" style="flex: 1; min-height: 0; padding: 0; display: flex; flex-direction: column; overflow: hidden;">
            <CoreSpecActionTable
              :data="articles"
              :loading="articleLoading"
              :error="articleError"
              :selected-article="tab1SelectedArticle"
              :indicator="cpkIndicator"
              :target-date="selectedTrendDate"
              :is-latest-date="isLatestDate"
              @drill-down="onTab1ArticleDrill"
              @open-recommend="handleOpenTableRecommend"
            />
          </div>
        </template>
      </div>


      <!-- 右侧: 机台 CPK (avg + 3σ) 数据表格 与 生产工序流转图 Tab 页面 (占 60%) -->
      <div id="tour-process-sankey" class="card" style="min-width:0; flex: 6; display: flex; flex-direction: column; overflow: hidden; height: 650px;">
        <div v-if="!selectedTrendDate" class="empty-period-card" style="height: 100%; display: flex; align-items: center; justify-content: center;">
          <el-empty description="请点击上方 CPK 趋势图的任意数据点以载入工序流转及路径分析" :image-size="60" />
        </div>
        <template v-else>
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 8px; flex-shrink: 0;">
            <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
              <!-- 显示 Tab 切换与诊断 -->
              <el-radio-group v-model="machineTabActive" size="small">
                <el-radio-button value="sankey_flow">单日生产工序路径</el-radio-button>
                <el-radio-button value="best_sankey_flow">全量最佳生产路径</el-radio-button>
              </el-radio-group>

              <el-tooltip v-if="machineTabActive === 'sankey_flow'" placement="top" raw-content>
                <template #content>
                  <div style="max-width: 280px; font-size: 12px; line-height: 1.5;">
                    展示选定日期当天的所有工序路径流转情况。连线和节点颜色标记代表存在多个机台分流生产，颜色的深浅代表 CPK 指数的好坏，发光红圈（红色阴影发光效果）代表该工段的瓶颈/问题机台。
                  </div>
                </template>
                <el-icon class="help-icon" style="margin-left: 2px; cursor: pointer; color: var(--c-text-muted);"><QuestionFilled /></el-icon>
              </el-tooltip>

              <el-tooltip v-else-if="machineTabActive === 'best_sankey_flow'" placement="top" raw-content>
                <template #content>
                  <div style="max-width: 280px; font-size: 12px; line-height: 1.5;">
                    基于过去 30 天的历史生产数据，通过算法计算出的 TU 检测结果（CPK）最优的推荐流转路径。
                  </div>
                </template>
                <el-icon class="help-icon" style="margin-left: 2px; cursor: pointer; color: var(--c-text-muted);"><QuestionFilled /></el-icon>
              </el-tooltip>

              <!-- 决策树分析入口按钮 -->
              <el-button type="primary" size="small" plain style="margin-left: 12px;" @click="combinationTreeDialogVisible = true">
                机台组合分析
              </el-button>

              <el-tag v-if="tab1SelectedArticle" size="small" type="success">
                规格: {{ tab1SelectedArticle }}
              </el-tag>
              <el-tag v-else size="small" type="warning" effect="plain">
                未选定规格
              </el-tag>
            </div>
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 12px; color: var(--el-text-color-regular);">样本门槛:</span>
                <el-input-number v-model="machineMinSamples" :min="1" :max="1000" size="small" style="width: 90px;" @change="handleMachineMinSamplesChange" />
              </div>
              <el-button size="small" type="primary" plain :icon="ZoomIn" @click="handleOpenSankeyZoom">
                放大查看
              </el-button>
            </div>
          </div>

          <div class="card-body" style="flex: 1; min-height: 0; padding-top: 10px; display: flex; flex-direction: column; overflow: hidden;">
            <!-- 未选定规格提示 -->
            <div v-if="!tab1SelectedArticle" style="height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;">
              <el-empty
                description="请在上方搜索栏或左侧预警列表中选定具体规格"
                :image-size="90"
              >
                <template #extra>
                  <div style="font-size: 12.5px; color: #64748b; line-height: 1.6; text-align: center; max-width: 480px; margin-top: 6px;">
                    💡 <strong>操作提示</strong>：单日工序流转与全量最佳路径针对具体规格进行分析。<br/>
                    请在左侧<strong>「恶化预警规格」</strong>中点击任意规格，或在顶部<strong>「规格」</strong>下拉栏中搜索选定。
                  </div>
                </template>
              </el-empty>
            </div>

            <!-- Tab 2: 单日生产工序流转桑基图 -->
            <MachineProcessSankeyChart
              v-else-if="machineTabActive === 'sankey_flow'"
              ref="sankeyChartRef"
              :sankey-data="sankeyData"
              :loading="sankeyLoading"
              :error="sankeyError"
              :indicator="cpkIndicator"
              :tolerance="filterStore.weightTolerance"
              :article="tab1SelectedArticle"
              @open-cgrs="handleOpenCgrs"
            />
            <!-- Tab 3: 全量数据集最佳生产路径桑基图 -->
            <MachineBestProcessSankeyChart
              v-else-if="machineTabActive === 'best_sankey_flow'"
              ref="bestSankeyChartRef"
              :sankey-data="bestSankeyData"
              :loading="bestSankeyLoading"
              :error="bestSankeyError"
              :indicator="cpkIndicator"
              :tolerance="filterStore.weightTolerance"
              :article="tab1SelectedArticle"
              :recommendation-data="paramRecommendationData"
              :recommendation-loading="paramRecommendationLoading"
              @open-cgrs="handleOpenCgrs"
            />

          </div>
        </template>
      </div>
    </section>

    <!-- Row 3.5: 横跨两列 (Full-Width 通栏): 物料批次分析卡片 -->
    <section class="section-row" v-if="selectedTrendDate">
      <div class="card full-width" style="width: 100%;">
        <template v-if="true">
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
              <div class="card-title" style="display: inline-flex; align-items: center; gap: 6px;">
                <span>物料批次分析</span>
              </div>
              <el-tag v-if="tab1SelectedArticle" size="small" type="success">
                规格: {{ tab1SelectedArticle }}
              </el-tag>
              <el-tag v-else size="small" type="warning" effect="plain">
                未选定规格
              </el-tag>
              <span style="font-size: 12px; color: var(--el-text-color-secondary);">
                | 日期: {{ selectedTrendDate }}
              </span>
            </div>
          </div>
          <div class="card-body" style="min-height: 380px; padding-top: 10px;">
            <div v-if="!tab1SelectedArticle" style="height: 340px; display: flex; align-items: center; justify-content: center;">
              <el-empty
                description="请先选定规格以查看物料批次质量追溯数据"
                :image-size="75"
              />
            </div>
            <ArticleLotCpkChart
              v-else
              :lot-data="lotCpkData"
              :usl-value="lotUslValue"
              :lsl-value="lotLslValue"
              :loading="lotCpkLoading"
              :error="lotCpkError"
              :selected-article="tab1SelectedArticle"
              :target-date="selectedTrendDate"
              :indicator="cpkIndicator"
              @reload="handleLotChartReload"
            />
          </div>
        </template>
      </div>
    </section>



    <!-- 成型机台 CGRS 参数变更记录弹窗 -->
    <CgrsRecordDialog
      v-model:visible="cgrsDialogVisible"
      :machine="cgrsDialogMachine"
      :date="cgrsDialogDate"
      :article="cgrsDialogArticle"
      :indicator="cgrsDialogIndicator || cpkIndicator"
      :is-top-warning="cgrsIsTopWarning"
      :top-machines="cgrsTopMachines"
    />

    <!-- 机台排列组合树分析弹窗 -->
    <el-dialog
      v-model="combinationTreeDialogVisible"
      title="机台组合分析"
      width="90%"
      top="4vh"
      destroy-on-close
      append-to-body
      @opened="handleCombinationTreeDialogOpened"
    >
      <div style="height: 600px; display: flex; flex-direction: column;">
        <MachineCombinationTree
          v-if="combinationTreeDialogRendered"
          :selected-article="tab1SelectedArticle || null"
          :start-date="machineCpkDateRange && machineCpkDateRange.length === 2 ? machineCpkDateRange[0] : null"
          :end-date="machineCpkDateRange && machineCpkDateRange.length === 2 ? machineCpkDateRange[1] : null"
          :target-date="selectedTrendDate"
          :indicator="cpkIndicator"
          :min-samples="machineMinSamples"
          :tolerance="filterStore.weightTolerance"
        />
      </div>
    </el-dialog>

    <!-- 单规格单胎实测值折线图弹窗 -->
    <BarcodeMeasurementsDialog
      v-model:visible="barcodeDialogVisible"
      :article10="barcodeDialogArticle || tab1SelectedArticle"
      :target-date="selectedTrendDate"
      :indicator="cpkIndicator"
      :time-col="filterStore.selectedTimeCol"
      :phase="filterStore.selectedPhase"
    />

    <!-- 专属轻量工艺参数推荐弹窗 (从核心规格行动表触发) -->
    <MachineRecommendParamDialog
      v-model:visible="recDialogVisible"
      :machine="recDialogMachine"
      :target-date="selectedTrendDate"
      :article="recDialogArticle"
      :workcenter-type="recDialogStage"
      :indicator="cpkIndicator"
      :reason="recDialogReason"
    />

  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useFilterStore } from '../store/filter.js'
import { api } from '../api/index.js'
import TrendChart from '../components/charts/TrendChart.vue'
import CoreSpecActionTable from '../components/tables/CoreSpecActionTable.vue'
import MachineRecommendParamDialog from '../components/dialogs/MachineRecommendParamDialog.vue'
import CgrsRecordDialog from '../components/dialogs/CgrsRecordDialog.vue'
import MachineProcessSankeyChart from '../components/charts/MachineProcessSankeyChart.vue'
import MachineBestProcessSankeyChart from '../components/charts/MachineBestProcessSankeyChart.vue'
import MachineCombinationTree from '../components/charts/MachineCombinationTree.vue'
import ArticleLotCpkChart from '../components/charts/ArticleLotCpkChart.vue'
import BarcodeMeasurementsDialog from '../components/modals/BarcodeMeasurementsDialog.vue'

import { QuestionFilled, RefreshLeft, ZoomIn, TrendCharts, Select } from '@element-plus/icons-vue'
import { useDashboardTour } from '../composables/useDashboardTour.js'

const filterStore = useFilterStore()
const { startTour } = useDashboardTour()

onMounted(() => {
  // 首次访问自动唤醒新手引导 (延时 1000ms 等待图表与布局初次渲染完成)
  setTimeout(() => {
    startTour(false)
  }, 1000)
})

// ── 核心规格行动表参数推荐弹窗控制 ──
const recDialogVisible = ref(false)
const recDialogMachine = ref('')
const recDialogArticle = ref('')
const recDialogStage = ref('gt')
const recDialogReason = ref('degradation')

function handleOpenTableRecommend(row) {
  if (!row || !row.warning_machine) return
  recDialogMachine.value = row.warning_machine
  recDialogArticle.value = row.article10 || tab1SelectedArticle.value || ''
  recDialogStage.value = row.recommend_stage || 'gt'
  recDialogReason.value = 'degradation'
  recDialogVisible.value = true
}

// ── 单胎实际测量值折线图 (Barcode Run Chart) 弹窗 ──
const barcodeDialogVisible = ref(false)
const barcodeDialogArticle = ref(null)

function handleOpenBarcodeMeasurements(article = null) {
  const target = article || tab1SelectedArticle.value
  if (!target) {
    ElMessage.warning('请先选定要查看单胎实测值的规格')
    return
  }
  barcodeDialogArticle.value = target
  barcodeDialogVisible.value = true
}

// 排序控制 (固定使用异常贡献率与提升度)


// Tab 1 本地下钻规格状态
const tab1SelectedArticle = ref(null)

// 同步选中规格至全局 Store，以便导航栏同步展示
watch(() => filterStore.selectedArticle, (newVal) => {
  if (tab1SelectedArticle.value !== newVal) {
    tab1SelectedArticle.value = newVal
    loadCpkTrend()
    if (selectedTrendDate.value) {
      loadWarningArticles()
      loadLotCpkTrend()
    }
    if (machineTabActive.value === 'sankey_flow') {
      loadMachineProcessSankey()
    } else if (machineTabActive.value === 'best_sankey_flow') {
      loadMachineBestProcessSankey()
    }
  }
}, { immediate: true })

watch(() => tab1SelectedArticle.value, (newVal) => {
  if (filterStore.selectedArticle !== newVal) {
    filterStore.selectedArticle = newVal
  }
})


// CPK 趋势与指标状态
const cpkIndicator = computed(() => filterStore.cpkIndicator)
const selectedTrendDate = ref(null) // 点击选中日期
const cpkData = ref({})
const cpkLoading = ref(false)
const cpkError = ref(null)
const excludeTop10 = ref(false)
const excludeOutliers = ref(false)

async function loadCpkTrend() {
  cpkLoading.value = true
  cpkError.value = null
  try {
    const params = {}
    params.grain = filterStore.trendGranularity
    params.time_col = filterStore.selectedTimeCol
    params.phase = filterStore.selectedPhase
    params.shift = filterStore.selectedShift
    if (excludeOutliers.value) {
      params.exclude_outliers = true
    }
    if (tab1SelectedArticle.value) {
      params.article10 = tab1SelectedArticle.value
    } else if (excludeTop10.value) {
      let topArticlesList = articles.value
      if (!topArticlesList || topArticlesList.length === 0) {
        try {
          const warnRes = await api.getWarningArticles({
            indicator: cpkIndicator.value,
            min_samples: warningMinSamples.value,
            time_col: filterStore.selectedTimeCol,
            phase: filterStore.selectedPhase,
            max_cpk: warningMaxCpk.value
          })
          if (warnRes.data && warnRes.data.status === 'success') {
            topArticlesList = warnRes.data.data || []
          }
        } catch (err) {
          console.warn('Failed to pre-fetch warning articles for top 10 exclusion', err)
        }
      }
      if (topArticlesList && topArticlesList.length > 0) {
        const top10Articles = topArticlesList.slice(0, 10).map(a => a.article10).filter(Boolean)
        if (top10Articles.length > 0) {
          params.exclude_articles = top10Articles.join(',')
        }
      }
    }
    const res = await api.getCpkTrend(params)
    cpkData.value = res.data.status === 'success' ? res.data.data : {}
    if (res.data.status === 'error') cpkError.value = res.data.message
  } catch (e) {
    cpkError.value = 'CPK 趋势数据加载异常'
  } finally {
    cpkLoading.value = false
  }
}

function handleExcludeTop10Change() {
  loadCpkTrend()
}

function handlePhaseChange(val) {
  if (val && filterStore.selectedPhase !== val) {
    filterStore.setSelectedPhase(val)
  }
  loadCpkTrend()
  if (selectedTrendDate.value) {
    loadWarningArticles()
  }
}

watch(
  [
    () => filterStore.selectedPhase,
    () => filterStore.selectedShift,
    () => filterStore.selectedTimeCol,
    () => filterStore.cpkIndicator
  ],
  () => {
    loadCpkTrend()
    if (selectedTrendDate.value) {
      loadWarningArticles()
      loadMachineProcessSankey()
      loadLotCpkTrend()
    }
  }
)

// 防抖重型接口请求，防止拖动日期快速更新导致高并发拥堵
let debounceTimer = null
function debounceLoad(fn, delay = 300) {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fn, delay)
}

function onTab1ArticleDrill(article) {
  if (tab1SelectedArticle.value === article) {
    resetTab1Article()
  } else {
    tab1SelectedArticle.value = article
    loadCpkTrend()
    loadLotCpkTrend()
  }
}

function resetTab1Article() {
  tab1SelectedArticle.value = null
  loadCpkTrend()
  loadLotCpkTrend()
}

const machineCpkDateRange = ref([])

function handleDateSelect(date) {
  selectedTrendDate.value = date
  
  if (date) {
    const dObj = new Date(date)
    const dStart = new Date(dObj.getTime() - 7 * 24 * 60 * 60 * 1000)
    const fmt = (d) => d.toISOString().split('T')[0]
    machineCpkDateRange.value = [fmt(dStart), date]
  }

  loadWarningArticles().then(() => {
    loadMachineProcessSankey()
    loadLotCpkTrend()
  })
}

// ── 预警规格列表 (CPK稳定值) ──────────────────────────────────────────────────
const articles      = ref([])
const isLatestDate  = ref(false)
const articleLoading= ref(false) // 默认不处于 loading 状态，直到用户点击加载
const articleError  = ref(null)
const onlyDeclining = ref(true)
const warningMinSamples = ref(30)
const warningMaxCpk     = ref(0.9)

async function loadWarningArticles() {
  if (!selectedTrendDate.value) {
    articles.value = []
    isLatestDate.value = false
    return
  }
  articleLoading.value = true
  articleError.value   = null
  try {
    const params = {
      indicator: cpkIndicator.value,
      only_declining: onlyDeclining.value,
      study_from: selectedTrendDate.value,
      study_to: selectedTrendDate.value,
      min_samples: warningMinSamples.value,
      time_col: filterStore.selectedTimeCol,
      phase: filterStore.selectedPhase,
      max_cpk: warningMaxCpk.value
    }
    if (tab1SelectedArticle.value) {
      params.article10 = tab1SelectedArticle.value
    }
    const res = await api.getWarningArticles(params)
    if (res.data && res.data.status === 'success') {
      articles.value = res.data.data || []
      isLatestDate.value = !!res.data.is_latest_date
    } else {
      articles.value = []
      isLatestDate.value = false
    }
    if (excludeTop10.value && !tab1SelectedArticle.value) {
      loadCpkTrend()
    }
  } catch (e) {
    articleError.value = '预警规格列表加载异常'
    isLatestDate.value = false
  } finally {
    articleLoading.value = false
  }
}


// ── 机台 CPK / 桑基图 Tab 页签控制 ──────────────────────────────
const machineTabActive = ref('sankey_flow')
const machineMinSamples = ref(50)

const sankeyData = ref({ nodes: [], links: [] })
const sankeyLoading = ref(false)
const sankeyError = ref(null)

const bestSankeyData = ref({ nodes: [], links: [] })
const bestSankeyLoading = ref(false)
const bestSankeyError = ref(null)
const bestPathArticle = ref(null)
const sankeyChartRef = ref(null)
const bestSankeyChartRef = ref(null)

function handleOpenSankeyZoom() {
  if (machineTabActive.value === 'sankey_flow' && sankeyChartRef.value) {
    sankeyChartRef.value.openZoomDialog()
  } else if (machineTabActive.value === 'best_sankey_flow' && bestSankeyChartRef.value) {
    bestSankeyChartRef.value.openZoomDialog()
  }
}

async function loadMachineProcessSankey() {
  if (!selectedTrendDate.value || !tab1SelectedArticle.value) {
    sankeyData.value = { nodes: [], links: [] }
    return
  }
  const articleParam = tab1SelectedArticle.value
  sankeyLoading.value = true
  sankeyError.value = null
  try {
    const effectiveMinSamples = tab1SelectedArticle.value ? 1 : machineMinSamples.value
    const params = {
      article10: articleParam,
      indicator: cpkIndicator.value,
      target_date: selectedTrendDate.value,
      min_samples: effectiveMinSamples
    }
    const res = await api.getMachineProcessSankey(params)
    sankeyData.value = res.data.status === 'success' ? res.data.data : { nodes: [], links: [] }
  } catch (e) {
    sankeyError.value = '单日工序流转桑基图加载异常'
  } finally {
    sankeyLoading.value = false
  }
}

const paramRecommendationData = ref(null)
const paramRecommendationLoading = ref(false)

async function loadParamRecommendation() {
  const articleParam = tab1SelectedArticle.value || bestPathArticle.value
  if (!articleParam) {
    paramRecommendationData.value = null
    return
  }
  paramRecommendationLoading.value = true
  try {
    const params = {
      article: articleParam,
      indicator: cpkIndicator.value,
      target_date: selectedTrendDate.value || undefined
    }

    const res = await api.getParamRecommendation(params)
    paramRecommendationData.value = res.data && res.data.status === 'success' ? res.data : null
  } catch (e) {
    console.error('Failed to load parameter recommendation', e)
    paramRecommendationData.value = null
  } finally {
    paramRecommendationLoading.value = false
  }
}


async function loadMachineBestProcessSankey() {
  const articleParam = tab1SelectedArticle.value || bestPathArticle.value
  if (!articleParam) {
    bestSankeyData.value = { nodes: [], links: [] }
    return
  }
  bestSankeyLoading.value = true
  bestSankeyError.value = null
  try {
    const effectiveMinSamples = (tab1SelectedArticle.value || bestPathArticle.value) ? 1 : machineMinSamples.value
    const params = {
      article10: articleParam,
      indicator: cpkIndicator.value,
      min_samples: effectiveMinSamples
    }
    const res = await api.getMachineBestProcessSankey(params)
    bestSankeyData.value = res.data.status === 'success' ? res.data.data : { nodes: [], links: [] }
    loadParamRecommendation()
  } catch (e) {
    bestSankeyError.value = '全量最佳工序流转路径加载异常'
  } finally {
    bestSankeyLoading.value = false
  }
}


// ── 选中规格关联物料批次 (Lot) 质量追溯 ─────────────────────────
const lotCpkData = ref([])
const lotUslValue = ref(100)
const lotLslValue = ref(null)
const lotCpkLoading = ref(false)
const lotCpkError = ref(null)

async function loadLotCpkTrend(customParams = {}) {
  const articleParam = tab1SelectedArticle.value
  if (!articleParam || !selectedTrendDate.value) {
    lotCpkData.value = []
    return
  }
  lotCpkLoading.value = true
  lotCpkError.value = null
  try {
    const params = {
      article10: articleParam,
      indicator: customParams.indicator || cpkIndicator.value,
      target_date: selectedTrendDate.value,
      min_samples: 1
    }
    if (customParams.component && customParams.component !== '全部工段') {
      params.component = customParams.component
    }
    if (customParams.time_col) {
      params.time_col = customParams.time_col
    }
    if (customParams.dateRange && customParams.dateRange.length === 2) {
      params.start_date = customParams.dateRange[0]
      params.end_date = customParams.dateRange[1]
    } else if (machineCpkDateRange.value && machineCpkDateRange.value.length === 2) {
      params.start_date = machineCpkDateRange.value[0]
      params.end_date = machineCpkDateRange.value[1]
    }
    const res = await api.getLotCpkTrend(params)
    if (res.data.status === 'success') {
      lotCpkData.value = res.data.data
      if (res.data.usl !== undefined) lotUslValue.value = res.data.usl
      lotLslValue.value = res.data.lsl !== undefined ? res.data.lsl : null
    } else {
      lotCpkData.value = []
    }
  } catch (e) {
    lotCpkError.value = '选中规格物料批次追溯数据加载异常'
  } finally {
    lotCpkLoading.value = false
  }
}

function handleLotChartReload(payload) {
  loadLotCpkTrend(payload)
}

function handleMachineMinSamplesChange() {
  if (machineTabActive.value === 'sankey_flow') {
    loadMachineProcessSankey()
  } else if (machineTabActive.value === 'best_sankey_flow') {
    loadMachineBestProcessSankey()
  }
}

watch(
  tab1SelectedArticle,
  (newVal) => {
    if (newVal) {
      bestPathArticle.value = newVal
    }
  }
)

watch(
  [machineTabActive, tab1SelectedArticle, selectedTrendDate, cpkIndicator],
  ([tabVal]) => {
    if (tabVal === 'sankey_flow') {
      loadMachineProcessSankey()
    } else if (tabVal === 'best_sankey_flow') {
      loadMachineBestProcessSankey()
    }
  }
)

// ── 成型机台 CGRS 参数变更记录弹窗状态 ──────────────────────────
const WORKCENTER_COL_LABEL_MAP = {
  gt_workcenter: '生胎成型GT',
  ct_workcenter: '硫化CT',
  tu_first_workcenter: '终检TU',
  tread_workcenter: '胎面',
  bead_workcenter: '胎圈',
  inner_liner_workcenter: '内衬',
  sidewall_workcenter: '胎侧',
  first_breaker_workcenter: '带束层1',
  second_breaker_workcenter: '带束层2',
  first_ply_workcenter: '帘布层1',
  second_ply_workcenter: '帘布层2',
  wound_cap_ply1_workcenter: '冠带层1',
  wound_cap_ply2_workcenter: '冠带层2',
  tb_first_workcenter: '动平衡TB'
}

const cgrsDialogVisible = ref(false)
const cgrsDialogMachine = ref('')
const cgrsDialogDate = ref('')
const cgrsDialogArticle = ref('')
const cgrsDialogIndicator = ref('rfpp')
const cgrsIsTopWarning = ref(false)
const cgrsTopMachines = ref([])

function handleOpenCgrs(payload) {
  cgrsDialogMachine.value = payload.machine || ''
  cgrsDialogDate.value = selectedTrendDate.value || payload.date || ''
  cgrsDialogArticle.value = payload.article || tab1SelectedArticle.value || ''
  cgrsDialogIndicator.value = payload.indicator || cpkIndicator.value || 'rfpp'
  
  const topList = payload.topWarningMachines || []
  // 提取影响度为负的 Top 3 全局预警机台
  const negMachines = topList
    .map(m => (typeof m === 'string' ? m : (m.machine || '')).toUpperCase())
    .filter(Boolean)
  cgrsTopMachines.value = Array.from(new Set(negMachines)).slice(0, 3)
  
  const rank1 = topList[0]
  const curMach = (payload.machine || '').toUpperCase()
  const rank1Name = typeof rank1 === 'string' ? rank1.toUpperCase() : (rank1?.machine || '').toUpperCase()
  const isRank1 = rank1Name && (rank1Name === curMach || curMach.includes(rank1Name) || rank1Name.includes(curMach))
  cgrsIsTopWarning.value = !!isRank1
  
  cgrsDialogVisible.value = true
}

const combinationTreeDialogVisible = ref(false)
const combinationTreeDialogRendered = ref(false)

watch(combinationTreeDialogVisible, (val) => {
  if (!val) {
    combinationTreeDialogRendered.value = false
  }
})

function handleCombinationTreeDialogOpened() {
  combinationTreeDialogRendered.value = true
}


// ── 监听状态变动刷新数据 ──────────────────────────────────────

watch(
  () => filterStore.minYieldThreshold,
  () => {
    selectedTrendDate.value = null
    articles.value = []
    onlyBelowMean.value = false
  }
)

watch(
  [() => filterStore.baselineRange, () => filterStore.studyRange],
  () => {
    selectedTrendDate.value = null
    articles.value = []
    onlyBelowMean.value = false
    loadCpkTrend()
  }
)

watch(cpkIndicator, () => {
  if (selectedTrendDate.value) {
    loadWarningArticles()
    loadLotCpkTrend()
  }
})

watch(() => filterStore.selectedTimeCol, () => {
  loadCpkTrend()
  if (selectedTrendDate.value) {
    loadWarningArticles()
    loadLotCpkTrend()
  }
  if (machineTabActive.value === 'sankey_flow') {
    loadMachineProcessSankey()
  } else if (machineTabActive.value === 'best_sankey_flow') {
    loadMachineBestProcessSankey()
  }
})

watch(() => tab1SelectedArticle.value, (newVal) => {
  if (cpkIndicator.value === 'cony') {
    if (bestPathArticle.value !== newVal) {
      bestPathArticle.value = newVal
      loadMachineBestProcessSankey()
    }
  }
})

watch(() => bestPathArticle.value, (newVal) => {
  if (cpkIndicator.value === 'cony') {
    if (tab1SelectedArticle.value !== newVal) {
      tab1SelectedArticle.value = newVal
      loadCpkTrend()
    }
  }
})

watch(machineTabActive, (newTab) => {
  if (newTab === 'sankey_flow') {
    loadMachineProcessSankey()
  } else if (newTab === 'best_sankey_flow') {
    loadMachineBestProcessSankey()
  }
})

// 全量规格列表
const allArticles = ref([])

async function loadAllArticles() {
  try {
    const res = await api.getAllArticles()
    if (res.data.status === 'success') {
      allArticles.value = res.data.data
    }
  } catch (e) {
    console.error('全量规格加载失败', e)
  }
}

// ── 初始挂载 ──────────────────────────────────────────────────
onMounted(async () => {
  await Promise.all([
    loadCpkTrend(),
    loadAllArticles()
  ])
})

</script>

<style scoped>
.app-container {
  max-width: min(1600px, 98vw);
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-row {
  width: 100%;
  display: flex;
  gap: 20px;
}
.section-row.two-col {
  align-items: stretch;
}

.card {
  background-color: #fff;
  border: 1px solid #e5e8ef;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
}
.full-width {
  width: 100%;
}

.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #f0f2f5;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.card-header-tabs {
  border-bottom: 1px solid #f0f2f5;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text-primary);
}

.card-body {
  padding: 20px;
  flex: 1;
}

.tab-pane-content {
  padding: 16px 20px 20px 20px;
}

.filter-row-sub {
  margin-bottom: 12px;
}

.text-muted {
  font-size: 12px;
  color: var(--c-text-secondary);
}

.mt-4 { margin-top: 4px; }
.mt-8 { margin-top: 8px; }
.mt-16 { margin-top: 16px; }
.text-bold { font-weight: 600; }
.font-mono { font-family: 'JetBrains Mono', monospace; }
.text-danger { color: var(--c-danger); }

/* 面板空提示 */
.empty-period-card {
  padding: 60px 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  background-color: #fff;
  border: 1px solid #e5e8ef;
  border-radius: var(--radius-md);
}

/* 导航面包屑 */
.breadcrumb {
  font-size: 11px;
}
.breadcrumb-link {
  color: var(--c-accent);
  cursor: pointer;
  font-weight: 500;
}
.breadcrumb-link:hover {
  text-decoration: underline;
}
.breadcrumb-sep {
  margin: 0 4px;
  color: var(--c-text-muted);
}
.breadcrumb-current {
  color: var(--c-text-secondary);
}

.help-icon {
  font-size: 14px;
  color: var(--c-text-muted);
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease);
}
.help-icon:hover {
  color: var(--c-accent);
}

.jump-link {
  padding: 0;
  height: auto;
  font-size: 13px;
}
.jump-link:hover {
  text-decoration: underline;
}



/* ── 数据时间胶囊徽章样式 (类似服务状态胶囊) ── */
.data-update-capsule {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 3px 12px;
  border-radius: 20px;
  box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.04);
  margin-left: 8px;
  vertical-align: middle;
}

.capsule-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.4; transform: scale(0.9); }
}

.capsule-label {
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
}

.capsule-val {
  font-size: 12px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  color: #1e293b;
}

/* ── 剔除异常值按钮高亮样式 (与 Main Hall 选中橙色/黄色主题保持一致) ── */
.exclude-outliers-btn {
  margin-left: 10px;
  font-weight: 500 !important;
  border-radius: 20px !important;
  height: 28px !important;
  line-height: 28px !important;
  padding: 0 14px !important;
  font-size: 12px !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
  background: #f8fafc !important;
  border: 1px solid #e2e8f0 !important;
  color: #475569 !important;
}

.exclude-outliers-btn:hover {
  background-color: #fffbeb !important;
  border-color: #fde68a !important;
  color: #b45309 !important;
}

.exclude-outliers-btn.is-active {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
  border-color: #d97706 !important;
  color: #ffffff !important;
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3) !important;
  font-weight: 700 !important;
}

.exclude-outliers-btn.is-active:hover {
  background: linear-gradient(135deg, #d97706 0%, #b45309 100%) !important;
  box-shadow: 0 3px 10px rgba(245, 158, 11, 0.4) !important;
}

/* ── 核心规格行动表黄色风格统一控件 ── */
.spec-focus-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  line-height: 20px;
  padding: 0 9px;
  border-radius: 11px;
  background-color: #fffbeb;
  border: 1px solid #fde68a;
  color: #b45309;
  font-weight: 700;
  font-size: 11.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  box-shadow: 0 1px 2px rgba(245, 158, 11, 0.08);
}

.btn-warm-outline {
  background: #ffffff !important;
  border: 1px solid #fde68a !important;
  color: #92400e !important;
  font-weight: 600 !important;
  border-radius: 14px !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.btn-warm-outline:hover {
  background: #fffbeb !important;
  border-color: #f59e0b !important;
  color: #78350f !important;
  box-shadow: 0 2px 6px rgba(245, 158, 11, 0.15) !important;
  transform: translateY(-1px);
}

.btn-warm-primary {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
  border: 1px solid #d97706 !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  border-radius: 14px !important;
  box-shadow: 0 2px 6px rgba(245, 158, 11, 0.25) !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.btn-warm-primary:hover {
  background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.35) !important;
  transform: translateY(-1px);
}
</style>
