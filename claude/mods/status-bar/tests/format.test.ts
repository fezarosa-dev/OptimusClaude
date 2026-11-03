import { expect, test } from 'claude-code/testing'

import { dur, left, prettyModel, prune, pct, spent, tok } from '../hooks/register'

test('formata barra, duração, countdown e tokens', async () => {
  expect(pct(6.4)).toBe('6%')
  expect(pct(140)).toBe('100%')
  expect(dur(100_000)).toBe('1m40s')
  expect(dur(3_780_000)).toBe('1h3m')
  expect(left(10_980_000)).toBe('3h3m')
  expect(left(30_000)).toBe('<1m')
  expect(tok(1_234_567)).toBe('1.23 Mtok')
  expect(tok(117_800)).toBe('0.12 Mtok')
  expect(prettyModel('claude-opus-5-5[1m]')).toBe('Opus 5.5')
  expect(prettyModel('Claude Sonnet 5.5 (1M context)')).toBe('Sonnet 5.5')
})

test('painel guarda todos os rodando e só os 5 últimos finalizados', async () => {
  const row = (id: string, endedAt?: number) => ({ id, label: id, type: '', tokens: 0, startedAt: 0, endedAt })
  const rows = [row('r1'), ...[1, 2, 3, 4, 5, 6, 7].map(n => row(`d${n}`, n)), row('r2')]
  expect(prune(rows).map(r => r.id)).toEqual(['r1', 'd3', 'd4', 'd5', 'd6', 'd7', 'r2'])
  expect(spent({ input_tokens: 1, output_tokens: 2, cache_creation_input_tokens: 3, cache_read_input_tokens: 4 })).toBe(10)
  expect(spent(null)).toBe(0)
})
