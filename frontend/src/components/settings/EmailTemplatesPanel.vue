<template>
  <DocListView doctype="Email Template" class="h-full" />
</template>

<script setup>
// Email Templates list, embedded in ERP Configuration. Mounted only while its tab is open
// (DetailPageLayout renders only the active tab), so the list isn't fetched up front.
import DocListView from '@/components/list/DocListView.vue'
</script>
