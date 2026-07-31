import "@testing-library/jest-dom/vitest";

// jsdom does not implement window.scrollTo — stub it to suppress stderr noise
window.scrollTo = (() => {}) as typeof window.scrollTo;
