interface CheckboxOption {
  value: string;
  label: string;
}

interface CheckboxGroupProps {
  name: string;
  options: CheckboxOption[];
  value: string[];
  onChange: (value: string[]) => void;
  label?: React.ReactNode;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
}

export function CheckboxGroup({
  name,
  options,
  value,
  onChange,
  label,
  "aria-describedby": ariaDescribedBy,
  "aria-invalid": ariaInvalid,
}: CheckboxGroupProps) {
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
            className="flex items-center gap-3 cursor-pointer group"
          >
            <span className="relative w-[27px] h-[27px] shrink-0">
              <input
                type="checkbox"
                name={name}
                value={opt.value}
                checked={value.includes(opt.value)}
                onChange={() => {
                  const next = value.includes(opt.value)
                    ? value.filter((v) => v !== opt.value)
                    : [...value, opt.value];
                  onChange(next);
                }}
                className="sr-only peer"
              />
              <span className="absolute inset-0 rounded-sm border-2 border-neutral-700 peer-checked:border-neutral-600 peer-focus-visible:ring-[3px] peer-focus-visible:ring-offset-[3px] peer-focus-visible:ring-[#3b82f6] transition-colors" />
              <svg
                className="absolute inset-[5px] text-neutral-600 scale-0 peer-checked:scale-100 transition-transform"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="2 8.5 6 12.5 14 3.5" />
              </svg>
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
