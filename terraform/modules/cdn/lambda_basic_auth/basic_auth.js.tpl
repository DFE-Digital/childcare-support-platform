// CloudFront Function — Basic Auth gate
// Expected credentials are baked in at Terraform plan time as a base64-encoded
// "user:pass" string. No runtime calls, no IAM, sub-millisecond latency.
var EXPECTED = "Basic ${expected_b64}";

function handler(event) {
  var auth = event.request.headers.authorization;
  if (auth && auth.value === EXPECTED) {
    return event.request;
  }
  return {
    statusCode: 401,
    statusDescription: "Unauthorized",
    headers: {
      "www-authenticate": { value: 'Basic realm="Beta Access"' },
    },
  };
}
