<script setup>
/**
 * KPI 数值滚动（visual-v0 §10.6 count-up）
 *
 * 纯数字（可含千分位逗号）→ rAF 补间滚动；其他文本（如「警告Ⅲ级」）原样渲染。
 */
import { useCountUp } from '@/composables/useCountUp'

const props = defineProps({
  value: { type: [String, Number], default: '' },
})

const text = useCountUp(() => props.value)
</script>

<template><span class="anim-num">{{ text }}</span></template>

<style scoped>
.anim-num { white-space: nowrap; }
</style>
