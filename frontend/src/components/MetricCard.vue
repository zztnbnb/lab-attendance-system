<script setup lang="ts">
defineProps<{ label: string; value: string | number; note?: string; tone?: 'mint' | 'blue' | 'amber' | 'purple' }>()
</script>

<template>
  <div class="metric-card" :class="`metric-card--${tone ?? 'mint'}`">
    <div class="metric-card__top">
      <span>{{ label }}</span>
      <span class="metric-card__dot" />
    </div>
    <strong>{{ value }}</strong>
    <small v-if="note">{{ note }}</small>
  </div>
</template>
