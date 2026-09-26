<template>
  <SectionCard
    title="Start from an Agreement Template"
    :subtitle="detail.isNew.value ? 'Or upload your own PDF below.' : 'Replaces the current PDF and fields.'"
  >
    <div class="flex max-w-md flex-col gap-4">
      <AppInput v-model="signerEmail" type="email" label="Signer email" placeholder="signer@email.com" required />
    </div>
    <TemplateFillForm ref="form" />
    <div v-if="hasTemplate">
      <AppButton icon="check" :loading="applying" @click="apply">{{ detail.isNew.value ? 'Create from Template' : 'Apply Template' }}</AppButton>
    </div>
  </SectionCard>
</template>

<script setup>
// E Sign form, inline: fill an Agreement Template right here (no dialog). On a new
// document it creates the E Sign from the template and opens it; on a Draft it applies the
// template to this document (server: esign.template_flow).
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import TemplateFillForm from '@/components/detail/esign/TemplateFillForm.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, default: '' },
})

const router = useRouter()
const form = ref(null)
const signerEmail = ref('')
const applying = ref(false)
const hasTemplate = computed(() => !!form.value?.template)

async function apply() {
  if (!/^\S+@\S+\.\S+$/.test(signerEmail.value.trim())) return notify.error('Enter a valid signer email.')
  applying.value = true
  try {
    const args = { template: form.value.template, data: form.value.payload(), signer_email: signerEmail.value.trim() }
    if (props.detail.isNew.value) {
      const r = await call('verp_staffing.esign.template_flow.create_from_template', { ...args, title: props.detail.values.title || '' })
      notify.success('E Sign created from template.')
      router.replace(`/${encodeURIComponent('E Sign')}/${encodeURIComponent(r.esign)}`)
      return
    }
    if (props.detail.isDirty.value && !(await props.detail.submit())) return
    await call('verp_staffing.esign.template_flow.apply_template', { esign: props.name, ...args })
    notify.success('Template applied.')
    form.value.reset()
    props.detail.refresh()
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    applying.value = false
  }
}
</script>
