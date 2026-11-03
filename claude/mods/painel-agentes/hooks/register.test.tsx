import { expect, mock, test } from 'claude-code/testing'

const PAINEL = {
  plugin: 'painel-agentes',
  component: 'Pane',
  requestId: 'agentes',
  props: {
    title: 'Agentes',
    isFocused: false,
    bodyColumns: 120,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

// Respostas do git por repositório: a sessão roda no app; /srv/site é outro repositório.
const REPOS: Record<string, Record<string, string>> = {
  '/home/usuario/meu-app': {
    'rev-parse --show-toplevel': '/home/usuario/meu-app',
    'symbolic-ref --short HEAD': 'dev',
    'rev-parse --short HEAD': 'abc1234',
    'remote get-url origin': 'git@github.com:Org/meu-app.git',
  },
  '/srv/site': {
    'rev-parse --show-toplevel': '/srv/site',
    'symbolic-ref --short HEAD': 'main',
    'rev-parse --short HEAD': 'def5678',
    'remote get-url origin': 'https://github.com/Org/meu-site.git',
  },
}

// Sem cwd é a pasta da sessão; um arquivo não é pasta (git -C falha); subpasta de um repo é o repo.
function git(cwd: string | undefined, argv: readonly string[]): string | undefined {
  const pasta = cwd ?? '/home/usuario/meu-app'
  if (/\.[a-z]+$/.test(pasta)) return undefined
  const raiz = Object.keys(REPOS).find(r => pasta === r || pasta.startsWith(`${r}/`))
  return raiz ? REPOS[raiz]?.[argv.slice(1).join(' ')] : undefined
}

const USO = {
  input_tokens: 1000,
  output_tokens: 1000,
  cache_read_input_tokens: 40000,
  cache_creation_input_tokens: 8000,
  model: 'claude-sonnet-5-5',
}

test('duas linhas por agente: missão, tempo, % de contexto, tokens; pasta, repo, branch e modelo', async ($, on) => {
  const relogio = mock.clock(on, { now: 1_000_000 })
  let status: 'running' | 'completed' = 'running'
  on('command.register', () => ({ value: { command: 'agentes' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    const saida = git(e.init?.cwd, e.argv)
    const value = { exitCode: saida === undefined ? 128 : 0, stdout: saida ?? '', stderr: '' }
    return { value: { ...value, isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('agent.list', () => ({ value: [{ id: 'a1', description: 'Rodar a suíte', type: 'runner', status }] }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('agent.spawn', () => ({ model: 'claude-sonnet-5-5', agentId: 'a1' }))
  on('turn.step', async function* (_, e) {
    return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: 'tool_use' as const, usage: USO }
  })
  on('tool.call', () => ({ result: {} }))
  on('turn.complete', () => ({ text: 'ok' }))

  await $.session.start({ cwd: '/home/usuario/meu-app', surface: 'terminal', isInteractive: true })
  await $.agent.spawn({
    prompt: '{"missao":"Suíte do app","faz":"npm test"}', description: 'Rodar a suíte', subagentType: 'runner', tool_use_id: 'tu1',
    provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', background: true, fork: false,
  })
  const passo = { turnId: 't', model: 'claude-sonnet-5-5', effort: 'high', messageCount: 1, agentId: 'a1' } as const
  for await (const _ of $.turn.step({ ...passo, index: 0 })) void _
  for await (const _ of $.turn.step({ ...passo, index: 1 })) void _
  await $.tool.call({ tool: 'Bash', command: 'npm test', agentId: 'a1' })
  await relogio.advance(65_000)

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PAINEL, surface })
    // dois passos de 50k: o contexto é o do último (5% de 1M), o consumo soma os dois
    expect((await ui.find({ type: 'Text', text: /Suíte do app/ }))?.text).toBe('Suíte do app · ⏱ 1m05s · ctx 5% · 100k tok')
    expect((await ui.find({ type: 'Text', text: /⎇/ }))?.text).toBe(
      '  📁 meu-app · Org/meu-app · ⎇ dev · Sonnet 5.5 high',
    )
    await ui.unmount()
  }

  // o agente passa a mexer em outro repositório: o painel acompanha pelo caminho tocado
  await $.tool.call({ tool: 'Read', file_path: '/srv/site/src/pages/index.astro', agentId: 'a1' })
  await relogio.settle()
  const noSite = await $.ui.mount({ ...PAINEL, surface: 'terminal' })
  expect((await noSite.find({ type: 'Text', text: /⎇/ }))?.text).toBe(
    '  📁 site · Org/meu-site · ⎇ main · Sonnet 5.5 high',
  )
  await noSite.unmount()

  status = 'completed'
  await $.turn.complete({ turnId: 't', answer: 'ok', durationMs: 1, isAborted: false, reason: 'answer', agentId: 'a1' })
  await relogio.advance(60_000)
  const ui = await $.ui.mount({ ...PAINEL, surface: 'terminal' })
  // terminou: o tempo para de correr e a linha 2 continua mostrando onde ele trabalhou
  expect((await ui.find({ type: 'Text', text: /Suíte do app/ }))?.text).toBe('Suíte do app · ⏱ 1m05s · ctx 5% · 100k tok')
  expect((await ui.find({ type: 'Text', text: /✓/ }))?.text).toBe('✓ ')
  expect((await ui.find({ type: 'Text', text: /⎇/ }))?.text).toBe('  📁 site · Org/meu-site · ⎇ main · Sonnet 5.5 high')
  await ui.unmount()
})

test('sem agentes o painel avisa', async ($, on) => {
  mock.clock(on)
  on('agent.list', () => ({ value: [] }))
  const ui = await $.ui.mount({ ...PAINEL, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /Nenhum/ }))?.text).toBe('Nenhum agente nesta sessão.')
  await ui.unmount()
})

test('prompt sem missão em JSON: o painel usa a descrição do agente', async ($, on) => {
  mock.clock(on, { now: 5000 })
  on('process.run', () => ({
    value: { exitCode: 128, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
  }))
  on('agent.list', () => ({ value: [{ id: 'a2', description: 'Contar migrações', type: 'runner', status: 'running' }] }))
  on('agent.spawn', () => ({ model: 'claude-haiku-5-5', agentId: 'a2' }))
  await $.agent.spawn({
    prompt: 'conte as migrações', description: 'Contar migrações', subagentType: 'runner', tool_use_id: 'tu2',
    provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', background: true, fork: false,
  })
  const ui = await $.ui.mount({ ...PAINEL, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /Contar/ }))?.text).toBe('Contar migrações · ⏱ 0m00s')
  await ui.unmount()
})

test('agente numa pasta que não é repositório mostra a pasta da sessão', async ($, on) => {
  mock.clock(on, { now: 5000 })
  on('command.register', () => ({ value: { command: 'agentes' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('process.run', () => ({
    value: { exitCode: 128, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
  }))
  on('agent.list', () => ({ value: [{ id: 'a3', description: 'Olhar a pasta', type: 'runner', status: 'running' }] }))
  on('agent.spawn', () => ({ model: 'claude-haiku-5-5', agentId: 'a3' }))
  await $.session.start({ cwd: '/home/usuario/pasta-sem-git', surface: 'terminal', isInteractive: true })
  await $.agent.spawn({
    prompt: '{"missao":"Olhar a pasta"}', description: 'Olhar a pasta', subagentType: 'runner', tool_use_id: 'tu3',
    provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', background: true, fork: false,
  })
  const ui = await $.ui.mount({ ...PAINEL, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /📁/ }))?.text).toBe('  📁 pasta-sem-git · Haiku 5.5')
  await ui.unmount()
})
