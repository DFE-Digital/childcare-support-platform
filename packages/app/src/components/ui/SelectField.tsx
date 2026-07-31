import type { SelectHTMLAttributes } from "react";

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
}

export function SelectField({
  label,
  options,
  className = "",
  id,
  placeholder,
  ...rest
}: SelectFieldProps) {
  const selectId = id || label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <div>
      {label && (
        <label htmlFor={selectId} className="block text-sm font-bold mb-1.5">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={selectId}
          className={`w-full border-2 rounded-lg px-4 py-3 text-base bg-white appearance-none pr-10 border-neutral-700 ${className}`}
          {...rest}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
          <svg
            width="12"
            height="8"
            viewBox="0 0 12 8"
            fill="none"
            className="text-neutral-700"
            aria-hidden="true"
          >
            <path
              d="M1 1.5L6 6.5L11 1.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>
    </div>
  );
}
