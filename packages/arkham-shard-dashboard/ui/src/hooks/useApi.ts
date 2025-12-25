import { useState, useEffect, useCallback } from 'react'

const API_BASE = ''  // Uses Vite proxy

export interface ServiceHealth {
  database: { available: boolean; info: { url?: string } | null }
  vectors: { available: boolean; info: any }
  llm: { available: boolean; info: { endpoint?: string } | null }
  workers: { available: boolean; info: any[] | null }
  events: { available: boolean; info: any }
}

export interface LLMConfig {
  endpoint: string
  model: string
  available: boolean
}

export interface DatabaseInfo {
  available: boolean
  url: string
  schemas: string[]
}

export interface QueueStats {
  name: string
  pending: number
  active: number
  completed: number
  failed: number
}

export function useHealth() {
  const [health, setHealth] = useState<ServiceHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/health`)
      if (!res.ok) throw new Error('Failed to fetch health')
      const data = await res.json()
      setHealth(data)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  return { health, loading, error, refresh }
}

export function useLLMConfig() {
  const [config, setConfig] = useState<LLMConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/llm`)
      if (!res.ok) throw new Error('Failed to fetch LLM config')
      const data = await res.json()
      setConfig(data)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  const updateConfig = async (endpoint?: string, model?: string) => {
    const res = await fetch(`${API_BASE}/api/dashboard/llm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ endpoint, model }),
    })
    if (!res.ok) throw new Error('Failed to update LLM config')
    await refresh()
  }

  const testConnection = async () => {
    const res = await fetch(`${API_BASE}/api/dashboard/llm/test`, { method: 'POST' })
    return res.json()
  }

  useEffect(() => { refresh() }, [refresh])

  return { config, loading, error, refresh, updateConfig, testConnection }
}

export function useDatabase() {
  const [info, setInfo] = useState<DatabaseInfo | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/database`)
      if (!res.ok) throw new Error('Failed to fetch database info')
      setInfo(await res.json())
    } finally {
      setLoading(false)
    }
  }, [])

  const runMigrations = async () => {
    const res = await fetch(`${API_BASE}/api/dashboard/database/migrate`, { method: 'POST' })
    return res.json()
  }

  const resetDatabase = async (confirm: boolean) => {
    const res = await fetch(`${API_BASE}/api/dashboard/database/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm }),
    })
    return res.json()
  }

  const vacuumDatabase = async () => {
    const res = await fetch(`${API_BASE}/api/dashboard/database/vacuum`, { method: 'POST' })
    return res.json()
  }

  useEffect(() => { refresh() }, [refresh])

  return { info, loading, refresh, runMigrations, resetDatabase, vacuumDatabase }
}

export function useQueues() {
  const [queues, setQueues] = useState<QueueStats[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/queues`)
      if (!res.ok) throw new Error('Failed to fetch queues')
      const data = await res.json()
      setQueues(data.queues || [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 3000)
    return () => clearInterval(interval)
  }, [refresh])

  return { queues, loading, refresh }
}

export function useEvents() {
  const [events, setEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/events?limit=50`)
      if (!res.ok) throw new Error('Failed to fetch events')
      const data = await res.json()
      setEvents(data.events || [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  return { events, loading, refresh }
}
