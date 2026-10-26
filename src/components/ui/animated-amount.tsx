import { CountingNumber } from '@animate-ui/react/primitives/texts/counting-number';
export function AnimatedAmount({ value, signed = false }: { value: number; signed?: boolean }) {
  return <span className="ui-amount" aria-label={`${signed && value >= 0 ? 'Плюс ' : ''}${Math.round(value)} рублей`}>
    <span aria-hidden="true">{signed && value >= 0 ? '+' : ''}<CountingNumber number={Math.round(value)} initiallyStable thousandSeparator=" " transition={{ type: 'tween', duration: 0.4, ease: 'easeOut' }}/>{' ₽'}</span>
  </span>;
}
