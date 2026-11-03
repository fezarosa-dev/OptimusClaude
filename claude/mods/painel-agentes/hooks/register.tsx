import { atom, read, update } from 'claude-code'
import type { AgentInfo, AgentStatus, EngineInterface, ModelUsage, Register } from 'claude-code'

import type { Agente, Git } from '../types'

const PAINEL = 'agentes'
const TITULO = 'Agentes'
const CONCLUIDOS_VISIVEIS = 3
const PULSO_MS = 5000
// shortcut: janela por família (tabela de modelos de 06/10/2026: tudo 1M, menos a geração 4.5 e anteriores); modelo novo cai em 1M.
const JANELA_PADRAO = 1_000_000
const JANELA_ANTIGA = 200_000
const MODELO_ANTIGO = /-4-5|haiku-4|claude-3/
const ATIVOS: ReadonlySet<AgentStatus> = new Set(['pending', 'running', 'waiting', 'idle'])
const SIMBOLO: Record<AgentStatus, string> = {
  pending: '…', running: '●', waiting: '◐', idle: '○', completed: '✓', failed: '✗', killed: '✗',
}
const COR: Partial<Record<AgentStatus, string>> = {
  running: 'success', pending: 'warning', waiting: 'warning', failed: 'error', killed: 'error',
}
const CAMPOS_DE_CAMINHO = ['file_path', 'notebook_path', 'path']
const CAMINHO_NO_COMANDO = /(?:^|[\s'"=])(\/[^\s'"`;|&()]+)/
const SEM_GIT: Git = { pasta: '', repo: '', branch: '' }
const VAZIO: Agente = { ...SEM_GIT, modelo: '', effort: '', contexto: 0, tokens: 0, missao: '', inicio: 0, fim: 0 }

const agentes = atom({ plugin: 'painel-agentes', key: 'agentes' } as const, {})
const sessao = atom({ plugin: 'painel-agentes', key: 'sessao' } as const, SEM_GIT)
// Só serve para redesenhar o painel enquanto há agente ativo, e o tempo de cada um andar.
const agora = atom({ plugin: 'painel-agentes', key: 'agora' } as const, 0)
// shortcut: o repo de cada caminho fica guardado até o mod recarregar; uma troca de branch depois disso não aparece.
const repoPorCaminho = new Map<string, Promise<Git | undefined>>()

async function lerGit($: EngineInterface, cwd?: string): Promise<Git> {
  const git = async (...args: string[]) => {
    const feito = await $.process.run(['git', ...args], { cwd, timeoutMs: 3000 }).catch(() => undefined)
    return feito?.exitCode === 0 ? feito.stdout.trim() : ''
  }
  const [raiz, branch, commit, remoto] = await Promise.all([
    git('rev-parse', '--show-toplevel'),
    git('symbolic-ref', '--short', 'HEAD'),
    git('rev-parse', '--short', 'HEAD'),
    git('remote', 'get-url', 'origin'),
  ])
  const pasta = (raiz || cwd || '').split('/').pop() ?? ''
  const repo = /github\.com[:/](.+?)(?:\.git)?\/?$/.exec(remoto)?.[1] ?? ''
  return { pasta, repo, branch: raiz ? branch || commit : '' }
}

// Um arquivo não é pasta: tenta o caminho e depois a pasta dele.
async function repoDoCaminho($: EngineInterface, caminho: string): Promise<Git | undefined> {
  for (const dir of [caminho, caminho.replace(/\/[^/]+\/?$/, '') || '/']) {
    const git = await lerGit($, dir)
    if (git.branch) return git
  }
  return undefined
}

function caminhoTocado(campos: Record<string, unknown>): string | undefined {
  const direto = CAMPOS_DE_CAMINHO.map(c => campos[c]).find(v => typeof v === 'string' && v.startsWith('/'))
  if (typeof direto === 'string') return direto
  return typeof campos.command === 'string' ? CAMINHO_NO_COMANDO.exec(campos.command)?.[1] : undefined
}

async function mudar($: EngineInterface, id: string, campos: Partial<Agente> | ((a: Agente) => Partial<Agente>)) {
  const instante = await $.clock.now()
  await update($, agentes, todos => {
    const atual = todos[id] ?? { ...VAZIO, inicio: instante }
    const novos = typeof campos === 'function' ? campos(atual) : campos

    return { ...todos, [id]: { ...atual, ...novos } }
  })
}

async function pulsar($: EngineInterface) {
  const [lista, instante] = await Promise.all([$.agent.list(), $.clock.now()])
  if (lista.some(a => ATIVOS.has(a.status))) await update($, agora, () => instante)
}

// O prompt de agente vai em JSON mínimo com `missao`: o nome curto da tarefa. Sem ela, vale a descrição.
function missao(prompt: string, descricao: string): string {
  try {
    const dados: unknown = JSON.parse(prompt)
    if (dados && typeof dados === 'object' && 'missao' in dados && typeof dados.missao === 'string') return dados.missao
  } catch {
    // prompt em texto livre
  }
  return descricao
}

async function registrarCaminho($: EngineInterface, id: string, e: { tool: string }) {
  const caminho = caminhoTocado(e as unknown as Record<string, unknown>)
  if (!caminho) return
  if (!repoPorCaminho.has(caminho)) repoPorCaminho.set(caminho, repoDoCaminho($, caminho))
  const git = await repoPorCaminho.get(caminho)
  if (git) await mudar($, id, git)
}

type Passo = { agentId?: string; model: string; effort?: string | number }

async function registrarPasso($: EngineInterface, passo: Passo, uso: ModelUsage | null | undefined) {
  if (!passo.agentId) return
  const usados = uso
    ? uso.input_tokens + uso.cache_read_input_tokens + uso.cache_creation_input_tokens + uso.output_tokens
    : 0
  const effort = passo.effort === undefined ? '' : String(passo.effort)
  await mudar($, passo.agentId, atual => ({
    modelo: passo.model,
    effort,
    ...(usados > 0 ? { contexto: usados, tokens: atual.tokens + usados } : {}),
  }))
}

function nomeDoModelo(id: string): string {
  const curto = id.replace(/^claude-/, '').replace(/\[.*\]$/, '').replace(/-(\d+)-(\d+)(?:-\d{8})?$/, ' $1.$2')
  return curto.charAt(0).toUpperCase() + curto.slice(1)
}

function tokens(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${Math.round(n / 1e3)}k`
  return String(n)
}

function duracao(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}h${String(m).padStart(2, '0')}m`
  return `${m}m${String(s % 60).padStart(2, '0')}s`
}

function contexto(agente: Agente): string {
  if (agente.contexto === 0) return ''
  const janela = MODELO_ANTIGO.test(agente.modelo) ? JANELA_ANTIGA : JANELA_PADRAO
  const pct = Math.round((agente.contexto * 100) / janela)
  return pct < 1 ? 'ctx <1%' : `ctx ${pct}%`
}

// Linha 1: missão, tempo, contexto e consumo.
function resumo(info: AgentInfo, agente: Agente, ativo: boolean, instante: number): string {
  const fim = ativo || agente.fim === 0 ? instante : agente.fim
  return [
    agente.missao || info.description || info.name || info.type,
    agente.inicio > 0 ? `⏱ ${duracao(fim - agente.inicio)}` : '',
    contexto(agente),
    agente.tokens > 0 ? `${tokens(agente.tokens)} tok` : '',
  ].filter(Boolean).join(' · ')
}

// Linha 2: pasta · repositório no GitHub · branch · modelo/effort.
function detalhe(agente: Agente, daSessao: Git): string {
  const git = agente.pasta ? agente : daSessao
  const modelo = agente.modelo ? `${nomeDoModelo(agente.modelo)}${agente.effort ? ` ${agente.effort}` : ''}` : ''
  return [`📁 ${git.pasta}`, git.repo, git.branch && `⎇ ${git.branch}`, modelo].filter(Boolean).join(' · ')
}

function ordenar(lista: readonly AgentInfo[]): AgentInfo[] {
  const ativos = lista.filter(a => ATIVOS.has(a.status))
  const concluidos = lista.filter(a => !ATIVOS.has(a.status)).slice(-CONCLUIDOS_VISIVEIS)
  return [...ativos, ...concluidos]
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'agentes', description: 'Abre o painel com os agentes em execução' })
    const git = await lerGit($, e.cwd)
    await update($, sessao, () => git)
    $.clock.every(PULSO_MS, () => void pulsar($))
    void $.ui.open({ id: PAINEL, title: TITULO })

    return next(e)
  })

  on('command.run', { command: 'agentes' }, async $ => {
    await $.ui.open({ id: PAINEL, title: TITULO })

    return { text: 'Painel de agentes aberto.' }
  })

  on('agent.spawn', async ($, e, next) => {
    const feito = await next(e)
    if (!('agentId' in feito) || !feito.agentId) return feito
    const id = feito.agentId
    // Sem pasta própria, o agente mostra a da sessão até tocar um caminho de algum repositório.
    const git = e.cwd ? await lerGit($, e.cwd).catch(() => undefined) : undefined
    await mudar($, id, { modelo: feito.model, missao: missao(e.prompt, e.description), ...git }).catch(() => undefined)

    return feito
  })

  // turn.step chega em fluxo: o hook repassa os pedaços (yield*) e lê o resultado no fim.
  on('turn.step', async function* ($, e, next) {
    const feito = yield* next(e)
    await registrarPasso($, e, feito && 'usage' in feito ? feito.usage : null).catch(() => undefined)

    return feito
  })

  // Não espera o registro: o painel nunca segura nem derruba a chamada da ferramenta.
  on('tool.call', ($, e, next) => {
    if (e.agentId) void registrarCaminho($, e.agentId, e).catch(() => undefined)

    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const feito = await next(e)
    if (e.agentId) await mudar($, e.agentId, { fim: await $.clock.now() }).catch(() => undefined)

    return feito
  })

  on('ui.render', { component: 'Pane', requestId: PAINEL }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const [lista, detalhes, daSessao, instante] = await Promise.all([
      $.agent.list(),
      read($, agentes),
      read($, sessao),
      $.clock.now(),
      read($, agora),
    ])
    if (lista.length === 0) return <Text dimColor>Nenhum agente nesta sessão.</Text>

    return (
      <Box flexDirection="column">
        {ordenar(lista).map(info => {
          const agente = { ...VAZIO, ...detalhes[info.id] }
          const ativo = ATIVOS.has(info.status)
          // Rodando: verde e negrito, para achar de relance; concluído: apagado.
          const destaque = { color: COR[info.status], bold: info.status === 'running', dimColor: !ativo }

          return (
            <Box flexDirection="column">
              <Box flexDirection="row">
                <Text {...destaque}>{SIMBOLO[info.status]} </Text>
                <Text {...destaque} wrap="truncate-end">{resumo(info, agente, ativo, instante)}</Text>
              </Box>
              <Text dimColor wrap="truncate-end">  {detalhe(agente, daSessao)}</Text>
            </Box>
          )
        })}
      </Box>
    )
  })
}
