<template>
  <div class="machine-cpk-table-wrap">
    <div v-if="loading" class="skeleton" style="height: 100%; display: flex; align-items: center; justify-content: center; min-height: 300px;">
      <el-icon class="is-loading" size="24"><Loading /></el-icon>
      <span style="margin-left: 8px; font-size: 13px; color: var(--c-text-muted);">正在分析选中日期下的各工位机台 CPK...</span>
    </div>

    <div v-else-if="error" class="table-error" style="height: 100%; display: flex; align-items: center; justify-content: center; min-height: 300px; color: #ef4444;">
      <el-icon size="20"><WarningFilled /></el-icon>
      <span style="margin-left: 6px;">{{ error }}</span>
    </div>

    <div v-else-if="!data || Object.keys(data).length === 0" class="table-empty" style="height: 100%; display: flex; align-items: center; justify-content: center; min-height: 300px; color: #8c959f;">
      <el-empty description="选中日期下该规格无符合条件的生产机台数据" :image-size="60" />
    </div>

    <div v-else class="workcenter-scroll-container">
      <div
        v-for="(machines, wcLabel) in sortedData"
        :key="wcLabel"
        class="wc-group-card"
      >
        <div class="wc-group-title">
          <span class="wc-name">{{ wcLabel }}</span>
          <span class="wc-count">{{ machines.length }} 台机器生产</span>
        </div>

        <el-table
          :data="machines"
          size="small"
          stripe
          border
          style="width: 100%;"
        >
          <el-table-column prop="machine" label="机台编号" min-width="95" fixed>
            <template #default="{ row }">
              <span class="machine-badge">{{ row.machine }}</span>
            </template>
          </el-table-column>

          <!-- 第一列：单规格 (Single Spec / Weight Deviation) -->
          <el-table-column min-width="155">
            <template #header>
              <div class="header-with-tip">
                <span>{{ props.indicator === 'weight' ? '单规格偏差' : '单规格' }}</span>
                <span class="header-sub">规格: {{ selectedArticle || '未选中' }}</span>
              </div>
            </template>
            <template #default="{ row }">
              <el-tooltip placement="top" raw-content>
                <template #content>
                  <div style="font-size:12px; line-height:1.5;">
                    <template v-if="props.indicator === 'weight'">
                      <div>胎重指标偏差考核范围: <strong>±{{ row.spec_warning_threshold ?? '0.8' }}%</strong></div>
                      <div>偏差计算规则: <strong>(实际值 - 目标值) / 目标值 * 100%</strong></div>
                    </template>
                    <template v-else>
                      <div>单规格基准预警线 (μ - 1σ): <strong>{{ row.spec_warning_threshold ?? '-' }}</strong></div>
                      <div>规则A (5天内≥3点低于预警线): <strong :style="row.spec_rule_a ? 'color:#ef4444' : ''">{{ row.spec_rule_a ? '已触发 (' + row.spec_rule_a_count + '点)' : '未触发' }}</strong></div>
                      <div>规则B (连续3天下滑): <strong :style="row.spec_rule_b ? 'color:#ef4444' : ''">{{ row.spec_rule_b ? '已触发' : '未触发' }}</strong></div>
                    </template>
                  </div>
                </template>
                <el-button
                  size="small"
                  :type="row.spec_is_warning ? 'danger' : 'primary'"
                  text
                  bg
                  class="click-metric-btn"
                  :style="row.spec_is_warning ? 'color: #ef4444 !important; background-color: #fee2e2 !important; border: 1px solid #fecaca !important; font-weight: bold;' : ''"
                  @click="onCellClick(row, 'single')"
                >
                  <strong v-if="props.indicator === 'weight'">偏差: {{ row.spec_cpk > 0 ? '+' : '' }}{{ row.spec_cpk?.toFixed(2) }}%</strong>
                  <strong v-else>CPK: {{ row.spec_cpk?.toFixed(2) ?? '-' }}</strong>
                  <span class="sample-tag">(N={{ row.spec_n }})</span>
                </el-button>
              </el-tooltip>
            </template>
          </el-table-column>

          <!-- 第二列：多规格 (Multi Spec 全规格产量加权) -->
          <el-table-column min-width="165">
            <template #header>
              <div class="header-with-tip">
                <span>{{ props.indicator === 'weight' ? '多规格偏差' : '多规格' }}</span>
                <span class="header-sub">全规格产量加权</span>
              </div>
            </template>
            <template #default="{ row }">
              <el-tooltip placement="top" raw-content>
                <template #content>
                  <div style="font-size:12px; line-height:1.5;">
                    <template v-if="props.indicator === 'weight'">
                      <div>多规格加权生产偏差: <strong>{{ row.multi_cpk > 0 ? '+' : '' }}{{ row.multi_cpk?.toFixed(2) }}%</strong></div>
                      <div>按照当日该规格在机台上的多规格产量占比进行加权求和得出。</div>
                    </template>
                    <template v-else>
                      <div>多规格加权预警线 (μ - 1σ): <strong>{{ row.multi_warning_threshold ?? '-' }}</strong></div>
                      <div>规则A (5天内≥3点低于预警线): <strong :style="row.multi_rule_a ? 'color:#ef4444' : ''">{{ row.multi_rule_a ? '已触发 (' + row.multi_rule_a_count + '点)' : '未触发' }}</strong></div>
                      <div>规则B (连续3天下滑): <strong :style="row.multi_rule_b ? 'color:#ef4444' : ''">{{ row.multi_rule_b ? '已触发' : '未触发' }}</strong></div>
                    </template>
                  </div>
                </template>
                <el-button
                  size="small"
                  :type="row.multi_is_warning ? 'danger' : 'success'"
                  text
                  bg
                  class="click-metric-btn"
                  :style="row.multi_is_warning ? 'color: #ef4444 !important; background-color: #fee2e2 !important; border: 1px solid #fecaca !important; font-weight: bold;' : ''"
                  @click="onCellClick(row, 'multi')"
                >
                  <strong v-if="props.indicator === 'weight'">加权偏差: {{ row.multi_cpk > 0 ? '+' : '' }}{{ row.multi_cpk?.toFixed(2) }}%</strong>
                  <strong v-else>加权 CPK: {{ row.multi_cpk?.toFixed(2) ?? '-' }}</strong>
                  <span class="sample-tag">(N={{ row.multi_n }})</span>
                </el-button>
              </el-tooltip>
            </template>
          </el-table-column>

          <!-- 均值与标准差 / 物理均值差 -->
          <el-table-column :label="props.indicator === 'weight' ? '物理均值差' : '单规格 μ / σ'" min-width="120" align="right">
            <template #default="{ row }">
              <div class="stat-meta">
                <span v-if="props.indicator === 'weight'">{{ row.spec_avg > 0 ? '+' : '' }}{{ row.spec_avg?.toFixed(3) }} kg</span>
                <template v-else>
                  <span>μ: {{ row.spec_avg?.toFixed(2) }}</span>
                  <span class="meta-divider">|</span>
                  <span>σ: {{ row.spec_std?.toFixed(2) }}</span>
                </template>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  data:            { type: Object, default: () => ({}) },
  loading:         { type: Boolean, default: false },
  error:           { type: String, default: null },
  indicator:       { type: String, default: 'rfpp' },
  targetDate:      { type: String, default: null },
  selectedArticle: { type: String, default: null }
})

const emit = defineEmits(['open-trend'])

const workcenterRank = {
  // 终检
  "tu_first_workcenter": 1,
  "tg_first_workcenter": 2,
  "tb_first_workcenter": 3,
  // 硫化
  "ct_workcenter": 4,
  // 成型
  "gt_workcenter": 5,
  "ccs_workcenter": 6,
  // 裁断
  "first_breaker_workcenter": 7,
  "second_breaker_workcenter": 8,
  "first_ply_workcenter": 9,
  "wound_cap_ply1_workcenter": 10,
  "wound_cap_ply2_workcenter": 11,
  // 热准备
  "tread_workcenter": 12,
  "inner_liner_workcenter": 13,
  "sidewall_workcenter": 14,
  "bead_workcenter": 15
}

const sortedData = computed(() => {
  if (!props.data) return {}
  const entries = Object.entries(props.data)
  entries.sort((a, b) => {
    const aCol = a[1]?.[0]?.workcenter_col || ''
    const bCol = b[1]?.[0]?.workcenter_col || ''
    const aRank = workcenterRank[aCol] ?? 99
    const bRank = workcenterRank[bCol] ?? 99
    return aRank - bRank
  })
  return Object.fromEntries(entries)
})

function onCellClick(row, mode) {
  emit('open-trend', {
    machine: row.machine,
    workcenterCol: row.workcenter_col,
    mode: mode,
    article10: (mode === 'single' || mode === 'spec_3sigma') ? props.selectedArticle : null
  })
}
</script>

<style scoped>
.machine-cpk-table-wrap {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
}

.workcenter-scroll-container {
  height: 380px;
  overflow-y: auto;
  padding-right: 4px;
}

.wc-group-card {
  margin-bottom: 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 8px;
}

.wc-group-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  padding: 2px 4px;
}

.wc-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.wc-count {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.machine-badge {
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  color: var(--el-color-primary);
}

.header-with-tip {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.header-sub {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  font-weight: normal;
}

.click-metric-btn {
  font-family: 'JetBrains Mono', monospace;
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.sample-tag {
  font-size: 10px;
  opacity: 0.8;
}

.stat-meta {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-family: 'JetBrains Mono', monospace;
}

.meta-divider {
  margin: 0 4px;
  opacity: 0.4;
}
</style>
