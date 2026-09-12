<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { StickyNote, Container, Cog, Server } from 'lucide-vue-next'
import type { PortCard } from '@/api'

defineProps<{ card: PortCard }>()

const { t } = useI18n()
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
    <span
      class="port-source"
      :class="card.source"
    >
      <Container v-if="card.source === 'docker'" :size="13" class="port-source-icon" />
      <Cog v-else-if="card.source === 'system'" :size="13" class="port-source-icon" />
      <Server v-else :size="13" class="port-source-icon" />
      <span>{{ card.source === 'docker' ? t('common.sourceDocker') : card.source === 'system' ? t('common.sourceSystem') : t('common.sourceHost') }}</span>
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
