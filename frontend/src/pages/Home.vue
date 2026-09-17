<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-8">
    <div
      class="flex flex-col gap-4 rounded-lg border border-app-border bg-app-panel p-6"
    >
      <h1 class="text-2xl font-semibold text-app-text">
        Vrugle Staffing ERP
      </h1>
      <p class="text-p-base text-app-text-muted">
        Navbar and sidebar are wired up to the same permission-filtered
        module tree as the desk sidebar. Build pages here to replace each
        module screen by screen.
      </p>
      <div class="flex items-center gap-2">
        <Button variant="solid" theme="blue" @click="ping">
          Ping backend
        </Button>
        <span v-if="pong" class="text-p-base text-app-text-muted">
          {{ pong }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, call } from 'frappe-ui'
import { notify } from '@/utils/common/notify'

const pong = ref('')

function ping() {
  call('frappe.ping')
    .then((r) => {
      pong.value = r
      notify.success('Backend responded: ' + r)
    })
    .catch(() => notify.error('Could not reach the backend.'))
}
</script>
