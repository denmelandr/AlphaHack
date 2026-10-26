import { calculate } from '../finance.ts';
export type Case = { id: string; company: string; sector: string; revenue: number; expenses: number; debt: number; monthsInBusiness: number; overdueDays: number; volatility: number; amount: number; term: number; purpose: string };
export type Conditions = { amount: number; months: number; collateral: boolean; guarantee: boolean };
export type Policy = { minScore: number; maxDti: number; maxAmount: number; baseRate: number; collateralBonus: number; guaranteeBonus: number };
export const baselinePolicy: Policy = { minScore: 65, maxDti: 0.55, maxAmount: 5000000, baseRate: 24, collateralBonus: 10, guaranteeBonus: 7 };
export const cases: Case[] = [
  { id: 'DEMO-1042', company: 'Полярная пекарня', sector: 'Производство и розница', revenue: 1800000, expenses: 1350000, debt: 180000, monthsInBusiness: 36, overdueDays: 0, volatility: .16, amount: 3600000, term: 24, purpose: 'Открытие второй точки' },
  { id: 'DEMO-1043', company: 'Северный маркет', sector: 'Онлайн-торговля', revenue: 2400000, expenses: 1600000, debt: 60000, monthsInBusiness: 48, overdueDays: 0, volatility: .12, amount: 2000000, term: 36, purpose: 'Закупка товаров' },
  { id: 'DEMO-1044', company: 'Старт мастерская', sector: 'Услуги', revenue: 900000, expenses: 720000, debt: 170000, monthsInBusiness: 8, overdueDays: 45, volatility: .42, amount: 1800000, term: 24, purpose: 'Обновление оборудования' },
  { id: 'DEMO-1045', company: 'Линия кофе', sector: 'Общественное питание', revenue: 1400000, expenses: 1050000, debt: 70000, monthsInBusiness: 30, overdueDays: 0, volatility: .3, amount: 1200000, term: 24, purpose: 'Оборотные средства' },
];
export const initialConditions = (c: Case): Conditions => ({ amount: c.amount, months: c.term, collateral: false, guarantee: false });
export type Factor = { id: string; label: string; value: string; points: number; explanation: string };
export function evaluate(c: Case, conditions: Conditions, policy: Policy) {
  const rate = Math.max(0, policy.baseRate - (conditions.collateral ? 2 : 0) - (conditions.guarantee ? 1 : 0) + (c.overdueDays > 0 ? 4 : 0) + (c.volatility > .25 ? 2 : 0));
  const payment = calculate(conditions.amount, rate, conditions.months, 0).payment;
  const cash = c.revenue - c.expenses;
  const dti = (c.debt + payment) / Math.max(cash, 1);
  const debtPoints = dti > .7 ? -24 : dti > .55 ? -18 : dti > .4 ? -8 : 12;
  const factors: Factor[] = [
    { id: 'load', label: 'Долговая нагрузка', value: `${Math.round(dti * 100)}%`, points: debtPoints, explanation: 'Все ежемесячные платежи / денежный поток после операционных расходов.' },
    { id: 'history', label: 'Платёжная дисциплина', value: c.overdueDays ? `${c.overdueDays} дней просрочки` : 'Без просрочек', points: c.overdueDays ? -25 : 10, explanation: 'Синтетическая кредитная история компании.' },
    { id: 'tenure', label: 'Возраст бизнеса', value: `${c.monthsInBusiness} мес.`, points: c.monthsInBusiness >= 24 ? 8 : -8, explanation: 'В учебном правиле устойчивой считается история от 24 месяцев.' },
    { id: 'flow', label: 'Колебания выручки', value: `${Math.round(c.volatility * 100)}%`, points: c.volatility <= .2 ? 8 : -8, explanation: 'Синтетическая вариативность месячных поступлений.' },
    { id: 'security', label: 'Обеспечение', value: conditions.collateral && conditions.guarantee ? 'Залог + поручительство' : conditions.collateral ? 'Залог' : conditions.guarantee ? 'Поручительство' : 'Без обеспечения', points: (conditions.collateral ? policy.collateralBonus : 0) + (conditions.guarantee ? policy.guaranteeBonus : 0), explanation: 'Оценка предмета залога и поручителя не выполняется. В демо учитывается только переключатель.' },
  ];
  const score = Math.max(0, Math.min(100, 55 + factors.reduce((total, f) => total + f.points, 0)));
  const checks = { score: score >= policy.minScore, load: dti <= policy.maxDti, limit: conditions.amount <= policy.maxAmount, history: c.overdueDays < 30 };
  const approved = Object.values(checks).every(Boolean);
  return { score, factors, checks, approved, rate, payment, dti, cash, interest: payment * conditions.months - conditions.amount };
}
export function counterOffers(c: Case, conditions: Conditions, policy: Policy): Conditions[] {
  if (evaluate(c, conditions, policy).approved) return [];
  const offers: Conditions[] = [];
  for (const security of [{ collateral: false, guarantee: false }, { collateral: false, guarantee: true }, { collateral: true, guarantee: false }]) {
    for (const amountFactor of [.85, .7, .5, .3]) {
      for (const months of [conditions.months, 36, 48, 60]) {
        const amount = Math.max(100000, Math.floor(Math.min(conditions.amount * amountFactor, policy.maxAmount) / 50000) * 50000);
        const candidate = { amount, months, ...security };
        if (evaluate(c, candidate, policy).approved && !offers.some(o => o.amount === amount && o.months === months && o.collateral === candidate.collateral && o.guarantee === candidate.guarantee)) offers.push(candidate);
        if (offers.length === 3) return offers;
      }
    }
  }
  return offers;
}
export function parsePolicy(raw: string): Policy {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Нужен JSON-объект с правилами политики.');
  const p = value as Record<string, unknown>;
  if (Object.keys(p).some(key => !(key in baselinePolicy)) || Object.keys(baselinePolicy).some(key => !(key in p))) throw new Error('Состав полей должен совпадать с шаблоном политики.');
  const ranges: Record<keyof Policy, [number, number]> = { minScore: [0, 100], maxDti: [.1, 1], maxAmount: [100000, 10000000], baseRate: [0, 60], collateralBonus: [0, 25], guaranteeBonus: [0, 25] };
  for (const key of Object.keys(ranges) as (keyof Policy)[]) {
    const [min, max] = ranges[key];
    if (typeof p[key] !== 'number' || !Number.isFinite(p[key]) || (p[key] as number) < min || (p[key] as number) > max) throw new Error(`${key}: ожидается число от ${min} до ${max}.`);
  }
  return p as Policy;
}
export function portfolio(count = 500): Case[] {
  let seed = 2026;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  return Array.from({ length: count }, (_, i) => {
    const revenue = Math.round(700000 + random() * 3600000);
    const expenses = Math.round(revenue * (.5 + random() * .35));
    return { id: `SYNTH-${i + 1}`, company: `Синтетическая компания ${i + 1}`, sector: 'Демо', revenue, expenses, debt: Math.round((revenue - expenses) * random() * .55), monthsInBusiness: Math.round(6 + random() * 60), overdueDays: random() < .12 ? 35 : 0, volatility: .05 + random() * .4, amount: Math.round((500000 + random() * 5000000) / 50000) * 50000, term: [12, 24, 36, 48][Math.floor(random() * 4)], purpose: 'Демо' };
  });
}
export function simulatePolicy(champion: Policy, challenger: Policy) {
  const rows = portfolio();
  let before = 0, after = 0, newlyApproved = 0, newlyRejected = 0;
  for (const c of rows) {
    const a = evaluate(c, initialConditions(c), champion).approved;
    const b = evaluate(c, initialConditions(c), challenger).approved;
    before += Number(a); after += Number(b);
    newlyApproved += Number(!a && b); newlyRejected += Number(a && !b);
  }
  return { size: rows.length, before, after, beforeRate: before / rows.length * 100, afterRate: after / rows.length * 100, newlyApproved, newlyRejected };
}
export type SourceId = 'bank' | 'ofd' | 'accounting' | 'marketplace';
export type FlowPoint = { day: number; incoming: number; outgoing: number; balance: number; event: string | null };
export function forecast(sources: SourceId[], horizon: number, initial = 320000): FlowPoint[] {
  if (!sources.includes('bank')) return [];
  let balance = initial;
  return Array.from({ length: horizon }, (_, i) => {
    const day = i + 1;
    let incoming = 65000 + Math.round(Math.sin(day * .8) * 9000);
    if (sources.includes('ofd')) incoming += 8000;
    if (sources.includes('marketplace') && day % 7 === 0) incoming += 135000;
    let outgoing = 44000 + Math.round(Math.cos(day * .6) * 4000);
    let event: string | null = null;
    if (sources.includes('accounting') && day === 12) { outgoing += 900000; event = 'Налог и зарплата'; }
    if (sources.includes('accounting') && day === 35) { outgoing += 650000; event = 'Оплата поставщику'; }
    balance += incoming - outgoing;
    return { day, incoming, outgoing, balance, event };
  });
}
export function flowSummary(points: FlowPoint[]) {
  const firstGap = points.find(point => point.balance < 0);
  const minimum = points.length ? Math.min(...points.map(p => p.balance)) : 0;
  return { firstGap: firstGap?.day ?? null, gap: Math.max(0, -minimum), calculatedLimit: minimum < 0 ? Math.ceil(-minimum * 1.2 / 10000) * 10000 : 0 };
}
export function cashCare(amount: number, rate: number, months: number, extension: number, idleBalance: number, assumedYield: number) {
  const original = calculate(amount, rate, months, 0);
  const changed = calculate(amount, rate, months + extension, 0);
  const monthlyYield = idleBalance * assumedYield / 1200;
  return { originalPayment: original.payment, newPayment: changed.payment, paymentRelief: original.payment - changed.payment, extraInterest: changed.interest - original.interest, monthlyYield, modeledInterestOffset: Math.min(monthlyYield, amount * rate / 1200) };
}
