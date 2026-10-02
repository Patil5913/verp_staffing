<template>
  <div class="flex flex-col" :class="variant === 'text' ? 'gap-2' : ''" aria-hidden="true">
    <template v-if="variant === 'text'">
      <div
        v-for="i in lines"
        :key="i"
        class="h-3 animate-pulse rounded bg-app-panel-2"
        :style="{ width: i === lines && lines > 1 ? '60%' : '100%' }"
      />
    </template>
    <div v-else-if="variant === 'avatar'" class="size-9 animate-pulse rounded-full bg-app-panel-2" />
    <div v-else class="animate-pulse rounded-xl bg-app-panel-2" :style="{ height }" />
  </div>
</template>

<script setup>
// Loading placeholder: text lines, an avatar circle or a card-sized block.
defineProps({
  variant: { type: String, default: 'text' }, // text | avatar | block
  lines: { type: Number, default: 3 },
  height: { type: String, default: '6rem' },
})
</script>
