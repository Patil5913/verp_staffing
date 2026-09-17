<template>
  <div class="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8">
    <h1 class="text-2xl font-semibold text-app-text">{{ doctype }}</h1>
    <DocListView :key="doctype" :doctype="doctype" />
  </div>
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
