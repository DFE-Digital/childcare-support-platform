import { useState } from "react";
import { Modal } from "./Modal";

interface ExplainerProps {
  label: string;
  modalTitle?: string;
  children: React.ReactNode;
}

export function Explainer({ label, modalTitle, children }: ExplainerProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-expanded={open}
        className="flex items-start gap-2 text-left text-base text-zinc-600 hover:text-zinc-900 transition-colors"
      >
        <i className="bi bi-info-circle shrink-0" aria-hidden="true" />
        {label}
      </button>
      {open && (
        <Modal
          onClose={() => setOpen(false)}
          title={
            <span className="flex items-baseline gap-2">
              <i className="bi bi-info-circle text-zinc-600" />
              {modalTitle ?? label}
            </span>
          }
        >
          <div className="space-y-3 text-sm text-zinc-700">{children}</div>
        </Modal>
      )}
    </>
  );
}
