<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <img
    src="/logo.png"
    :width="size ?? 40"
    :height="size ?? 40"
    alt="知南·Echo"
    role="img"
    style="border-radius: 50%; object-fit: cover; display: block;"
  />
</template>
