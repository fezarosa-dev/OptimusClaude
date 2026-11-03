export const meta = {
  name: 'fazer-revisar-corrigir',
  description: 'Cada tarefa: um agente faz, outro revisa, e enquanto houver problema alto ou médio um agente corrige e outro revisa de novo, até o limite de rodadas. Tarefas em paralelo; passos de uma tarefa em sequência no mesmo worktree',
  whenToUse: 'Para disparar um lote de tarefas já especificadas (código ou documento de desenho), cada uma no seu worktree, com revisão por outro agente e correção automática. A sessão principal continua com git, commit e merge. args: {tarefas:[{id, worktree, brief, modelo?, revModelo?, effort?, revEffort?, desenho?, passos?}], regras?, rodadas?, effort?, revEffort?, referencia?, max_paralelo?, permitir_sem_worktree?}',
  phases: [
    { title: 'Fazer', detail: 'um agente por tarefa (ou por passo) implementa ou escreve o documento' },
    { title: 'Revisar', detail: 'outro agente lê o pedido, a entrega e o diff, e aponta problemas com gravidade' },
    { title: 'Corrigir', detail: 'enquanto houver alta ou média: corrige e volta para a revisão, até o limite de rodadas' },
  ],
}

// Uso:
// Workflow({name: 'fazer-revisar-corrigir', args: {
//   referencia: '/caminho/do/checkout/na/dev',          // opcional: o revisor compara com diff -ruN contra ele
//   rodadas: 3, effort: 'high',                          // opcionais (padrão 3 e high; low vira medium)
//   revEffort: 'high',                                   // effort do revisor (padrão high; por tarefa: revEffort)
//   max_paralelo: 4,                                     // opcional: roda as tarefas em lotes desse tamanho (padrão: todas juntas, com aviso se mais de 4 de código)
//   permitir_sem_worktree: false,                        // padrão false: tarefa sem worktree é recusada (editaria o checkout da sessão)
//   regras: {banco: 'só o banco local', memoria: '...'}, // opcional: vai para todo brief, por cima das padrão
//   tarefas: [
//     {id: 'T1', worktree: '/caminho/wt/t1', modelo: 'sonnet', brief: {tarefa: '...', criterios: ['...']}},
//     {id: 'T2', worktree: '/caminho/wt/t2', modelo: 'opus', revModelo: 'opus', desenho: true,
//      brief: {tarefa: 'Desenho de ...', saida: 'docs/roteiros/x.md (só esse arquivo)'}},
//     {id: 'T3', worktree: '/caminho/wt/t3', passos: [{nome: 'T3a', brief: '...'}, {nome: 'T3b', brief: {...}}]},
//   ]}})
// brief pode ser objeto ou texto. passos: lista de briefs (ou {nome, brief, modelo?, revModelo?, effort?, revEffort?}) feitos em sequência no mesmo worktree;
// a sequência para se um passo não entregar ou terminar reprovado. Duas tarefas não podem dividir worktree.
// Revisor padrão: o mesmo modelo de quem faz, mas nunca abaixo de sonnet (haiku faz, sonnet revisa); outro olhar, effort próprio.
// Retorno: [{id, worktree, aprovada, interrompida?, passos:[{id, entrega, revisao_final, rodadas, historico}]}].

const A = args || {}
const TAREFAS_IN = Array.isArray(A.tarefas) ? A.tarefas : []
if (!TAREFAS_IN.length) throw new Error('args.tarefas vazio: passe ao menos uma tarefa {id, worktree, brief}')
const RODADAS = Math.max(1, Math.min(6, Number(A.rodadas) || 3))
// regra do usuário: effort nunca low
const EF = e => e === 'low' ? 'medium' : (e || null)
const EFFORT = EF(A.effort) || 'high'
const REF = A.referencia || null
const REV_EFFORT = EF(A.revEffort) || 'high'
const PARALELO = Math.max(0, Math.floor(Number(A.max_paralelo) || 0))

const REGRAS_PADRAO = {
  tdd: 'TDD: escreva o teste primeiro, rode e veja FALHAR pelo motivo certo, implemente, veja PASSAR; devolva trechos da saída do vermelho e do verde (sem executor de teste: diga isso e descreva a verificação manual)',
  git: 'não rode git; a sessão principal commita. Só mexa dentro do worktree indicado',
  rtk: 'comandos passam pelo rtk (hook); não chame binário por caminho absoluto; se o rtk bloquear, diga no retorno',
  casa: 'português do Brasil; o que depender de decisão ou permissão do usuário vai em duvidas (não pare o resto)',
}
const REGRAS = {...REGRAS_PADRAO, ...(A.regras || {})}
const REGRAS_DOC = (() => { const r = {...REGRAS}; delete r.tdd; return {...r, so: 'só o documento pedido; nada de código'} })()

const IMPL = {type:'object',properties:{status:{type:'string',enum:['pronto','parcial','travado']},arquivos:{type:'array',items:{type:'string'}},vermelho:{type:'string'},verde:{type:'string'},testes:{type:'array',items:{type:'object',properties:{comando:{type:'string'},resultado:{type:'string'}},required:['comando','resultado']}},duvidas:{type:'array',items:{type:'string'}},resumo:{type:'string'}},required:['status','arquivos','vermelho','verde','testes','duvidas','resumo']}
const DOC = {type:'object',properties:{arquivo:{type:'string'},mudancas:{type:'array',items:{type:'string'}},duvidas:{type:'array',items:{type:'string'}},resumo:{type:'string'}},required:['arquivo','mudancas','duvidas','resumo']}
const REV = {type:'object',properties:{veredito:{type:'string',enum:['aprovado','aprovado_com_ressalvas','reprovado']},problemas:{type:'array',items:{type:'object',properties:{arquivo_linha:{type:'string'},gravidade:{type:'string',enum:['alta','media','baixa']},descricao:{type:'string'},correcao:{type:'string'}},required:['arquivo_linha','gravidade','descricao','correcao']}},conferiu:{type:'array',items:{type:'string'}}},required:['veredito','problemas','conferiu']}

const asBrief = b => typeof b === 'string' ? {tarefa: b} : (b || {})
const TAREFAS = TAREFAS_IN.map((t, i) => {
  if (!t || !t.id) throw new Error(`tarefa ${i + 1} sem id`)
  const lista = Array.isArray(t.passos) && t.passos.length ? t.passos : [t.brief]
  const passos = lista.map((p, j) => {
    const temNome = p && typeof p === 'object' && 'brief' in p
    // passo pode trocar modelo e effort (ex.: só as fatias difíceis com o modelo mais forte)
    const prop = k => (temNome && p[k]) || undefined
    return {nome: (temNome && p.nome) || (lista.length > 1 ? `${t.id}.${j + 1}` : t.id), brief: asBrief(temNome ? p.brief : p),
      modelo: prop('modelo'), revModelo: prop('revModelo'), effort: EF(prop('effort')) || undefined, revEffort: EF(prop('revEffort')) || undefined}
  })
  if (passos.some(p => !Object.keys(p.brief).length)) throw new Error(`tarefa ${t.id} sem brief`)
  if (!t.worktree && A.permitir_sem_worktree !== true) throw new Error(`tarefa ${t.id} sem worktree: ela editaria o checkout da sessão principal (passe worktree, ou permitir_sem_worktree: true)`)
  const modelo = t.modelo || 'sonnet'
  return {id: t.id, wt: t.worktree || null, desenho: t.desenho === true, modelo, revModelo: t.revModelo || (modelo === 'haiku' ? 'sonnet' : modelo), effort: EF(t.effort) || EFFORT, revEffort: EF(t.revEffort) || REV_EFFORT, passos}
})
const ids = TAREFAS.map(t => t.id), wts = TAREFAS.map(t => t.wt).filter(Boolean)
if (new Set(ids).size !== ids.length) throw new Error('ids de tarefa repetidos')
if (new Set(wts).size !== wts.length) throw new Error('duas tarefas no mesmo worktree rodariam em paralelo e se pisariam: junte-as em passos de uma tarefa')

log(`tarefa → modelo/effort (revisor) · até ${RODADAS} revisão(ões) por passo`)
for (const t of TAREFAS) log(`${t.id}${t.desenho ? ' [desenho]' : ''}: ${t.passos.length} passo(s) · faz ${t.modelo}/${t.effort} · revisa ${t.revModelo}/${t.revEffort} · ${t.wt || 'diretório atual'}`)
const testando = TAREFAS.filter(t => !t.desenho).length
if (!PARALELO && testando > 4) log(`AVISO: ${testando} tarefas de código rodam juntas; se elas rodam teste, use max_paralelo: 4 (PC com pouca memória)`)

const onde = t => t.wt || 'o diretório atual'
const comoVer = (t, passo, feito) => {
  if (t.desenho) return `leia o documento ${feito && feito.arquivo ? feito.arquivo : (passo.brief.saida || '(veja a entrega)')} em ${onde(t)}`
  const base = REF ? `compare cada arquivo da entrega com diff -ruN ${REF}/<arq> ${onde(t)}/<arq> (arquivo novo: leia inteiro)` : `leia direto, em ${onde(t)}, cada arquivo da entrega e o código ao redor`
  return `${base}. Não rode git.`
}
const fazer = (t, passo, extra) => agent(JSON.stringify({...passo.brief, ...(extra || {}), worktree: t.wt || undefined, regras: t.desenho ? REGRAS_DOC : REGRAS, retorno: 'JSON do schema'}),
  {label: `${passo.nome} fazer`, phase: 'Fazer', model: passo.modelo || t.modelo, effort: passo.effort || t.effort, schema: t.desenho ? DOC : IMPL})
const revisar = (t, passo, feito, rodada) => agent(JSON.stringify({
  tarefa: t.desenho
    ? `Revisar o documento ${passo.nome} (outro agente escreveu). Tente derrubar: afirmação errada sobre o código (confira no código)? falha de segurança ou de privacidade no que propõe? contradiz o pedido? falta algo que o pedido exigia? fatias sem teste?`
    : `Revisar a mudança ${passo.nome} (outro agente fez). Procure defeito de correção, segurança (autorização, injeção, segredo ou dado pessoal exposto), teste que não prova o que diz, vermelho que não falharia sem a mudança, regressão em quem chama o código mexido, desvio do pedido, regra violada. Rode os testes mexidos se precisar confirmar.`,
  pedido: passo.brief, entrega: feito, rodada, worktree: t.wt || undefined, como_ver: comoVer(t, passo, feito),
  regras: {...(t.desenho ? REGRAS_DOC : REGRAS), so_ler: 'não altere arquivo nenhum'},
  retorno: 'JSON do schema; gravidade alta = bloqueia; media = tem de corrigir; baixa = opcional',
}), {label: `${passo.nome} revisar ${rodada}`, phase: 'Revisar', model: passo.revModelo || passo.modelo || t.revModelo, effort: passo.revEffort || t.revEffort, schema: REV})
const corrigir = (t, passo, feito, rev) => agent(JSON.stringify({
  tarefa: `Corrigir ${passo.nome} conforme a revisão (problemas alta e media obrigatórios; baixa se for barato).${t.desenho ? ' Confira no código cada afirmação que mexer.' : ' Teste primeiro onde couber.'}`,
  pedido: passo.brief, entrega_anterior: feito, revisao: rev, worktree: t.wt || undefined, regras: t.desenho ? REGRAS_DOC : REGRAS, retorno: 'JSON do schema',
}), {label: `${passo.nome} corrigir`, phase: 'Corrigir', model: passo.modelo || t.modelo, effort: passo.effort || t.effort, schema: t.desenho ? DOC : IMPL})

const precisa = r => !r || r.veredito === 'reprovado' || (r.problemas || []).some(p => p.gravidade !== 'baixa')
const rodarPasso = async (t, passo, extra) => {
  let atual = await fazer(t, passo, extra)
  if (!atual) return {id: passo.nome, erro: 'fazer não devolveu'}
  let rev = await revisar(t, passo, atual, 1), hist = [rev]
  for (let r = 2; r <= RODADAS && precisa(rev); r++) {
    atual = (await corrigir(t, passo, atual, rev)) || atual
    rev = await revisar(t, passo, atual, r); hist.push(rev)
  }
  return {id: passo.nome, entrega: atual, revisao_final: rev, aprovado: !precisa(rev), rodadas: hist.length,
    historico: hist.map(h => h ? {veredito: h.veredito, alta: h.problemas.filter(p => p.gravidade === 'alta').length, media: h.problemas.filter(p => p.gravidade === 'media').length, baixa: h.problemas.filter(p => p.gravidade === 'baixa').length} : {veredito: 'revisor não devolveu'})}
}

const rodarTarefa = async t => {
  const passos = []
  let interrompida
  for (const passo of t.passos) {
    const ant = passos[passos.length - 1]
    const extra = ant ? {antes_neste_worktree: `o passo ${ant.id} já foi feito neste mesmo worktree (não commitado ainda): parta do estado atual dos arquivos`} : null
    const p = await rodarPasso(t, passo, extra)
    passos.push(p)
    // passo seguinte parte do estado deste: não segue sobre entrega ausente ou reprovada
    if (p.erro || (p.revisao_final && p.revisao_final.veredito === 'reprovado') || !p.revisao_final) {
      const resto = t.passos.length - passos.length
      if (resto) { interrompida = `parou em ${p.id} (${p.erro || 'reprovado no limite de rodadas'}); ${resto} passo(s) não rodaram`; log(`${t.id}: ${interrompida}`) }
      break
    }
  }
  const aprovada = passos.length === t.passos.length && passos.every(p => p.aprovado)
  log(`${t.id}: ${aprovada ? 'aprovada' : 'NÃO aprovada'} (${passos.map(p => `${p.id} ${p.rodadas || 0} rodada(s)`).join(', ')})`)
  return {id: t.id, worktree: t.wt, aprovada, ...(interrompida ? {interrompida} : {}), passos}
}
// em lotes de max_paralelo (cada lote termina antes do próximo); sem o arg, todas de uma vez
const res = []
for (let i = 0; i < TAREFAS.length; i += (PARALELO || TAREFAS.length)) res.push(...await pipeline(TAREFAS.slice(i, i + (PARALELO || TAREFAS.length)), rodarTarefa))
return res.map((r, i) => r || {id: TAREFAS[i].id, worktree: TAREFAS[i].wt, aprovada: false, interrompida: 'erro no roteiro desta tarefa', passos: []})
