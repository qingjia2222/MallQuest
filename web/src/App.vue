<script setup>
import { useRoute, useRouter } from 'vue-router';
const route = useRoute();
const router = useRouter();

const tabs = [
  { path: '/chat', label: '对话', icon: '💬' },
  { path: '/map', label: '地图', icon: '🗺️' },
  { path: '/profile', label: '我的', icon: '👤' }
];

const showTabs = () => Boolean(route.meta.tab) && (localStorage.getItem('mall_role') || 'visitor') === 'visitor';
</script>

<template>
  <div class="app-shell">
    <main class="app-main" :class="{ 'has-tabs': showTabs() }">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- 底部 tab（仅对话/地图/我的显示） -->
    <nav v-if="showTabs()" class="tabbar">
      <div v-for="t in tabs" :key="t.path" class="tab"
           :class="{ active: route.path === t.path }" @click="router.push(t.path)">
        <span class="tab-icon">{{ t.icon }}</span>
        <span class="tab-label">{{ t.label }}</span>
      </div>
    </nav>
  </div>
</template>

<style scoped>
.tabbar {
  display: flex; border-top: 1px solid var(--border); background: #fff;
  padding-bottom: env(safe-area-inset-bottom); height: 60px; flex-shrink: 0;
}
.tab {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #9CA3AF; cursor: pointer; font-size: 12px;
}
.tab.active { color: var(--primary); }
.tab-icon { font-size: 20px; margin-bottom: 2px; }
.app-main.has-tabs { padding-bottom: 60px; }
</style>
