import { useEffect, useRef } from 'react';

export function Toast({ message }: { message: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (message) element.showPopover();
    else if (element.matches(':popover-open')) element.hidePopover();
  }, [message]);
  return (
    <div
      ref={ref}
      popover="manual"
      className={`toast ${message ? 'show' : ''}`}
      role="status"
      aria-live="polite"
    >
      {message}
    </div>
  );
}
