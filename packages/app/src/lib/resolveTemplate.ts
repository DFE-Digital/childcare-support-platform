export function resolveTemplate(
  template: string,
  params?: Record<string, string>,
): string {
  if (!params) return template;
  return Object.entries(params).reduce(
    (text, [key, value]) => text.replace(`{${key}}`, value),
    template,
  );
}
