# Single-invocation bake file for the deploy pipeline.
#
# Builds bsil-test (Vite SPA + node tests + glibc SIS binaries) and
# bsil-lambda-builder (musl SIS binary for AWS Lambda) in one buildx call so
# both stages share a cache scope and the chef/planner layers are computed
# exactly once per CI run.
#
# Output mode is set on the CLI via `docker buildx bake --load`, which loads
# both target images into the local docker daemon so the deploy steps can
# `docker create` from them.

group "default" {
  targets = ["bsil-test", "bsil-lambda-builder"]
}

target "bsil-test" {
  context    = "."
  dockerfile = "Dockerfile"
  target     = "test"
  tags       = ["bsil-test"]
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
}

target "bsil-lambda-builder" {
  context    = "."
  dockerfile = "Dockerfile"
  target     = "lambda-builder"
  tags       = ["bsil-lambda-builder"]
  platforms  = ["linux/amd64"]
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
}
