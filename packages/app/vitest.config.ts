import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
  },
  resolve: {
    alias: [
      { find: /^@(?=\/)/, replacement: path.resolve(__dirname, "./src") },
    ],
    conditions: ["source"],
  },
});
