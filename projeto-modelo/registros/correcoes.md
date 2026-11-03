# Livro de correções

Cada achado de revisão, teste ou bateria que virou correção. Numeração em sequência, sem pular e sem reaproveitar.
Nunca apague uma entrada: achado que não se confirmou fica com o porquê.

Formato de cada entrada:

```markdown
### C-001 · <o problema em uma linha>

- **Origem:** revisão <tipo> de AAAA-MM-DD (registros/revisoes/<arquivo>) | teste | bateria
- **Gravidade:** alta | média | baixa
- **Onde:** `caminho/arquivo:linha`
- **Correção:** commit `<sha curto>` (Tn)
- **Prova:** `<teste>`: vermelho antes (commit base `<sha>`), verde depois
- **Depende de:** ninguém | <quem e o quê>
```

---

_Nenhuma correção ainda._
