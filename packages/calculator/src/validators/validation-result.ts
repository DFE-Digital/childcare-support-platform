export interface ValidationError {
  path: string;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

export function ok(): ValidationResult {
  return { valid: true, errors: [] };
}

export function fail(errors: ValidationError[]): ValidationResult {
  return { valid: false, errors };
}

export function merge(...results: ValidationResult[]): ValidationResult {
  const errors = results.flatMap((r) => r.errors);
  return { valid: errors.length === 0, errors };
}

export function nest(
  prefix: string,
  result: ValidationResult,
): ValidationResult {
  return {
    valid: result.valid,
    errors: result.errors.map((e) => ({
      path: prefix + (e.path ? "." + e.path : ""),
      message: e.message,
    })),
  };
}
