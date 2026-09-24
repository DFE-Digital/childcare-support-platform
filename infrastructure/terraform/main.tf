// !!! TEMPORARY !!! //

module "edge" {
  source = "./edge"
}

module "core" {
  source = "./core"
}

module "runtime" {
  source = "./runtime"
}

module "security" {
  source = "./security"
}