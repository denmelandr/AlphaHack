import { test } from 'node:test';
import assert from 'node:assert/strict';
import { calculate } from './finance.ts';
test('Аннуитет: 1 млн, 24%, 24 месяца', () => { const r = calculate(1000000, 24, 24, 95000); assert.ok(Math.abs(r.payment - 52871.10) < .01); assert.ok(Math.abs(r.interest - 268906.34) < .1); assert.equal(r.projectedProfit, 2280000); assert.equal(r.shortage, false); });
test('Нулевая ставка не даёт NaN и переплату', () => { const r = calculate(120000, 0, 12, 10000); assert.equal(r.payment, 10000); assert.equal(r.interest, 0); assert.equal(r.shortage, false); });
test('Положительный эффект не отменяет риск денежного потока', () => { const r = calculate(1000000, 24, 24, 20000); assert.ok(r.benefit > 0); assert.equal(r.shortage, true); });
test('Отложенная прибыль требует резерва и уменьшает прогноз', () => { const r = calculate(1000000, 24, 24, 95000, 3); assert.equal(r.projectedProfit, 1995000); assert.equal(r.shortage, true); });
test('Убыточный сценарий', () => { const r = calculate(1000000, 24, 24, 0); assert.ok(r.benefit < 0); assert.equal(r.shortage, true); });
