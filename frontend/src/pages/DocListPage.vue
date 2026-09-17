<template>
  <DocListView :key="doctype" :doctype="doctype" class="h-full" />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DocListView from '@/components/list/DocListView.vue'

const route = useRoute()
// vue-router decodes path params, so this is the exact Frappe doctype name
// (e.g. "Email Domain"), matching what sidebar.py's _frontend_route encoded.
const doctype = computed(() => route.params.doctype)
</script>
