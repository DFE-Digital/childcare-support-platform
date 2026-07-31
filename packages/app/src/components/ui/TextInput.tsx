import type { InputHTMLAttributes } from "react";

interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function TextInput({
  label,
  className = "",
  id,
  type,
  onKeyDown,
  ...rest
}: TextInputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");

  const handleKeyDown =
    type === "number"
      ? (e: React.KeyboardEvent<HTMLInputElement>) => {
          if (["e", "E", "+", "-"].includes(e.key)) {
            e.preventDefault();
          }
          onKeyDown?.(e);
        }
      : onKeyDown;

  return (
    <div>
      {label && (
        <label htmlFor={inputId} className="block text-sm font-bold mb-1.5">
          {label}
        </label>
      )}
      <input
        id={inputId}
        type={type}
        className={`w-full border-2 border-neutral-700 rounded-lg px-4 py-3 text-base ${className}`}
        onKeyDown={handleKeyDown}
        {...rest}
      />
    </div>
  );
}
