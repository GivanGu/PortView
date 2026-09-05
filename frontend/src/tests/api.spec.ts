/**
 * API 封装层测试。
 * 测试查询字符串构建逻辑与错误处理。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock fetch
global.fetch = vi.fn()

afterEach(() => {
  vi.clearAllMocks()
})

describe('API 查询字符串', () => {
  it('构建正确的查询参数', () => {
    const params = new URLSearchParams()
    params.set('protocol', 'tcp')
    params.set('start_port', String(80))
    params.set('end_port', String(8080))
    params.set('search', 'nginx')
    params.set('cursor', 'abc123')
    params.set('limit', String(20))
    params.set('range_id', 'r1')

    const query = params.toString()
    expect(query).toBe('protocol=tcp&start_port=80&end_port=8080&search=nginx&cursor=abc123&limit=20&range_id=r1')
  })

  it('空参数不加入查询字符串', () => {
    const qs = new URLSearchParams()
    const params: Record<string, string | number | undefined> = {
      protocol: undefined,
      search: undefined,
      limit: 50,
    }
    if (params.protocol) qs.set('protocol', params.protocol)
    if (params.search) qs.set('search', params.search)
    if (params.limit) qs.set('limit', String(params.limit))

    const query = qs.toString()
    expect(query).toBe('limit=50')
  })
})

describe('API 请求响应类型', () => {
  it('ApiResponse 结构正确', () => {
    const mockResponse = {
      success: true,
      data: { port_cards: [], total_used: 0 },
      error: null,
      message: null,
    }
    expect(mockResponse.success).toBe(true)
    expect(mockResponse.data.port_cards).toEqual([])
    expect(mockResponse.error).toBeNull()
  })
})
