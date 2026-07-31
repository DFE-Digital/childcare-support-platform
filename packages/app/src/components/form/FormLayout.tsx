import type { ReactNode } from "react";
import { StepIndicator } from "@/components/ui/StepIndicator";

interface FormLayoutProps {
  children: ReactNode;
  steps: Array<{ number: number; label: string }>;
  currentStep: number;
}

export function FormLayout({ children, steps, currentStep }: FormLayoutProps) {
  return (
    <div className="max-w-[960px] mx-auto">
      {/* Mobile step indicator (rendered by StepIndicator) */}
      <div className="md:hidden">
        <StepIndicator steps={steps} currentStep={currentStep} />
      </div>

      <div className="grid md:grid-cols-5 gap-8 md:gap-10">
        <div className="md:col-span-3">{children}</div>
        <div className="hidden md:block md:col-span-2">
          <StepIndicator steps={steps} currentStep={currentStep} />
        </div>
      </div>
    </div>
  );
}
