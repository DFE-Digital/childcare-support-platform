export function scrollToFirstError() {
  setTimeout(() => {
    const first = document.querySelector<HTMLElement>("[data-error-field]");
    if (!first) return;
    const stickyHeader = document.getElementById("sticky-header");
    const offset = (stickyHeader?.offsetHeight ?? 0) + 16;
    const top = first.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top, behavior: "smooth" });

    const focusable = first.querySelector<HTMLElement>(
      "input, select, textarea, [tabindex]",
    );
    if (focusable) focusable.focus({ preventScroll: true });
  }, 0);
}
