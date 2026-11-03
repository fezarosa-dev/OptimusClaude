export type Git = { pasta: string; repo: string; branch: string }

export type Agente = Git & {
  modelo: string
  effort: string
  contexto: number
  tokens: number
  missao: string
  inicio: number
  fim: number
}

declare module 'claude-code' {
  interface PluginState {
    'painel-agentes': { agentes: Record<string, Agente>; sessao: Git; agora: number }
  }
}
