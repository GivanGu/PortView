<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { StickyNote, Container, Cog, Server, Lock, Globe, Pencil, MousePointerClick, Star } from 'lucide-vue-next'
import type { PortCard } from '@/api'
import { usePrefs, hasPortFavorite } from '@/store/prefs'

const props = defineProps<{
  card: PortCard
  // 最终展示的服务协议（人工指定 > 自动探测）；unknown 或未探测时不传
  scheme?: 'http' | 'https' | 'unknown'
  // 是否为人工指定（徽章显示铅笔标记）
  manual?: boolean
}>()

const emit = defineEmits<{
  (e: 'scheme-toggle'): void
  (e: 'favorite-toggle'): void
}>()

const { t } = useI18n()
const { favorites } = usePrefs()

// v1.6.2：已收藏端口在端口号旁显示实心 ★，点击取消收藏
const isFavorite = computed(
  () => props.card.port != null && hasPortFavorite(favorites.value, props.card.port),
)
</script>

<template>
  <div class="port-card-header">
    <span class="port-header-left">
      <span
        class="port-status-dot"
        :class="card.is_running === false ? 'is-offline' : 'is-online'"
        :title="card.is_running === false ? t('common.offline') : t('common.online')"
        :aria-label="card.is_running === false ? t('common.offline') : t('common.online')"
        role="img"
      ></span>
      <span class="port-number">{{ card.port }}</span>
      <button
        v-if="isFavorite"
        type="button"
        class="port-fav-star"
        :title="t('ports.favorited')"
        :aria-label="t('ports.favorited')"
        @click.stop="emit('favorite-toggle')"
      >
        <Star :size="14" fill="currentColor" />
      </button>
    </span>
    <span
      class="port-protocol"
      :class="(card.protocol || '').toLowerCase()"
    >{{ card.protocol }}</span>
  </div>

  <div class="port-service">
    {{ card.service_name || t('ports.unknownService') }}
  </div>

  <!-- v1.2：用户备注 -->
  <div v-if="card.remark" class="port-remark" :title="card.remark">
    <StickyNote :size="11" class="port-remark-icon" />
    <span class="port-remark-text">{{ card.remark }}</span>
  </div>

  <div class="port-detail">
    <span class="port-detail-left">
      <span
        class="port-source"
        :class="card.source"
      >
        <Container v-if="card.source === 'docker'" :size="13" class="port-source-icon" />
        <Cog v-else-if="card.source === 'system'" :size="13" class="port-source-icon" />
        <Server v-else :size="13" class="port-source-icon" />
        <span>{{ card.source === 'docker' ? t('common.sourceDocker') : card.source === 'system' ? t('common.sourceSystem') : t('common.sourceHost') }}</span>
      </span>

      <!-- 服务协议徽章：可点击循环切换（选择 → HTTP → HTTPS → 自动） -->
      <button
        v-if="scheme === 'https'"
        type="button"
        class="port-scheme https"
        :class="{ manual }"
        :title="manual ? t('ports.schemeManualHttpsTip') : t('ports.schemeHttpsTip')"
        @click.stop="emit('scheme-toggle')"
      >
        <Lock :size="11" class="port-scheme-icon" />
        <span>HTTPS</span>
        <Pencil v-if="manual" :size="9" class="port-scheme-manual-icon" />
      </button>
      <button
        v-else-if="scheme === 'http'"
        type="button"
        class="port-scheme http"
        :class="{ manual }"
        :title="manual ? t('ports.schemeManualHttpTip') : t('ports.schemeHttpTip')"
        @click.stop="emit('scheme-toggle')"
      >
        <Globe :size="11" class="port-scheme-icon" />
        <span>HTTP</span>
        <Pencil v-if="manual" :size="9" class="port-scheme-manual-icon" />
      </button>
      <button
        v-else-if="scheme === 'unknown'"
        type="button"
        class="port-scheme unknown"
        :title="t('ports.schemeSelectTip')"
        @click.stop="emit('scheme-toggle')"
      >
        <MousePointerClick :size="11" class="port-scheme-icon" />
        <span>{{ t('ports.schemeSelect') }}</span>
      </button>
    </span>

    <!-- 容器名（在线/离线状态由左上角圆点 + 背景深浅统一表达） -->
    <span
      v-if="card.container"
      class="port-status"
      :title="card.container"
    >
      <span class="port-status-container">{{ card.container }}</span>
    </span>
  </div>

  <!-- 镜像信息独立成一行，避免卡片高度不齐 -->
  <div v-if="card.image" class="port-image">
    <span class="port-image-label">{{ t('ports.image') }}</span>
    <span class="port-image-value">{{ card.image }}</span>
  </div>
</template>
