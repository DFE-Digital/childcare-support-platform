interface Step {
  number: number;
  label: string;
}

interface StepIndicatorProps {
  steps: Step[];
  currentStep: number;
}

export function StepIndicator({ steps, currentStep }: StepIndicatorProps) {
  return (
    <>
      {/* Mobile: horizontal compact */}
      <div className="md:hidden mb-6">
        <div className="flex items-center gap-2 mb-2" aria-hidden="true">
          {steps.map((step) => {
            const isCompleted = step.number < currentStep;
            const isCurrent = step.number === currentStep;

            return (
              <div
                key={step.number}
                className={`h-1.5 flex-1 rounded-full ${
                  isCompleted
                    ? "bg-neutral-700"
                    : isCurrent
                      ? "bg-neutral-600"
                      : "bg-zinc-300"
                }`}
              />
            );
          })}
        </div>
        <p className="text-xs text-zinc-500">
          Step {currentStep} of {steps.length}:{" "}
          {steps.find((s) => s.number === currentStep)?.label}
        </p>
      </div>

      {/* Desktop: vertical */}
      <div className="hidden md:block">
        <nav aria-label="Progress">
          <ol className="space-y-0">
            {steps.map((step, i) => {
              const isCompleted = step.number < currentStep;
              const isCurrent = step.number === currentStep;

              return (
                <li
                  key={step.number}
                  className="relative"
                  aria-current={isCurrent ? "step" : undefined}
                >
                  <div className="flex items-start gap-5">
                    {i < steps.length - 1 && (
                      <div className="absolute left-[19px] top-[40px] w-[2px] h-[calc(100%-2px)] border-l-2 border-solid border-neutral-700" />
                    )}
                    <div
                      className={`relative z-10 w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0 border-2 ${
                        isCompleted || isCurrent
                          ? "bg-blue-100 border-neutral-700 text-neutral-700"
                          : "bg-white border-neutral-700 text-neutral-700"
                      }`}
                    >
                      {isCompleted ? (
                        <svg
                          width="14"
                          height="11"
                          viewBox="0 0 14 11"
                          fill="none"
                        >
                          <path
                            d="M1 5L5 9L13 1"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      ) : (
                        step.number
                      )}
                    </div>
                    <div className="pt-2 pb-[30px]">
                      <span className="text-base font-medium text-neutral-700">
                        {step.label}
                      </span>
                    </div>
                  </div>
                  {i < steps.length - 1 && (
                    <div className="absolute top-[calc(50%+20px)] left-[60px] right-0 border-t border-dashed border-neutral-700" />
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      </div>
    </>
  );
}
