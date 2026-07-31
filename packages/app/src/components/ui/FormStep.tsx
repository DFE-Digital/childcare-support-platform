import type { ReactNode } from "react";

interface FormStepProps {
  title: string;
  children: ReactNode;
  onBack?: () => void;
  onContinue?: () => void;
  continueLabel?: string;
  continueDisabled?: boolean;
  showBack?: boolean;
  footer?: ReactNode;
  secondaryAction?: ReactNode;
}

export function FormStep({
  title,
  children,
  onBack,
  onContinue,
  continueLabel = "Continue",
  continueDisabled = false,
  showBack = true,
  footer,
  secondaryAction,
}: FormStepProps) {
  return (
    <div>
      {showBack && onBack && (
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-base font-bold text-neutral-700 hover:text-neutral-600 mb-6 transition-colors"
        >
          <span aria-hidden="true">&larr;</span> Back
        </button>
      )}
      <h2 className="text-[27px] md:text-[31px] xl:text-[36px] font-bold mb-6">
        {title}
      </h2>
      <div className="space-y-6">{children}</div>
      {onContinue && (
        <div className="mt-8 flex flex-col items-start gap-3">
          <button
            onClick={onContinue}
            className={`btn-dark${continueDisabled ? " opacity-50 cursor-not-allowed" : ""}`}
            disabled={continueDisabled}
          >
            {continueLabel} <span aria-hidden="true">&rarr;</span>
          </button>
          {secondaryAction}
        </div>
      )}
      {footer && <div className="mt-8 space-y-3">{footer}</div>}
    </div>
  );
}
