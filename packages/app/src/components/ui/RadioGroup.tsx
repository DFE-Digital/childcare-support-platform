interface RadioOption {
  value: string;
  label: string;
}

interface RadioGroupProps {
  name: string;
  options: RadioOption[];
  value: string;
  onChange: (value: string) => void;
  label?: React.ReactNode;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
}

export function RadioGroup({
  name,
  options,
  value,
  onChange,
  label,
  "aria-describedby": ariaDescribedBy,
  "aria-invalid": ariaInvalid,
}: RadioGroupProps) {
  return (
    <fieldset
      aria-describedby={ariaDescribedBy}
      aria-invalid={ariaInvalid || undefined}
    >
      {label && <legend className="font-bold text-lg mb-3">{label}</legend>}
      <div className="space-y-3">
        {options.map((opt) => (
          <label
            key={opt.value}
            className="flex items-start gap-3 cursor-pointer group"
          >
            <span className="relative w-[27px] h-[27px] shrink-0">
              <input
                type="radio"
                name={name}
                value={opt.value}
                checked={value === opt.value}
                onChange={() => onChange(opt.value)}
                className="sr-only peer"
              />
              <span className="absolute inset-0 rounded-full border-2 border-neutral-700 peer-checked:border-neutral-600 peer-focus-visible:ring-[3px] peer-focus-visible:ring-offset-[3px] peer-focus-visible:ring-[#3b82f6] transition-colors" />
              <span className="absolute inset-[5px] rounded-full bg-neutral-600 scale-0 peer-checked:scale-100 transition-transform" />
            </span>
            <span className="text-base group-hover:text-neutral-600">
              {opt.label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
