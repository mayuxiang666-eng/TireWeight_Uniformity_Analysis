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
    <CgrsRecordPanel
      v-if="dialogVisible"
      :machine="machine"
      :date="date"
      :article="article"
      :indicator="indicator"
      :is-top-warning="isTopWarning"
      :top-machines="topMachines"
      :recommend-reason="recommendReason"
      @open-recommend-dialog="payload => emit('open-recommend-dialog', payload)"
      @close="dialogVisible = false"
    />

    <!-- 底部操作栏 -->
    <template #footer>
      <div class="cgrs-dialog-footer">
        <el-button type="primary" size="small" @click="dialogVisible = false">关闭</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import CgrsRecordPanel from './CgrsRecordPanel.vue'

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

const emit = defineEmits(['update:visible', 'open-recommend-dialog'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const isCu = computed(() => String(props.machine || '').trim().toUpperCase().startsWith('CU'))
</script>

<style scoped>
.cgrs-dialog :deep(.el-dialog__body) {
  padding: 14px 18px 16px;
  background: #f8fafc;
}
.cgrs-dialog-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
