<template>
  <SectionCard title="Interviews" :subtitle="`${interviews.length} linked`">
    <p v-if="!interviews.length" class="py-4 text-center text-p-sm text-app-text-muted">No interviews linked yet.</p>
    <ul v-else class="flex flex-col divide-y divide-app-border">
      <li v-for="iv in visible" :key="iv.name" class="flex items-center gap-3 py-2">
        <span class="size-2 shrink-0 rounded-full bg-sky-400" />
        <!-- Every interview of this Marketing is listed, but only its owner can open it. -->
        <router-link
          v-if="iv.owner"
          :to="`/Interview/${encodeURIComponent(iv.name)}`"
          class="min-w-0 flex-1 truncate text-p-sm text-app-text hover:text-app-primary"
        >
          {{ iv.company }}<span v-if="iv.role" class="text-app-text-muted"> · {{ iv.role }}</span>
        </router-link>
        <span v-else class="min-w-0 flex-1 cursor-default truncate text-p-sm text-app-text-muted" title="Only the person who created this interview can open it">
          {{ iv.company }}<span v-if="iv.role"> · {{ iv.role }}</span>
          <span class="lucide-lock ml-1 inline-block size-3 align-[-1px]" />
        </span>
        <DocStatusBadge :status="iv.status" />
      </li>
    </ul>
    <button
      v-if="interviews.length > LIMIT"
      type="button"
      class="self-start text-p-sm font-medium text-app-primary hover:underline"
      @click="expanded = !expanded"
    >
      {{ expanded ? 'Show less' : `Read more (${interviews.length - LIMIT} more)` }}
    </button>
  </SectionCard>
</template>

<script setup>
// The Interviews linked to this Marketing record (desk form's
// render_interview_list), each linking through to the Interview page.
import { computed, ref, watch } from 'vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { useResource } from '@/composables/list/useResource'

const LIMIT = 5
defineOptions({ inheritAttrs: false })
const props = defineProps({ name: { type: String, required: true } })

// verp_staffing...marketing.get_interviews_by_marketing: all of this Marketing's interviews, each
// flagged `owner` when the current user created it (a permission-free read, so the list is complete).
const list = useResource({ url: 'verp_staffing.marketing.doctype.marketing.marketing.get_interviews_by_marketing', notifyOnError: false })
watch(
  () => props.name,
  (name) => name && list.resource.submit({ marketing: name }),
  { immediate: true },
)

const interviews = computed(() => list.resource.data || [])
const expanded = ref(false)
const visible = computed(() => (expanded.value ? interviews.value : interviews.value.slice(0, LIMIT)))
</script>
