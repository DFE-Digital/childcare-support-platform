# Deployer Access — Provisioning and Revocation

Operational runbook for granting and revoking manual deployment access to the BSIL AWS accounts.

For architecture context and day-to-day Switch Role usage, see [terraform/README.md](../terraform/README.md#manual-deployer-access-switch-role).

---

## Admin: provisioning a new user

### Step 1 — Add the user to the iam module

Add the username to `deploy_users` in `terraform/live/<env>/iam/terragrunt.hcl` for each account they need access to:

```hcl
deploy_users = [
  "existing-user@example.com",
  "alice@example.com",
]
```

Apply for each account:

```bash
make tg/apply env=dev module=iam
make tg/apply env=preprod module=iam  # if needed
make tg/apply env=prod module=iam     # if needed
```

### Step 2 — Create console credentials

Repeat for each account the user has been added to (set the correct `AWS_PROFILE` before each command):

```bash
aws iam create-login-profile \
  --user-name alice \
  --password "TempPassword123!" \
  --password-reset-required
```

### Step 3 — Share credentials securely

Send the following for each account via a secure channel (e.g. 1Password):

| Detail              | Value                                                |
| ------------------- | ---------------------------------------------------- |
| Console sign-in URL | `https://<account-id>.signin.aws.amazon.com/console` |
| Username            | `alice`                                              |
| Temporary password  | The value set in Step 2                              |

Account IDs for reference:

| Account | ID             |
| ------- | -------------- |
| dev     | `146072879673` |
| preprod | `135133927908` |
| prod    | `522029197016` |

---

## New user: first-time setup

### Step 1 — Sign in and change your password

1. Open the console sign-in URL provided by the admin.
2. Sign in with your username and temporary password.
3. You will be prompted to set a new password immediately.

### Step 2 — Enrol MFA

MFA is mandatory — the `EnforceMFA` policy blocks every action until a device is registered.

1. Go to **[your username in top right] → Security credentials**.
2. Under **Multi-factor authentication**, choose **Assign MFA device**.
3. For **MFA Device Name** enter your username (or it won't work)
4. Select **Authenticator app** and follow the wizard to register an MFA device (recommend you pick Authenticator App so that you have a code you can input in the CLI).
5. **You must** sign out, and back in, entering your MFA code when prompted, otherwise you won't have the permissions required for creating an access key.

Repeat this for each account you have access to — each account has its own IAM user and MFA device.

### Step 3 — Create an access key (for CLI use)

In each account, go to **[your username in top right] → Security credentials → Create access key**.

Select **Command Line Interface (CLI)**, acknowledge the warning, and note the **Access Key ID** and **Secret Access Key** — you will not be able to view the secret again.

### Step 4 — Set up aws-vault

[aws-vault](https://github.com/99designs/aws-vault) stores IAM credentials in your OS keychain and handles MFA-based role assumption automatically.

```bash
brew install aws-vault
```

Add your base credentials for each account (you will be prompted for the Access Key ID and Secret Access Key). You can leave MFA blank here as we specify it directly in the profile definitions below.

```bash
aws-vault add bsil-base-dev
aws-vault add bsil-base-preprod  # if you have preprod access
aws-vault add bsil-base-prod     # if you have prod access
```

### Step 5 — Configure AWS profiles

Add the following to `~/.aws/config`, replacing `YOUR_USERNAME` with your IAM username:

```ini
[profile bsil-base-dev]
region = eu-west-2
mfa_serial     = arn:aws:iam::146072879673:mfa/YOUR_USERNAME

[profile bsil-deployer-dev]
source_profile = bsil-base-dev
role_arn       = arn:aws:iam::146072879673:role/Manual-Deployer-Role
region         = eu-west-2

[profile bsil-base-preprod]
region = eu-west-2

[profile bsil-deployer-preprod]
source_profile = bsil-base-preprod
mfa_serial     = arn:aws:iam::135133927908:mfa/YOUR_USERNAME
role_arn       = arn:aws:iam::135133927908:role/Manual-Deployer-Role
region         = eu-west-2

[profile bsil-base-prod]
region = eu-west-2
mfa_serial     = arn:aws:iam::522029197016:mfa/YOUR_USERNAME

[profile bsil-deployer-prod]
source_profile = bsil-base-prod
role_arn       = arn:aws:iam::522029197016:role/Manual-Deployer-Role
region         = eu-west-2
```

### Step 6 — Test CLI access

> **Note — temporary workaround (April 2026):** `sts:AssumeRole` is currently blocked by an
> organisation-level SCP that we don't yet have access to modify. As a temporary measure,
> the deployer permissions have been attached directly to `Deployment-Users-Group` in addition
> to the role. Use the `bsil-base-*` profiles directly (not `bsil-deployer-*`) until the SCP
> is resolved. The `bsil-deployer-*` profiles and role-assumption flow remain in place for when
> the SCP is lifted.
>
> We have moved the `mfa_serial` config into the base profiles for the moment while this is
> being sorted out.

```bash
# Prompts for your TOTP code
aws-vault exec bsil-base-dev -- aws sts get-caller-identity
```

You should see your IAM user ARN in the response. You can now use any Makefile target by prefixing with `aws-vault exec`:

```bash
aws-vault exec bsil-base-dev -- make tg/plan env=dev module=storage
```

---

## Revoking access

### Full removal

Remove the username from `deploy_users` in each account's `terraform/live/<env>/iam/terragrunt.hcl` and apply:

```bash
make tg/apply env=dev module=iam
make tg/apply env=preprod module=iam  # repeat for each account
make tg/apply env=prod module=iam
```

Terraform will automatically delete the user's access keys, login profile, and MFA devices before destroying the user (`force_destroy = true` is set on the resource).

### Temporary suspension

Remove the username from `deploy_users` in the relevant `terragrunt.hcl` and apply as above. Terraform destroys the user entirely. When access should be reinstated, add the name back and repeat the provisioning steps.

If you need to suspend access immediately without a Terraform apply (e.g. pending investigation), remove the user from the group manually:

```bash
aws iam remove-user-from-group \
  --user-name alice \
  --group-name Deployment-Users-Group
```

Follow this up with a proper Terraform removal.

---

## Checklists

### Admin — granting access

- [ ] Username added to `deploy_users` in each required `live/<env>/iam/terragrunt.hcl`
- [ ] `make tg/apply env=<env> module=iam` run for each account
- [ ] Login profile created in each account
- [ ] Credentials shared securely (console URL, username, temp password)

### New user — first-time setup

- [ ] Signed in and changed password
- [ ] MFA device enrolled in each account
- [ ] Access key created in each account
- [ ] aws-vault configured with base credentials
- [ ] `~/.aws/config` profiles added
- [ ] `aws-vault exec bsil-base-dev -- aws sts get-caller-identity` returns your IAM user (role assumption temporarily bypassed — see Step 6 note)

### Admin — revoking access

- [ ] Username removed from `deploy_users` in each account's `live/<env>/iam/terragrunt.hcl`
- [ ] `make tg/apply env=<env> module=iam` run for each account
