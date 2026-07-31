// CloudFront Function — PostHog reverse-proxy URI rewriter (viewer-request)
//
// CloudFront routes /ingest/static/* to the eu-assets.i.posthog.com origin and
// /ingest/* to the eu.i.posthog.com origin. PostHog expects requests at the
// root of those domains, so we strip our /ingest prefix here before the
// request is forwarded to the origin.
//
// Runs at every PoP, sub-millisecond, no IAM, no cold start.

function handler(event) {
  var req = event.request;
  if (req.uri.indexOf("/ingest/static/") === 0) {
    req.uri = req.uri.replace("/ingest/static/", "/static/");
  } else if (req.uri.indexOf("/ingest/") === 0) {
    req.uri = req.uri.replace("/ingest/", "/");
  } else if (req.uri === "/ingest" || req.uri === "/ingest/") {
    req.uri = "/";
  }
  return req;
}
