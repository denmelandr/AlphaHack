import test from 'node:test';
import assert from 'node:assert/strict';
import { baselinePolicy as p, cases, initialConditions, evaluate, counterOffers, parsePolicy, simulatePolicy, portfolio, forecast, flowSummary, cashCare } from './engine.ts';

test('four fixtures cover counteroffer, approval, rejection and volatile approval', () => {
  assert.deepEqual(cases.map(c => evaluate(c, initialConditions(c), p).approved), [false, true, false, true]);
  assert.ok(counterOffers(cases[0], initialConditions(cases[0]), p).length > 0);
  assert.equal(counterOffers(cases[2], initialConditions(cases[2]), p).length, 0);
});
test('every counteroffer passes the exact same policy engine', () => {
  for (const c of cases) for (const offer of counterOffers(c, initialConditions(c), p)) {
    assert.ok(evaluate(c, offer, p).approved);
    assert.ok(offer.amount <= p.maxAmount && offer.amount >= 100000);
  }
});
test('lower amount improves burden; security adjusts rate and factor contributions', () => {
  const c = cases[0], terms = initialConditions(c), original = evaluate(c, terms, p);
  const reduced = evaluate(c, { ...terms, amount: 1000000 }, p);
  const secured = evaluate(c, { ...terms, collateral: true, guarantee: true }, p);
  assert.ok(reduced.dti < original.dti && reduced.payment < original.payment);
  assert.equal(secured.rate, original.rate - 3);
  assert.equal(secured.factors.find(f => f.id === 'security')?.points, 17);
});
test('policy parser rejects unexpected fields, missing fields and invalid numeric values', () => {
  assert.deepEqual(parsePolicy(JSON.stringify(p)), p);
  for (const value of [null, [], { ...p, extra: 3 }, { ...p, maxDti: 2 }, { ...p, minScore: '65' }, { minScore: 65 }]) assert.throws(() => parsePolicy(JSON.stringify(value)));
});
test('simulation is deterministic and transitions reconcile with total approvals', () => {
  assert.deepEqual(portfolio(), portfolio());
  const same = simulatePolicy(p, p);
  assert.equal(same.before, same.after); assert.equal(same.newlyApproved + same.newlyRejected, 0);
  const softer = simulatePolicy(p, { ...p, minScore: 60, maxDti: .65 });
  assert.equal(softer.size, 500);
  assert.equal(softer.after - softer.before, softer.newlyApproved - softer.newlyRejected);
  assert.ok(softer.after >= softer.before);
});
test('forecast needs bank balance; accounting reveals day-12 obligation', () => {
  assert.deepEqual(forecast(['accounting'], 30), []);
  const base = forecast(['bank'], 30), accounting = forecast(['bank', 'accounting'], 30);
  assert.equal(flowSummary(base).firstGap, null);
  assert.equal(flowSummary(accounting).firstGap, 12);
  assert.ok(flowSummary(accounting).gap > 0);
  assert.ok(flowSummary(accounting).calculatedLimit >= flowSummary(accounting).gap * 1.2);
  assert.equal(forecast(['bank', 'accounting'], 60).filter(p => p.event).length, 2);
});
test('source changes affect cash flow and longer term increases interest', () => {
  const base = forecast(['bank', 'accounting'], 30), augmented = forecast(['bank', 'accounting', 'ofd', 'marketplace'], 30);
  assert.ok(augmented[29].balance > base[29].balance);
  const care = cashCare(1200000, 24, 24, 12, 300000, 12);
  assert.ok(care.newPayment < care.originalPayment && care.extraInterest > 0);
  assert.equal(care.monthlyYield, 3000); assert.ok(care.modeledInterestOffset <= 24000);
});
test('score always remains bounded across synthetic portfolio', () => {
  for (const c of portfolio()) { const decision = evaluate(c, initialConditions(c), p); assert.ok(decision.score >= 0 && decision.score <= 100); assert.equal(decision.factors.length, 5); }
});
