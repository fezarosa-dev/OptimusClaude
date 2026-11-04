<!-- Título: tipo(escopo): descrição (mesmo padrão do commit). Frases curtas; sem enfeite; sem autoria de IA. -->

## O quê
<!-- 1 a 3 linhas: o que muda para quem usa o kit. -->

## Por quê
<!-- O problema ou pedido. -->

## Como testei
<!-- Só os que o diff toca. -->
- Hooks: `python3 -m unittest discover -s claude/hooks`
- Painel: `cd painel && python3 testar.py`
- Projeto modelo: `cd projeto-modelo && python3 -I -m unittest discover -s scripts -p 'test_*.py'`

## Riscos
<!-- O que pode quebrar na instalação ou nas sessões de quem já usa. "Nenhum conhecido" se for o caso. -->
