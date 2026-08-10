<template>
  <div class="app-container">
    
    <!-- Row 1: 加权 CPK 控制区间分析 (全宽) -->
    <section class="section-row">
      <div class="card full-width">
        <div class="card-header">
          <div>
            <div class="card-title" style="display: inline-flex; align-items: center; gap: 4px;">
              <span>{{ tab1SelectedArticle ? tab1SelectedArticle + ' · ' : '' }}{{ cpkIndicator === 'cony' ? '整体指标预览 (实际值指标)' : '整体指标预览 (CPK指标)' }}</span>
              <el-tooltip placement="top" raw-content>
                <template #content>
                  <div v-if="cpkIndicator === 'cony'" style="max-width: 290px; font-size: 12px; line-height: 1.6; padding: 4px;">
                    <strong style="color: #10b981;">实际测量值分析 (CONY)：</strong><br/>
                    以规格 (Article10) 为基本单元，展示当前规格下实际测量数据的每日加权均值变化曲线。<br/><br/>
                    <strong style="color: #f59e0b;">SPC 动态控制线：</strong><br/>
                    本指标无固定标准限。控制线基于全量数据动态计算均值 (CL) 和标准差 (σ)，绘制：<br/>
                    * UCL (上限控制限) = Mean + 3σ<br/>
                    * LCL (下限控制限) = Mean - 3σ<br/>
                    * 警戒线分别为 Mean ± 1σ 与 Mean ± 2σ。数据点超出 1σ 范围时自动触发预警并高亮显示。
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
            </div>
            <div class="breadcrumb mt-4" v-if="tab1SelectedArticle" style="display: flex; align-items: center; gap: 8px;">
              <el-button size="small" type="primary" plain :icon="RefreshLeft" @click="resetTab1Article()">全部规格 (重置)</el-button>
              <span class="breadcrumb-sep">›</span>
              <span class="breadcrumb-current" style="font-weight: 600; color: #1e293b; font-family: 'JetBrains Mono', monospace; font-size: 13px;">{{ tab1SelectedArticle }}</span>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 16px;">
            <div style="display: flex; align-items: center; gap: 6px;" v-if="cpkIndicator === 'cony'">
              <span style="font-size: 12px; color: var(--el-text-color-regular); font-weight: 500;">选择规格:</span>
              <el-select
                v-model="tab1SelectedArticle"
                filterable
                clearable
                placeholder="全部规格"
                size="small"
                style="width: 170px;"
                @change="loadCpkTrend"
              >
                <el-option
                  v-for="item in (allArticles.length > 0 ? allArticles : (filterStore.filterArticles || articles))"
                  :key="item.article10 || item"
                  :label="item.article10 || item"
                  :value="item.article10 || item"
                />
              </el-select>
            </div>
            
            <el-checkbox
              v-if="!tab1SelectedArticle"
              v-model="excludeTop10"
              size="small"
              style="margin-left: 10px; font-weight: 500;"
              @change="handleExcludeTop10Change"
            >
              🚫 剔除 Top 10 预警规格
            </el-checkbox>
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


    <!-- Row 2: 智能诊断预警卡片面板 (已暂时关闭以提升页面响应速度) -->
    <section class="section-row" v-if="false">
      <InsightsPanel
        :alerts="alerts"
        :loading="insightsLoading"
        @select-article="onTab1ArticleDrill"
        @select-machine="handleSelectMachine"
      />
    </section>

    <!-- Row 3: 规格排行与机台排行并排 -->
    <section class="section-row two-col">
      <!-- 左侧: 预警规格型号排行 -->
      <div class="card" style="min-width:0; flex: 3.5; display: flex; flex-direction: column; overflow: hidden;">
        <template v-if="cpkIndicator === 'cony'">
          <div style="height: 100%; min-height: 585px; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 24px; text-align: center;">
            <el-icon size="40" style="color: var(--el-color-warning); margin-bottom: 12px;"><WarningFilled /></el-icon>
            <div style="font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); margin-bottom: 6px;">
              模块已停用
            </div>
            <div style="font-size: 12px; color: var(--el-text-color-secondary); max-width: 260px; line-height: 1.6;">
              当前研究指标为 [CONY] 。此模块仅在 rfpp 和 rfh1 指标模式下启用。
            </div>
          </div>
        </template>
        <div v-else-if="!selectedTrendDate" class="empty-period-card" style="height: 100%; display: flex; align-items: center; justify-content: center; min-height: 585px;">
          <el-empty description="请点击上方 CPK 趋势图的任意数据点以载入该天的规格预警分析" :image-size="60" />
        </div>
        <template v-else>
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; gap: 16px; padding-bottom: 8px;">
            <div class="card-title" style="display: inline-flex; align-items: center; gap: 4px;">
              <span>{{ cpkIndicator === 'weight' ? '生产偏差贡献规格排行' : 'CPK 负向贡献规格排行' }} - {{ selectedTrendDate }}</span>
              <el-tooltip placement="top" raw-content>
                <template #content>
                  <div style="max-width: 280px; font-size: 12px; line-height: 1.5;">
                    <template v-if="cpkIndicator === 'weight'">
                      <strong>偏差贡献排行逻辑：</strong><br/>
                      计算当日规格对全厂整体偏差率的拉低贡献度：<br/>
                      <code>贡献度 = (单规格偏差率 - 全厂整体偏差率) × 规格产量占比</code><br/><br/>
                      系统筛选出当天影响整体偏差最大的规格，按拉低贡献大小进行降序排列。
                    </template>
                    <template v-else>
                      <strong>负向贡献排行逻辑 (方案 B)：</strong><br/>
                      计算当日规格对全区加权综合 CPK 的负向拉低贡献度：<br/>
                      <code>CPK 负向贡献 = (当日系统综合 CPK - 单规格 CPK) × 规格产量 (N)</code><br/><br/>
                      系统筛选出当天 CPK 低于全日系统加权平均值的规格，按拉低贡献度大小进行降序排列（排在最前的规格即是对整体质量影响最大的核心瓶颈规格）。
                    </template>
                  </div>
                </template>
                <el-icon class="help-icon"><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0; white-space: nowrap;">
              <span style="font-size: 12px; color: var(--el-text-color-regular);">日产量门槛:</span>
              <el-input-number v-model="warningMinSamples" :min="1" :max="1000" size="small" style="width: 90px;" @change="loadWarningArticles" />
            </div>
          </div>
          
          <!-- 公式的警示说明框 (放在 header 之外，宽度自适应铺满) -->
          <div style="padding: 0 20px 8px 20px;">
            <el-alert
              type="warning"
              :closable="false"
              style="padding: 8px 12px; background-color: #fffbeb; border: 1px solid #fef3c7; border-radius: 6px; width: 100%;"
            >
              <template #title>
                <div style="color: #b45309; font-size: 12px; line-height: 1.6; display: flex; flex-direction: column; gap: 4px;">
                  <div style="color: #b45309; font-weight: bold;">
                    {{ cpkIndicator === 'weight' ? '排查依据公式：贡献度 = (单规格偏差率 - 全厂整体偏差率) × 规格产量占比' : '排查依据公式：贡献度 = (系统综合 CPK - 单规格 CPK) × 规格产量 (N)' }}
                  </div>
                  <div style="color: #78350f; font-size: 11px; font-weight: normal;">
                    {{ cpkIndicator === 'weight' ? '⚠️ 说明：贡献度数值（绝对值）越大，表明该规格拉大或偏离整体均值的问题越严重。红色圆点标志表示该规格的主要责任机台已识别。' : '⚠️ 说明：贡献度数值越大，表明该规格拉低整体质量的问题越严重。红色圆点标志表示该规格的主要责任机台已识别。' }}
                  </div>
                </div>
              </template>
            </el-alert>
          </div>
          
          <div class="card-body" style="min-height: 585px; height: 585px;">
            <ArticleBarChart
              :data="articles"
              :loading="articleLoading"
              :error="articleError"
              :selected-article="tab1SelectedArticle"
              :indicator="cpkIndicator"
              @drill-down="onTab1ArticleDrill"
            />
          </div>
        </template>
      </div>


      <!-- 右侧: 机台 CPK (avg + 3σ) 数据表格 与 生产工序流转图 Tab 页面 -->
      <div class="card" style="min-width:0; flex: 6.5; display: flex; flex-direction: column; overflow: hidden;">
        <div v-if="!selectedTrendDate" class="empty-period-card" style="height: 100%; display: flex; align-items: center; justify-content: center; min-height: 585px;">
          <el-empty description="请点击上方 CPK 趋势图的任意数据点以载入工序流转及路径分析" :image-size="60" />
        </div>
        <template v-else>
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
              <!-- 仅在 CPK 模式下显示 Tab 切换与诊断 -->
              <template v-if="cpkIndicator !== 'cony'">
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
              </template>
              <span v-else style="font-size: 14px; font-weight: 600; color: var(--el-text-color-primary);">全量最佳生产路径</span>

              <!-- Tab 1 / Tab 2 显示静态绑定规格 Tag (仅在非 cony 且非 best 模式下) -->
              <template v-if="cpkIndicator !== 'cony' && machineTabActive !== 'best_sankey_flow'">
                <el-tag v-if="tab1SelectedArticle" size="small" type="success">
                  规格: {{ tab1SelectedArticle }}
                </el-tag>
                <el-tag v-else size="small" type="info">
                  规格: {{ articles[0]?.article10 || '未选中' }}
                </el-tag>
              </template>

              <!-- Tab 3 显示可搜索/可输入的规格选择框 (best 模式，或在 cony 指标下直接显示) -->
              <template v-else>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="font-size: 12px; color: var(--el-text-color-regular); font-weight: 500;">分析规格:</span>
                  <el-select
                    v-model="bestPathArticle"
                    filterable
                    clearable
                    placeholder="选择或输入 10 位规格"
                    size="small"
                    style="width: 170px;"
                    @change="loadMachineBestProcessSankey"
                  >
                    <el-option
                      v-for="item in (allArticles.length > 0 ? allArticles : (filterStore.filterArticles || articles))"
                      :key="item.article10 || item"
                      :label="item.article10 || item"
                      :value="item.article10 || item"
                    />
                  </el-select>
                </div>
              </template>
            </div>
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 12px; color: var(--el-text-color-regular);">样本门槛:</span>
                <el-input-number v-model="machineMinSamples" :min="1" :max="1000" size="small" style="width: 90px;" @change="handleMachineMinSamplesChange" />
              </div>
            </div>
          </div>

          <div class="card-body" style="min-height: 585px; height: 585px; padding-top: 10px;">
            <!-- Tab 2: 单日生产工序流转桑基图 -->
            <MachineProcessSankeyChart
              v-if="machineTabActive === 'sankey_flow'"
              :sankey-data="sankeyData"
              :loading="sankeyLoading"
              :error="sankeyError"
              :indicator="cpkIndicator"
              :tolerance="filterStore.weightTolerance"
              @click-node="handleSankeyNodeClick"
            />
            <!-- Tab 3: 全量数据集最佳生产路径桑基图 -->
            <MachineBestProcessSankeyChart
              v-else-if="machineTabActive === 'best_sankey_flow'"
              :sankey-data="bestSankeyData"
              :loading="bestSankeyLoading"
              :error="bestSankeyError"
              :indicator="cpkIndicator"
              :tolerance="filterStore.weightTolerance"
              @click-node="handleSankeyNodeClick"
            />
          </div>
        </template>
      </div>
    </section>

    <!-- Row 3.5: 横跨两列 (Full-Width 通栏): 物料批次分析卡片 -->
    <section class="section-row" v-if="selectedTrendDate">
      <div class="card full-width" style="width: 100%;">
        <template v-if="cpkIndicator === 'cony'">
          <div style="height: 250px; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 24px; text-align: center; width: 100%;">
            <el-icon size="40" style="color: var(--el-color-warning); margin-bottom: 12px;"><WarningFilled /></el-icon>
            <div style="font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); margin-bottom: 6px;">
              模块已停用
            </div>
            <div style="font-size: 12px; color: var(--el-text-color-secondary); max-width: 320px; line-height: 1.6;">
              当前研究指标为 [CONY] 。此模块仅在 rfpp 和 rfh1 指标模式下启用。
            </div>
          </div>
        </template>
        <template v-else>
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
              <div class="card-title" style="display: inline-flex; align-items: center; gap: 6px;">
                <span>物料批次分析</span>
              </div>
              <el-tag v-if="tab1SelectedArticle" size="small" type="success">
                规格: {{ tab1SelectedArticle }}
              </el-tag>
              <el-tag v-else size="small" type="info">
                规格: {{ articles[0]?.article10 || '未选中' }}
              </el-tag>
              <span style="font-size: 12px; color: var(--el-text-color-secondary);">
                | 日期: {{ selectedTrendDate }}
              </span>
            </div>
          </div>
          <div class="card-body" style="min-height: 380px; padding-top: 10px;">
            <ArticleLotCpkChart
              :lot-data="lotCpkData"
              :usl-value="lotUslValue"
              :loading="lotCpkLoading"
              :error="lotCpkError"
              :selected-article="tab1SelectedArticle || (articles[0]?.article10 ?? '')"
              :target-date="selectedTrendDate"
              :indicator="cpkIndicator"
              @reload="handleLotChartReload"
            />
          </div>
        </template>
      </div>
    </section>

    <!-- Row 4: 制造工序主导路径表与深度归因诊断面板 (已暂时关闭以提升页面响应速度) -->
    <section class="section-row two-col diagnostics-panel-section" v-if="false">
      <!-- 左侧: 制造工序主导路径 / 双机台联合风险 Tab 切换 -->
      <div class="card" style="min-width:0; flex:1.3; height: 680px; display: flex; flex-direction: column;" v-loading="pathsLoading || combLoading">
        <el-tabs v-model="row4ActiveTab" class="row4-custom-tabs">
          <!-- Tab 1: 主导路径 -->
          <el-tab-pane name="paths">
            <template #label>
              <span style="display:inline-flex;align-items:center;gap:4px;">
                工艺主导路径
                <el-tooltip placement="top" raw-content>
                  <template #content>
                    <div style="max-width:300px;font-size:12px;line-height:1.6">
                      <strong>计算逻辑：</strong><br/>
                      基于 KMeans 将研究期批次分离为「异常簇」与「正常簇」，每个工序取集中度最高的机台作为主导机台。<br/><br/>
                      <strong>工艺集中度</strong> = 该机台在本簇内的出现频率<br/>
                      <strong>全量自然基准</strong> = 该机台在全量样本的出现频率<br/>
                      <strong>Step Lift</strong> = 工艺集中度 / 全量自然基准<br/><br/>
                      Step Lift ≥ 1.5 视为显著异常富集，意味着异常批次对该机台存在超额依赖。
                    </div>
                  </template>
                  <el-icon class="help-icon" style="font-size:12px;"><QuestionFilled /></el-icon>
                </el-tooltip>
              </span>
            </template>
              <div class="tab-pane-content">
                <div class="filter-row-sub">
                  <div class="text-muted"></div>
                  <!-- 自定义下划线选中样式的子簇选择器 -->
                <div class="cluster-tab-group mt-8" v-if="filterStore.hasAnalysisPeriod">
                  <button
                    v-for="key in Object.keys(pathsData)"
                    :key="key"
                    :class="['cluster-tab-btn', activePathTab === key ? (key.startsWith('anomaly_cluster_') ? 'active-anomaly' : 'active-normal') : '']" 
                    @click="activePathTab = key"
                  >
                    {{ getPathTabName(key) }}
                  </button>
                </div>
              </div>

              <div v-if="!filterStore.hasAnalysisPeriod" class="empty-period-card" style="padding: 20px 0; border: none; box-shadow: none;">
                <el-empty description="请先在左侧选择“基准期”与“研究期”以激活工艺路径对比聚类诊断" :image-size="60" />
              </div>
              <template v-else>
                <!-- 警告 Banner -->
                <el-alert
                  v-if="pathSuspects.length"
                  title="算法判定：工艺路径富集机台警报"
                  type="warning"
                  show-icon
                  :closable="false"
                  style="margin-bottom:12px; margin-top: 8px;"
                >
                  <template #default>
                    <div style="font-size:12px;line-height:1.6">
                      对比分析发现，在当前的工艺组画像中，以下设备展现出高度的异常富集：
                      <div v-for="item in pathSuspects" :key="item.step + item.machine">
                        • <strong>{{ item.cluster }}</strong> 的 <strong>{{ item.step }}</strong> 工序，
                        机台 <strong>{{ item.machine }}</strong> 发生富集（提升度达 <strong>{{ item.lift }}x</strong>）。
                      </div>
                      这反映了该设备加工参数偏离，点击下方表格内机台名称可直接跳转开展物料批次诊断。
                    </div>
                  </template>
                </el-alert>

                <!-- 路径对照表格 -->
                <el-table
                  :data="currentPathList"
                  size="small"
                  border
                  stripe
                  style="width:100%"
                  :cell-class-name="pathCellClass"
                >
                  <el-table-column label="制造工序步骤 (Step)" width="130">
                    <template #default="{ row }">
                      <span
                        class="step-interactive-link"
                        :class="{ 'is-active': selectedWorkcenter === row.step }"
                        @click="toggleWorkcenterFilter(row.step)"
                      >
                        {{ row.step }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="首选设备机台 (Dominant Machine)">
                    <template #default="{ row }">
                      <button
                        :class="['machine-tag-btn', 'step-' + getStepPrefix(row.step)]" 
                        @click="handleTableMachineJump(row)"
                      >
                        {{ row.machine }}
                      </button>
                    </template>
                  </el-table-column>
                  <el-table-column prop="concentration_ratio" label="工艺集中度" align="right" width="110">
                    <template #default="{ row }">{{ row.concentration_ratio }}%</template>
                  </el-table-column>
                  <el-table-column prop="natural_baseline" label="全量自然基准" align="right" width="110">
                    <template #default="{ row }">{{ row.natural_baseline }}%</template>
                  </el-table-column>
                  <el-table-column prop="step_lift" label="Step Lift" align="right" width="100">
                    <template #default="{ row }">
                      <span v-if="row.step_lift >= 1.5" class="lift-badge-danger">{{ row.step_lift }}x</span>
                      <span v-else class="lift-badge-normal">{{ row.step_lift }}x</span>
                    </template>
                  </el-table-column>
                </el-table>
              </template>
            </div>
          </el-tab-pane>

          <!-- Tab 2: 联合风险 (若 combinations 无数据则 disabled) -->
          <el-tab-pane name="combinations" :disabled="combinations.length === 0">
            <template #label>
              <span style="display:inline-flex;align-items:center;gap:4px;">
                双机台联合风险
                <el-tooltip placement="top" raw-content>
                  <template #content>
                    <div style="max-width:300px;font-size:12px;line-height:1.6">
                      <strong>计算逻辑：</strong><br/>
                      统计研究期内同时流经机台 A 与机台 B 的物料批次（联合排产量），计算该批次组合的异常率。<br/><br/>
                      <strong>联合异常率</strong> = 联合异常件数 / 联合排产量<br/>
                      <strong>联合提升度</strong> = 联合异常率 / 全局异常基准率<br/><br/>
                      提升度 > 1 表示双机台组合存在交叉污染或工艺干涉放大效应，值越高风险越大。
                    </div>
                  </template>
                  <el-icon class="help-icon" style="font-size:12px;"><QuestionFilled /></el-icon>
                </el-tooltip>
              </span>
            </template>
            <div class="tab-pane-content">
              <div class="text-muted" style="margin-bottom: 12px;">评估在研究期内同时流经特定两个设备的产品坏损几率，查找跨工序交叠溢出风险。</div>
              <el-table :data="combinations" size="small" border stripe style="width:100%">
                <el-table-column label="工位 A" width="90">
                  <template #default="{ row }">{{ row.wc_a.replace('_workcenter', '') }}</template>
                </el-table-column>
                <el-table-column label="机台 A" prop="machine_a" />
                <el-table-column label="工位 B" width="90">
                  <template #default="{ row }">{{ row.wc_b.replace('_workcenter', '') }}</template>
                </el-table-column>
                <el-table-column label="机台 B" prop="machine_b" />
                <el-table-column label="联合排产" prop="total_matches" align="right" width="80" />
                <el-table-column label="联合异常" prop="anomaly_matches" align="right" width="80" />
                <el-table-column label="联合异常率" align="right" width="95">
                  <template #default="{ row }">{{ row.joint_anomaly_rate }}%</template>
                </el-table-column>
                <el-table-column label="联合提升度" align="right" width="95">
                  <template #default="{ row }">
                    <span class="text-danger text-bold">{{ row.joint_lift }}x</span>
                  </template>
                </el-table-column>
                <el-table-column label="工艺瓶颈判定说明" min-width="150">
                  <template #default="{ row }">
                    <span style="color:#d97706; font-weight:500; font-size: 11px;">
                      流经 {{ row.machine_a }} + {{ row.machine_b }} 时，异常几率提升至 {{ row.joint_lift }} 倍。
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 右侧: 深度归因诊断面板 (与左侧等高 680px) -->
      <div class="card" style="flex:1; min-width:0; height: 680px; display: flex; flex-direction: column; overflow: hidden;">
        <div v-if="!filterStore.hasAnalysisPeriod" class="empty-period-card" style="height: 100%; display: flex; align-items: center; justify-content: center;">
          <el-empty description="请在左侧选择“基准期”和“研究期”以激活深度根因诊断模块" :image-size="60">
            <div class="text-muted mt-8">该模块将自动结合对照直方图判定原料批次缺陷或设备精度漂移。</div>
          </el-empty>
        </div>
        <DiagnosticsPanel
          v-else
          :baseline-range="filterStore.baselineRange"
          :study-range="filterStore.studyRange"
        />
      </div>
    </section>

    <!-- 机台 CPK 趋势下钻弹窗 -->
    <MachineCpkTrendDialog
      v-model:visible="trendDialogVisible"
      :machine="trendDialogMachine"
      :workcenter-col="trendDialogWorkcenterCol"
      :article10="trendDialogArticle10"
      :mode="trendDialogMode"
      :indicator="cpkIndicator"
      :selected-date="selectedTrendDate"
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
          :selected-article="tab1SelectedArticle || (articles[0]?.article10 ?? null)"
          :start-date="machineCpkDateRange && machineCpkDateRange.length === 2 ? machineCpkDateRange[0] : null"
          :end-date="machineCpkDateRange && machineCpkDateRange.length === 2 ? machineCpkDateRange[1] : null"
          :target-date="selectedTrendDate"
          :indicator="cpkIndicator"
          :min-samples="machineMinSamples"
          :tolerance="filterStore.weightTolerance"
        />
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useFilterStore } from '../store/filter.js'
import { api } from '../api/index.js'
import TrendChart from '../components/charts/TrendChart.vue'
import ArticleBarChart from '../components/charts/ArticleBarChart.vue'
import MachineCpkTrendDialog from '../components/dialogs/MachineCpkTrendDialog.vue'
import MachineProcessSankeyChart from '../components/charts/MachineProcessSankeyChart.vue'
import MachineBestProcessSankeyChart from '../components/charts/MachineBestProcessSankeyChart.vue'
import MachineCombinationTree from '../components/charts/MachineCombinationTree.vue'
import ArticleLotCpkChart from '../components/charts/ArticleLotCpkChart.vue'
import InsightsPanel from '../components/panels/InsightsPanel.vue'
import DiagnosticsPanel from '../components/panels/DiagnosticsPanel.vue'

import { QuestionFilled, RefreshLeft } from '@element-plus/icons-vue'

const filterStore = useFilterStore()

// 排序控制 (固定使用异常贡献率与提升度)

// Row 4 Active Tab
const row4ActiveTab = ref('paths')

// Tab 1 本地下钻规格状态
const tab1SelectedArticle = ref(null)

// 同步选中规格至全局 Store，以便导航栏同步展示
watch(() => filterStore.selectedArticle, (newVal) => {
  if (tab1SelectedArticle.value !== newVal) {
    tab1SelectedArticle.value = newVal
  }
}, { immediate: true })

watch(() => tab1SelectedArticle.value, (newVal) => {
  if (filterStore.selectedArticle !== newVal) {
    filterStore.selectedArticle = newVal
  }
})

const selectedWorkcenter = ref(null)

// CPK 趋势与指标状态
const cpkIndicator = computed(() => filterStore.cpkIndicator)
const selectedTrendDate = ref(null) // 点击选中日期
const cpkData = ref({})
const cpkLoading = ref(false)
const cpkError = ref(null)
const excludeTop10 = ref(false)

async function loadCpkTrend() {
  cpkLoading.value = true
  cpkError.value = null
  try {
    const params = {}
    params.grain = filterStore.trendGranularity
    if (tab1SelectedArticle.value) {
      params.article10 = tab1SelectedArticle.value
    } else if (excludeTop10.value && articles.value && articles.value.length > 0) {
      const top10Articles = articles.value.slice(0, 10).map(a => a.article10).filter(Boolean)
      if (top10Articles.length > 0) {
        params.exclude_articles = top10Articles.join(',')
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

// 动态计算图表容器高度，防止 ECharts 机台过多时挤压
const machineChartHeight = computed(() => {
  const count = machines.value?.length || 0
  return count > 0 ? `${Math.max(380, count * 28 + 40)}px` : '380px'
})

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
    selectedWorkcenter.value = null
    loadCpkTrend()
    loadLotCpkTrend()
  }
}

function resetTab1Article() {
  tab1SelectedArticle.value = null
  selectedWorkcenter.value = null
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

function toggleWorkcenterFilter(step) {
  if (selectedWorkcenter.value === step) {
    selectedWorkcenter.value = null
  } else {
    selectedWorkcenter.value = step
  }
}

// ── 预警卡片 ──────────────────────────────────────────────────
const insights = ref({})
const insightsLoading = ref(false)
const alerts = computed(() => insights.value.alerts ?? [])

async function loadInsights() {
  return // 已关闭预警卡片请求以提升性能
}

// ── 趋势数据 (对兼容性做桩函数处理) ─────────────────────────
const trendData    = ref([])
const trendLoading = ref(false)
const trendError   = ref(null)

async function loadTrend() {
  // 产量与异常率已重构为 CPK，此处保留桩函数
}

// ── 预警规格列表 (CPK稳定值) ──────────────────────────────────────────────────
const articles      = ref([])
const articleLoading= ref(false) // 默认不处于 loading 状态，直到用户点击加载
const articleError  = ref(null)
const onlyDeclining = ref(true)
const warningMinSamples = ref(30)

async function loadWarningArticles() {
  if (!selectedTrendDate.value) {
    articles.value = []
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
      min_samples: warningMinSamples.value
    }
    const res = await api.getWarningArticles(params)
    articles.value = res.data.status === 'success' ? res.data.data : []
    if (excludeTop10.value && !tab1SelectedArticle.value) {
      loadCpkTrend()
    }
  } catch (e) {
    articleError.value = '预警规格列表加载异常'
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

async function loadMachineProcessSankey() {
  if (!selectedTrendDate.value) {
    sankeyData.value = { nodes: [], links: [] }
    return
  }
  const articleParam = tab1SelectedArticle.value || (articles.value[0]?.article10 ?? null)
  if (!articleParam) {
    sankeyData.value = { nodes: [], links: [] }
    return
  }
  sankeyLoading.value = true
  sankeyError.value = null
  try {
    const params = {
      article10: articleParam,
      indicator: cpkIndicator.value,
      target_date: selectedTrendDate.value,
      min_samples: machineMinSamples.value
    }
    const res = await api.getMachineProcessSankey(params)
    sankeyData.value = res.data.status === 'success' ? res.data.data : { nodes: [], links: [] }
  } catch (e) {
    sankeyError.value = '单日工序流转桑基图加载异常'
  } finally {
    sankeyLoading.value = false
  }
}

async function loadMachineBestProcessSankey() {
  const articleParam = bestPathArticle.value || tab1SelectedArticle.value || (articles.value[0]?.article10 ?? null)
  if (!articleParam) {
    bestSankeyData.value = { nodes: [], links: [] }
    return
  }
  bestSankeyLoading.value = true
  bestSankeyError.value = null
  try {
    const params = {
      article10: articleParam,
      indicator: cpkIndicator.value,
      min_samples: machineMinSamples.value
    }
    const res = await api.getMachineBestProcessSankey(params)
    bestSankeyData.value = res.data.status === 'success' ? res.data.data : { nodes: [], links: [] }
  } catch (e) {
    bestSankeyError.value = '全量最佳工序流转路径加载异常'
  } finally {
    bestSankeyLoading.value = false
  }
}

// ── 选中规格关联物料批次 (Lot) 质量追溯 ─────────────────────────
const lotCpkData = ref([])
const lotUslValue = ref(100)
const lotCpkLoading = ref(false)
const lotCpkError = ref(null)

async function loadLotCpkTrend(customParams = {}) {
  const articleParam = tab1SelectedArticle.value || (articles.value[0]?.article10 ?? null)
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
      if (res.data.usl) lotUslValue.value = res.data.usl
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

// ── 机台 CPK 历史下钻弹窗状态 ────────────────────────────────────
const trendDialogVisible = ref(false)
const trendDialogMachine = ref('')
const trendDialogWorkcenterCol = ref('')
const trendDialogArticle10 = ref(null)
const trendDialogMode = ref(null)

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

function handleOpenMachineTrend(payload) {
  trendDialogMachine.value = payload.machine
  trendDialogWorkcenterCol.value = payload.workcenterCol
  trendDialogArticle10.value = payload.article10
  trendDialogMode.value = payload.mode || null
  trendDialogVisible.value = true
}

function handleSankeyNodeClick(payload) {
  const articleParam = tab1SelectedArticle.value || (articles.value[0]?.article10 ?? null)
  handleOpenMachineTrend({
    machine: payload.machine,
    workcenterCol: payload.workcenterCol,
    article10: articleParam
  })
}


// ── 工位机台排行 ──────────────────────────────────────────────
const machines      = ref([])
const machineLoading= ref(true)
const machineError  = ref(null)

async function loadMachines() {
  machineLoading.value = true
  machineError.value   = null
  try {
    const params = {
      limit: 20,
      min_yield: filterStore.minYieldThreshold,
      sort_by: 'step_lift'
    }
    if (tab1SelectedArticle.value) {
      params.article10 = tab1SelectedArticle.value
    }
    if (selectedWorkcenter.value) {
      params.workcenter_col = selectedWorkcenter.value
      if (filterStore.hasAnalysisPeriod && activePathTab.value) {
        if (activePathTab.value.startsWith('anomaly_cluster_')) {
          params.cluster_id = Number(activePathTab.value.replace('anomaly_cluster_', ''))
          params.cluster_type = 'anomaly'
        } else if (activePathTab.value.startsWith('normal_cluster_')) {
          params.cluster_id = Number(activePathTab.value.replace('normal_cluster_', ''))
          params.cluster_type = 'normal'
        }
      }
    }
    if (filterStore.studyRange && filterStore.studyRange.length === 2) {
      params.study_from = filterStore.studyRange[0]
      params.study_to   = filterStore.studyRange[1]
    }
    if (filterStore.baselineRange && filterStore.baselineRange.length === 2) {
      params.baseline_from = filterStore.baselineRange[0]
      params.baseline_to   = filterStore.baselineRange[1]
    }
    const res = await api.getMachines(params)
    machines.value = res.data.status === 'success' ? res.data.data : []
  } catch (e) {
    machineError.value = '机台数据加载异常'
  } finally {
    machineLoading.value = false
  }
}

// ── 工艺特征流转路径对比 ──────────────────────────────────────
const pathsData = ref({})
const pathsLoading = ref(false)
const pathsError = ref(null)
const activePathTab = ref('')

async function loadPaths() {
  return // 已暂时关闭聚类分析与路径对比
}

// ── 联合路径诊断 ──────────────────────────────────────────────
const combinations = ref([])
const combLoading = ref(false)

async function loadCombinations() {
  return // 已暂时关闭双机台联合分析
}

// 标签转换辅助
function getPathTabName(key) {
  if (key.startsWith('anomaly_cluster_')) {
    return '🔴 故障簇 ' + key.replace('anomaly_cluster_', '')
  } else if (key.startsWith('normal_cluster_')) {
    return '🟢 常规簇 ' + key.replace('normal_cluster_', '')
  }
  return key
}

// 工序前缀辅助，用于机台标签着色
function getStepPrefix(step) {
  if (!step) return 'default'
  // 取工序字母前缀（如 TB, CU, EX, CL, BA 等）
  const match = step.match(/^([A-Za-z]+)/)
  return match ? match[1].toUpperCase() : 'DEFAULT'
}

// Step Lift 单元格样式回调
function pathCellClass({ row, column }) {
  if (column.property === 'step_lift' && row.step_lift >= 1.5) {
    return 'cell-lift-danger'
  }
  return ''
}

// 计算当前路径列表
const currentPathList = computed(() => {
  return pathsData.value[activePathTab.value] ?? []
})

// 异常富集机台警报
const pathSuspects = computed(() => {
  const suspectsList = []
  Object.keys(pathsData.value).forEach(key => {
    if (key.startsWith('anomaly_cluster_')) {
      const clusterNum = key.replace('anomaly_cluster_', '')
      const list = pathsData.value[key] ?? []
      if (list.length > 0) {
        let maxItem = list[0]
        for (let i = 1; i < list.length; i++) {
          if (list[i].step_lift > maxItem.step_lift) {
            maxItem = list[i]
          }
        }
        if (maxItem.step_lift >= 1.5) {
          suspectsList.push({
            cluster: '故障簇 ' + clusterNum,
            step: maxItem.step,
            machine: maxItem.machine,
            lift: maxItem.step_lift
          })
        }
      }
    }
  })
  return suspectsList
})

// Smooth Scroll to Diagnostics Area
function scrollToDiagnostics() {
  const el = document.querySelector('.diagnostics-panel-section')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// ── 跳转交互处理器 (点击联动至深度诊断) ─────────────────────────
function handleMachineJump(row) {
  if (!row) return
  const wc = row.workcenter_col || ''
  if (wc.includes('ccs') || wc.includes('gt') || wc.includes('ct')) {
    ElMessage.warning(`提示：工序 ${wc.replace('_workcenter', '').toUpperCase()} 无对应物理物料批次，排除特定批次物料影响，系统已判定为设备零点精度漂移。`)
  }
  filterStore.setDiagnosticMachine(row.machine, row.workcenter_col, row.cluster ?? 0)
  nextTick(() => {
    scrollToDiagnostics()
  })
}

function handleSelectMachine(data) {
  if (!data) return
  tab1SelectedArticle.value = data.article10
  selectedWorkcenter.value = null
  loadTrend()
  loadMachines()
  
  handleMachineJump({
    machine: data.machine,
    workcenter_col: data.workcenter_col,
    cluster: 0
  })
}

function handleTableMachineJump(row) {
  if (!row) return
  const wcCol = row.step + '_workcenter'
  if (wcCol.includes('ccs') || wcCol.includes('gt') || wcCol.includes('ct')) {
    ElMessage.warning(`提示：工序 ${row.step.toUpperCase()} 无对应物理物料批次，排除特定批次物料影响，系统已判定为设备零点精度漂移。`)
  }
  let clusterId = 0
  if (activePathTab.value.startsWith('anomaly_cluster_')) {
    clusterId = Number(activePathTab.value.replace('anomaly_cluster_', ''))
  }
  filterStore.setDiagnosticMachine(row.machine, wcCol, clusterId)
  nextTick(() => {
    scrollToDiagnostics()
  })
}

// ── 监听状态变动刷新数据 ──────────────────────────────────────


watch(
  () => filterStore.minYieldThreshold,
  () => {
    selectedWorkcenter.value = null
    selectedTrendDate.value = null
    articles.value = []
    onlyBelowMean.value = false
    debounceLoad(() => {
      loadInsights()
      loadPaths()
      loadCombinations()
    }, 300)
  }
)

watch(
  () => filterStore.hasAnalysisPeriod,
  () => {
    selectedWorkcenter.value = null
  }
)

watch(
  [() => filterStore.baselineRange, () => filterStore.studyRange],
  () => {
    selectedWorkcenter.value = null
    selectedTrendDate.value = null
    articles.value = []
    onlyBelowMean.value = false
    loadCpkTrend()
    debounceLoad(() => {
      loadInsights()
      loadPaths()
      loadCombinations()
    }, 300)
  }
)

watch(cpkIndicator, (newVal) => {
  if (newVal === 'cony') {
    machineTabActive.value = 'best_sankey_flow'
  }
  if (selectedTrendDate.value) {
    if (newVal !== 'cony') {
      loadWarningArticles()
      loadLotCpkTrend()
    }
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

// 已移除对应排序控制器监听

watch(selectedWorkcenter, () => {
  loadMachines()
})

watch(activePathTab, () => {
  if (selectedWorkcenter.value) {
    loadMachines()
  }
})

watch(machineTabActive, (newTab) => {
  if (newTab === 'sankey_flow') {
    loadMachineProcessSankey()
  } else if (newTab === 'best_sankey_flow') {
    loadMachineBestProcessSankey()
  }
})

// 全量规格列表 (支持 Tab 3 任意规格搜索)
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
    loadAllArticles(),
    loadInsights(),
    loadPaths(),
    loadCombinations()
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

.row4-custom-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.row4-custom-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 12px 20px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border-light);
  border-top-left-radius: var(--radius-md);
  border-top-right-radius: var(--radius-md);
}
.row4-custom-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}
.row4-custom-tabs :deep(.el-tabs__active-bar) {
  display: none;
}
.row4-custom-tabs :deep(.el-tabs__item) {
  font-size: 13px;
  font-weight: 600;
  height: 32px;
  line-height: 32px;
  padding: 0 16px !important;
  border-radius: 6px;
  color: var(--c-text-secondary);
  transition: all 0.2s ease;
}
.row4-custom-tabs :deep(.el-tabs__item.is-active) {
  background-color: var(--c-accent-light) !important;
  color: var(--c-accent) !important;
}
.row4-custom-tabs :deep(.el-tabs__item.is-disabled) {
  color: var(--c-text-muted) !important;
  background: transparent !important;
  cursor: not-allowed !important;
}
.row4-custom-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.row4-right-scrollable {
  border-radius: var(--radius-md);
}
.row4-right-scrollable::-webkit-scrollbar {
  width: 6px;
}
.row4-right-scrollable::-webkit-scrollbar-thumb {
  background: var(--c-border);
  border-radius: 3px;
}
.row4-right-scrollable::-webkit-scrollbar-thumb:hover {
  background: var(--c-text-muted);
}

/* ── 聚类子簇选择器（下划线样式）──────────────── */
.cluster-tab-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cluster-tab-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 10px;
  font-size: 12.5px;
  color: var(--c-text-muted);
  border-bottom: 2px solid transparent;
  border-radius: 0;
  transition: color .2s, border-color .2s;
  line-height: 1.4;
}
.cluster-tab-btn:hover {
  color: var(--c-text);
}
.cluster-tab-btn.active-anomaly {
  color: #dc2626;
  font-weight: 600;
  border-bottom-color: #dc2626;
}
.cluster-tab-btn.active-normal {
  color: #16a34a;
  font-weight: 600;
  border-bottom-color: #16a34a;
}

/* ── 首选机台彩色标签（按工序着色）────────────── */
.machine-tag-btn {
  display: inline-block;
  border: none;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  transition: opacity .15s;
}
.machine-tag-btn:hover { opacity: .75; }

/* 工序颜色 - 可扩展 */
.step-TB  { background: #dbeafe; color: #1d4ed8; }
.step-CU  { background: #ede9fe; color: #6d28d9; }
.step-EX  { background: #ffedd5; color: #c2410c; }
.step-CL  { background: #cffafe; color: #0e7490; }
.step-BA  { background: #dcfce7; color: #15803d; }
.step-PL  { background: #fce7f3; color: #be185d; }
.step-LI  { background: #fef9c3; color: #a16207; }
.step-WA  { background: #f0fdf4; color: #166534; }
.step-DE  { background: #fff7ed; color: #9a3412; }
.step-DEFAULT { background: #f1f5f9; color: #475569; }

/* ── Step Lift Badge ────────────────────────── */
.lift-badge-danger {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 4px;
  background: #fef2f2;
  color: #dc2626;
  font-weight: 700;
  font-size: 12px;
}
.lift-badge-normal {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 4px;
  background: transparent;
  color: var(--c-text);
  font-size: 12px;
}

/* ── 整格底色高亮（Step Lift ≥ 1.5）────────── */
:deep(.cell-lift-danger) {
  background-color: #fef2f2 !important;
}

/* ── 可点击工序链接样式 ── */
.step-interactive-link {
  color: var(--c-accent, #3b82f6);
  cursor: pointer;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.step-interactive-link:hover {
  text-decoration: underline;
}
.step-interactive-link.is-active {
  background: var(--c-accent-light, #e0f2fe);
  color: var(--c-accent, #2563eb);
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 700;
}
</style>
