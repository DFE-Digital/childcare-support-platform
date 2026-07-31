# Terraform Modules

Reusable modules for the Best Start in Life infrastructure. Each module is self-contained and exposes typed inputs and outputs.

## Modules

| Module | Description | README |
|---|---|---|
| [vpc](vpc/) | VPC, subnets, IGW, NAT Gateway, S3 endpoint | [vpc/README.md](vpc/README.md) |
| [security](security/) | WAFv2 WebACLs (global + regional), security groups | [security/README.md](security/README.md) |
| [storage](storage/) | S3 buckets (provider-data, vite-build, tile-data), OAC | [storage/README.md](storage/README.md) |
| [compute](compute/) | Lambda, API Gateway, EC2 GitHub Actions runner | [compute/README.md](compute/README.md) |
| [cdn](cdn/) | CloudFront distribution with WAF and OAC | [cdn/README.md](cdn/README.md) |
| [iam](iam/) | Manual-Deployer-Role (scoped deploy permissions), Deployment-Users-Group, deployer IAM users | - |

## Dependency graph

```
vpc ──────────────────┐
  │                   │
  ▼                   ▼
security          compute ◄── security
  │                   
  ▼               
  ├──► compute    
  └──► cdn ◄──── storage
                    │
                    └── (re-apply with CDN ARN after first deploy)
```

Full dependency details and apply order are documented in [../live/README.md](../live/README.md).

## Usage

Modules are consumed by Terragrunt configurations under [../live/](../live/). They are not intended to be used as root modules directly.

See the individual module READMEs for inputs, outputs, and design notes.
