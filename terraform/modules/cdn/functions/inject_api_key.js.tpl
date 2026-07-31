// CloudFront Function — API key injector
// The key value is baked in at Terraform plan time from SSM — never visible to browser clients.
var API_KEY = "${api_key}";
function handler(event) {
  event.request.headers["x-api-key"] = { value: API_KEY };
  return event.request;
}
