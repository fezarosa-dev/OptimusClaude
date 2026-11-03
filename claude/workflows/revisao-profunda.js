export const meta = {
  name: 'revisao-profunda',
  description: 'Revisão profunda do diff (ou do repositório inteiro, com tudo: true), local e no molde do ultra: revisores por dimensão e cada achado confirmado por céticos independentes',
  whenToUse: 'Antes de publicar ou de juntar uma branch grande, ou quando pedirem revisão profunda "tipo o ultra" sem custo à parte; com tudo: true, revisão do estado atual do repositório inteiro (a documentação de domínio, como textos de lei, normas e manuais, fica sempre fora; prompts de agentes de IA entram, por prompt injection). Só lê: não altera arquivo nenhum. args opcionais: {base, caminhos, foco, dimensoes, votos, max_blocos, tudo, incluir_docs}; dimensoes aceita também "lgpd", que só roda quando pedida.',
  phases: [
    { title: 'Escopo', detail: 'um agente lê o diff (ou lista o repositório, com tudo) e divide em blocos' },
    { title: 'Revisão', detail: 'um revisor por dimensão e bloco' },
    { title: 'Verificação', detail: 'céticos independentes tentam derrubar cada achado' },
    { title: 'Lacunas', detail: 'um crítico procura o que ninguém olhou; revisores extras nas lacunas' },
  ],
}

// Uso: Workflow({name: 'revisao-profunda', args: {base: 'main', foco: '...', dimensoes: ['seguranca'], votos: 3, max_blocos: 3, caminhos: ['src/']}})
// LGPD é opcional (não roda no padrão): dimensoes: ['lgpd'] só ela, ou ['correcao','seguranca','concorrencia','dados','testes','lgpd'] tudo junto.
// Todos os args são opcionais. Sem base, usa a branch principal (main, master ou origin/HEAD).
// No modo tudo a documentação de domínio (leis, normas, manuais) fica sempre fora, mesmo com incluir_docs; os prompts de agentes de IA entram, por prompt injection.
// Repositório inteiro: Workflow({name: 'revisao-profunda', args: {tudo: true, max_blocos: 16, incluir_docs: false}}) — revisa o estado atual (git ls-files), não um diff.
const A = args || {}
const TUDO = A.tudo === true
const VOTOS = Math.max(1, Math.min(5, A.votos || 3))
const MAX_BLOCOS = TUDO ? Math.max(1, Math.min(40, A.max_blocos || 16)) : Math.max(1, Math.min(8, A.max_blocos || 3))
const FOCO = A.foco ? `\nFoco pedido por quem chamou: ${A.foco}` : ''
const SO_LEITURA = 'Regras: você só LÊ. Não crie, edite nem apague arquivos; não rode git que escreva (commit, checkout, stash, reset, merge, worktree); nada de banco, deploy, produção ou rede externa; não rode a suíte de testes. Pode usar git diff/log/show/blame/merge-base/status, grep e ler arquivos. Responda em português do Brasil.'

const DIMENSOES_TODAS = [
  { chave: 'correcao', titulo: 'Correção', foco: 'bugs de lógica: condição invertida; caso de borda (vazio, nulo, zero, limite, data e fuso, unicode); erro engolido ou retorno ignorado; regressão em quem chama o código alterado (procure os chamadores); estado inconsistente' },
  { chave: 'seguranca', titulo: 'Segurança', foco: 'autorização e autenticação (checagem que falta ou que dá para contornar); injeção (SQL, comando, caminho, HTML/XSS, prompt injection em IA); segredo ou dado pessoal exposto (log, URL, armazenamento do navegador, mensagem de erro, evento); validação na fronteira de confiança; permissões de banco (RLS, security definer, grants)' },
  { chave: 'concorrencia', titulo: 'Concorrência e idempotência', foco: 'corrida entre processos, threads ou abas; async sem await ou sem tratamento de erro; retentativa que duplica efeito; ordem não garantida; trava presa; recurso não liberado (arquivo, conexão, temporário); timeout' },
  { chave: 'dados', titulo: 'Dados e contratos', foco: 'migration e schema (compatibilidade, ordem de publicação, dado existente que quebra); contrato entre partes (API, JSON, assinatura) mudado sem atualizar todos os lados; perda ou corrupção de dado; paginação e limites (corte silencioso); apagar o que não devia' },
  { chave: 'testes', titulo: 'Testes', foco: 'o que mudou sem um teste que pegaria a quebra; teste que não testa (sempre passa, mock que esconde o bug, asserção fraca); teste frágil (relógio, ordem, rede, dado compartilhado)' },
]
// dimensões que só rodam quando pedidas em args.dimensoes; o padrão continua as cinco de cima
const DIMENSOES_EXTRAS = [
  { chave: 'lgpd', titulo: 'LGPD (Lei 13.709/2018)', foco: 'o que se verifica em código à luz da LGPD. Princípios do art. 6 (finalidade, adequação, necessidade/minimização, livre acesso, qualidade, transparência, segurança, prevenção, responsabilização). Dado pessoal e dado sensível (CPF, RG/CNH e foto, telefone, e-mail, endereço, certificado digital e senha) aparecendo onde não devia: log, evento, trilha, URL, mensagem de erro, armazenamento do navegador, prompt ou resposta de IA, nome de arquivo. Quem vê o quê (permissão, RLS, mascaramento) e acesso além do necessário. Retenção sem prazo e término do tratamento/eliminação (arts. 15 e 16), inclusive cópias esquecidas (histórico, jsonb, filas, buckets, cache). Direitos do titular (art. 18: confirmação, acesso, correção, eliminação, portabilidade) e se o sistema consegue atendê-los. Registro das operações (art. 37: trilha de quem leu e mudou dado pessoal). Segurança e incidente (arts. 46 a 49: controles, segredo, criptografia, detecção). Compartilhamento com terceiros e transferência internacional (art. 33: envio a provedor de IA, mensageria, APIs de terceiros), com minimização do que sai. Dado de criança e adolescente (art. 14), se houver. No resumo de cada achado, cite o artigo ou o princípio em causa (ex.: "art. 6, III (necessidade): ...")' },
]
const DIMENSOES = Array.isArray(A.dimensoes) ? [...DIMENSOES_TODAS, ...DIMENSOES_EXTRAS].filter(d => A.dimensoes.includes(d.chave)) : DIMENSOES_TODAS

// cada cético recebe uma pergunta diferente: diversidade pega o que repetição não pega
const LENTES = [
  { chave: 'acontece', pergunta: 'Siga o código de verdade: o cenário descrito acontece? Procure a guarda, validação, tipo ou chamador que o impeça.' },
  { chave: 'desta_mudanca', pergunta: 'Isto é introduzido ou piorado por ESTA mudança (o diff)? Se já existia igual antes e a mudança não o torna alcançável, derrube.' },
  { chave: 'importa', pergunta: 'O efeito é real e relevante (dano, dado errado, falha visível, brecha)? Ou é teórico, impossível na prática, ou só estilo e preferência?' },
  { chave: 'contra_exemplo', pergunta: 'Tente montar um contra-exemplo concreto que mostre o código correto neste ponto.' },
  { chave: 'testes', pergunta: 'Há teste existente que já cobre e prova o comportamento correto neste ponto? Se sim, derrube.' },
]
// no modo tudo não há "esta mudança": a lente vira "isto é alcançável hoje?"
const LENTES_USADAS = TUDO ? LENTES.map(l => l.chave !== 'desta_mudanca' ? l : { chave: 'alcancavel', pergunta: 'O código com defeito é alcançável hoje (alguém o chama, a rota ou tela existe, a configuração o liga)? Se é código morto ou inalcançável, derrube.' }) : LENTES

const GRAVIDADE = { type: 'string', enum: ['alta', 'media', 'baixa'] }
const ESCOPO = {
  type: 'object',
  properties: {
    base: { type: 'string', description: 'o commit do merge-base' },
    resumo: { type: 'string' },
    blocos: { type: 'array', items: { type: 'object', properties: { nome: { type: 'string' }, arquivos: { type: 'array', items: { type: 'string' } } }, required: ['nome', 'arquivos'] } },
    fora: { type: 'array', items: { type: 'string' } },
  },
  required: ['base', 'resumo', 'blocos'],
}
const ACHADOS = {
  type: 'object',
  properties: {
    achados: { type: 'array', items: { type: 'object', properties: {
      arquivo: { type: 'string' }, linha: { type: 'integer' }, gravidade: GRAVIDADE,
      resumo: { type: 'string' }, cenario: { type: 'string' }, evidencia: { type: 'string' },
    }, required: ['arquivo', 'linha', 'gravidade', 'resumo', 'cenario'] } },
    olhado: { type: 'string', description: 'o que você leu além do diff' },
  },
  required: ['achados'],
}
const VEREDITO = {
  type: 'object',
  properties: { derrubado: { type: 'boolean' }, motivo: { type: 'string' }, gravidade: GRAVIDADE },
  required: ['derrubado', 'motivo'],
}
const LACUNAS = {
  type: 'object',
  properties: { lacunas: { type: 'array', items: { type: 'object', properties: { onde: { type: 'string' }, o_que_olhar: { type: 'string' } }, required: ['onde', 'o_que_olhar'] } } },
  required: ['lacunas'],
}

const chave = a => `${a.arquivo}:${a.linha}`
const unicos = lista => {
  const vistos = new Map()
  for (const a of lista) {
    const ja = vistos.get(chave(a))
    if (!ja) vistos.set(chave(a), { ...a, dimensoes: [a.dimensao] })
    else if (!ja.dimensoes.includes(a.dimensao)) ja.dimensoes.push(a.dimensao)
  }
  return [...vistos.values()]
}
const maisComum = lista => {
  const conta = {}
  for (const x of lista) conta[x] = (conta[x] || 0) + 1
  return Object.keys(conta).sort((p, q) => conta[q] - conta[p])[0]
}

phase('Escopo')
const escopo = await agent(TUDO ? `Prepare o escopo de uma revisão do repositório INTEIRO, no estado atual (não é revisão de mudança). ${SO_LEITURA}
1. base: devolva o commit de git rev-parse HEAD.
2. Parta dos arquivos rastreados (git ls-files).${Array.isArray(A.caminhos) ? ` Só estes caminhos: ${A.caminhos.join(', ')}.` : ''}
3. Tire o que não é código revisável e liste TUDO o que tirou em "fora", agrupado por pasta ou padrão com a contagem (ex.: "docs/referencia/ (312 .md)", "web/package-lock.json"), sem omitir nada: lockfiles; node_modules, .venv, build, dist; fixtures grandes geradas; binários e imagens; dados de teste; a DOCUMENTAÇÃO DE DOMÍNIO fica SEMPRE fora, em qualquer extensão e mesmo com incluir_docs (pastas de referência de domínio, textos de lei ou norma e suas cópias em qualquer pasta, manuais de domínio); ${A.incluir_docs ? 'os Markdown de docs/ ENTRAM na revisão (incluir_docs)' : 'docs/ em Markdown'}. EXCEÇÃO: os prompts dos agentes (ex.: prompt*.md e qualquer arquivo de prompt de sistema) ENTRAM, no bloco do código que os usa, mesmo sendo Markdown.
4. Divida o resto em no máximo ${MAX_BLOCOS} blocos por área coerente — por exemplo: cada módulo ou serviço; o código compartilhado; o frontend por pasta; migrations por faixa de data ou assunto; testes; scripts/ e CI — de tamanho parecido, de preferência abaixo de ~3.000 linhas cada (conte com wc -l). Todo arquivo que fica na revisão tem de estar em algum bloco; se não couber em ${MAX_BLOCOS} blocos, junte áreas vizinhas em vez de deixar arquivo de fora.
5. resumo: em 3 a 6 linhas, o que o repositório é e como as partes conversam entre si.${FOCO}` : `Prepare o escopo de uma revisão de código. ${SO_LEITURA}
1. Base: ${A.base ? `use "${A.base}"` : 'use a branch principal do repositório (main, senão master, senão origin/HEAD)'}. Calcule o ponto de partida com git merge-base <base> HEAD e devolva esse commit em "base".
2. O diff a revisar é git diff <merge-base> (inclui o que ainda não foi commitado) mais os arquivos novos não rastreados (git status --porcelain).${Array.isArray(A.caminhos) ? ` Só estes caminhos: ${A.caminhos.join(', ')}.` : ''}
3. Deixe de fora o que é gerado ou não é código (lockfiles, build, dist, imagens, binários, dados grandes) e liste em "fora".
4. Divida o resto em no máximo ${MAX_BLOCOS} blocos coerentes, por área ou assunto, de tamanho parecido (de preferência abaixo de ~2.000 linhas de diff cada). Diff pequeno = um bloco só. Todo arquivo que fica na revisão tem de estar em algum bloco.
5. resumo: em 3 a 6 linhas, o que a mudança faz.${FOCO}`, { phase: 'Escopo', schema: ESCOPO, model: 'sonnet', effort: 'medium' })

if (!escopo || !escopo.blocos || !escopo.blocos.length) return { confirmados: [], aviso: 'nada para revisar (diff vazio, ou o escopo falhou)' }
if (escopo.blocos.length > MAX_BLOCOS) {
  // junta o excedente no último bloco em vez de cortar: nenhum arquivo fica sem revisor
  const resto = escopo.blocos.splice(MAX_BLOCOS - 1)
  escopo.blocos.push({ nome: resto.map(b => b.nome).join(' + '), arquivos: resto.flatMap(b => b.arquivos) })
}
if (TUDO) log(`fora do escopo: ${(escopo.fora || []).join('; ') || 'nada'}`)
else if (escopo.fora && escopo.fora.length) log(`fora da revisão (gerado ou não é código): ${escopo.fora.length} arquivo(s)`)
log(`${escopo.blocos.length} bloco(s) × ${DIMENSOES.length} dimensão(ões) = ${escopo.blocos.length * DIMENSOES.length} revisores; ${VOTOS} cético(s) por achado (1 nos de gravidade baixa)`)

const revisor = (titulo, foco, arquivos, label, fase) => agent(TUDO ? `Você é revisor de código da dimensão "${titulo}": ${foco}.
${SO_LEITURA}
Isto é revisão do ESTADO ATUAL do código, não de uma mudança: onde a dimensão fala em "mudança" ou "o que mudou", leia como "o código deste bloco".
Repositório: ${escopo.resumo}
Leia INTEIROS estes arquivos: ${arquivos.join(', ')}.
Leia também o código em volta (quem chama, quem é chamado, os testes) antes de afirmar. Procure defeitos reais que existem hoje, na sua dimensão. Para cada achado: arquivo e linha no código atual, gravidade, resumo de uma frase, cenário concreto (entrada ou estado → resultado errado) e a evidência. Nada de estilo ou gosto. Lista vazia é um resultado válido.${/prompt/i.test(arquivos.join(' ')) ? '\nHá prompt de agente neste bloco: confira também a prompt injection. Texto de fora (mensagem, documento, página, anexo) é tratado como dado e não como ordem? A ação espera a confirmação de uma pessoa? O prompt promete algo que o código não garante, ou o contrário? Use só as dimensões que já existem (seguranca e, quando pedida, lgpd). Não revise o conteúdo de domínio do prompt (se a regra de negócio está certa).' : ''}${FOCO}` : `Você é revisor de código da dimensão "${titulo}": ${foco}.
${SO_LEITURA}
Mudança: ${escopo.resumo}
Diff: git diff ${escopo.base} -- <arquivo> (inclui o que não foi commitado; arquivo novo não rastreado: leia inteiro). Arquivos: ${arquivos.join(', ')}.
Leia o diff E o código em volta (quem chama, quem é chamado, os testes) antes de afirmar. Só reporte o que esta mudança introduz ou piora. Para cada achado: arquivo e linha no código novo, gravidade, resumo de uma frase, cenário concreto (entrada ou estado → resultado errado) e a evidência. Nada de estilo ou gosto. Lista vazia é um resultado válido.${FOCO}`,
  { label, phase: fase, schema: ACHADOS, model: 'sonnet', effort: 'medium' }).then(r => (r ? r.achados : []))

const verificar = a => {
  const n = a.gravidade === 'baixa' ? 1 : VOTOS
  return parallel(LENTES_USADAS.slice(0, n).map(l => () => agent(`Você é um cético. Tente DERRUBAR este achado de revisão de código; na dúvida, derrubado=true.
${SO_LEITURA}
${TUDO ? `Revisão do estado atual do repositório (não de uma mudança). Leia ${a.arquivo} inteiro e o código em volta.` : `Diff: git diff ${escopo.base} -- ${a.arquivo}`}
Achado (${(a.dimensoes || [a.dimensao]).join('+')}, ${a.gravidade}) em ${a.arquivo}:${a.linha}: ${a.resumo}
Cenário: ${a.cenario}
Evidência: ${a.evidencia || '(nenhuma)'}
Sua pergunta: ${l.pergunta}
Se ficar de pé, diga a gravidade que você daria.`,
    { label: `${l.chave}:${chave(a)}`, phase: 'Verificação', schema: VEREDITO, model: 'sonnet', effort: 'medium' }))).then(votos => {
    const v = votos.filter(Boolean)
    const dePe = v.filter(x => !x.derrubado)
    return {
      ...a,
      votos: v.length,
      de_pe: dePe.length,
      confirmado: v.length > 0 && dePe.length * 2 > v.length,
      gravidade_verificada: maisComum(dePe.map(x => x.gravidade).filter(Boolean)) || a.gravidade,
      motivos_contra: v.filter(x => x.derrubado).map(x => x.motivo),
    }
  })
}

phase('Revisão')
const brutos = (await parallel(escopo.blocos.flatMap(b => DIMENSOES.map(d => () =>
  revisor(d.titulo, d.foco, b.arquivos, `${d.chave}:${b.nome}`, 'Revisão').then(l => l.map(a => ({ ...a, dimensao: d.chave }))))))).filter(Boolean).flat()
const candidatos = unicos(brutos)
log(`${brutos.length} achado(s) brutos, ${candidatos.length} depois de juntar os repetidos`)

// a verificação e o crítico de cobertura correm juntos
const [verificados, lacunas] = await Promise.all([
  parallel(candidatos.map(a => () => verificar(a))),
  agent(TUDO ? `Você é o crítico de cobertura de uma revisão do repositório inteiro, no estado atual. ${SO_LEITURA}
Repositório: ${escopo.resumo}
Blocos revisados (cada revisor viu só o seu): ${escopo.blocos.map(b => `${b.nome} (${b.arquivos.length} arquivos)`).join('; ')}. Fora do escopo: ${(escopo.fora || []).join('; ') || 'nada'}. Dimensões: ${DIMENSOES.map(d => d.titulo).join(', ')}.
Achados até agora: ${candidatos.map(a => `${chave(a)} ${a.resumo}`).join(' | ') || 'nenhum'}.
O que ninguém olhou e devia é a interação ENTRE blocos, que nenhum revisor via inteira: chamadas entre módulos, serviços ou agentes; banco ↔ frontend ↔ backend/worker (função, view, coluna ou payload que um lado usa e o outro não tem ou entende diferente); permissões (RLS, papéis) ↔ telas e serviços que dependem delas; configuração compartilhada. No máximo 3 lacunas, só as que valem um revisor a mais; lista vazia se a cobertura está boa.` : `Você é o crítico de cobertura de uma revisão de código. ${SO_LEITURA}
Mudança: ${escopo.resumo}
Diff: git diff ${escopo.base}. Blocos revisados: ${escopo.blocos.map(b => `${b.nome} (${b.arquivos.length} arquivos)`).join('; ')}. Dimensões: ${DIMENSOES.map(d => d.titulo).join(', ')}.
Achados até agora: ${candidatos.map(a => `${chave(a)} ${a.resumo}`).join(' | ') || 'nenhum'}.
O que ninguém olhou e devia: trecho do diff sem achado que mexe em algo arriscado; interação ENTRE arquivos ou blocos (um lado mudou e o outro não); chamador fora do diff que a mudança afeta; configuração. No máximo 3 lacunas, só as que valem um revisor a mais; lista vazia se a cobertura está boa.`,
    { phase: 'Lacunas', schema: LACUNAS, model: 'sonnet', effort: 'medium' }),
])

let extras = []
const listaLacunas = ((lacunas && lacunas.lacunas) || []).slice(0, 3)
if (listaLacunas.length) {
  phase('Lacunas')
  log(`${listaLacunas.length} lacuna(s): revisores extras`)
  const achadosExtras = (await parallel(listaLacunas.map((l, i) => () =>
    revisor('Lacuna', `${l.o_que_olhar} (onde: ${l.onde}); vale qualquer tipo de problema real`, [l.onde], `lacuna:${i + 1}`, 'Lacunas')
      .then(lst => lst.map(a => ({ ...a, dimensao: 'lacuna' })))))).filter(Boolean).flat()
  const jaVistos = new Set(candidatos.map(chave))
  const novos = unicos(achadosExtras).filter(a => !jaVistos.has(chave(a)))
  extras = (await parallel(novos.map(a => () => verificar(a)))).filter(Boolean)
}

const todos = [...verificados.filter(Boolean), ...extras]
const ordem = { alta: 0, media: 1, baixa: 2 }
const confirmados = todos.filter(a => a.confirmado)
  .sort((x, y) => (ordem[x.gravidade_verificada] ?? 3) - (ordem[y.gravidade_verificada] ?? 3) || x.arquivo.localeCompare(y.arquivo) || x.linha - y.linha)
const derrubados = todos.filter(a => !a.confirmado && a.votos > 0)
const semVeredito = todos.filter(a => a.votos === 0)
if (semVeredito.length) log(`${semVeredito.length} achado(s) sem veredito (os céticos falharam): vão como não verificados`)
log(`${confirmados.length} confirmado(s), ${derrubados.length} derrubado(s)`)

return {
  base: escopo.base,
  resumo: escopo.resumo,
  fora: escopo.fora || [],
  confirmados: confirmados.map(a => ({
    arquivo: a.arquivo, linha: a.linha, gravidade: a.gravidade_verificada,
    dimensao: (a.dimensoes || [a.dimensao]).join('+'), resumo: a.resumo, cenario: a.cenario,
    evidencia: a.evidencia, votos: `${a.de_pe}/${a.votos}`,
  })),
  nao_verificados: semVeredito.map(a => ({ arquivo: a.arquivo, linha: a.linha, gravidade: a.gravidade, resumo: a.resumo })),
  derrubados: derrubados.map(a => ({ arquivo: a.arquivo, linha: a.linha, resumo: a.resumo, motivo: a.motivos_contra[0] })),
  ...(TUDO ? { escopo: { blocos: escopo.blocos.map(b => ({ nome: b.nome, arquivos: b.arquivos })), fora: escopo.fora || [] } } : {}),
}
