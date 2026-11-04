# Padrões e armadilhas deste projeto

Lições que as revisões acharam. Uma linha cada, sem repetir; no máximo ~60 linhas. Todo agente que implementa
lê este arquivo antes de começar. Quem grava: a sessão principal, com o campo `licoes` do revisor.

- (exemplo) Datas sempre com fuso: `datetime.now(tz)`, nunca `utcnow()`.
