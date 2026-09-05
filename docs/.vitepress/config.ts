import { defineConfig } from 'vitepress'

export default defineConfig({
  locale: {
    root: {
      label: 'English',
      lang: 'en',
      themeLocale: {
        nav: [
          { text: 'Guide', link: '/guide/getting-started' },
          { text: 'API', link: '/guide/api' },
          { text: 'GitHub', link: 'https://github.com/GivanGu/PortView' },
        ],
        sidebar: {
          '/guide/': [
            {
              text: 'Guide',
              items: [
                { text: 'Getting Started', link: '/guide/getting-started' },
                { text: 'Configuration', link: '/guide/configuration' },
                { text: 'API Reference', link: '/guide/api' },
                { text: 'Keyboard Shortcuts', link: '/guide/shortcuts' },
                { text: 'Architecture', link: '/guide/architecture' },
              ],
            },
          ],
        },
        outline: {
          level: 'deep',
        },
        docFooter: {
          prev: 'Previous',
          next: 'Next',
        },
        sidebarMenuLabel: 'Menu',
        returnToTopLabel: 'Return to top',
      },
    },
  },
  themeConfig: {
    logo: '/portview-logo.png',
    site: {
      name: 'PortView',
      url: 'https://portview.givangu.com',
      description: 'Docker 容器与主机端口监控与可视化工具 — NAS 友好 · 轻量 · 极简依赖',
    },
    footer: {
      copyright: 'Copyright © 2025 PortView. Released under MIT.',
    },
  },
  cleanUrls: true,
  lastUpdatedText: 'Last updated',
  locales: {
    root: {
      label: 'English',
      lang: 'en',
      themeLocale: {
        nav: [
          { text: 'Guide', link: '/guide/getting-started' },
          { text: 'API', link: '/guide/api' },
          { text: 'GitHub', link: 'https://github.com/GivanGu/PortView' },
        ],
        sidebar: {
          '/guide/': [
            {
              text: 'Guide',
              items: [
                { text: 'Getting Started', link: '/guide/getting-started' },
                { text: 'Configuration', link: '/guide/configuration' },
                { text: 'API Reference', link: '/guide/api' },
                { text: 'Keyboard Shortcuts', link: '/guide/shortcuts' },
                { text: 'Architecture', link: '/guide/architecture' },
              ],
            },
          ],
        },
        docFooter: { prev: 'Previous', next: 'Next' },
        sidebarMenuLabel: 'Menu',
        returnToTopLabel: 'Return to top',
      },
    },
    'zh-CN': {
      label: '简体中文',
      lang: 'zh-CN',
      themeLocale: {
        nav: [
          { text: '指南', link: '/zh/guide/getting-started' },
          { text: 'API', link: '/zh/guide/api' },
          { text: 'GitHub', link: 'https://github.com/GivanGu/PortView' },
        ],
        sidebar: {
          '/zh/guide/': [
            {
              text: '指南',
              items: [
                { text: '快速开始', link: '/zh/guide/getting-started' },
                { text: '配置', link: '/zh/guide/configuration' },
                { text: 'API 参考', link: '/zh/guide/api' },
                { text: '快捷键', link: '/zh/guide/shortcuts' },
                { text: '架构', link: '/zh/guide/architecture' },
              ],
            },
          ],
        },
        docFooter: { prev: '上一页', next: '下一页' },
        sidebarMenuLabel: '菜单',
        returnToTopLabel: '返回顶部',
      },
    },
  },
})
