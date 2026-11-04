# Registros de garantia

O que foi testado, revisado e corrigido, guardado de um jeito que se possa provar depois: com data, commit e hash. Serve
para mostrar diligência ("testei, revisei e corrigi isto, nesta data, neste commit"), não para prometer que não há falha.

Nada aqui tem dado pessoal nem segredo: o resumo da bateria guarda contagens e resultados (nunca a saída dos testes), e o
relatório de revisão cita onde está o problema, não o dado.

## O que é cada coisa

| O quê | O que guarda | Quem grava |
|---|---|---|
| `baterias/` | Um resumo por rodada do `scripts/testar_como_o_ci.py`: data com fuso, branch, commit, hash da árvore, se havia mudança não commitada (o sha256 do `git diff`, nunca o conteúdo), cada passo com OK, FALHOU ou PULADO, `EXIGIR_TUDO`, duração e o sha256 do log completo | a própria bateria, ao sair (verde, vermelha ou interrompida) |
| `revisoes/` | O relatório de cada revisão (`AAAA-MM-DD-<tipo>.md`): achados, veredito dos céticos, o que foi derrubado e por quê | `python3 scripts/registros/salvar_revisao.py <tipo> <arquivo>` |
| `correcoes.md` | O livro de correções: cada achado numerado (C-001...), origem, gravidade, onde, commit da correção, o teste que prova (vermelho e verde) | à mão, no formato do próprio arquivo |
| `padroes.md` | As lições das revisões: armadilhas e padrões deste projeto, uma linha cada, no máximo ~60 linhas (consolida as parecidas ao passar disso). Todo agente que implementa lê antes de começar | a sessão principal, com o campo `licoes` que o revisor devolve |
| `INDICE.md` | Cada arquivo desta pasta com o sha256 | `python3 scripts/registros/indice.py`, na `dev`, pela sessão principal |

O `salvar_revisao.py` **recusa** (saída 1) o relatório que tiver segredo ou dado pessoal (JWT, Authorization/Bearer,
Cookie, chave privada, tokens conhecidos, senha em URL, CPF/CNPJ válido, e-mail fora dos domínios de teste). Diz a linha e
o tipo, nunca o valor. Ajuste os padrões em `scripts/registros/sensivel.py`.

## Como provar que um log é aquele

O log completo de cada rodada não entra no repositório (é grande e tem caminhos da máquina). Ele fica comprimido em
`${REGISTROS_FORA:-~/.local/share/registros-de-garantia}/<projeto>/baterias/<nome>.log.gz`, e o resumo diz o sha256 dele:

```bash
sha256sum ~/.local/share/registros-de-garantia/<projeto>/baterias/<nome>.log.gz   # tem de bater com o resumo
zcat ~/.local/share/registros-de-garantia/<projeto>/baterias/<nome>.log.gz | less
```

A árvore testada: `git rev-parse <commit>^{tree}` tem de dar o "Árvore (hash)" do resumo. Guarde a pasta de fora num backup.

## Quando grava, e o que entra no git

- A bateria grava sozinha. `SO_DECIDIR=1` não grava (não roda teste); `REGISTRO=0` desliga (o CI usa).
- Branches paralelas não conflitam por causa daqui: nelas só entram arquivos novos (`baterias/*.md`, nomes únicos), e
  ninguém reescreve o `INDICE.md` fora da `dev`.
- **Bateria de uma branch:** depois da bateria verde e antes do merge, o resumo é commitado na própria branch
  (`chore(registros): bateria de <branch>`).
- **Depois de cada merge na `dev`:** `gitleaks dir registros --no-banner --redact` (limpo),
  `python3 scripts/registros/indice.py && git add registros/` e o commit `chore(registros): índice`.
- **Antes do PR para a `main`:** a bateria completa e as revisões salvas, o índice regenerado e commitado, e só então o PR
  (registro commitado depois do PR aberto dispara o CI de novo).
- **Na publicação:** uma tag anotada `testado-AAAA-MM-DD` no commit publicado, com o sha256 do `INDICE.md` na mensagem.
- Registro nunca se apaga. Conflito no `INDICE.md`: não edite à mão; resolva o resto e regenere.
