/**
 * PortCard 类型校验测试。
 */
import { describe, it, expect } from 'vitest'
import type { PortCard, PortAnalysis } from '@/api'

describe('PortCard 类型', () => {
  it('支持 conflict 来源标记', () => {
    const card: PortCard = {
      type: 'used',
      port: 8080,
      protocol: 'TCP',
      conflict: true,
      conflict_sources: ['docker', 'host'],
    }
    expect(card.conflict).toBe(true)
    expect(card.conflict_sources).toEqual(['docker', 'host'])
  })

  it('PortAnalysis 包含分页游标', () => {
    const analysis: PortAnalysis = {
      port_cards: [],
      total_used: 100,
      total_available: 65435,
      tcp_used: 80,
      udp_used: 20,
      docker_containers: 5,
      hidden_ports: [22],
      protocol_filter: 'TCP',
      start_port: 1,
      end_port: 65535,
      next_cursor: 'cursor123',
      has_more: true,
    }
    expect(analysis.next_cursor).toBe('cursor123')
    expect(analysis.has_more).toBe(true)
  })

  it('CustomRange 字段正确', () => {
    const range = {
      id: 'a1b2c3d4',
      name: '游戏服务器',
      start_port: 22500,
      end_port: 22600,
      color: '#00b4d8',
      created_at: '2025-01-01T00:00:00Z',
    }
    expect(range.start_port).toBeLessThan(range.end_port)
    expect(range.color).toMatch(/^#/)
  })
})
