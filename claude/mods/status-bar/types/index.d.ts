export type Totals = { ms: number; tokens: number }

export type AgentRow = {
  id: string
  label: string
  type: string
  model?: string
  effort?: string | number
  tokens: number
  startedAt: number
  endedAt?: number
}

declare module 'claude-code' {
  interface PluginState {
    'status-bar': { totals: Totals; agents: AgentRow[]; now: number }
  }
}
