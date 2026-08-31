<script setup>
import { useRoute, useRouter } from 'vue-router';
const route = useRoute();
const router = useRouter();

const tabs = [
  { path: '/chat', label: '对话', icon: 'chat' },
  { path: '/map', label: '地图', icon: 'map' },
  { path: '/profile', label: '我的', icon: 'profile' }
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
        <svg v-if="t.icon==='chat'" class="tab-icon" viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4V5Z"/><path d="M8 9h8M8 12h5"/></svg>
        <svg v-else-if="t.icon==='map'" class="tab-icon" viewBox="0 0 24 24"><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/></svg>
        <svg v-else class="tab-icon" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c.7-5 3.3-7 8-7s7.3 2 8 7"/></svg>
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
.tab-icon { width: 22px; height: 22px; margin-bottom: 2px; fill: none; stroke: currentColor; stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }
.app-main.has-tabs { padding-bottom: 60px; }
</style>
