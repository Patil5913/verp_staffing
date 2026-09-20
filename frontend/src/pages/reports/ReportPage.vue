<template>
  <!-- Keyed by name so moving between reports (e.g. from the hub's links or a
  ledger link) starts each with its own filters and result, not the last one's. -->
  <ReportView :key="reportName" :report-name="reportName" />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ReportView from '@/components/report/ReportView.vue'

const route = useRoute()
const reportName = computed(() => route.params.reportName)
</script>
