"use strict";
/* Ordenação das listas do painel. Chave nula (item sem tempo) vai para o fim, em qualquer sentido. */
const RANK={andando:0,fila:1,bloqueada:2,desconhecido:3,concluida:4};
const tempoSeg=t=>t.tempo&&t.tempo.segundos!=null?t.tempo.segundos:null;
const falta=t=>t.estado!=="concluida"?tempoSeg(t):null;
const previsto=t=>t.estado!=="concluida"&&t.tempo&&t.tempo.conclusao_em!=null?t.tempo.conclusao_em:null;
const levou=t=>t.estado==="concluida"?tempoSeg(t):null;
const wfCon=(w,c)=>c&&c.consumo&&(c.consumo.workflows||[]).find(y=>y.id===w.id)||null;
const O=(id,rotulo,chave,dir)=>({id,rotulo,chave,dir});
const ORDENS={
  tarefas:{nome:"tarefas",opcoes:[
    {id:"",rotulo:"padrão (andando primeiro)",cmp:(x,y)=>(x.estado==="andando"?0:1)-(y.estado==="andando"?0:1)||y.id-x.id},
    O("numero-maior","número (maior primeiro)",t=>t.id,-1),O("numero-menor","número (menor primeiro)",t=>t.id,1),
    O("estado","estado",t=>RANK[t.estado]??9,1),
    O("pct-maior","% (maior primeiro)",t=>t.percentual,-1),O("pct-menor","% (menor primeiro)",t=>t.percentual,1),
    O("falta-menor","tempo que falta (menor)",falta,1),O("falta-maior","tempo que falta (maior)",falta,-1),
    O("previsao-cedo","hora prevista (mais cedo)",previsto,1),O("previsao-tarde","hora prevista (mais tarde)",previsto,-1),
    O("levou-menor","tempo que levou (menor)",levou,1),O("levou-maior","tempo que levou (maior)",levou,-1)]},
  agentes:{nome:"agentes",opcoes:[
    {id:"",rotulo:"padrão (atividade recente)"},
    O("tempo-maior","rodando há mais tempo",(x,c)=>x.ativo&&x.inicio?c.agora-x.inicio:null,-1),
    O("tempo-menor","rodando há menos tempo",(x,c)=>x.ativo&&x.inicio?c.agora-x.inicio:null,1),
    O("tokens-maior","tokens (maior)",(x,c)=>c.consumo&&c.consumo.agentes?c.consumo.agentes[x.id]??null:null,-1),
    O("tokens-menor","tokens (menor)",(x,c)=>c.consumo&&c.consumo.agentes?c.consumo.agentes[x.id]??null:null,1)]},
  workflows:{nome:"workflows",opcoes:[
    {id:"",rotulo:"padrão (atividade recente)"},
    O("duracao-maior","duração (maior)",(w,c)=>(wfCon(w,c)||{}).segundos??null,-1),O("duracao-menor","duração (menor)",(w,c)=>(wfCon(w,c)||{}).segundos??null,1),
    O("tokens-maior","tokens (maior)",(w,c)=>(wfCon(w,c)||{}).tokens??null,-1),O("tokens-menor","tokens (menor)",(w,c)=>(wfCon(w,c)||{}).tokens??null,1)]},
  baterias:{nome:"baterias",opcoes:[
    {id:"",rotulo:"padrão"},
    O("recente","mais recente",b=>b.atividade??null,-1),O("antiga","mais antiga",b=>b.atividade??null,1),
    O("duracao-maior","duração (maior)",b=>b.duracao??null,-1),O("duracao-menor","duração (menor)",b=>b.duracao??null,1)]},
  merges:{nome:"merges",opcoes:[
    {id:"",rotulo:"padrão (mais recente)"},
    O("recente","mais recente",m=>m.quando??null,-1),O("antiga","mais antigo",m=>m.quando??null,1)]},
  perguntas:{nome:"perguntas",opcoes:[
    {id:"",rotulo:"padrão (mais antiga primeiro)"},
    O("antiga","mais antiga",(x,c,i)=>i,1),O("nova","mais nova",(x,c,i)=>i,-1)]},
  worktrees:{nome:"worktrees",opcoes:[
    {id:"",rotulo:"padrão"},
    O("nome","nome (A–Z)",w=>w.nome.toLowerCase(),1),
    O("frente","mais commits à frente",w=>w.a_frente??null,-1)]}
};
const valida=(tipo,id)=>!!ORDENS[tipo]&&ORDENS[tipo].opcoes.some(o=>o.id===id)?id:"";
function ordenar(lista,tipo,id,ctx){
  const o=ORDENS[tipo]&&ORDENS[tipo].opcoes.find(x=>x.id===id);
  if(!o||(!o.cmp&&!o.chave))return lista.slice();
  ctx=ctx||{};
  const v=lista.map((x,i)=>({x,i,k:o.cmp?0:o.chave(x,ctx,i)}));
  v.sort((a,b)=>{
    if(o.cmp)return o.cmp(a.x,b.x,ctx)||a.i-b.i;
    const an=a.k==null,bn=b.k==null;
    if(an||bn)return an&&bn?a.i-b.i:an?1:-1;
    return a.k===b.k?a.i-b.i:(a.k<b.k?-1:1)*o.dir;
  });
  return v.map(e=>e.x);
}
/* Junta a ordem salva dos quadros com os quadros de agora: o que sumiu é ignorado, o que é novo entra no fim. */
function mesclarOrdem(salva,atuais){
  const ok=new Set(atuais),vistos=new Set(),r=[];
  for(const k of Array.isArray(salva)?salva:[])if(ok.has(k)&&!vistos.has(k)){vistos.add(k);r.push(k)}
  for(const k of atuais)if(!vistos.has(k)){vistos.add(k);r.push(k)}
  return r;
}
/* Grade dos quadros: 3 colunas, linhas de altura fixa. Cada quadro tem posição {x 0..2, y >= 0} e tamanho P (1x1), M (2x1) ou G (3x2).
   O layout é um objeto {chave:{x,y,t}}; as funções abaixo nunca mudam o que recebem e nunca deixam dois quadros sobrepostos. */
const COLUNAS=3,LINHAS_MAX=200,TAMANHOS={P:{w:1,h:1},M:{w:2,h:1},G:{w:3,h:2}},ORDEM_T=["P","M","G"];
const copiaLayout=l=>{const r={};for(const k of Object.keys(l))r[k]={x:l[k].x,y:l[k].y,t:l[k].t};return r};
const celulas=(x,y,t)=>{const{w,h}=TAMANHOS[t],r=[];for(let j=0;j<h;j++)for(let i=0;i<w;i++)r.push((x+i)+","+(y+j));return r};
/* Mapa "x,y" -> chave de cada célula ocupada. */
function ocupacao(l){const o={};for(const k of Object.keys(l))for(const c of celulas(l[k].x,l[k].y,l[k].t))o[c]=k;return o}
/* O quadro `chave` (que não conta contra si mesmo) cabe em (x,y) com o tamanho t, dentro das 3 colunas e sem tocar em outro? */
function cabe(l,chave,x,y,t){
  if(!Object.hasOwn(TAMANHOS,t)||!Number.isInteger(x)||!Number.isInteger(y)||x<0||y<0||x+TAMANHOS[t].w>COLUNAS)return false;
  const o=ocupacao(l);
  return celulas(x,y,t).every(c=>o[c]===undefined||o[c]===chave);
}
const porLinha=l=>Object.keys(l).sort((a,b)=>l[a].y-l[b].y||l[a].x-l[b].x||(a<b?-1:a>b?1:0));
/* Quadros em ordem de leitura (linha, depois coluna): é a ordem do DOM e do Tab. */
const ordemLinear=porLinha;
/* Primeiro lugar livre varrendo linha a linha a partir de y0. */
function primeiroLivre(l,chave,t,y0){
  for(let y=y0;;y++)for(let x=0;x+TAMANHOS[t].w<=COLUNAS;x++)if(cabe(l,chave,x,y,t))return{x,y};
}
const tamPadrao=(tp,k)=>{const t=typeof tp==="string"?tp:tp&&Object.hasOwn(tp,k)?tp[k]:"M";return Object.hasOwn(TAMANHOS,t)?t:"M"};
/* Quadros de `chaves` com posição válida em `l` ficam onde estão; os demais (novos, ou que não cabem) vão para o primeiro lugar livre,
   na ordem de `chaves`, com o tamanho de `tp` (um tamanho ou {chave:tamanho}). Quem não está em `chaves` some. */
function autoPosicionar(l,chaves,tp){
  l=l&&typeof l==="object"?l:{};
  const tem=k=>Object.hasOwn(l,k)&&l[k]&&Object.hasOwn(TAMANHOS,l[k].t),r={};
  for(const k of chaves.filter(tem).sort((a,b)=>l[a].y-l[b].y||l[a].x-l[b].x))
    if(cabe(r,k,l[k].x,l[k].y,l[k].t))r[k]={x:l[k].x,y:l[k].y,t:l[k].t};
  for(const k of chaves)if(!Object.hasOwn(r,k)){const t=tem(k)?l[k].t:tamPadrao(tp,k);r[k]={...primeiroLivre(r,k,t,0),t}}
  const o={};for(const k of chaves)o[k]=r[k];return o;
}
/* Põe `k` em (x,y) com tamanho t. Quem fica sobreposto troca de lugar com ele se cabe onde ele estava (ax,ay);
   senão desce para o primeiro lugar livre a partir da própria linha. Determinístico: os sobrepostos seguem a ordem de leitura. */
function colocar(l,k,x,y,t,ax,ay){
  x=Math.max(0,Math.min(COLUNAS-TAMANHOS[t].w,x));y=Math.max(0,y);
  const r=copiaLayout(l),o=ocupacao({[k]:{x,y,t}}),
    des=porLinha(r).filter(j=>j!==k&&celulas(r[j].x,r[j].y,r[j].t).some(c=>o[c]!==undefined));
  for(const j of des)delete r[j];
  r[k]={x,y,t};
  for(const j of des){const d=l[j];r[j]=cabe(r,j,ax,ay,d.t)?{x:ax,y:ay,t:d.t}:{...primeiroLivre(r,j,d.t,d.y),t:d.t}}
  return r;
}
function mover(l,k,x,y){
  if(!Object.hasOwn(l,k)||!Number.isFinite(x)||!Number.isFinite(y))return copiaLayout(l);
  return colocar(l,k,Math.round(x),Math.round(y),l[k].t,l[k].x,l[k].y);
}
function redimensionar(l,k,t){
  if(!Object.hasOwn(l,k)||!Object.hasOwn(TAMANHOS,t))return copiaLayout(l);
  return colocar(l,k,t==="G"?0:l[k].x,l[k].y,t,l[k].x,l[k].y);
}
/* Layout a partir do formato antigo do "painel-quadros" de uma aba ({ordem,larguras}, ou só a lista da ordem):
   largura 2 vira P, 3 e 4 viram M, 6 vira G; sem largura salva vale o tamanho padrão. Posições pela ordem antiga. */
const DE_LARGURA={2:"P",3:"M",4:"M",6:"G"};
function migrar(antigo,chaves,tp){
  const o=antigo&&typeof antigo==="object"&&!Array.isArray(antigo)?antigo:{},ordem=mesclarOrdem(Array.isArray(antigo)?antigo:o.ordem,chaves),
    l=o.larguras&&typeof o.larguras==="object"?o.larguras:{},tam={};
  for(const k of ordem)tam[k]=Object.hasOwn(l,k)&&Object.hasOwn(DE_LARGURA,l[k])?DE_LARGURA[l[k]]:tamPadrao(tp,k);
  return autoPosicionar({},ordem,tam);
}
/* Layout vindo do armazenamento: só quadros de `chaves` (se dada) com posição e tamanho válidos e que não se sobrepõem. */
function validaGrade(l,chaves){
  const r={};
  if(!l||typeof l!=="object"||Array.isArray(l))return r;
  for(const k of Object.keys(l)){
    const e=l[k];
    if(k==="__proto__"||(chaves&&!chaves.includes(k))||!e||typeof e!=="object"||!Object.hasOwn(TAMANHOS,e.t)||!(e.y<=LINHAS_MAX))continue;
    if(cabe(r,k,e.x,e.y,e.t))r[k]={x:e.x,y:e.y,t:e.t};
  }
  return r;
}
/* Os dois layouts são iguais? (decide se há o que guardar e se o botão "layout padrão" aparece) */
function ehPadrao(l,p){
  const a=Object.keys(l),b=Object.keys(p);
  return a.length===b.length&&a.every(k=>Object.hasOwn(p,k)&&l[k].x===p[k].x&&l[k].y===p[k].y&&l[k].t===p[k].t);
}
/* Um passo de tamanho pelo teclado (dir -1 ou 1), parando nas pontas. */
function passoTamanho(t,dir){return ORDEM_T[Math.max(0,Math.min(ORDEM_T.length-1,ORDEM_T.indexOf(t)+dir))]}
const NOME_T={P:"Pequeno",M:"Médio",G:"Grande"};
/* Limites de uso (janela de 5 h e semana): faixa de cor, tempos e gráfico. Tudo recebe o "agora" (epoch s) para ser testável. */
function faixaLimite(p){
  if(p==null||!Number.isFinite(p))return{faixa:"sem",texto:"sem dados"};
  return p>=90?{faixa:"erro",texto:"crítico"}:p>=70?{faixa:"alerta",texto:"atenção"}:{faixa:"ok",texto:"normal"};
}
function restante(s){
  if(s==null||!Number.isFinite(s))return"";
  s=Math.round(s);if(s<=0)return"agora";
  if(s<60)return s+" s";
  if(s<3600)return Math.floor(s/60)+" min";
  if(s<86400){const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h+" h"+(m?" "+m+" min":"")}
  const d=Math.floor(s/86400),h=Math.floor(s%86400/3600);return d+" d"+(h?" "+h+" h":"");
}
const DIAS_SEM=["dom","seg","ter","qua","qui","sex","sáb"];
/* "17:40" se cai no mesmo dia (local) de agora; senão "sáb 10:00". */
function horaAlvo(alvo,agora){
  if(alvo==null||!Number.isFinite(alvo))return"";
  const a=new Date(alvo*1000),b=new Date(agora*1000),p=n=>String(n).padStart(2,"0"),hm=p(a.getHours())+":"+p(a.getMinutes());
  return a.toDateString()===b.toDateString()?hm:DIAS_SEM[a.getDay()]+" "+hm;
}
function textoPrevisao(j,agora){
  if(!j)return"";
  if(j.previsao_100_em!=null)return"chega a 100% às "+horaAlvo(j.previsao_100_em,agora);
  if(j.ritmo_pct_por_hora!=null)return"ritmo: "+(+j.ritmo_pct_por_hora).toLocaleString("pt-BR",{maximumFractionDigits:1})+"%/h";
  return"";
}
/* Pontos de um gráfico de linha w×h: eixo x = a janela inteira (reset_em-duracao .. reset_em), y = 0..100% (y100 é a linha dos 100%). */
function grafico(serie,resetEm,duracao,w,h){
  const ini=resetEm-duracao,r=n=>Math.round(n*10)/10,pts=[];
  for(const[t,p]of Array.isArray(serie)?serie:[]){
    if(!Number.isFinite(t)||!Number.isFinite(p)||t<ini||t>resetEm)continue;
    pts.push([r((t-ini)/duracao*w),r(h-Math.max(0,Math.min(100,p))/100*h)]);
  }
  return{pontos:pts.map(q=>q.join(",")).join(" "),atual:pts.length?pts[pts.length-1]:null,y100:0};
}
if(typeof module!=="undefined")module.exports={ORDENS,ordenar,valida,mesclarOrdem,COLUNAS,TAMANHOS,NOME_T,ocupacao,cabe,autoPosicionar,mover,redimensionar,ordemLinear,migrar,validaGrade,ehPadrao,passoTamanho,faixaLimite,restante,horaAlvo,textoPrevisao,grafico};
