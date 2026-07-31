import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
import { PostHogProvider } from "posthog-js/react";

const VITE_PUBLIC_POSTHOG_PROJECT_TOKEN =
  "phc_BEUy25B775nodzGfKTCce4aUUdrUe6QXLxhkSh2BpSsw"; // pragma: allowlist secret

// Analytics ride the same CloudFront distribution as the app via /ingest/*,
// which is reverse-proxied to eu.i.posthog.com. ui_host keeps deep links
// from the PostHog UI (e.g. session replays) pointing at the real dashboard.
const options = {
  api_host: "/ingest",
  ui_host: "https://eu.posthog.com",
  defaults: "2026-01-30",
  capture_pageview: false, // we are doing this manually in Layout.tsx to mimic react navigation, rather than initial load
  cookieless_mode: "always", // GDPR compliant, no cookies, no cookie banner needed
  capture_pageleave: true, // get page dwell time
  disable_session_recording: true, // turn off session replay
  autocapture: false, // turn off bulk interaction data collection - e.g we don't want child name input sent to analytics
} as const;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PostHogProvider
      apiKey={VITE_PUBLIC_POSTHOG_PROJECT_TOKEN}
      options={options}
    >
      <App />
    </PostHogProvider>
  </StrictMode>,
);
