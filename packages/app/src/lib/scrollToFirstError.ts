export function scrollToFirstError() {
  setTimeout(() => {
    const error = document.querySelector<HTMLElement>("[data-error-field]");
    if (!error) return;

    const field = error.previousElementSibling as HTMLElement | null;

    const stickyHeader = document.getElementById("sticky-header");
    const offset = (stickyHeader?.offsetHeight ?? 0) + 16;

    // Keep the input AND its error message in view
    const errorRect = error.getBoundingClientRect();
    const fieldRect = (field ?? error).getBoundingClientRect();
    const regionTop = Math.min(fieldRect.top, errorRect.top);
    const regionBottom = Math.max(fieldRect.bottom, errorRect.bottom);

    const fullyVisible = regionTop >= offset && regionBottom <= window.innerHeight;

    if (!fullyVisible) {
      window.scrollTo({
        top: regionTop + window.scrollY - offset,
        behavior: "smooth",
      });
    }

    field?.focus({ preventScroll: true });
  }, 0);
}