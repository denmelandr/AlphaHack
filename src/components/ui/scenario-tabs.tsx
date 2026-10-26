import * as TabsPrimitive from '@radix-ui/react-tabs';
import { LayoutGroup, motion, useReducedMotion } from 'motion/react';
import { useId, type ReactNode } from 'react';

// A shadcn/Radix control with an original sliding indicator inspired by Fluid Functionalism.
const scenarios = [{ id: 'low', label: 'Осторожный', description: 'Прибыль ниже прогноза на 30%' }, { id: 'base', label: 'Базовый', description: 'Прибыль по вашему прогнозу' }, { id: 'high', label: 'Оптимистичный', description: 'Прибыль выше прогноза на 20%' }];
export function ScenarioTabs({ value, onValueChange, children }: { value: string; onValueChange: (value: string) => void; children: ReactNode }) {
  const id = useId();
  const reduceMotion = useReducedMotion();
  return <TabsPrimitive.Root value={value} onValueChange={onValueChange}>
    <LayoutGroup id={id}>
      <TabsPrimitive.List className="segmented ui-scenario-tabs" aria-label="Сценарий прогноза">
        {scenarios.map(scenario => <TabsPrimitive.Trigger key={scenario.id} value={scenario.id} className="ui-scenario-trigger">
          {value === scenario.id && <motion.span className="ui-scenario-indicator" layoutId="active-scenario" transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 34 }}/>}<span>{scenario.label}</span>
        </TabsPrimitive.Trigger>)}
      </TabsPrimitive.List>
    </LayoutGroup>
    <TabsPrimitive.Content value={value} className="ui-scenario-content" tabIndex={-1}>
      <p className="ui-scenario-description">{scenarios.find(s => s.id === value)?.description}</p>
      {children}
    </TabsPrimitive.Content>
  </TabsPrimitive.Root>;
}
