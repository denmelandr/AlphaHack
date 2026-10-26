import { test } from 'node:test';
import assert from 'node:assert/strict';
import { documentList, invalidateReport, recommendProducts, repaymentModel } from './concept-model.ts';

test('Смена ИП на ООО сбрасывает только отчёт и не изменяет исходные документы', () => {
  const docs = { passport: { name: 'passport.png' }, statement: { name: 'statement.pdf' }, report: { name: 'tax.pdf' } };
  const next = invalidateReport(docs, 'ИП', 'ООО');
  assert.equal(next.report, undefined);
  assert.deepEqual(next.passport, docs.passport);
  assert.deepEqual(next.statement, docs.statement);
  assert.equal(docs.report.name, 'tax.pdf');
  assert.equal(invalidateReport(docs, 'ИП', 'ИП'), docs);
});
test('Список и инструкции соответствуют форме бизнеса', () => {
  assert.equal(documentList('ИП')[2].title, 'Налоговая декларация');
  assert.equal(documentList('ООО')[2].title, 'Бухгалтерская отчётность');
  assert.ok(documentList('ООО').every(doc => doc.steps.length >= 3 && doc.checks.length >= 3));
});
test('Неполный опрос не создаёт персональную подборку', () => {
  assert.deepEqual(recommendProducts({ goal: 'growth', channel: '', priority: '' }), []);
});
test('Подборка объясняет выбранные оборудование и онлайн-продажи', () => {
  const matches = recommendProducts({ goal: 'equipment', channel: 'online', priority: 'payments' });
  assert.equal(matches[0].purpose, 'Оборудование');
  assert.equal(matches[1].id, 'online-payments');
});
test('Свободный остаток ведёт к категории без обещания доходности', () => {
  const matches = recommendProducts({ goal: 'growth', channel: 'offline', priority: 'reserve' });
  assert.equal(matches[1].id, 'reserve');
  assert.ok(matches.every(product => !('rate' in product)));
});
test('Модель погашения при нулевой ставке и полном сроке', () => {
  assert.deepEqual(repaymentModel(120000, 0, 12, 6), { payment: 10000, balance: 60000, remainingMonths: 6 });
  const finished = repaymentModel(1000000, 24, 24, 24);
  assert.ok(finished.balance < .01);
  assert.equal(finished.remainingMonths, 0);
});
test('Расчётный долг убывает по мере учтённых платежей', () => {
  const start = repaymentModel(1000000, 24, 24, 0);
  const middle = repaymentModel(1000000, 24, 24, 12);
  assert.ok(Math.abs(start.balance - 1000000) < .01);
  assert.ok(middle.balance > 0 && middle.balance < start.balance);
  assert.equal(middle.payment, start.payment);
});
test('Задача контроля потока влияет на сопутствующую категорию', () => {
  const matches = recommendProducts({ goal: 'turnover', channel: 'online', priority: 'cashgap' });
  assert.equal(matches[1].id, 'cashflow');
});
