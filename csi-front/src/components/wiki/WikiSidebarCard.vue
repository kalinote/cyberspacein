<template>
  <section class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
    <header
      v-if="title || $slots.title || $slots.actions"
      class="px-5 py-3.5 border-b border-gray-100 bg-gray-50/60 flex items-center justify-between gap-2"
    >
      <h2 class="text-base font-bold text-gray-900 min-w-0">
        <slot name="title">{{ title }}</slot>
      </h2>
      <div v-if="$slots.actions" class="shrink-0 flex items-center gap-1">
        <slot name="actions" />
      </div>
    </header>
    <div :class="bodyClass">
      <slot />
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '',
  },
  subtitle: {
    type: String,
    default: '',
  },
  bodyClass: {
    type: String,
    default: 'p-4 sm:p-5',
  },
})
</script>
