import { atom, read, update } from 'claude-code'
import type { EngineInterface, ModelUsage, Register, SessionRateLimit } from 'claude-code'

import type { AgentRow, Totals } from '../types'

// Somatório de todos os turnos (main + subagentes): sobrevive a reload, zera no /clear.
const totals = atom({ plugin: 'status-bar', key: 'totals' } as const, {
  ms: 0,
  tokens: 0,
} as Totals)

// Agentes vistos nesta sessão (rodando + últimos finalizados) e o relógio que redesenha o painel.
const agents = atom({ plugin: 'status-bar', key: 'agents' } as const, [] as AgentRow[])
const clock = atom({ plugin: 'status-bar', key: 'now' } as const, 0)
const PANE = 'agentes'
const KEEP_DONE = 5

const DAYS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']
const EFFORT: Record<string, string> = { low: 'lo', medium: 'md', high: 'hi', xhigh: 'xh', max: 'mx' }

export const pct = (n: number) => `${Math.min(100, Math.max(0, Math.round(n)))}%`

// "claude-opus-5-5[1m]" → "Opus 5.5"; nomes já legíveis só perdem o "Claude " e o sufixo.
export const prettyModel = (model: string) => {
  const [, fam, major, minor] = model.match(/^claude-([a-z]+)-(\d+)-(\d+)/) ?? []
  if (fam) return `${fam.charAt(0).toUpperCase()}${fam.slice(1)} ${major}.${minor}`
  return model.replace(/^Claude /, '').replace(/ \(.*\)$/, '')
}

export const dur = (ms: number) => {
  const s = Math.floor(ms / 1000)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}h${m}m`
  if (m > 0) return `${m}m${s % 60}s`
  return `${s}s`
}

export const left = (ms: number) => {
  const m = Math.floor(ms / 60_000)
  return m >= 60 ? `${Math.floor(m / 60)}h${m % 60}m` : m > 0 ? `${m}m` : '<1m'
}

export const tok = (n: number) => `${(n / 1e6).toFixed(2)} Mtok`

export const spent = (u: ModelUsage | null | undefined) =>
  u ? u.input_tokens + u.output_tokens + u.cache_creation_input_tokens + u.cache_read_input_tokens : 0

const effortLabel = (e: string | number | undefined) => (e === undefined ? '' : `/${EFFORT[String(e)] ?? e}`)

// Mantém todos os rodando e só os KEEP_DONE finalizados mais recentes.
export const prune = (rows: AgentRow[]) => {
  const done = rows.filter(r => r.endedAt !== undefined).slice(-KEEP_DONE)
  return rows.filter(r => r.endedAt === undefined || done.includes(r))
}

const patch = ($: EngineInterface, id: string, fn: (row: AgentRow) => AgentRow) =>
  update($, agents, rows => rows.map(r => (r.id === id ? fn(r) : r)))

const quota = (label: string, rl: SessionRateLimit | undefined, now: number, weekly: boolean) => {
  if (!rl) return undefined
  const reset = rl.resetsAt ? Date.parse(rl.resetsAt) : NaN
  // Janela já virou desde a última resposta da API → uso voltou a 0.
  const used = reset <= now ? 0 : rl.percentUsed
  let out = `${label} ${pct(used)}`
  if (reset > now) {
    const d = new Date(reset)
    out += weekly ? ` ↻ ${DAYS[d.getDay()]} ${d.getHours()}h` : ` ↻ ${left(reset - now)}`
  }
  return out
}

const git = async ($: EngineInterface) => {
  const run = (args: string[]) =>
    $.process.run(['git', '--no-optional-locks', ...args], { timeoutMs: 2000 }).catch(() => undefined)
  const [branch, top, dirty] = await Promise.all([
    run(['symbolic-ref', '--short', 'HEAD']),
    run(['rev-parse', '--show-toplevel']),
    run(['status', '--porcelain']),
  ])
  if (!branch || branch.exitCode !== 0) return '(no git)'
  const repo = top?.exitCode === 0 ? `${top.stdout.trim().split('/').pop()}:` : ''
  const star = dirty?.stdout.trim() ? '★' : ''
  return `${repo}${branch.stdout.trim()}${star}`
}

let effort: string | number | undefined
let busy = false

async function refresh($: EngineInterface) {
  // ponytail: refresh descartado se outro estiver rodando; o próximo tick (30s) cobre.
  if (busy) return
  busy = true
  try {
    const [branch, model, usage, sum, now] = await Promise.all([
      git($),
      $.session.model(),
      $.session.usage(),
      read($, totals),
      $.clock.now(),
    ])
    const name = prettyModel(model)
    const eff = effortLabel(effort)
    const ctx = usage.context
    const ctxLabel = ctx.window >= 900_000 ? '1M' : 'Ctx'
    const rl = (kind: string) => usage.rateLimits.find(r => r.kind === kind)

    const parts = [
      branch,
      `${name}${eff}`,
      `${ctxLabel} ${pct(ctx.percent ?? 0)}`,
      quota('5h', rl('five_hour'), now, false),
      quota('sem', rl('seven_day'), now, true),
      `Σ${dur(sum.ms)}`,
      `Σ${tok(sum.tokens)}`,
    ]
    $.ui.status(parts.filter(Boolean).join(' │ '))
  } finally {
    busy = false
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // Até o primeiro request, o effort vem do settings; depois, do próprio request.
    effort ??= (await $.settings.read({ key: 'effortLevel' })) as string | undefined
    await refresh($)
    $.clock.every(30_000, () => void refresh($))
    // Relógio do painel: só escreve (e redesenha) enquanto houver agente rodando.
    $.clock.every(1000, async () => {
      if ((await read($, agents)).some(r => r.endedAt === undefined)) {
        const now = await $.clock.now()
        await update($, clock, () => now)
      }
    })
    await $.command.register({ name: PANE, description: 'Abre o painel de agentes' })
    void $.ui.open({ id: PANE, title: 'Agentes' })
    return next(e)
  })

  on('command.run', { command: PANE }, async $ => {
    await $.ui.open({ id: PANE, title: 'Agentes' })
    return { text: 'Painel de agentes aberto.' }
  })

  on('turn.start', async ($, e, next) => {
    const id = e.agentId
    if (id !== undefined) {
      const [list, now] = await Promise.all([$.agent.list(), $.clock.now()])
      const info = list.find(a => a.id === id)
      const label = info?.name ?? info?.description ?? id.slice(0, 8)
      await update($, agents, rows => {
        const old = rows.find(r => r.id === id)
        // Agente que acorda de novo (mensagem nova) volta a rodar mantendo o consumo.
        if (old) return rows.map(r => (r.id === id ? { ...r, endedAt: undefined } : r))
        return prune([...rows, { id, label, type: info?.type ?? '', tokens: 0, startedAt: now }])
      })
    }
    return next(e)
  })

  on('session.measure', async ($, e, next) => {
    const r = await next(e)
    void refresh($)
    return r
  })

  // Só observa: guarda o effort do loop principal e deixa a resposta passar intacta.
  on('turn.step', async function* ($, e, next) {
    const id = e.agentId
    if (id === undefined) {
      effort = e.effort
      return yield* next(e)
    }
    await patch($, id, r => ({ ...r, model: e.model, effort: e.effort }))
    const r = yield* next(e)
    const used = spent(r.usage)
    if (used) await patch($, id, row => ({ ...row, tokens: row.tokens + used }))
    return r
  })

  on('turn.complete', async ($, e, next) => {
    const used = spent(e.usage)
    await update($, totals, t => ({ ms: t.ms + e.durationMs, tokens: t.tokens + used }))
    const id = e.agentId
    if (id !== undefined) {
      const now = await $.clock.now()
      await patch($, id, r => ({ ...r, endedAt: now }))
      await update($, agents, prune)
    }
    void refresh($)
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear') {
      await update($, totals, () => ({ ms: 0, tokens: 0 }))
      await update($, agents, () => [])
    }
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const [rows, ticked, now] = await Promise.all([read($, agents), read($, clock), $.clock.now()])
    const at = Math.max(ticked, now)
    const running = rows.filter(r => r.endedAt === undefined)
    const done = rows.filter(r => r.endedAt !== undefined).reverse()

    const row = (r: AgentRow) => {
      const isDone = r.endedAt !== undefined
      const model = r.model ? `${prettyModel(r.model)}${effortLabel(r.effort)}` : '…'
      return (
        <Box flexDirection="column">
          <Text bold={!isDone} dimColor={isDone}>
            {isDone ? '✓' : '▸'} {r.label}
            {r.type ? ` (${r.type})` : ''}
          </Text>
          <Text dimColor>
            {'  '}
            {model} · {tok(r.tokens)} · {dur((r.endedAt ?? at) - r.startedAt)}
          </Text>
        </Box>
      )
    }

    return (
      <Box flexDirection="column">
        <Text bold>Rodando ({running.length})</Text>
        {running.length === 0 && <Text dimColor>Nenhum agente rodando.</Text>}
        {running.map(row)}
        {done.length > 0 && <Text bold>Finalizados</Text>}
        {done.map(row)}
      </Box>
    )
  })
}
