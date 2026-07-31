import { useRef, useEffect, useId } from "react";

interface ModalProps {
  onClose: () => void;
  title: React.ReactNode;
  children: React.ReactNode;
  maxWidth?: string;
  headerExtra?: React.ReactNode;
}

export function Modal({
  onClose,
  title,
  children,
  maxWidth = "max-w-lg",
  headerExtra,
}: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<Element | null>(document.activeElement);
  const titleId = useId();

  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleCancel = (e: Event) => {
      e.preventDefault();
      onCloseRef.current();
    };
    dialog.addEventListener("cancel", handleCancel);
    return () => {
      dialog.removeEventListener("cancel", handleCancel);
      document.body.style.overflow = previousOverflow;
      (triggerRef.current as HTMLElement)?.focus();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      className={`backdrop:bg-black/50 bg-transparent p-4 ${maxWidth} w-full max-h-[90vh] m-auto overflow-hidden overscroll-none`}
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose();
      }}
    >
      <div className="bg-white rounded-xl max-h-[calc(90vh-2rem)] flex flex-col overflow-hidden">
        <div className="shrink-0 bg-white px-6 pt-6 pb-3 border-b border-zinc-100 flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h3 id={titleId} className="font-bold text-lg">
              {title}
            </h3>
            {headerExtra && <div className="mt-1">{headerExtra}</div>}
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 shrink-0 flex items-center justify-center rounded-full border-2 border-neutral-700 bg-neutral-700 text-white hover:bg-white hover:text-neutral-700 transition-all duration-200 focus-visible:outline-[3px] focus-visible:outline-[#3b82f6] focus-visible:outline-offset-[3px] focus-visible:shadow-[0_0_0_3px_white]"
            aria-label="Close"
          >
            <i className="bi bi-x-lg block leading-none" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-8 pt-4">
          {children}
        </div>
      </div>
    </dialog>
  );
}
