export function calculate(amount: number, rate: number, months: number, profit: number, delay = 0) {
  const monthlyRate = rate / 1200;
  const payment = monthlyRate === 0 ? amount / months : amount * monthlyRate / (1 - (1 + monthlyRate) ** -months);
  const interest = payment * months - amount;
  const projectedProfit = profit * Math.max(0, months - delay);
  return { payment, interest, total: amount + interest, projectedProfit, benefit: projectedProfit - interest, coverage: profit / payment, shortage: profit < payment || delay > 0 };
}
