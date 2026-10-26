// Adapted from shadcn/ui (MIT), replacing the earlier handwritten menu behavior.
// https://ui.shadcn.com/r/styles/new-york/dropdown-menu.json
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { useState, type ComponentPropsWithoutRef, type ReactNode } from 'react';

type Props = { label: string; className: string; trigger: ReactNode; children: (close: () => void) => ReactNode };
export default function Dropdown({ label, className, trigger, children }: Props) {
  const [open, setOpen] = useState(false);
  return <div className={`dropdown ${className}-dropdown`}>
    <DropdownMenuPrimitive.Root open={open} onOpenChange={setOpen} modal={false}>
      <DropdownMenuPrimitive.Trigger asChild>
        <button type="button" className={className} aria-label={label}>{trigger}</button>
      </DropdownMenuPrimitive.Trigger>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content className={`dropdown-panel ui-dropdown-panel ${className}-panel`} aria-label={label}
          sideOffset={8} collisionPadding={12} align={className === 'profile' ? 'end' : 'start'}>
          {children(() => setOpen(false))}
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  </div>;
}
export function DropdownItem({ className = '', ...props }: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item>) {
  return <DropdownMenuPrimitive.Item className={`dropdown-item ${className}`} {...props}/>;
}
