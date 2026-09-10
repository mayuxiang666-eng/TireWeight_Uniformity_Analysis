<template>
  <el-dialog
    v-model="dialogVisible"
    :title="`${isCu ? '硫化机台' : '成型机台'} [${machine}] CGRS 参数修改与生产表现对比`"
    width="1160px"
    top="3vh"
    destroy-on-close
    append-to-body
    class="cgrs-dialog"
  >
    <!-- 头部信息提示胶囊 -->
    <div class="cgrs-meta-bar">
      <div class="meta-left">
        <span class="meta-badge machine-badge">
          <el-icon><Cpu /></el-icon>
          {{ isCu ? '硫化机台' : '成型机台' }}: <strong>{{ machine }}</strong>
        </span>
        <span class="meta-badge date-badge">
          <el-icon><Calendar /></el-icon>
          查询日期: <strong>{{ date }}</strong>
        </span>
        <span v-if="article" class="meta-badge article-badge">
          <el-icon><Document /></el-icon>
          选定规格: <strong>{{ article }}</strong>
        </span>
        <span v-else class="meta-badge article-badge" style="background: #f1f5f9; color: #475569;">
          <el-icon><Document /></el-icon>
          规格范围: <strong>全部规格</strong>
        </span>
        <span class="meta-badge indicator-badge">
          <el-icon><DataLine /></el-icon>
          质量指标: <strong>{{ indicatorLabel }}</strong>
        </span>
      </div>
      <div class="meta-right">
        <span v-if="!loading && records.length > 0" class="count-badge">
          共 <strong>{{ records.length }}</strong> 条参数变更明细 <span v-if="controlledData?.events?.length > 1" style="font-weight: normal; opacity: 0.85;">({{ controlledData.events.length }} 次调参事件)</span>
        </span>
      </div>
    </div>

    <!-- 主体内容区 -->
    <div class="cgrs-body-wrap">

      <!-- Loading 状态 -->
      <div v-if="loading || controlledLoading" class="cgrs-state-box">
        <el-icon class="is-loading" size="26" style="color: #f59e0b;"><Loading /></el-icon>
        <span style="margin-left: 10px; font-size: 13px; color: #64748b; font-weight: 500;">
          正在检索机台 {{ machine }} 在 {{ date }} {{ article ? `针对规格 [${article}]` : '' }} 的 CGRS 调参事件，并按 {{ isCu ? '硫化 CT ➔ 成型 GT ➔ 终检 TU' : '成型 GT ➔ 硫化 CT ➔ 终检 TU' }} 拆分全路径分析...
        </span>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error || controlledError" class="cgrs-state-box state-error">
        <el-icon size="22"><WarningFilled /></el-icon>
        <span style="margin-left: 8px;">{{ error || controlledError }}</span>
      </div>

      <!-- 空数据状态 (仅在既无推荐也无历史调参记录时展示) -->
      <div v-else-if="records.length === 0 && (!controlledData || !controlledData.has_cgrs) && (!recommendData || !recommendData.has_recommendation)" class="cgrs-state-box state-empty">
        <el-empty
          :description="emptyDescriptionText"
          :image-size="70"
        />
      </div>

      <!-- 数据正常展示 -->
      <div v-else style="display: flex; flex-direction: column; gap: 14px;">
        
        <!-- 全工序路径拆分与有效路径加总分析面板 -->
        <div v-if="controlledData && controlledData.has_cgrs" class="controlled-panel">
          <div class="ctrl-header">
            <div class="ctrl-title">
              <el-icon style="color: #d97706; font-size: 15px;"><TrendCharts /></el-icon>
              <span>{{ isCu ? '硫化机' : '成型机' }} [{{ machine }}] ➔ {{ isCu ? '成型 GT' : '硫化 CT' }} ➔ 终检 TU 全工序路径拆分与调参趋势对照</span>
            </div>

            <!-- 多次调参事件切换 Tab 按钮 (无有效对比路径时置灰禁用并悬浮提示) -->
            <div v-if="controlledData.events && controlledData.events.length > 1" class="ctrl-switcher">
              <span class="switcher-label">调参事件:</span>
              <el-radio-group v-model="selectedEventIndex" size="small">
                <el-tooltip
                  v-for="(ev, idx) in controlledData.events"
                  :key="ev.timestamp"
                  :content="isEventDisabled(ev) ? '无有效对比路径 (样本不足 5 胎或数量失衡 >2.5 倍)' : `第 ${controlledData.events.length - idx} 次调参`"
                  placement="top"
                  :disabled="!isEventDisabled(ev)"
                >
                  <el-radio-button
                    :value="idx"
                    :disabled="isEventDisabled(ev)"
                    :class="{ 'is-disabled-event': isEventDisabled(ev) }"
                  >
                    第 {{ controlledData.events.length - idx }} 次
                  </el-radio-button>
                </el-tooltip>
              </el-radio-group>
            </div>
          </div>

          <!-- 当前选中的调参事件详情 -->
          <div class="ctrl-body">
            <!-- 1. 结论展示卡片 (均为提升展示单绿卡，均为下降展示单红卡，有升有降双卡展示) -->
            <div v-if="globalBestWorstSummary && (globalBestWorstSummary.best || globalBestWorstSummary.worst)" class="ranking-cards-container">
              <div class="ranking-grid" :class="{ 'single-card-grid': !globalBestWorstSummary.best || !globalBestWorstSummary.worst }">
                <!-- 提升最多/最佳修改 (绿卡) -->
                <div
                  v-if="globalBestWorstSummary.best"
                  class="rank-card is-best"
                  :class="{ 'is-active': selectedEventIndex === globalBestWorstSummary.best.idx }"
                  @click="selectedEventIndex = globalBestWorstSummary.best.idx"
                >
                  <div class="rank-card-header">
                    <span class="rank-tag tag-best">🏆 CPK 最佳提升</span>
                    <span v-if="selectedEventIndex === globalBestWorstSummary.best.idx" class="active-pill">当前选中</span>
                    <span v-else class="click-hint">点击切至该次</span>
                  </div>
                  <div class="rank-card-body">
                    <div class="event-title">
                      <strong>第 {{ globalBestWorstSummary.best.eventNum }} 次修改</strong>
                      <span class="event-time font-mono">{{ formatShortTime(globalBestWorstSummary.best.timeStr) }}</span>
                    </div>
                    <div class="metrics-row font-mono">
                      <span class="pct-val pos-text">+{{ globalBestWorstSummary.best.summary.yoy_pct }}%</span>
                      <span class="cpk-pair">(CPK {{ globalBestWorstSummary.best.summary.cpk_before }} ➔ {{ globalBestWorstSummary.best.summary.cpk_after }})</span>
                    </div>
                  </div>
                </div>

                <!-- 恶化最严/最差修改 (红卡) -->
                <div
                  v-if="globalBestWorstSummary.worst"
                  class="rank-card is-worst"
                  :class="{ 'is-active': selectedEventIndex === globalBestWorstSummary.worst.idx }"
                  @click="selectedEventIndex = globalBestWorstSummary.worst.idx"
                >
                  <div class="rank-card-header">
                    <span class="rank-tag tag-worst">⚠️ CPK 恶化最严</span>
                    <span v-if="selectedEventIndex === globalBestWorstSummary.worst.idx" class="active-pill">当前选中</span>
                    <span v-else class="click-hint">点击切至该次</span>
                  </div>
                  <div class="rank-card-body">
                    <div class="event-title">
                      <strong>第 {{ globalBestWorstSummary.worst.eventNum }} 次修改</strong>
                      <span class="event-time font-mono">{{ formatShortTime(globalBestWorstSummary.worst.timeStr) }}</span>
                    </div>
                    <div class="metrics-row font-mono">
                      <span class="pct-val neg-text">
                        {{ globalBestWorstSummary.worst.summary.yoy_pct > 0 ? '+' : '' }}{{ globalBestWorstSummary.worst.summary.yoy_pct }}%
                      </span>
                      <span class="cpk-pair">(CPK {{ globalBestWorstSummary.worst.summary.cpk_before }} ➔ {{ globalBestWorstSummary.worst.summary.cpk_after }})</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 4. 调参前后单胎实测值趋势图 (横向充满全宽，Hover 显示质量指标对比浮窗) -->
            <div class="ctrl-chart-box full-width-chart-box">
              <div class="chart-header">
                <div class="chart-header-left">
                  <span class="chart-title">
                    <el-icon style="margin-right: 5px; vertical-align: -2px; color: #0284c7;"><TrendCharts /></el-icon>
                    多次调参实测值趋势对比 (按时间先后时序)
                  </span>
                  <el-tag
                    v-if="!selectedPath"
                    type="primary"
                    effect="light"
                    size="small"
                    class="view-tag"
                  >
                    总体视图 (共 {{ combinedChartData.eventsCount || 0 }} 次调参事件拼接)
                  </el-tag>
                  <el-tag
                    v-else
                    type="success"
                    effect="dark"
                    size="small"
                    class="view-tag"
                  >
                    {{ selectedPath.path_label }}
                  </el-tag>
                </div>
                <div class="chart-header-right">
                  <el-button
                    v-if="selectedPath"
                    size="small"
                    type="primary"
                    link
                    @click="selectedPath = null"
                  >
                    重置为总体视图
                  </el-button>
                  <span class="chart-legend-hint">
                    <span class="legend-dot before"></span> 调参前
                    <span class="legend-dot after"></span> 调参后
                    <span style="color: #64748b; font-size: 11px; margin-left: 8px; font-weight: 500;">💡 悬停折线点实时浮出该次质量指标对比</span>
                  </span>
                </div>
              </div>

              <!-- 折线图主容器 (100% 全宽) -->
              <div class="trend-chart-wrapper">
                <div v-if="!combinedChartData.hasData" class="chart-empty-tip">
                  <el-empty description="当前视图暂无单胎实测时序数据" :image-size="60" />
                </div>
                <div ref="trendChartRef" class="trend-chart-canvas" style="width: 100%; height: 265px; min-height: 265px;"></div>
              </div>
            </div>

            <!-- 5. 【折叠模块 1】本次调参涉及的具体参数变更明细表 (默认收起) -->
            <div class="collapsible-card">
              <div class="collapsible-header" @click="isParamsExpanded = !isParamsExpanded">
                <div class="collapsible-header-left">
                  <el-icon style="color: #0284c7;"><Document /></el-icon>
                  <span class="collapsible-title">本次调参涉及的具体参数变更明细</span>
                  <span class="count-tag">共 <strong>{{ activeControlledEvent?.params_changed?.length || displayedRecords.length }}</strong> 条参数记录</span>
                </div>
                <div class="collapsible-header-right">
                  <el-button size="small" type="primary" link>
                    {{ isParamsExpanded ? '收起参数变更明细' : '展开参数变更明细' }}
                    <el-icon><ArrowDown v-if="!isParamsExpanded" /><ArrowUp v-else /></el-icon>
                  </el-button>
                </div>
              </div>

              <el-collapse-transition>
                <div v-show="isParamsExpanded" class="collapsible-body">
                  <el-table
                    :data="displayedRecords"
                    size="small"
                    stripe
                    border
                    highlight-current-row
                    @row-click="handleRecordRowClick"
                    :row-class-name="recordTableRowClassName"
                    style="width: 100%; cursor: pointer;"
                    max-height="320"
                    :header-cell-style="{ background: '#f8fafc', color: '#1e293b', fontWeight: '700', fontSize: '12px' }"
                  >
                    <el-table-column label="调参事件" width="85" align="center" fixed="left">
                      <template #default="{ row }">
                        <el-tag
                          v-if="getEventIndexForRow(row) >= 0"
                          size="small"
                          :type="isRowActive(row) ? 'warning' : 'info'"
                          :effect="isRowActive(row) ? 'dark' : 'plain'"
                          style="font-size: 10px; height: 18px; line-height: 16px; padding: 0 4px; border-radius: 3px; font-weight: 700;"
                        >
                          第 {{ controlledData.events.length - getEventIndexForRow(row) }} 次
                        </el-tag>
                        <span v-else style="color: #94a3b8; font-size: 11px;">-</span>
                      </template>
                    </el-table-column>

                    <el-table-column label="生效时间" width="145" fixed="left">
                      <template #default="{ row }">
                        <div class="time-col">
                          <el-icon style="color: #f59e0b; font-size: 12px;"><Clock /></el-icon>
                          <span>{{ formatEventTime(row) }}</span>
                        </div>
                      </template>
                    </el-table-column>

                    <el-table-column label="参数名称" min-width="190">
                      <template #default="{ row }">
                        <div class="param-name-cell">
                          <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
                            <span class="param-local-name">{{ formatParamName(row) }}</span>
                            <el-tag
                              v-if="row.Priority"
                              size="small"
                              :type="row.Priority === 1 ? 'danger' : (row.Priority === 2 ? 'warning' : 'info')"
                              effect="plain"
                              style="font-size: 10px; height: 16px; line-height: 14px; padding: 0 4px; border-radius: 3px;"
                            >
                              P{{ row.Priority }}
                            </el-tag>
                            <el-tag
                              v-if="isRowActive(row)"
                              size="small"
                              type="warning"
                              effect="plain"
                              style="font-size: 9.5px; height: 16px; line-height: 14px; padding: 0 3px; border-radius: 3px;"
                            >
                              当前所选
                            </el-tag>
                          </div>
                          <span v-if="row.ParameterName && formatParamName(row) !== row.ParameterName" class="param-code-name">
                            {{ row.ParameterName }}
                          </span>
                        </div>
                      </template>
                    </el-table-column>

                    <el-table-column label="系统标准值" width="105" align="right">
                      <template #default="{ row }">
                        <span class="standard-val font-mono">
                          {{ row.ParameterValue ?? '-' }}
                          <small class="unit-text">{{ row.ParameterUnitSymbol }}</small>
                        </span>
                      </template>
                    </el-table-column>

                    <el-table-column label="改前历史值" width="105" align="right">
                      <template #default="{ row }">
                        <span class="from-tag font-mono">
                          {{ calcHistoryValue(row) }}
                          <small class="unit-text">{{ row.ParameterUnitSymbol }}</small>
                        </span>
                      </template>
                    </el-table-column>

                    <el-table-column label="改后变更值" width="105" align="right">
                      <template #default="{ row }">
                        <span class="to-tag font-mono" style="font-weight: 700; color: #0284c7;">
                          {{ calcNewValue(row) }}
                          <small class="unit-text">{{ row.ParameterUnitSymbol }}</small>
                        </span>
                      </template>
                    </el-table-column>

                    <el-table-column label="参数变更轨迹" min-width="160" align="center">
                      <template #default="{ row }">
                        <div class="change-diff-cell">
                          <span class="from-tag font-mono">{{ calcHistoryValue(row) }}</span>
                          <span class="arrow-sep">➔</span>
                          <span class="to-tag font-mono font-bold" style="color: #0284c7;">{{ calcNewValue(row) }}</span>
                          <small class="unit-text" style="margin-left: 2px;">{{ row.ParameterUnitSymbol }}</small>
                        </div>
                      </template>
                    </el-table-column>

                    <el-table-column label="适用规格 / 配方 / 工序机台" min-width="185">
                      <template #default="{ row }">
                        <div class="recipe-cell">
                          <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
                            <span class="spec-code">{{ row.ProdSpecific2 || '全部规格' }}</span>
                            <el-tag
                              v-if="row.Workcenter"
                              size="small"
                              :type="row.Workcenter.startsWith('TB1') ? 'primary' : (row.Workcenter.startsWith('TB2') ? 'success' : 'info')"
                              effect="plain"
                              style="font-size: 10px; height: 16px; line-height: 14px; padding: 0 4px;"
                            >
                              {{ row.Workcenter }} · {{ row.Item || (row.Workcenter.startsWith('TB1') ? '一段' : (row.Workcenter.startsWith('TB2') ? '二段' : '硫化')) }}
                            </el-tag>
                          </div>
                          <span v-if="row.RecipeDescription" class="recipe-desc">{{ row.RecipeDescription }}</span>
                        </div>
                      </template>
                    </el-table-column>

                    <el-table-column prop="UserName" label="操作人员" width="125">
                      <template #default="{ row }">
                        <div class="user-cell">
                          <el-icon style="color: #64748b; font-size: 12px;"><User /></el-icon>
                          <span>{{ row.UserName || '-' }}</span>
                        </div>
                      </template>
                    </el-table-column>

                    <el-table-column prop="comments" label="变更备注 / 原因" min-width="150" show-overflow-tooltip>
                      <template #default="{ row }">
                        <span class="comments-text">{{ row.comments || '-' }}</span>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </el-collapse-transition>
            </div>

            <!-- 6. 【折叠模块 2】GT ➔ CT ➔ TU 拆分路径明细对照 (默认收起) -->
            <div class="collapsible-card">
              <div class="collapsible-header" @click="isPathsExpanded = !isPathsExpanded">
                <div class="collapsible-header-left">
                  <el-icon style="color: #d97706;"><TrendCharts /></el-icon>
                  <span class="collapsible-title">GT ➔ CT ➔ TU 拆分路径明细对照</span>
                  <span class="count-tag">有效入选 <strong>{{ filteredControlledPaths.length }}</strong> / {{ activeControlledPaths.length }} 条路径 (按双侧 ≥5 胎及 ≤2.5 倍样本均衡过滤)</span>
                </div>
                <div class="collapsible-header-right">
                  <el-button size="small" type="primary" link>
                    {{ isPathsExpanded ? '收起路径表格' : '展开拆分路径表格' }}
                    <el-icon><ArrowDown v-if="!isPathsExpanded" /><ArrowUp v-else /></el-icon>
                  </el-button>
                </div>
              </div>

              <el-collapse-transition>
                <div v-show="isPathsExpanded" class="collapsible-body">
                  <!-- 工具栏 -->
                  <div class="table-toolbar" style="margin-top: 0;">
                    <div class="toolbar-left">
                      <span class="click-hint-tag">💡 点击下方任意行可切换上方折线图</span>
                    </div>
                    <div class="toolbar-right">
                      <el-checkbox v-model="sameDayOnly" size="small" @change="fetchControlledAnalysis">仅看调参当天样本</el-checkbox>
                      <el-input
                        v-model="searchPathKeyword"
                        placeholder="搜索机台 (如 CU617, TU1)..."
                        size="small"
                        clearable
                        :prefix-icon="Search"
                        style="width: 185px;"
                      />
                    </div>
                  </div>

                  <!-- 表格 -->
                  <div class="ctrl-table-box">
                    <el-table
                      :data="filteredControlledPaths"
                      size="small"
                      border
                      stripe
                      highlight-current-row
                      @row-click="handlePathRowClick"
                      :row-class-name="tableRowClassName"
                      style="width: 100%; cursor: pointer;"
                      max-height="400"
                      :header-cell-style="{ background: '#f8fafc', color: '#334155', fontWeight: '700', fontSize: '11.5px' }"
                    >
                      <el-table-column label="全工序拆分路径 (GT ➔ CT ➔ TU)" min-width="195" fixed="left">
                        <template #default="{ row }">
                          <div class="path-cell">
                            <span class="path-gt font-mono font-bold">{{ row.gt_workcenter }}</span>
                            <span class="path-arrow">➔</span>
                            <span class="path-ct font-mono" :class="{ 'is-suspect': row.suspect_machines?.includes(row.ct_workcenter) }">
                              {{ row.ct_workcenter }}
                            </span>
                            <span class="path-arrow">➔</span>
                            <span class="path-tu font-mono" :class="{ 'is-suspect': row.suspect_machines?.includes(row.tu_workcenter) }">
                              {{ row.tu_workcenter }}
                            </span>
                            <el-tag
                              v-if="row.is_suspect_path"
                              size="small"
                              type="danger"
                              effect="plain"
                              style="margin-left: 5px; font-size: 10px; height: 18px; line-height: 16px; padding: 0 4px;"
                            >
                              {{ row.suspect_machines.join(',') }} 预警
                            </el-tag>
                          </div>
                        </template>
                      </el-table-column>

                      <el-table-column label="【调参前表现】" align="center">
                        <el-table-column label="样本(N)" prop="n_before" width="75" align="center" sortable>
                          <template #default="{ row }">
                            <span class="font-mono">{{ row.n_before }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column label="均值 (μ)" prop="mean_before" width="80" align="right" sortable>
                          <template #default="{ row }">
                            <span class="font-mono" style="color: #475569;">{{ row.mean_before }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column label="标准差 (σ)" prop="std_before" width="85" align="right" sortable>
                          <template #default="{ row }">
                            <span class="font-mono" style="color: #475569;">{{ row.std_before }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column label="改前 CPK" prop="cpk_before" width="85" align="right" sortable>
                          <template #default="{ row }">
                            <span class="font-mono font-bold" :style="{ color: row.cpk_before < 0 ? '#dc2626' : '#0284c7' }">{{ row.cpk_before }}</span>
                          </template>
                        </el-table-column>
                      </el-table-column>

                      <el-table-column label="【调参后表现】" align="center">
                        <el-table-column label="样本(N)" prop="n_after" width="75" align="center" sortable>
                          <template #default="{ row }">
                            <span class="font-mono">{{ row.n_after }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column label="均值 (μ)" prop="mean_after" width="80" align="right" sortable>
                          <template #default="{ row }">
                            <span class="font-mono" style="color: #1e293b;">{{ row.mean_after }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column label="标准差 (σ)" prop="std_after" width="85" align="right" sortable>
                          <template #default="{ row }">
                            <span class="font-mono" style="color: #1e293b;">{{ row.std_after }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column label="改后 CPK" prop="cpk_after" width="85" align="right" sortable>
                          <template #default="{ row }">
                            <span class="font-mono font-bold" :style="{ color: row.cpk_after < 0 ? '#dc2626' : '#2563eb' }">{{ row.cpk_after }}</span>
                          </template>
                        </el-table-column>
                      </el-table-column>

                      <el-table-column label="CPK 净变" prop="cpk_diff" width="85" align="right" sortable>
                        <template #default="{ row }">
                          <span class="font-mono font-bold" :style="{ color: row.cpk_diff >= 0 ? '#15803d' : '#b91c1c' }">
                            {{ row.cpk_diff > 0 ? '+' : '' }}{{ row.cpk_diff }}
                          </span>
                        </template>
                      </el-table-column>

                      <el-table-column label="CPK 同比增幅" min-width="110" align="center" sortable prop="yoy_pct" fixed="right">
                        <template #default="{ row }">
                          <span v-if="row.has_before_data && row.has_after_data" class="yoy-badge" :class="row.yoy_pct >= 0 ? 'pos-badge' : 'neg-badge'" style="font-size: 11.5px; padding: 2px 8px;">
                            {{ row.yoy_pct > 0 ? '+' : '' }}{{ row.yoy_pct }}%
                          </span>
                          <span v-else style="color: #94a3b8; font-size: 11px;">单侧样本不足</span>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </div>
              </el-collapse-transition>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <template #footer>
      <div class="cgrs-dialog-footer">
        <el-button type="primary" size="small" @click="dialogVisible = false">关闭</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import {
  Loading, WarningFilled, Clock, Cpu, Calendar, User, Document, TrendCharts,
  DataLine, CircleCheckFilled, CircleCloseFilled, InfoFilled, DataAnalysis, Search, ArrowDown, ArrowUp
} from '@element-plus/icons-vue'
import { api } from '../../api'

const props = defineProps({
  visible:         { type: Boolean, default: false },
  machine:         { type: String,  default: '' },
  date:            { type: String,  default: '' },
  article:         { type: String,  default: '' },
  indicator:       { type: String,  default: 'rfpp' },
  isTopWarning:    { type: Boolean, default: false },
  topMachines:     { type: [Array, String], default: () => [] },
  recommendReason: { type: String,  default: 'degradation' }
})

const emit = defineEmits(['update:visible'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const loading = ref(false)
const error = ref(null)
const records = ref([])
const selectedEventIndex = ref(0)
const filterOnlySelectedEvent = ref(false)

const recommendData = ref(null)

async function fetchRecommendedParams() {
  if (!props.machine || !props.article) return
  try {
    const res = await api.getRecommendedCgrsParams({
      machine: props.machine,
      article10: props.article,
      indicator: props.indicator,
      reason: props.recommendReason || 'degradation'
    })
    const d = res?.data || res
    if (d && d.status === 'success') {
      recommendData.value = d
    }
  } catch (e) {
    console.error('fetchRecommendedParams error:', e)
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    fetchRecommendedParams()
  } else {
    recommendData.value = null
  }
})

// 折叠面板展开状态 (默认全部收起)
const isParamsExpanded = ref(false)
const isPathsExpanded = ref(false)

function isRowActive(row) {
  if (!activeControlledEvent.value) return false
  const ev = activeControlledEvent.value
  const rowTime = new Date(row.event_timestamp || row.TechOffsetHistoryLocalDate || row.TechOffsetLocalDate).getTime()
  const startTs = new Date(ev.start_timestamp || ev.timestamp).getTime() - 300000
  const endTs = new Date(ev.end_timestamp || ev.timestamp).getTime() + 300000
  return rowTime >= startTs && rowTime <= endTs
}

function getEventIndexForRow(row) {
  if (!controlledData.value?.events) return -1
  const rowTime = new Date(row.event_timestamp || row.TechOffsetHistoryLocalDate || row.TechOffsetLocalDate).getTime()
  const events = controlledData.value.events
  for (let i = 0; i < events.length; i++) {
    const ev = events[i]
    const startTs = new Date(ev.start_timestamp || ev.timestamp).getTime() - 300000
    const endTs = new Date(ev.end_timestamp || ev.timestamp).getTime() + 300000
    if (rowTime >= startTs && rowTime <= endTs) {
      return i
    }
  }
  return -1
}

function handleRecordRowClick(row) {
  const evIdx = getEventIndexForRow(row)
  if (evIdx >= 0) {
    selectedEventIndex.value = evIdx
  }
}

function recordTableRowClassName({ row }) {
  if (isRowActive(row)) {
    return 'active-event-record-row'
  }
  return ''
}

const displayedRecords = computed(() => {
  let list = records.value || []
  if (filterOnlySelectedEvent.value && activeControlledEvent.value) {
    const evTime = new Date(activeControlledEvent.value.timestamp).getTime()
    list = list.filter(row => {
      const rowTime = new Date(row.event_timestamp || row.TechOffsetHistoryLocalDate || row.TechOffsetLocalDate).getTime()
      return Math.abs(rowTime - evTime) <= 300000
    })
  }
  return list
})

// 控制变量全工序拆分状态
const controlledLoading = ref(false)
const controlledError = ref(null)
const controlledData = ref(null)

// 折线图与路径选中状态
const trendChartRef = ref(null)
let trendChartInstance = null
const selectedPath = ref(null)

// 表格筛选状态
const sameDayOnly = ref(false)
const searchPathKeyword = ref('')

const activeControlledEvent = computed(() => {
  if (!controlledData.value || !controlledData.value.events || controlledData.value.events.length === 0) {
    return null
  }
  const idx = selectedEventIndex.value
  return controlledData.value.events[idx] || controlledData.value.events[0]
})

const activeControlledPaths = computed(() => {
  return activeControlledEvent.value?.paths || []
})

// CPK 计算辅助函数 (支持负值)
function calcCpkJs(m, s, u, l) {
  if (!s || s <= 1e-6) return 0
  if (u !== null && u !== undefined && l !== null && l !== undefined) {
    const cpu = (u - m) / (3 * s)
    const cpl = (m - l) / (3 * s)
    return Math.max(-5.0, Math.min(5.0, Number(Math.min(cpu, cpl).toFixed(3))))
  } else if (u !== null && u !== undefined) {
    return Math.max(-5.0, Math.min(5.0, Number(((u - m) / (3 * s)).toFixed(3))))
  } else if (l !== null && l !== undefined) {
    return Math.max(-5.0, Math.min(5.0, Number(((m - l) / (3 * s)).toFixed(3))))
  }
  return 0
}

// 统一计算单次事件在双侧 ≥5 胎及 ≤2.5 倍样本均衡过滤器下筛选的有效路径及汇总指标
function computeEventSummary(eventObj) {
  if (!eventObj || !eventObj.paths || eventObj.paths.length === 0) return null
  const rawPaths = eventObj.paths || []
  
  const effectivePaths = rawPaths.filter(p => {
    const nb = p.n_before || 0
    const na = p.n_after || 0
    if (nb < 5 || na < 5) return false
    const ratio = Math.max(nb, na) / Math.min(nb, na)
    return ratio <= 2.5
  })
  if (effectivePaths.length === 0) return null

  let allB = [], allA = []
  effectivePaths.forEach(p => {
    if (p.vals_before && p.vals_before.length > 0) allB.push(...p.vals_before)
    if (p.vals_after && p.vals_after.length > 0) allA.push(...p.vals_after)
  })

  const nb = allB.length
  const na = allA.length
  const mb = nb > 0 ? allB.reduce((a, b) => a + b, 0) / nb : 0
  const ma = na > 0 ? allA.reduce((a, b) => a + b, 0) / na : 0
  const sb = nb > 1 ? Math.sqrt(allB.reduce((a, v) => a + Math.pow(v - mb, 2), 0) / (nb - 1)) : 0
  const sa = na > 1 ? Math.sqrt(allA.reduce((a, v) => a + Math.pow(v - ma, 2), 0) / (na - 1)) : 0

  const usl = eventObj.usl ?? (props.indicator === 'weight' ? null : 100.0)
  const lsl = eventObj.lsl ?? null

  let cpkB = 0, cpkA = 0
  if (props.indicator === 'weight') {
    cpkB = nb > 0 ? Number(mb.toFixed(3)) : 0
    cpkA = na > 0 ? Number(ma.toFixed(3)) : 0
  } else {
    cpkB = nb > 0 ? calcCpkJs(mb, sb, usl, lsl) : 0
    cpkA = na > 0 ? calcCpkJs(ma, sa, usl, lsl) : 0
  }
  const cpkDiff = Number((cpkA - cpkB).toFixed(3))
  const yoy = (nb > 0 && na > 0 && Math.abs(cpkB) > 1e-4) ? Number((((cpkA - cpkB) / Math.abs(cpkB)) * 100).toFixed(2)) : 0

  return {
    effectiveCount: effectivePaths.length,
    totalCount: rawPaths.length,
    n_before: nb,
    mean_before: Number(mb.toFixed(3)),
    std_before: Number(sb.toFixed(3)),
    cpk_before: cpkB,
    n_after: na,
    mean_after: Number(ma.toFixed(3)),
    std_after: Number(sa.toFixed(3)),
    cpk_after: cpkA,
    cpk_diff: cpkDiff,
    yoy_pct: yoy,
    effectivePaths
  }
}

// 检查某个调参事件是否缺乏有效路径 (若不足 5 胎或失衡 >2.5 倍则判定为禁用)
function isEventDisabled(ev) {
  const sum = computeEventSummary(ev)
  return !sum || sum.effectiveCount === 0
}

// 动态有效路径过滤：双侧 ≥5 胎，且样本大/小比例 ≤ 2.5 倍
const filteredControlledPaths = computed(() => {
  const paths = activeControlledPaths.value || []
  let list = paths.filter(p => {
    const nb = p.n_before || 0
    const na = p.n_after || 0
    if (nb < 5 || na < 5) return false
    const ratio = Math.max(nb, na) / Math.min(nb, na)
    return ratio <= 2.5
  })
  if (searchPathKeyword.value && searchPathKeyword.value.trim()) {
    const kw = searchPathKeyword.value.trim().toUpperCase()
    list = list.filter(p => 
      p.path_label?.toUpperCase().includes(kw) || 
      p.ct_workcenter?.toUpperCase().includes(kw) || 
      p.tu_workcenter?.toUpperCase().includes(kw)
    )
  }
  return list
})

// 根据 20% 动态过滤后有效路径，加总计算总体 CPK 与算法判定
const dynamicOverallSummary = computed(() => {
  const summary = computeEventSummary(activeControlledEvent.value)
  if (!summary) {
    return {
      n_before: 0, mean_before: 0, std_before: 0, cpk_before: 0,
      n_after: 0, mean_after: 0, std_after: 0, cpk_after: 0,
      cpk_diff: 0, yoy_pct: 0,
      conclusion_type: 'insufficient_data',
      conclusion_title: '无符合 20% 动态门槛的有效路径',
      conclusion_text: '当前事件中全工序拆分路径样本较少，已自动过滤小于总样本 20% 的小样本路径，暂无符合条件的有效路径。',
      interfering_machines: []
    }
  }

  const paths = summary.effectivePaths
  const yoy = summary.yoy_pct

  // 动态嫌疑机台干扰识别 (基于过滤后的有效路径)
  const interfering = new Set()
  paths.forEach(p => {
    if (p.has_before_data && p.has_after_data && p.suspect_machines && p.suspect_machines.length > 0) {
      if (yoy > 0 && p.yoy_pct < 0) {
        p.suspect_machines.forEach(m => interfering.add(m))
      } else if (yoy < 0 && p.yoy_pct < (yoy - 15.0)) {
        p.suspect_machines.forEach(m => interfering.add(m))
      }
    }
  })

  let concType = 'confirmed_gt_effect'
  let concTitle = '控制变量排查结论'
  let concText = ''
  const signStr = (yoy >= 0 ? '+' : '') + yoy.toFixed(2) + '%'
  const mList = Array.from(interfering).sort()

  if (interfering.size > 0) {
    concType = 'second_stage_interference'
    if (yoy >= 0) {
      concTitle = '算法判定：成型调参总体改善，部分路径受后工段预警机台负向干扰'
      concText = `成型机 [${props.machine}] 调参后在 20% 动态门槛有效路径样本加总中总体 CPK 呈改善提升趋势（总体增幅 ${signStr}）。但在流经全局预警机台 [${mList.join('、')}] 的组合路径中，CPK 表现为反向下滑，判定该路径主要受后工段高风险机台负向干扰，而非成型机本身调参失效。`
    } else {
      concTitle = '算法判定：成型调参受后工段预警机台加剧恶化干扰'
      concText = `成型机 [${props.machine}] 调参后在 20% 动态门槛有效路径样本加总中总体 CPK 呈下滑变动（总体增幅 ${signStr}）。且在流经全局预警机台 [${mList.join('、')}] 的组合路径中质量恶化尤为突出，判定该工序质量问题显著受后工段高风险机台叠加干扰。`
    }
  } else if (yoy > 2.0) {
    concType = 'confirmed_gt_effect'
    concTitle = '算法判定：排除后工段干扰，成型调参改善效果真实明确'
    concText = `符合 20% 门槛的各拆分路径调参前后 CPK 增幅方向总体一致（有效路径总体增幅 ${signStr}），排除硫化与终检后工段机台差异干扰，成型机 [${props.machine}] 调参改善效果真实有效。`
  } else if (yoy < -2.0) {
    concType = 'confirmed_gt_effect'
    concTitle = '算法判定：排除后工段干扰，成型调参对全路径呈负向影响'
    concText = `符合 20% 门槛的各拆分路径调参后 CPK 均表现为下滑（有效路径总体增幅 ${signStr}），排除后工段机台干扰，表明本次参数调整对各路径均未达到预期质量效果。`
  } else {
    concType = 'confirmed_gt_effect'
    concTitle = '算法判定：调参前后质量表现基本持平'
    concText = `成型机 [${props.machine}] 调参后总体 CPK 保持平稳（有效路径总体增幅 ${signStr}），各路径未见显著分歧。`
  }

  return {
    ...summary,
    conclusion_type: concType,
    conclusion_title: concTitle,
    conclusion_text: concText,
    interfering_machines: mList
  }
})

// 全局最佳/最差调参事件判定计算属性 (选拔时使用方案一 N开方加权得分，展示时保留实际物理数值)
const globalBestWorstSummary = computed(() => {
  if (!controlledData.value || !controlledData.value.events || controlledData.value.events.length === 0) {
    return null
  }
  const summaries = controlledData.value.events.map((ev, idx) => {
    const s = computeEventSummary(ev)
    if (!s) return null
    const nTotal = (s.n_before || 0) + (s.n_after || 0)
    // 方案一加权得分：增幅 * sqrt(总有效样本数)
    const weightedScore = (s.yoy_pct || 0) * Math.sqrt(nTotal)
    return {
      idx,
      eventNum: controlledData.value.events.length - idx,
      timeStr: ev.date_time_str,
      summary: s,
      weightedScore
    }
  }).filter(item => item && item.summary !== null)

  if (summaries.length === 0) return null

  const posSummaries = summaries.filter(e => e.summary.yoy_pct >= 0)
  const negSummaries = summaries.filter(e => e.summary.yoy_pct < 0)

  const allPositive = posSummaries.length > 0 && negSummaries.length === 0
  const allNegative = negSummaries.length > 0 && posSummaries.length === 0
  const hasMixed = posSummaries.length > 0 && negSummaries.length > 0

  let best = null
  let worst = null

  if (allPositive) {
    // 均为提升：按加权得分从大到小排序，选取综合加权效益最大的一项
    posSummaries.sort((a, b) => b.weightedScore - a.weightedScore)
    best = posSummaries[0]
  } else if (allNegative) {
    // 均为下降：按加权得分从小到大排序，选取综合加权恶化最严的一项
    negSummaries.sort((a, b) => a.weightedScore - b.weightedScore)
    worst = negSummaries[0]
  } else if (hasMixed) {
    // 有升有降：正值选加权得分最高，负值选加权得分最负
    posSummaries.sort((a, b) => b.weightedScore - a.weightedScore)
    negSummaries.sort((a, b) => a.weightedScore - b.weightedScore)
    best = posSummaries[0]
    worst = negSummaries[0]
  }

  return {
    best,
    worst,
    allPositive,
    allNegative,
    hasMixed
  }
})

// 结论展示大卡片相关衍生计算
const formattedConclusionTitle = computed(() => {
  const t = dynamicOverallSummary.value?.conclusion_title || '控制变量排查结论'
  return t.replace(/^算法判定[：:]\s*/, '')
})

const conclusionCardThemeClass = computed(() => {
  const type = dynamicOverallSummary.value?.conclusion_type
  const yoy = dynamicOverallSummary.value?.yoy_pct ?? 0
  if (type === 'second_stage_interference') return 'theme-warning'
  if (type === 'confirmed_gt_effect' && yoy >= 0) return 'theme-success'
  if (type === 'confirmed_gt_effect' && yoy < 0) return 'theme-danger'
  return 'theme-info'
})

// 判定当前选中修改事件在每条过滤后的路径上是否趋势一致 (若存在不同趋势则触发现红点预警 🔴)
const currentEventPathTrendConflict = computed(() => {
  const paths = filteredControlledPaths.value || []
  if (paths.length <= 1) return false
  const hasUp = paths.some(p => (p.cpk_diff || 0) > 0.001)
  const hasDown = paths.some(p => (p.cpk_diff || 0) < -0.001)
  return hasUp && hasDown
})

// 计算当前折线图需要渲染的样本集合 (支持总体加总与单路径切换)
const activeChartSamples = computed(() => {
  if (selectedPath.value) {
    return {
      before: selectedPath.value.samples_before || [],
      after: selectedPath.value.samples_after || [],
      label: selectedPath.value.path_label,
      mean_before: selectedPath.value.mean_before,
      mean_after: selectedPath.value.mean_after,
      std_before: selectedPath.value.std_before,
      std_after: selectedPath.value.std_after,
      cpk_before: selectedPath.value.cpk_before,
      cpk_after: selectedPath.value.cpk_after
    }
  }

  // 总体视图：加总当前过滤后有效路径的样本
  const paths = filteredControlledPaths.value || []
  const beforeList = []
  const afterList = []
  paths.forEach(p => {
    if (p.samples_before) beforeList.push(...p.samples_before)
    if (p.samples_after) afterList.push(...p.samples_after)
  })

  // 按生产时间升序排序
  beforeList.sort((a, b) => (a.time > b.time ? 1 : (a.time < b.time ? -1 : 0)))
  afterList.sort((a, b) => (a.time > b.time ? 1 : (a.time < b.time ? -1 : 0)))

  return {
    before: beforeList,
    after: afterList,
    label: '全工序总体加总样本',
    mean_before: dynamicOverallSummary.value?.mean_before,
    mean_after: dynamicOverallSummary.value?.mean_after,
    std_before: dynamicOverallSummary.value?.std_before,
    std_after: dynamicOverallSummary.value?.std_after,
    cpk_before: dynamicOverallSummary.value?.cpk_before,
    cpk_after: dynamicOverallSummary.value?.cpk_after
  }
})

function handlePathRowClick(row) {
  if (selectedPath.value?.path_label === row.path_label) {
    selectedPath.value = null // 再次点击取消选中，恢复总体视图
  } else {
    selectedPath.value = row // 选中该路径，上方折线图切换为该路径专属
  }
}

function tableRowClassName({ row }) {
  if (selectedPath.value?.path_label === row.path_label) {
    return 'selected-path-row'
  }
  return ''
}

const eventRangesMap = ref({})

// 按时间顺序 (第1次 ➔ 第N次) 拼接多次调参事件的样本数据
const combinedChartData = computed(() => {
  const events = controlledData.value?.events || []
  if (events.length === 0) {
    return {
      hasData: false,
      eventsCount: 0,
      xCategories: [],
      seriesBeforeVals: [],
      seriesAfterVals: [],
      sampleMetaList: [],
      usl: null,
      lsl: null
    }
  }

  const xCategories = []
  const seriesBeforeVals = []
  const seriesTransVals = []
  const seriesAfterVals = []
  const sampleMetaList = []
  const splitLines = []
  const ranges = {}

  let pointCounter = 0
  let totalDataCount = 0
  const totEvents = events.length

  // events 列表中索引 0 为最新一次（如第4次），索引 (len-1) 为最早一次（如第1次）
  // 按照时间先后升序排列：从 len-1 递减到 0
  for (let i = totEvents - 1; i >= 0; i--) {
    const ev = events[i]
    const eventNum = totEvents - i
    const eventTimeStr = formatShortTime(ev.date_time_str || ev.timestamp)

    let beforeList = []
    let transList = []
    let afterList = []
    let stats = null

    if (selectedPath.value) {
      const matchPath = ev.paths?.find(p => p.path_label === selectedPath.value.path_label)
      if (matchPath) {
        beforeList = matchPath.samples_before || []
        transList = matchPath.samples_transition || []
        afterList = matchPath.samples_after || []
        const mb = parseFloat(matchPath.mean_before)
        const ma = parseFloat(matchPath.mean_after)
        const sb = parseFloat(matchPath.std_before)
        const sa = parseFloat(matchPath.std_after)
        const cb = parseFloat(matchPath.cpk_before)
        const ca = parseFloat(matchPath.cpk_after)

        stats = {
          mean_before: isNaN(mb) ? null : mb,
          mean_after: isNaN(ma) ? null : ma,
          mean_diff: (!isNaN(ma) && !isNaN(mb)) ? (ma - mb) : null,
          std_before: isNaN(sb) ? null : sb,
          std_after: isNaN(sa) ? null : sa,
          std_diff: (!isNaN(sa) && !isNaN(sb)) ? (sa - sb) : null,
          cpk_before: isNaN(cb) ? null : cb,
          cpk_after: isNaN(ca) ? null : ca,
          cpk_diff: (!isNaN(ca) && !isNaN(cb)) ? (ca - cb) : null,
          cpk_yoy: matchPath.yoy_pct !== undefined ? matchPath.yoy_pct : null
        }
      }
    } else {
      beforeList = ev.overall_samples_before || []
      transList = ev.overall_samples_transition || []
      afterList = ev.overall_samples_after || []

      const sumObj = ev.overall_summary || {}
      stats = {
        mean_before: sumObj.mean_before,
        mean_after: sumObj.mean_after,
        mean_diff: sumObj.mean_diff,
        std_before: sumObj.std_before,
        std_after: sumObj.std_after,
        std_diff: (sumObj.std_after !== undefined && sumObj.std_before !== undefined) ? (sumObj.std_after - sumObj.std_before) : null,
        cpk_before: sumObj.cpk_before,
        cpk_after: sumObj.cpk_after,
        cpk_diff: sumObj.cpk_diff,
        cpk_yoy: sumObj.yoy_pct
      }
    }

    const startIdx = pointCounter

    // 1. 压入改前样本 (Before)
    beforeList.forEach((s, idx) => {
      xCategories.push(s.barcode || `B${eventNum}-${idx + 1}`)
      seriesBeforeVals.push(s.val)
      seriesTransVals.push(null)
      seriesAfterVals.push(null)
      sampleMetaList.push({
        eventNum,
        eventTimeStr,
        stage: 'before',
        stats,
        val: s.val,
        barcode: s.barcode,
        time: s.time,
        ct: s.ct,
        tu: s.tu,
        isContinuous: ev.is_continuous_adjust
      })
      pointCounter++
      totalDataCount++
    })

    // 记录调参交界时刻 (改前最后一个数据点位置绘制【第 X 次调参】垂直虚线)
    let splitCat = null
    if (beforeList.length > 0) {
      splitCat = xCategories[startIdx + beforeList.length - 1]
    } else if (transList.length > 0) {
      splitCat = xCategories[startIdx]
    } else if (afterList.length > 0) {
      splitCat = xCategories[startIdx]
    }

    if (splitCat !== null) {
      splitLines.push({ splitCat, eventNum, eventTimeStr })
    }

    // 2. 压入连续微调过渡段样本 (Transition <10 胎)
    transList.forEach((s, idx) => {
      xCategories.push(s.barcode || `T${eventNum}-${idx + 1}`)
      seriesBeforeVals.push(null)
      seriesTransVals.push(s.val)
      seriesAfterVals.push(null)
      sampleMetaList.push({
        eventNum,
        eventTimeStr,
        stage: 'transition',
        stats,
        val: s.val,
        barcode: s.barcode,
        time: s.time,
        ct: s.ct,
        tu: s.tu,
        isContinuous: true
      })
      pointCounter++
      totalDataCount++
    })

    // 3. 压入改后样本 (After)
    afterList.forEach((s, idx) => {
      xCategories.push(s.barcode || `A${eventNum}-${idx + 1}`)
      seriesBeforeVals.push(null)
      seriesTransVals.push(null)
      seriesAfterVals.push(s.val)
      sampleMetaList.push({
        eventNum,
        eventTimeStr,
        stage: 'after',
        stats,
        val: s.val,
        barcode: s.barcode,
        time: s.time,
        ct: s.ct,
        tu: s.tu,
        isContinuous: ev.is_continuous_adjust
      })
      pointCounter++
      totalDataCount++
    })

    const endIdx = pointCounter > startIdx ? pointCounter - 1 : startIdx
    ranges[i] = { startIdx, endIdx }

    // 在不同调参事件之间插入 6 个空数据点拉大隔离间隔
    if (i > 0) {
      for (let g = 0; g < 6; g++) {
        xCategories.push('')
        seriesBeforeVals.push(null)
        seriesTransVals.push(null)
        seriesAfterVals.push(null)
        sampleMetaList.push(null)
        pointCounter++
      }
    }
  }

  eventRangesMap.value = ranges

  const usl = controlledData.value?.events?.[0]?.usl
  const lsl = controlledData.value?.events?.[0]?.lsl

  return {
    hasData: totalDataCount > 0,
    eventsCount: totEvents,
    xCategories,
    seriesBeforeVals,
    seriesTransVals,
    seriesAfterVals,
    sampleMetaList,
    splitLines,
    usl,
    lsl
  }
})


function renderTrendChart() {
  if (!trendChartRef.value) return

  // 确保 instance 绑定在当前真实存活的 DOM 节点上
  let chart = echarts.getInstanceByDom(trendChartRef.value)
  if (!chart) {
    if (trendChartInstance) {
      try { trendChartInstance.dispose() } catch (e) {}
    }
    chart = echarts.init(trendChartRef.value)
    trendChartInstance = chart
    window.addEventListener('resize', handleResizeChart)
  } else {
    trendChartInstance = chart
  }

  const { hasData, xCategories, seriesBeforeVals, seriesTransVals, seriesAfterVals, sampleMetaList, splitLines, usl } = combinedChartData.value

  if (!hasData || xCategories.length === 0) {
    trendChartInstance.clear()
    return
  }

  // 确保尺寸同步
  trendChartInstance.resize()

  const unit = (props.indicator === 'weight' ? '%' : (props.indicator === 'cony' ? 'N' : 'N'))

  // 标线配置
  const markLineData = []

  // 1. 调参事件分割垂直虚线与标注 (第 X 次调参)
  if (splitLines && splitLines.length > 0) {
    splitLines.forEach(sp => {
      markLineData.push({
        xAxis: sp.splitCat,
        name: `第 ${sp.eventNum} 次调参`,
        lineStyle: {
          color: '#3b82f6',
          width: 1.5,
          type: 'dashed'
        },
        label: {
          formatter: `第 ${sp.eventNum} 次调参`,
          position: 'end',
          color: '#1e40af',
          fontWeight: 'bold',
          fontSize: 10,
          backgroundColor: '#eff6ff',
          borderColor: '#93c5fd',
          borderWidth: 1,
          borderRadius: 3,
          padding: [2, 6]
        }
      })
    })
  }

  // 2. 规格线 USL
  if (usl !== undefined && usl !== null) {
    markLineData.push({
      yAxis: usl,
      name: 'USL 规格上限',
      lineStyle: { color: '#ef4444', width: 1.5, type: 'dashed' },
      label: {
        formatter: `USL: ${usl}`,
        position: 'end',
        color: '#ef4444',
        fontWeight: 'bold',
        fontSize: 10
      }
    })
  }

  const option = {
    backgroundColor: '#ffffff',
    grid: {
      left: '3.5%',
      right: '4%',
      top: '14%',
      bottom: '20%',
      containLabel: true
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      extraCssText: 'box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.12), 0 8px 10px -6px rgba(0, 0, 0, 0.1); border-radius: 8px;',
      textStyle: { color: '#1e293b', fontSize: 12 },
      formatter: function(params) {
        if (!params || params.length === 0) return ''
        const idx = params[0].dataIndex
        const item = sampleMetaList[idx]
        if (!item) return ''

        // 过渡段样本 (<15 胎) Hover 专属 Tooltip (浅色主题)
        if (item.stage === 'transition') {
          return `
            <div style="padding: 2px 2px; min-width: 250px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b;">
              <div style="display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #e2e8f0; padding-bottom:6px; margin-bottom:8px; gap:12px;">
                <strong style="color:#7c3aed; font-size:13px;">第 ${item.eventNum} 次连续微调过渡段样本</strong>
                <span style="font-size:11px; color:#64748b; font-family:monospace;">${item.eventTimeStr}</span>
              </div>
              <div style="font-size:12px; color:#334155; margin-bottom:8px;">
                轮胎条码: <span style="color:#0f172a; font-family:monospace; font-weight:600;">${item.barcode || '-'}</span> | 
                测量值: <strong style="color:#0284c7;">${formatStatVal(item.val)}</strong>
              </div>
              <div style="font-size:11px; color:#6b21a8; background:#f5f3ff; padding:6px 9px; border-radius:6px; border:1px solid #ddd6fe; line-height:1.4;">
                💡 <strong>微调过渡段</strong>：该样本位于相邻调参间隔（< 15 胎），代表连续微调未稳定过程，不计入改前/改后的 CPK 统计。
              </div>
            </div>
          `
        }

        if (!item.stats) return ''

        const stats = item.stats
        const meanDiffStr = (stats.mean_diff !== null && stats.mean_diff !== undefined)
          ? `${stats.mean_diff > 0 ? '+' : ''}${formatStatVal(stats.mean_diff)}`
          : '-'
        const stdDiffStr = (stats.std_diff !== null && stats.std_diff !== undefined)
          ? `${stats.std_diff > 0 ? '+' : ''}${formatStatVal(stats.std_diff)}`
          : '-'
        const cpkYoyStr = (stats.cpk_yoy !== null && stats.cpk_yoy !== undefined)
          ? `<span style="background:${stats.cpk_yoy >= 0 ? '#dcfce7' : '#fee2e2'}; color:${stats.cpk_yoy >= 0 ? '#15803d' : '#b91c1c'}; padding:1px 6px; border-radius:4px; font-size:11px; font-weight:bold;">${stats.cpk_yoy > 0 ? '+' : ''}${stats.cpk_yoy}%</span>`
          : '-'

        return `
          <div style="padding: 2px 2px; min-width: 260px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b;">
            <div style="display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #e2e8f0; padding-bottom:6px; margin-bottom:8px; gap:12px;">
              <strong style="color:#0284c7; font-size:13px;">第 ${item.eventNum} 次调参质量指标对比</strong>
              <span style="font-size:11px; color:#64748b; font-family:monospace;">${item.eventTimeStr}</span>
            </div>
            <table style="width:100%; border-collapse:collapse; font-size:12px; line-height:1.7;">
              <thead>
                <tr style="color:#64748b; border-bottom:1px solid #f1f5f9; font-size:11px;">
                  <th style="text-align:left; padding-bottom:4px; font-weight:600;">指标项</th>
                  <th style="text-align:right; padding-bottom:4px; font-weight:600;">改前 (Before)</th>
                  <th style="text-align:right; padding-bottom:4px; font-weight:600;">改后 (After)</th>
                  <th style="text-align:right; padding-bottom:4px; font-weight:600;">变化 / 增幅</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style="color:#334155;"><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#f59e0b;margin-right:5px;"></span>均值 μ</td>
                  <td style="text-align:right; color:#0f172a; font-family:monospace; font-weight:500;">${formatStatVal(stats.mean_before)}</td>
                  <td style="text-align:right; color:#0f172a; font-family:monospace; font-weight:500;">${formatStatVal(stats.mean_after)}</td>
                  <td style="text-align:right; font-family:monospace; color:${stats.mean_diff > 0 ? '#d97706' : '#0284c7'}; font-weight:700;">${meanDiffStr}</td>
                </tr>
                <tr>
                  <td style="color:#334155;"><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#0284c7;margin-right:5px;"></span>标准差 σ</td>
                  <td style="text-align:right; color:#0f172a; font-family:monospace; font-weight:500;">${formatStatVal(stats.std_before)}</td>
                  <td style="text-align:right; color:#0f172a; font-family:monospace; font-weight:500;">${formatStatVal(stats.std_after)}</td>
                  <td style="text-align:right; font-family:monospace; color:${stats.std_diff < 0 ? '#16a34a' : '#dc2626'}; font-weight:700;">${stdDiffStr}</td>
                </tr>
                <tr style="border-top:1px solid #e2e8f0;">
                  <td style="color:#0f172a; font-weight:bold; padding-top:4px;"><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#10b981;margin-right:5px;"></span>CPK 指数</td>
                  <td style="text-align:right; color:#0f172a; font-weight:bold; font-family:monospace; padding-top:4px;">${formatCpkVal(stats.cpk_before)}</td>
                  <td style="text-align:right; color:#0f172a; font-weight:bold; font-family:monospace; padding-top:4px;">${formatCpkVal(stats.cpk_after)}</td>
                  <td style="text-align:right; font-weight:bold; font-family:monospace; padding-top:4px;">${cpkYoyStr}</td>
                </tr>
              </tbody>
            </table>
          </div>
        `
      }
    },
    xAxis: {
      type: 'category',
      data: xCategories,
      boundaryGap: true,
      axisLabel: {
        rotate: 35,
        fontSize: 10,
        color: '#64748b',
        interval: Math.max(0, Math.floor(xCategories.length / 35))
      },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisTick: { alignWithLabel: true }
    },
    yAxis: {
      type: 'value',
      name: `${indicatorLabel.value} (${unit})`,
      nameTextStyle: { color: '#475569', fontSize: 11, padding: [0, 0, 0, 10] },
      scale: true,
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
      axisLabel: { color: '#64748b', fontSize: 11 }
    },
    dataZoom: [
      {
        type: 'slider',
        show: true,
        xAxisIndex: [0],
        start: 0,
        end: 100,
        height: 18,
        bottom: '2%',
        borderColor: '#e2e8f0',
        fillerColor: 'rgba(59, 130, 246, 0.12)',
        handleStyle: { color: '#3b82f6' },
        textStyle: { color: '#64748b', fontSize: 9 }
      },
      {
        type: 'inside',
        xAxisIndex: [0],
        start: 0,
        end: 100
      }
    ],
    series: [
      {
        name: '调参前样本 (Before)',
        type: 'line',
        data: seriesBeforeVals,
        connectNulls: false,
        smooth: false,
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: {
          color: '#f59e0b',
          borderWidth: 1.5,
          borderColor: '#ffffff'
        },
        lineStyle: {
          color: '#f59e0b',
          width: 2
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(245, 158, 11, 0.22)' },
            { offset: 1, color: 'rgba(245, 158, 11, 0.01)' }
          ])
        },
        markLine: {
          symbol: 'none',
          data: markLineData
        }
      },
      {
        name: '微调过渡段 (<15胎)',
        type: 'line',
        data: seriesTransVals,
        connectNulls: false,
        smooth: false,
        symbol: 'circle',
        symbolSize: 5,
        itemStyle: {
          color: 'rgba(148, 163, 184, 0.85)',
          borderWidth: 1,
          borderColor: '#ffffff'
        },
        lineStyle: {
          color: 'rgba(148, 163, 184, 0.75)',
          width: 1.5,
          type: 'dashed'
        }
      },
      {
        name: '调参后样本 (After)',
        type: 'line',
        data: seriesAfterVals,
        connectNulls: false,
        smooth: false,
        symbol: 'diamond',
        symbolSize: 7,
        itemStyle: {
          color: '#10b981',
          borderWidth: 1.5,
          borderColor: '#ffffff'
        },
        lineStyle: {
          color: '#10b981',
          width: 2
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(16, 185, 129, 0.22)' },
            { offset: 1, color: 'rgba(16, 185, 129, 0.01)' }
          ])
        }
      }
    ]
  }

  trendChartInstance.setOption(option, true)
  trendChartInstance.resize()
}

function zoomToEvent(eventIdx) {
  if (!trendChartInstance || !combinedChartData.value) return
  const range = eventRangesMap.value[eventIdx]
  const totalPts = combinedChartData.value.xCategories.length
  if (!range || !totalPts) return

  const startPct = Math.max(0, Math.floor((range.startIdx / totalPts) * 100) - 2)
  const endPct = Math.min(100, Math.ceil(((range.endIdx + 1) / totalPts) * 100) + 2)

  trendChartInstance.dispatchAction({
    type: 'dataZoom',
    start: startPct,
    end: endPct
  })
}

let resizeObserver = null
function setupResizeObserver() {
  if (trendChartRef.value && window.ResizeObserver) {
    if (resizeObserver) resizeObserver.disconnect()
    resizeObserver = new ResizeObserver(() => {
      if (trendChartInstance) {
        trendChartInstance.resize()
      }
    })
    resizeObserver.observe(trendChartRef.value)
  }
}

function handleResizeChart() {
  if (trendChartInstance) {
    trendChartInstance.resize()
  }
}

const isCu = computed(() => String(props.machine || '').trim().toUpperCase().startsWith('CU'))

function formatStatVal(val) {
  if (val === undefined || val === null || isNaN(val)) return '-'
  return Number(val.toFixed(2)).toString()
}

function formatCpkVal(val) {
  if (val === undefined || val === null || isNaN(val)) return '-'
  return Number(val.toFixed(2)).toString()
}

const emptyDescriptionText = computed(() => {
  if (controlledData.value?.message) {
    return controlledData.value.message
  }
  if (props.article && !isCu.value) {
    return `未查询到机台 [${props.machine}] 在 [${props.date}] 针对规格 [${props.article}] 的 CGRS 调参记录`
  }
  return `未查询到机台 [${props.machine}] 在 [${props.date}] 的 CGRS 调参记录`
})

function formatShortTime(timeStr) {
  if (!timeStr) return ''
  const clean = String(timeStr).split('.')[0]
  const parts = clean.split(' ')
  return parts.length > 1 ? parts[1] : parts[0]
}

const indicatorLabel = computed(() => {
  const map = {
    rfpp: 'RFPP 峰峰值',
    rfh1: 'RFH1 一次谐波',
    cony: 'CONY 锥度力',
    weight: '胎重偏差'
  }
  return map[props.indicator] || props.indicator.toUpperCase()
})

function formatParamName(row) {
  if (!row) return ''
  const local = row.ParameterLocalName || ''
  if (!local || local.includes('\ufffd')) {
    return row.ParameterGlobalName || row.ParameterName || local || '参数'
  }
  return local || row.ParameterGlobalName || row.ParameterName || '参数'
}

function formatEventTime(row) {
  if (!row) return ''
  const t = row.TechOffsetHistoryLocalDate || row.TechOffsetLocalDate || row.event_timestamp || ''
  return String(t).replace('T', ' ').split('.')[0]
}

// 遵从用户公式对齐:
// 1. ParameterValue 为系统设定的标准值 (不随更改变动)
// 2. 修改前历史值 = ParameterValue + TechOffsetHistoryValueFrom
function calcHistoryValue(row) {
  if (!row) return '-'
  const base = parseFloat(row.ParameterValue) || 0
  const fromOffset = parseFloat(row.TechOffsetHistoryValueFrom) || 0
  const val = base + fromOffset
  if (Math.abs(val - Math.round(val)) < 1e-6) return Math.round(val).toString()
  return Number(val.toFixed(3)).toString()
}

// 3. 修改后变更值 = ParameterValue + TechOffsetHistoryValueTo (优先使用历史变更目标值)
function calcNewValue(row) {
  if (!row) return '-'
  const base = parseFloat(row.ParameterValue) || 0
  let toOffsetRaw = row.TechOffsetHistoryValueTo
  if (toOffsetRaw === null || toOffsetRaw === undefined || String(toOffsetRaw).trim() === '') {
    toOffsetRaw = row.TechOffsetValue
  }
  const toOffset = parseFloat(toOffsetRaw) || 0
  const val = base + toOffset
  if (Math.abs(val - Math.round(val)) < 1e-6) return Math.round(val).toString()
  return Number(val.toFixed(3)).toString()
}

async function fetchControlledAnalysis() {
  if (!props.machine || !props.date) return
  controlledLoading.value = true
  controlledError.value = null
  selectedPath.value = null
  try {
    const res = await api.getCgrsControlledAnalysis({
      workcenter: props.machine,
      date: props.date,
      article: props.article || undefined,
      indicator: props.indicator || undefined,
      top_machines: Array.isArray(props.topMachines) ? props.topMachines.filter(Boolean).join(',') : (props.topMachines || undefined),
      same_day_only: sameDayOnly.value,
      min_samples: 1
    })
    if (res.data && res.data.status === 'success') {
      controlledData.value = res.data
      const events = res.data.events || []
      const firstValidIdx = events.findIndex(ev => !isEventDisabled(ev))
      if (firstValidIdx !== -1) {
        selectedEventIndex.value = firstValidIdx
      } else {
        selectedEventIndex.value = 0
      }
      nextTick(() => {
        setupResizeObserver()
        renderTrendChart()
        setTimeout(renderTrendChart, 80)
        setTimeout(renderTrendChart, 250)
      })
    } else {
      controlledError.value = res.data?.message || '获取全路径排查数据失败'
    }
  } catch (e) {
    controlledError.value = '请求全路径排查数据异常'
  } finally {
    controlledLoading.value = false
  }
}

async function fetchCgrsRecords() {
  if (!props.machine || !props.date) return
  loading.value = true
  error.value = null
  records.value = []
  selectedEventIndex.value = 0
  selectedPath.value = null
  controlledData.value = null
  controlledError.value = null

  try {
    const [cgrsRes] = await Promise.allSettled([
      api.getCgrsRecords({
        workcenter: props.machine,
        date: props.date,
        article: props.article || undefined,
        indicator: props.indicator || undefined
      }),
      fetchControlledAnalysis()
    ])

    if (cgrsRes.status === 'fulfilled' && cgrsRes.value.data?.status === 'success') {
      records.value = cgrsRes.value.data.data || []
    }
  } catch (e) {
    error.value = '请求 CGRS 数据时发生网络或服务端异常'
  } finally {
    loading.value = false
  }
}

watch(
  [
    () => combinedChartData.value,
    () => selectedPath.value,
    () => controlledData.value,
    () => sameDayOnly.value,
    () => searchPathKeyword.value
  ],
  () => {
    nextTick(() => {
      setupResizeObserver()
      renderTrendChart()
      setTimeout(renderTrendChart, 50)
      setTimeout(renderTrendChart, 180)
    })
  },
  { deep: true }
)

watch(
  () => selectedEventIndex.value,
  (newIdx) => {
    nextTick(() => {
      zoomToEvent(newIdx)
    })
  }
)

watch(
  () => props.visible,
  (val) => {
    if (val) {
      fetchCgrsRecords()
    } else {
      selectedPath.value = null
      if (trendChartInstance) {
        trendChartInstance.dispose()
        trendChartInstance = null
      }
    }
  }
)

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (trendChartInstance) {
    window.removeEventListener('resize', handleResizeChart)
    trendChartInstance.dispose()
    trendChartInstance = null
  }
})
</script>

<style scoped>
.cgrs-meta-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 8px 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  flex-wrap: wrap;
  gap: 10px;
}

.meta-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.meta-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: #92400e;
}

.meta-badge strong {
  color: #b45309;
  font-family: 'JetBrains Mono', monospace;
}

.meta-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.warning-rank-tag {
  font-size: 11.5px;
  color: #dc2626;
  background: #fee2e2;
  border: 1px solid #fca5a5;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.count-badge {
  font-size: 12px;
  color: #b45309;
  background: #fef3c7;
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: 600;
  border: 1px solid #fde68a;
}

.cgrs-body-wrap {
  min-height: 260px;
  position: relative;
}

.cgrs-state-box {
  height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.state-error {
  color: #ef4444;
  font-size: 13px;
}

.cgrs-table-container {
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.table-title-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.table-title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-main-title {
  font-weight: 700;
  font-size: 13px;
  color: #1e293b;
}

.table-sub-count {
  font-size: 11.5px;
  color: #64748b;
}

.table-sub-count strong {
  color: #0369a1;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
}

:deep(.active-event-record-row) {
  background-color: #fffbeb !important;
}

:deep(.active-event-record-row td) {
  background-color: #fffbeb !important;
  border-bottom-color: #fde68a !important;
}

.time-col {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 11.5px;
  color: #334155;
}

.param-name-cell {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.param-local-name {
  font-weight: 700;
  font-size: 12.5px;
  color: #0f172a;
}

.param-code-name {
  font-size: 10.5px;
  color: #64748b;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}

.standard-val {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: #0f172a;
  font-size: 12px;
}

.change-diff-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
}

.from-tag {
  color: #64748b;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 500;
}

.arrow-sep {
  color: #f59e0b;
  font-weight: bold;
}

.to-tag {
  color: #0369a1;
  background: #e0f2fe;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 700;
}

.unit-text {
  font-size: 10.5px;
  color: #94a3b8;
  margin-left: 2px;
}

.offset-val {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  color: #b45309;
  font-size: 12px;
}

.offset-val.is-zero {
  color: #64748b;
  font-weight: 500;
}

.recipe-cell {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.spec-code {
  font-weight: 700;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
  color: #0369a1;
}

.recipe-desc {
  font-size: 10.5px;
  color: #64748b;
  margin-top: 1px;
}

.user-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: #334155;
  font-weight: 500;
}

.font-mono {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}

.font-bold {
  font-weight: 700;
}

.yoy-badge {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
  font-weight: 800;
  padding: 1px 8px;
  border-radius: 4px;
}

.pos-badge {
  color: #15803d;
  background: #dcfce7;
  border: 1px solid #86efac;
}

.neg-badge {
  color: #b91c1c;
  background: #fee2e2;
  border: 1px solid #fca5a5;
}

/* 控制变量排查详细面板 */
.controlled-panel {
  background: #ffffff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(2, 132, 199, 0.06);
}

.ctrl-header {
  background: #f0f9ff;
  padding: 8px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e0f2fe;
  flex-wrap: wrap;
  gap: 10px;
}

.ctrl-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #0369a1;
}

.ctrl-switcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.switcher-label {
  font-size: 12px;
  color: #0369a1;
  font-weight: 600;
}

.ctrl-body {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.event-meta-info {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: #475569;
  flex-wrap: wrap;
}

.event-meta-info strong {
  color: #1e293b;
  font-family: 'JetBrains Mono', monospace;
}

/* 结论卡片 */
.conclusion-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 6px;
  border: 1px solid transparent;
}

.conclusion-card.is-confirmed {
  background: #f0fdf4;
  border-color: #86efac;
  color: #166534;
}

.conclusion-card.is-interference {
  background: #fffbeb;
  border-color: #fde68a;
  color: #92400e;
}

.conclusion-card.is-insufficient {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #475569;
}

.conclusion-icon {
  margin-top: 1px;
  flex-shrink: 0;
}

.conclusion-card.is-confirmed .conclusion-icon {
  color: #16a34a;
}

.conclusion-card.is-interference .conclusion-icon {
  color: #d97706;
}

.conclusion-card.is-insufficient .conclusion-icon {
  color: #64748b;
}

.conclusion-text-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conclusion-title {
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.interfere-badge {
  font-size: 11px;
  background: #fee2e2;
  color: #b91c1c;
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid #fca5a5;
  font-weight: 600;
}

.conclusion-desc {
  font-size: 12px;
  line-height: 1.5;
  opacity: 0.95;
}

/* 全路径总体汇总指标卡片 */
.overall-summary-bar {
  display: flex;
  align-items: center;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  padding: 8px 14px;
  gap: 14px;
  flex-wrap: wrap;
}

.summary-title-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 700;
  color: #15803d;
  background: #dcfce7;
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid #86efac;
}

.summary-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.summary-item .lbl {
  font-size: 12px;
  color: #334155;
  font-weight: 500;
}

.summary-item .val {
  font-size: 13px;
  font-weight: 700;
}

.summary-sep {
  color: #16a34a;
  font-weight: bold;
  font-size: 13px;
}

.summary-divider {
  width: 1px;
  height: 16px;
  background: #cbd5e1;
}

/* 表格上方工具栏 */
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 2px;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-title {
  font-size: 12.5px;
  font-weight: 700;
  color: #0f172a;
}

.count-tag {
  font-size: 11.5px;
  color: #64748b;
}

.count-tag strong {
  color: #0284c7;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.filter-lbl {
  font-size: 12px;
  color: #475569;
}

/* 路径单元格样式 */
.path-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.path-gt {
  color: #0369a1;
  font-weight: 700;
}

.path-arrow {
  color: #94a3b8;
  font-size: 11px;
}

.path-ct {
  color: #0d9488;
  font-weight: 600;
}

.path-tu {
  color: #4338ca;
  font-weight: 600;
}

.path-ct.is-suspect, .path-tu.is-suspect {
  color: #dc2626;
  font-weight: 800;
  text-decoration: underline;
}

.ctrl-table-box {
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.table-title-bar {
  padding: 8px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

/* 折线图卡片样式 */
.ctrl-chart-box {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 14px 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

/* 左右双栏布局样式 (左侧折线图，右侧统计差异表) */
.trend-grid-layout {
  display: flex;
  gap: 16px;
  align-items: stretch;
  width: 100%;
}

.trend-left-panel {
  flex: 1.7;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.trend-right-panel {
  flex: 1;
  min-width: 280px;
  display: flex;
  flex-direction: column;
}

.stats-card {
  height: 100%;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.02);
}

.stats-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e2e8f0;
}

.stats-card-title-wrap {
  display: flex;
  align-items: center;
  gap: 5px;
}

.stats-card-title {
  font-size: 12.5px;
  font-weight: 700;
  color: #1e293b;
}

.stats-scope-badge {
  font-size: 10.5px;
  color: #4338ca;
  background: #e0e7ff;
  border: 1px solid #c7d2fe;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.stats-table-body {
  flex: 1;
  display: flex;
  align-items: center;
}

.stats-mini-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.stats-mini-table th {
  background: #f1f5f9;
  color: #475569;
  font-weight: 700;
  padding: 6px 8px;
  font-size: 11px;
  border-bottom: 1px solid #cbd5e1;
}

.stats-mini-table td {
  padding: 8px 8px;
  border-bottom: 1px solid #e2e8f0;
  vertical-align: middle;
}

.stats-mini-table tr.cpk-row {
  background: #ffffff;
}

.stats-mini-table tr.cpk-row td {
  border-bottom: none;
  padding-top: 10px;
  padding-bottom: 10px;
}

.metric-name-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #334155;
  font-weight: 500;
}

.metric-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.metric-dot.mu-dot { background: #f59e0b; }
.metric-dot.sigma-dot { background: #0284c7; }
.metric-dot.cpk-dot { background: #10b981; }

.val-cell {
  color: #1e293b;
  font-size: 12px;
}

.diff-cell {
  color: #475569;
  font-size: 12px;
}

.text-warn { color: #d97706; font-weight: 600; }
.text-info { color: #0284c7; font-weight: 600; }
.text-good { color: #059669; font-weight: 700; }
.text-bad { color: #dc2626; font-weight: 700; }

.yoy-chip {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11.5px;
  font-weight: 700;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-variant-numeric: tabular-nums;
}

.chip-good {
  background: #d1fae5;
  color: #047857;
  border: 1px solid #a7f3d0;
}

.chip-bad {
  background: #fee2e2;
  color: #b91c1c;
  border: 1px solid #fca5a5;
}

.stats-card-footer {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #cbd5e1;
}

.footer-note {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10.5px;
  color: #64748b;
}

.note-bullet {
  font-size: 11px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: wrap;
  gap: 8px;
}

.chart-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.chart-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
}

.view-tag {
  font-size: 11px;
}

.chart-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chart-legend-hint {
  font-size: 11px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot.before {
  background: #f59e0b;
}

.legend-dot.after {
  background: #10b981;
}

.legend-line.split {
  display: inline-block;
  width: 12px;
  height: 2px;
  background: #ef4444;
  border-top: 2px dashed #ef4444;
}

.trend-chart-wrapper {
  position: relative;
  width: 100%;
  height: 250px;
}

.trend-chart-canvas {
  width: 100%;
  height: 100%;
}

.chart-empty-tip {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
  z-index: 5;
}

.click-hint-tag {
  font-size: 11px;
  color: #0284c7;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 6px;
}

/* 高亮被选中的路径行 */
:deep(.selected-path-row) {
  background-color: #f0fdf4 !important;
}

:deep(.selected-path-row td) {
  background-color: #f0fdf4 !important;
  font-weight: 600;
}

/* 全局最佳/最差调参比对 Banner 样式 */
.global-ranking-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 2px;
}

/* 折叠面板通用卡片样式 */
.collapsible-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

.collapsible-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #f8fafc;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;
}

.collapsible-header:hover {
  background: #f1f5f9;
}

.collapsible-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapsible-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.collapsible-body {
  padding: 10px 14px 14px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
}

/* ==================== 高颜值的对比分析卡片 (Best/Worst Cards) ==================== */
.ranking-cards-container {
  width: 100%;
}

.ranking-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.ranking-grid.single-card-grid {
  grid-template-columns: 1fr;
}

@media (max-width: 768px) {
  .ranking-grid {
    grid-template-columns: 1fr;
  }
}

.rank-card {
  border-radius: 8px;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.rank-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.rank-card.is-best {
  background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
  border: 1px solid #a7f3d0;
}

.rank-card.is-best.is-active {
  border: 2px solid #059669;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
}

.rank-card.is-worst {
  background: linear-gradient(135deg, #fff5f5 0%, #fef2f2 100%);
  border: 1px solid #fecaca;
}

.rank-card.is-worst.is-active {
  border: 2px solid #dc2626;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2);
}

.rank-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.rank-tag {
  font-size: 11.5px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tag-best {
  background: #d1fae5;
  color: #047857;
  border: 1px solid #a7f3d0;
}

.tag-worst {
  background: #fee2e2;
  color: #b91c1c;
  border: 1px solid #fca5a5;
}

.active-pill {
  font-size: 10.5px;
  font-weight: 700;
  color: #ffffff;
  background: #0284c7;
  padding: 1px 7px;
  border-radius: 10px;
}

.click-hint {
  font-size: 10.5px;
  color: #94a3b8;
  transition: color 0.2s ease;
}

.rank-card:hover .click-hint {
  color: #0284c7;
  font-weight: 600;
}

.event-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: #1e293b;
  margin-bottom: 4px;
}

.event-time {
  font-size: 11.5px;
  color: #64748b;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(226, 232, 240, 0.8);
  padding: 1px 6px;
  border-radius: 4px;
}

.metrics-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.pct-val {
  font-size: 15px;
  font-weight: 800;
}

.pct-val.pos-text {
  color: #059669;
}

.pct-val.neg-text {
  color: #dc2626;
}

.cpk-pair {
  font-size: 11.5px;
  color: #475569;
}

.minimal-conclusion-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 6px;
  border-top: 1px dashed #e2e8f0;
  flex-wrap: wrap;
  gap: 8px;
}

.conc-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  flex-wrap: wrap;
}

.conc-title {
  font-weight: 800;
  color: #0f172a;
}

.conc-event {
  font-weight: 700;
  color: #0284c7;
  background: #e0f2fe;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11.5px;
}

.conc-metrics {
  color: #334155;
}

.path-warning-red-dot {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11.5px;
  font-weight: 700;
  color: #dc2626;
}

.red-dot {
  font-size: 10px;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.4; }
  100% { opacity: 1; }
}

.cgrs-dialog-footer {
  display: flex;
  justify-content: flex-end;
}

/* 样本不足/无记录被置灰禁用的调参事件按钮 */
:deep(.el-radio-button.is-disabled-event .el-radio-button__inner) {
  background-color: #f1f5f9 !important;
  color: #94a3b8 !important;
  border-color: #e2e8f0 !important;
  cursor: not-allowed !important;
  box-shadow: none !important;
  opacity: 0.85;
}

:deep(.el-radio-button.is-disabled-event:hover .el-radio-button__inner) {
  background-color: #e2e8f0 !important;
  color: #64748b !important;
}

/* 💡 智能推荐最佳工艺参数卡 (高级规格表 - 专注结果模式) */
.cgrs-recommend-panel {
  margin: 4px 0 16px 0;
  background: #ffffff;
  border: 1px solid #a7f3d0;
  border-radius: 10px;
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.09);
  overflow: hidden;
}

.recommend-panel-header {
  padding: 14px 18px;
  background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
  border-bottom: 1px solid #a7f3d0;
}

.header-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.recommend-badge-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 800;
  color: #065f46;
}

.recommend-meta-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #047857;
}

.recommend-meta-chips .chip-item {
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #6ee7b7;
  padding: 2px 9px;
  border-radius: 5px;
}

.recommend-meta-chips .scope-chip {
  background: #047857;
  color: #ffffff;
  border: none;
}

.recommend-panel-body {
  padding: 14px 18px 18px;
}

.recommend-banner-desc {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12.5px;
  color: #166534;
  margin-bottom: 14px;
}

.spec-grid-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.spec-grid-header {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.spec-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.spec-card-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-left: 4px solid #10b981;
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: all 0.2s ease;
}

.spec-card-item:hover {
  border-color: #34d399;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.12);
  transform: translateY(-1px);
}

.spec-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.spec-local-name {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.spec-card-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.val-num {
  font-size: 20px;
  font-weight: 800;
  color: #047857;
}

.val-unit {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.spec-sys-name {
  font-size: 10.5px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
