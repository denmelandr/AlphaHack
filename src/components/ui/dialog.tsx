// Adapted from shadcn/ui (MIT), using the existing Alfa CSS theme.
// https://ui.shadcn.com/r/styles/new-york/dialog.json
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { useRef, type ReactNode } from 'react';

export function CabinetDialog({ open, title, wide, onOpenChange, children }: {
  open: boolean; title: string; wide?: boolean; onOpenChange: (open: boolean) => void; children: ReactNode;
}) {
  const returnFocus = useRef<HTMLElement | null>(null);
  return <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="ui-dialog-overlay" />
      <DialogPrimitive.Content className={`modal ui-dialog-content${wide ? ' wide' : ''}`} aria-describedby={undefined}
        onOpenAutoFocus={() => { returnFocus.current = document.activeElement as HTMLElement; }}
        onCloseAutoFocus={event => {
          if (returnFocus.current?.isConnected) { event.preventDefault(); returnFocus.current.focus(); }
        }}>
        <DialogPrimitive.Title asChild><span className="sr-only">{title}</span></DialogPrimitive.Title>
        <DialogPrimitive.Close className="icon-button modal-close" aria-label="Закрыть"><X size={21}/></DialogPrimitive.Close>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  </DialogPrimitive.Root>;
}
