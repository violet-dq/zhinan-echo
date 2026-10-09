<script setup lang="ts">
import { ref } from 'vue'
import LoginView from './views/LoginView.vue'
import MainView from './views/MainView.vue'

const authed = ref(!!localStorage.getItem('echo_token'))
const onAuthed = () => (authed.value = true)
const onLogout = () => (authed.value = false)
</script>

<template>
  <LoginView v-if="!authed" @authed="onAuthed" />
  <MainView v-else @logout="onLogout" />
</template>
