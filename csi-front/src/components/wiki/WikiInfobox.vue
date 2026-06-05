<template>
  <aside
    v-if="display"
    class="wiki-infobox w-full sm:w-72 lg:w-80 float-none sm:float-right clear-right ml-0 sm:ml-4 mb-4 bg-white rounded-xl shadow-sm border border-gray-200 text-sm overflow-hidden shrink-0"
  >
    <div class="bg-linear-to-br from-blue-50 to-white border-b border-gray-200 px-4 py-3 text-center">
      <p class="font-bold text-gray-900">{{ display.caption }}</p>
      <p v-if="display.series" class="text-xs text-gray-600 mt-0.5">{{ display.series }}</p>
    </div>
    <div
      v-if="!display.image"
      class="flex items-center justify-center h-40 bg-gray-50 border-b border-gray-100"
    >
      <Icon icon="mdi:account" class="text-6xl text-gray-300" />
    </div>
    <img
      v-else
      :src="display.image"
      :alt="display.caption"
      class="w-full object-cover border-b border-gray-100"
    />
    <table v-if="display.rows.length" class="w-full border-collapse">
      <tbody>
        <tr
          v-for="(row, index) in display.rows"
          :key="`${row.label}-${index}`"
          :class="index % 2 === 0 ? 'bg-white' : 'bg-gray-50/60'"
        >
          <th
            scope="row"
            class="align-top text-left font-medium text-gray-600 px-4 py-2.5 w-[38%] border-t border-gray-100 text-xs"
          >
            {{ row.label }}
          </th>
          <td class="align-top text-gray-900 px-4 py-2.5 border-t border-gray-100">
            {{ row.value }}
          </td>
        </tr>
      </tbody>
    </table>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

/**
 * @typedef {import('@/types/wiki.js').WikiInfobox} WikiInfobox
 */

const props = defineProps({
  /** @type {import('vue').PropType<WikiInfobox|null>} */
  infobox: {
    type: Object,
    default: null,
  },
})

const display = computed(() => {
  if (!props.infobox?.caption) return null
  return {
    caption: props.infobox.caption,
    series: props.infobox.series || '',
    image: props.infobox.image ?? null,
    rows: Array.isArray(props.infobox.rows) ? props.infobox.rows : [],
  }
})
</script>
