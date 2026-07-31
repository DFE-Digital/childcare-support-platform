import { useId } from "react";

interface ValidationWrapperProps {
  error?: boolean;
  message?: string;
  className?: string;
  children:
    | React.ReactNode
    | ((props: { errorId?: string; invalid: boolean }) => React.ReactNode);
}

export function ValidationWrapper({
  error,
  message,
  className,
  children,
}: ValidationWrapperProps) {
  const id = useId();
  const errorId = error && message ? `${id}-error` : undefined;

  return (
    <div
      data-error-field={error || undefined}
      className={`${error ? "border-2 border-red-600 rounded-md overflow-hidden" : ""}${className ? ` ${className}` : ""}`}
    >
      <div className={error ? "p-3" : ""}>
        {typeof children === "function"
          ? children({ errorId, invalid: !!error })
          : children}
      </div>
      {error && message && (
        <p
          id={errorId}
          role="alert"
          className="text-sm text-white bg-red-600 px-3 py-1.5"
        >
          {message}
        </p>
      )}
    </div>
  );
}
