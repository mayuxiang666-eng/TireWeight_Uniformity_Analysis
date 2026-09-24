<template>
  <el-dialog
    v-model="dialogVisible"
    :title="`规格 [${article10 || '未选定'}] 单胎实测值时序折线图 (Barcode Run Chart)`"
    width="92%"
    top="4vh"
    destroy-on-close
    append-to-body
    class="barcode-measurements-dialog"
    @opened="loadData"
  >
    <!-- 弹窗顶栏信息与指标切换器 -->
    <div class="dialog-header-bar">
      <div class="header-tags">
        <el-tag type="success" size="default" effect="dark">
          规格: {{ article10 }}
        </el-tag>
        <el-tag type="info" size="default">
          📅 日期: {{ targetDate || '最新' }}
        </el-tag>
      </div>

      <div class="header-indicator-switch">
        <span style="font-size: 12px; color: var(--el-text-color-regular); margin-right: 8px;">切换分析指标:</span>
        <el-select v-model="currentIndicator" size="small" style="width: 130px;" @change="loadData">
          <el-option-group label="TU">
            <el-option label="RFPP" value="rfpp" />
            <el-option label="RFH1" value="rfh1" />
            <el-option label="RFH2" value="rfh2" />
            <el-option label="LFPP" value="lfpp" />
            <el-option label="LFH1" value="lfh1" />
            <el-option label="CONY" value="cony" />
            <el-option label="PLYS" value="plys" />
          </el-option-group>
          <el-option-group label="TG">
            <el-option label="TBUL" value="tbul" />
            <el-option label="BBUL" value="bbul" />
            <el-option label="TDEP" value="tdep" />
            <el-option label="BDEP" value="bdep" />
            <el-option label="TLRO" value="tlro" />
            <el-option label="BLRO" value="blro" />
            <el-option label="CRRO" value="crro" />
          </el-option-group>
          <el-option-group label="TB">
            <el-option label="TBALW" value="tbalw" />
            <el-option label="BBALW" value="bbalw" />
            <el-option label="SBALW" value="sbalw" />
          </el-option-group>
        </el-select>
      </div>
    </div>

    <!-- 主图表区域 -->
    <div class="dialog-body-container">
      <BarcodeMeasurementsChart
        :chart-data="chartData"
        :summary="summary"
        :loading="loading"
        :error="error"
        :indicator="currentIndicator"
        @reload="loadData"
      />
    </div>

    <template #footer>
      <div class="dialog-footer">
        <span class="footer-tip">
          * 数据源自生胎成型与终检机台实测记录，按生产发生时序严格正序排列
        </span>
        <el-button @click="dialogVisible = false">关闭</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { api } from '@/api'
import BarcodeMeasurementsChart from '@/components/charts/BarcodeMeasurementsChart.vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  article10: {
    type: String,
    default: ''
  },
  targetDate: {
    type: String,
    default: ''
  },
  indicator: {
    type: String,
    default: 'rfpp'
  },
  timeCol: {
    type: String,
    default: 'tu_first_loc_timestamp'
  },
  phase: {
    type: String,
    default: 'all'
  }
})

const emit = defineEmits(['update:visible'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const currentIndicator = ref(props.indicator || 'rfpp')
const chartData = ref([])
const summary = ref(null)
const loading = ref(false)
const error = ref(null)

watch(
  () => props.indicator,
  (newVal) => {
    if (newVal) currentIndicator.value = newVal
  }
)

async function loadData() {
  if (!props.article10) {
    chartData.value = []
    summary.value = null
    return
  }
  loading.value = true
  error.value = null
  try {
    const params = {
      article10: props.article10,
      target_date: props.targetDate,
      indicator: currentIndicator.value,
      time_col: props.timeCol,
      phase: props.phase
    }
    const res = await api.getBarcodeMeasurements(params)
    if (res.data.status === 'success') {
      chartData.value = res.data.data || []
      summary.value = res.data.summary || null
    } else {
      error.value = res.data.message || '获取单胎实测数据失败'
      chartData.value = []
      summary.value = null
    }
  } catch (e) {
    error.value = '网络请求异常，无法加载单胎实测数据'
    chartData.value = []
    summary.value = null
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.dialog-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 0 4px;
  flex-wrap: wrap;
  gap: 10px;
}

.header-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-indicator-switch {
  display: flex;
  align-items: center;
}

.dialog-body-container {
  min-height: 520px;
  height: 560px;
  display: flex;
  flex-direction: column;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-tip {
  font-size: 12px;
  color: #94a3b8;
}
</style>
