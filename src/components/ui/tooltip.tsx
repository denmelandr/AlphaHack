// Adapted from shadcn/ui (MIT). https://ui.shadcn.com/r/styles/new-york/tooltip.json
import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import { CircleHelp } from 'lucide-react';
import { useState, type ReactNode } from 'react';

export const TooltipProvider = TooltipPrimitive.Provider;
export function HelpTooltip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <TooltipPrimitive.Root open={open} onOpenChange={setOpen}>
    <TooltipPrimitive.Trigger asChild>
      <button type="button" className="info-tip ui-help-trigger" aria-label={label} onClick={() => setOpen(true)}><CircleHelp size={18}/></button>
    </TooltipPrimitive.Trigger>
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content className="ui-tooltip" sideOffset={8} collisionPadding={16}>
        {children}<TooltipPrimitive.Arrow className="ui-tooltip-arrow" width={12} height={6}/>
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  </TooltipPrimitive.Root>;
}
