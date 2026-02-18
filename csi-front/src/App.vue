<template>
  <router-view v-slot="{ Component }">
    <keep-alive :include="cachedViewNames">
      <component :is="Component" />
    </keep-alive>
  </router-view>
</template>

<script>
export default {
  name: 'App',
  computed: {
    cachedViewNames() {
      return this.$router.getRoutes()
        .filter(r => r.meta?.keepAlive)
        .map(r => {
          const comp = r.components?.default ?? r.component
          return comp?.name
        })
        .filter(Boolean)
    }
  }
}
</script>
