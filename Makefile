-include .env
export

pre-commit-setup:
	brew install bandit ruff pip-audit uv
	pre-commit install

node-setup:
	make pre-commit-setup
	chmod +x ./scripts/node-setup.sh && \
	./scripts/node-setup.sh
	source $$HOME/.nvm/nvm.sh && nvm use && npm install


# Docker
ECR_URL=$(ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
ECR_REPO_URL=$(ECR_URL)/$(ECR_REPO_NAME)
IMAGE=$(ECR_REPO_URL):$(IMAGE_TAG)
IMAGE_TAG = $$(git rev-parse HEAD)

ifdef docker_build_directory
	BUILD_DIR := ./$(docker_build_directory)
	DOCKERFILE := $(docker_build_directory)/$${dockerfile:-Dockerfile}
	REPO_SUFFIX := $(docker_build_directory)
else
	BUILD_DIR := .
	DOCKERFILE := $${dockerfile:-Dockerfile}
	# If no build directory, there's probably just a frontend
	REPO_SUFFIX := frontend
endif
# Derive final variables
DOCKER_BUILD_ARGS = $(BUILD_DIR) -f $(DOCKERFILE) --target=$${target:-production}
ECR_REPO_NAME = $(APP_NAME)-$(REPO_SUFFIX)


ifndef container_type
	override container_type = dash
endif

ifndef cache
	override cache = ./.build-cache
endif



ifeq ($(beta), true)
	ifeq ($(filter root frontend,$(docker_build_directory)),$(docker_build_directory))
	DOCKER_BUILD_ARGS +=--build-arg APP_NAME=beta-$(APP_NAME)
	IMAGE_TAG=$$(git rev-parse HEAD)-beta
	endif
else
DOCKER_BUILD_ARGS +=--build-arg APP_NAME=$(APP_NAME)
IMAGE_TAG=$$(git rev-parse HEAD)
endif


APP_CACHE_DIR = $(cache)/$(APP_NAME)/$(docker_build_directory)


fetch-data:
	@echo "Fetching app data from S3..."
	@mkdir -p .docker-data/app/providers .docker-data/app/inward .docker-data/parquet/published .docker-data/parquet/la
	aws s3 sync s3://ten-ds-clean-data/beststartinlife/app/ .docker-data/app/ --delete --no-progress
	@for f in providers care_types fee_rates opening_hours; do \
		aws s3 cp "s3://ten-ds-clean-data/beststartinlife/parquet/published/$$f.parquet" .docker-data/parquet/published/ --no-progress; \
	done
	aws s3 cp s3://ten-ds-clean-data/beststartinlife/parquet/la/family_information_services.parquet .docker-data/parquet/la/ --no-progress
	aws s3 cp s3://ten-ds-clean-data/beststartinlife/la_boundaries.geojson .docker-data/ --no-progress || true
	@if [ -f .docker-data/app/providers.tar.gz ]; then \
		echo "Extracting providers..."; \
		tar xzf .docker-data/app/providers.tar.gz -C .docker-data/app/providers; \
		rm .docker-data/app/providers.tar.gz; \
	fi
	@if [ -f .docker-data/app/inward.tar.gz ]; then \
		echo "Extracting inward postcodes..."; \
		tar xzf .docker-data/app/inward.tar.gz -C .docker-data/app/inward; \
		rm .docker-data/app/inward.tar.gz; \
	fi

# BSIL account IDs — used to validate credentials before pushing/fetching
BSIL_ACCOUNT_DEV     = 146072879673
BSIL_ACCOUNT_PREPROD = 135133927908
BSIL_ACCOUNT_PROD    = 522029197016

# Provider-data bucket in the BSIL account (project-scoped, no beststartinlife/ prefix needed)
BSIL_DATA_BUCKET = beststartinlife-$(env)-provider-data
# Intermediary source-data bucket — manually uploaded by deployers, read by GitHub runners
BSIL_SOURCE_BUCKET = beststartinlife-$(env)-source-data

bsil/check-account:
	$(eval CALLER_ACCOUNT := $(shell aws sts get-caller-identity --query Account --output text 2>/dev/null))
	@if [ "$(env)" = "dev" ]; then EXPECTED=$(BSIL_ACCOUNT_DEV); \
	elif [ "$(env)" = "preprod" ]; then EXPECTED=$(BSIL_ACCOUNT_PREPROD); \
	elif [ "$(env)" = "prod" ]; then EXPECTED=$(BSIL_ACCOUNT_PROD); \
	else echo "ERROR: env must be dev, preprod, or prod (got '$(env)')"; exit 1; fi; \
	if [ "$(CALLER_ACCOUNT)" != "$$EXPECTED" ]; then \
		echo "ERROR: AWS credentials are for account $(CALLER_ACCOUNT), but $(env) requires $$EXPECTED."; \
		echo "Run 'aws sso login --profile bsil-$(env)' and set AWS_PROFILE=bsil-$(env)."; \
		exit 1; \
	fi
	@echo "Account check passed ($(env): $(CALLER_ACCOUNT))."

fetch-data-bsil: bsil/check-account
	@echo "Fetching app data from BSIL $(env) S3 ($(BSIL_DATA_BUCKET))..."
	@mkdir -p .docker-data/app/providers .docker-data/app/inward .docker-data/parquet/published .docker-data/parquet/la
	aws s3 sync s3://$(BSIL_DATA_BUCKET)/app/ .docker-data/app/ --delete --no-progress
	@for f in providers care_types fee_rates; do \
		aws s3 cp "s3://$(BSIL_DATA_BUCKET)/parquet/published/$$f.parquet" .docker-data/parquet/published/ --no-progress; \
	done
	aws s3 cp s3://$(BSIL_DATA_BUCKET)/parquet/la/family_information_services.parquet .docker-data/parquet/la/ --no-progress
	aws s3 cp s3://$(BSIL_DATA_BUCKET)/la_boundaries.geojson .docker-data/ --no-progress || true
	@if [ -f .docker-data/app/providers.tar.gz ]; then \
		echo "Extracting providers..."; \
		tar xzf .docker-data/app/providers.tar.gz -C .docker-data/app/providers; \
		rm .docker-data/app/providers.tar.gz; \
	fi
	@if [ -f .docker-data/app/inward.tar.gz ]; then \
		echo "Extracting inward postcodes..."; \
		tar xzf .docker-data/app/inward.tar.gz -C .docker-data/app/inward; \
		rm .docker-data/app/inward.tar.gz; \
	fi

# DEPRECATED
# data/push-bsil: bsil/check-account


# Sync provider-data to the CloudFront-served bucket (no cache invalidation).
# Files are uploaded under the data/ prefix because CloudFront forwards the full /data/* path
# to S3 (no prefix stripping), so the app's requests for /data/outward.json etc. resolve to
# s3://bucket/data/outward.json.
# Called by cdn/push-provider-data and prod/deploy-bsil.
cdn/push-provider-data-no-invalidate: bsil/check-account
	@echo "Syncing to s3://$(BSIL_DATA_BUCKET)/data/..."
	aws s3 sync exported_data/app/ s3://$(BSIL_DATA_BUCKET)/data/ \
		--exclude "*" \
		--include "providers/*" \
		--include "inward/*" \
		--include "lad/*" \
		--include "outward.json" \
		--include "tiles/*" \
		--include "sis_schema.json" \
		--include "data_version.txt" \
		--cache-control "no-cache" \
		--delete \
		--no-progress
	@echo "Sync complete."

# Invalidate the provider-data CloudFront cache across all distributions that serve this bucket.
# Usage: make cdn/invalidate env=dev
cdn/invalidate: bsil/check-account
	@echo "Invalidating CloudFront cache for data bucket..."
	$(eval DIST_IDS := $(shell aws cloudfront list-distributions \
		--query "DistributionList.Items[?Origins.Items[?contains(DomainName, '$(BSIL_DATA_BUCKET)')]].Id" \
		--output text))
	@if [ -z "$(DIST_IDS)" ]; then echo "WARNING: No CloudFront distributions found for $(BSIL_DATA_BUCKET) — skipping invalidation."; \
	else for id in $(DIST_IDS); do \
		aws cloudfront create-invalidation --distribution-id $$id --paths "/data/*" > /dev/null && echo "Invalidation created for $$id."; \
	done; fi

# Sync provider-data to S3 and invalidate CloudFront.
# Usage: make cdn/push-provider-data env=dev
cdn/push-provider-data: cdn/push-provider-data-no-invalidate cdn/invalidate
	@echo "Done."

docker/login:
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_URL)

docker/build:
	# The build action can take the following arguments:
	#   - dockerfile: The Dockerfile to use (default: Dockerfile)
	#   - docker_build_directory: The directory to build from (default: not defined)
	#   - target: The target to build (default: production)
	#   - container_type: The type of container to build (default: dash)
	#   - cache: The cache directory to use (default: ./.build-cache)
	#   - data_source: Where to pull .docker-data from:
	#       omit        — pull from ten-ds-clean-data (default, shared data lake)
	#       bsil        — pull from beststartinlife-$(env)-provider-data (deployed data)
	#       exported    — pull from beststartinlife-$(env)-source-data (intermediary build data)
	#                     When data_source=bsil or exported, also set env=dev|preprod|prod.
ifeq ($(data_source),bsil)
	$(MAKE) fetch-data-bsil
else ifeq ($(data_source),exported)
	$(MAKE) data/fetch-exported
else
	$(MAKE) fetch-data
endif
	DOCKER_BUILDKIT=1 docker buildx build --platform linux/amd64 --load --build-arg GEMFURY_URL=$(GEMFURY_URL) --builder=$(container_type) -t $(IMAGE) \
	--cache-to type=local,dest=$(APP_CACHE_DIR) \
	--cache-from type=local,src=$(APP_CACHE_DIR) ${DOCKER_BUILD_ARGS}

docker/push:
	docker push $(IMAGE)

docker/update-tag:
	MANIFEST=$$(aws ecr batch-get-image --repository-name $(ECR_REPO_NAME) --image-ids imageTag=$(IMAGE_TAG) --query 'images[].imageManifest' --output text) && \
	aws ecr put-image --repository-name $(ECR_REPO_NAME) --image-tag $(tag) --image-manifest "$$MANIFEST"

# Ouputs the value that you're after - useful to get a value i.e. IMAGE_TAG out of the Makefile
docker/echo:
	echo $($(value))

# Bootstrap — run once per account using the bootstrap IAM role
# Usage: make bootstrap/plan account=dev
#        make bootstrap/apply account=dev
#        make bootstrap/destroy account=dev  (use with care!)
account ?= dev

bootstrap/init:
	terraform -chdir=terraform/bootstrap init

bootstrap/plan: bootstrap/init
	terraform -chdir=terraform/bootstrap plan -var-file="accounts/$(account).tfvars"

bootstrap/apply: bootstrap/init
	terraform -chdir=terraform/bootstrap apply -var-file="accounts/$(account).tfvars"

bootstrap/destroy: bootstrap/init
	@echo "\033[0;31mWARNING: This will DESTROY bootstrap resources for account '$(account)'.\033[0m"
	@read -p "Type 'yes' to continue: " confirm && \
	if [ "$$confirm" != "yes" ]; then \
		echo "Operation cancelled." && exit 1; \
	fi
	terraform -chdir=terraform/bootstrap destroy -var-file="accounts/$(account).tfvars"

bootstrap/output: bootstrap/init
	terraform -chdir=terraform/bootstrap output

# Terragrunt — module-level deploys
# Usage: make tg/plan env=dev module=storage
#        make tg/apply env=dev module=storage
#        make tg/apply env=dev module=all        (all modules in dependency order)
#        make tg/destroy env=dev module=storage  (use with care!)
env ?= dev
module ?= all

tg/plan:
	terragrunt $(if $(filter all,$(module)),run-all,) plan --working-dir terraform/live/$(env)$(if $(filter all,$(module)),,/$(module))

tg/apply:
	terragrunt $(if $(filter all,$(module)),run-all,) apply --working-dir terraform/live/$(env)$(if $(filter all,$(module)),,/$(module))

tg/destroy:
	@echo "\033[0;31mWARNING: This will DESTROY '$(module)' in $(env).\033[0m"
	@read -p "Type 'yes' to continue: " confirm && \
	if [ "$$confirm" != "yes" ]; then \
		echo "Operation cancelled." && exit 1; \
	fi
	terragrunt $(if $(filter all,$(module)),run-all,) destroy --working-dir terraform/live/$(env)$(if $(filter all,$(module)),,/$(module))

tg/output:
	terragrunt output --working-dir terraform/live/$(env)/$(module)

# Terraform
# Set terraform workspace ENV to default if env not specified
env ?= default
beta ?= false

tf_build_args=-var "image_tag=$(IMAGE_TAG)" -var "beta=$(beta)"

tf/set-or-create-workspace:
	terraform -chdir=terraform/$(instance) workspace select -or-create $(env)

tf/init:
	terraform -chdir=./terraform/$(instance) init ${args}

tf/plan:
	make tf/set-or-create-workspace && \
	terraform -chdir=./terraform/$(instance) plan ${args} ${tf_build_args}

tf/apply:
	make tf/set-or-create-workspace && \
	terraform -chdir=./terraform/$(instance) apply ${args} ${tf_build_args}

tf/destroy:
	make tf/set-or-create-workspace && \
	terraform -chdir=./terraform/$(instance) destroy ${tf_build_args} ${args}

# Docker Compose commands
ifeq ($(CI),true)
    COMPOSE_FILES := -f docker-compose.yml -f docker-compose.cicd.yml
else
    COMPOSE_FILES :=
endif

app/dash-up:
	@if [ ! -d packages/data-app/.venv ]; then \
		echo "Creating venv..."; \
		python3.13 -m venv packages/data-app/.venv; \
		packages/data-app/.venv/bin/pip install -r packages/data-app/requirements.txt; \
	fi
	cd packages/data-app && DASH_PATHNAME_PREFIX=/ .venv/bin/python app.py

# Production: standalone `docker run` container (bsil-frontend-prod, :8080).
# Dev: docker compose services (frontend :5173, spatial-index-service :3001).
# The two are independent — they can coexist on different ports.
# Use `make down` to stop everything.

# Shared build gate: compiles the Vite SPA (builder stage) and Rust SIS binaries
# (sis-builder stage) in parallel via BuildKit, then gates on all tests passing.
# Used by sis/preprocess and frontend/build so neither needs its own docker build.
bsil/build:
	DOCKER_BUILDKIT=1 docker build --target test -t bsil-test .

prod/build: fetch-data
	DOCKER_BUILDKIT=1 docker build --target production -t bsil-frontend .

prod/up: prod/down prod/build
	docker run -d --name bsil-frontend-prod -p 8080:8080 bsil-frontend

prod/down:
	@docker stop bsil-frontend-prod 2>/dev/null || true
	@docker rm bsil-frontend-prod 2>/dev/null || true

# Fail if the working tree has uncommitted changes.
git/check-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: Working tree is dirty. Commit or stash changes before deploying."; \
		git status --short; \
		exit 1; \
	fi

DEPLOY_VERSION_FILE = /tmp/bsil-deploy-version.txt

# Create a git tag encoding the environment, UTC timestamp, and GitHub username, then push it.
# Tag format: deploy/{env}/{YYYY-MM-DDTHH-MM-SS}/{github-username}
# List past deployments: git tag -l "deploy/prod/*"  (or dev, or preprod)
deploy/tag-and-version: git/check-clean
	@COMMIT_SHA=$$(git rev-parse HEAD); \
	TIMESTAMP=$$(date -u +%Y-%m-%dT%H:%M:%SZ); \
	TIMESTAMP_SAFE=$$(date -u +%Y-%m-%dT%H-%M-%S); \
	if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then \
		GH_USER=$$(gh api user --jq '.login'); \
	else \
		echo "WARNING: gh CLI unavailable — using git config user.name"; \
		GH_USER=$$(git config user.name | tr ' ' '-' | tr '[:upper:]' '[:lower:]'); \
	fi; \
	TAG_NAME="deploy/$(env)/$${TIMESTAMP_SAFE}/$${GH_USER}"; \
	echo "commit: $${COMMIT_SHA}" > $(DEPLOY_VERSION_FILE); \
	echo "environment: $(env)" >> $(DEPLOY_VERSION_FILE); \
	echo "timestamp: $${TIMESTAMP}" >> $(DEPLOY_VERSION_FILE); \
	echo ""; \
	echo "=== version.txt ==="; \
	cat $(DEPLOY_VERSION_FILE); \
	echo "==================="; \
	echo "Creating tag: $${TAG_NAME}"; \
	git tag "$${TAG_NAME}"; \
	git push origin "$${TAG_NAME}"; \
	echo "Tag pushed."

# Upload version.txt to the frontend bucket after s3 sync (which uses --delete).
# Accessible at: https://<cloudfront-domain>/version.txt
deploy/upload-version:
	@echo "Uploading version.txt to s3://$(VITE_BUCKET)/version.txt..."
	aws s3 cp $(DEPLOY_VERSION_FILE) s3://$(VITE_BUCKET)/version.txt \
		--cache-control "no-cache,no-store,must-revalidate" \
		--content-type "text/plain"
	@echo "version.txt uploaded."

# Full BSIL cloud deployment: spatial index → provider data → frontend → Lambda → coordinated invalidation.
# Uploads everything before firing cache invalidations so the SPA, data, and Lambda switch over together.
# Usage: make prod/deploy-bsil env=dev|preprod|prod
# Prereqs: exported_data/app/ must be populated (run make data/export-app first).
# After deploy, version.txt is at: https://<cloudfront-domain>/version.txt
prod/deploy-bsil: git/check-clean
	@if [ "$(env)" = "prod" ]; then \
		echo "WARNING: You are about to deploy to PRODUCTION."; \
		read -p "Type 'yes' to continue: " confirm && \
		if [ "$$confirm" != "yes" ]; then echo "Aborted." && exit 1; fi; \
	fi
	$(MAKE) deploy/tag-and-version env=$(env)
	$(MAKE) sis/preprocess
	$(MAKE) cdn/push-provider-data-no-invalidate env=$(env)
	$(MAKE) frontend/upload env=$(env)
	$(MAKE) deploy/upload-version env=$(env)
	$(MAKE) sis/deploy env=$(env)
	@echo "All uploads complete. Firing coordinated cache invalidations..."
	$(MAKE) cdn/invalidate env=$(env)
	$(MAKE) frontend/invalidate env=$(env)
	@echo "Deployment complete."

APP_SERVICES := frontend spatial-index-service

app/up:
	@mkdir -p exported_data/app/providers exported_data/app/inward exported_data/app/lad
	@echo "Starting application..."
	DOCKER_BUILDKIT=1 docker compose $(COMPOSE_FILES) up -d --build $(APP_SERVICES)

app/down:
	docker compose $(COMPOSE_FILES) stop $(APP_SERVICES)

app/logs:
	open http://localhost:9999
app/restart:
	docker compose $(COMPOSE_FILES) restart $(APP_SERVICES)


# Data pipeline (compose services only)
DATA_SERVICES := postgres prisma-migrate dagster-user-code dagster-webserver dagster-daemon

data/_ensure-postcode-lookup:
# Postcode lookup is copied into the container, but it's also generated by the container
# and docker copy isn't optional. Therefore to bootstrap first use, we create an empty placeholder:
	@if [ ! -f packages/data-pipeline/data/postcode_lad_lookup.csv.gz ]; then \
		echo "Creating placeholder postcode_lad_lookup.csv.gz (run postcode_lookup asset to generate real data)..."; \
		mkdir -p packages/data-pipeline/data; \
		printf 'pcds,oslaua,lat,long\n' | gzip > packages/data-pipeline/data/postcode_lad_lookup.csv.gz; \
	fi

sandwich:
	@if [ "$$(id -u)" = "0" ]; then \
			echo "Okay"; \
	else \
			echo "what? $(notdir $(MAKE)) it yourself!"; \
	fi

data/up: data/_ensure-postcode-lookup
	@echo "Starting data pipeline services..."
	docker compose $(COMPOSE_FILES) up -d --build $(DATA_SERVICES)

data/down:
	docker compose $(COMPOSE_FILES) stop $(DATA_SERVICES)

data/wipe:
	@echo "This will destroy all Docker volumes including the database."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || (echo "Aborted."; exit 1)
	docker compose $(COMPOSE_FILES) down -v

# Stop everything: all compose services + standalone prod container
down: app/down data/down prod/down

data/psql:
	docker compose exec postgres psql -U $${POSTGRES_USER:-bsil} -d $${POSTGRES_DB:-bsil}

data/dagster:
	open http://localhost:3000


data/draft-fixtures:
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j draft_provider_data

data/migrate:
	docker compose $(COMPOSE_FILES) run --rm prisma-migrate

data/rebuild:
	docker compose $(COMPOSE_FILES) up -d --build --force-recreate $(DATA_SERVICES)

data/test:
	@docker compose exec -T postgres psql -U $${POSTGRES_USER:-bsil} -tc \
		"SELECT 1 FROM pg_database WHERE datname='bsil_test'" | grep -q 1 || \
		docker compose exec -T postgres psql -U $${POSTGRES_USER:-bsil} -c "CREATE DATABASE bsil_test"
	@docker compose run --rm \
		-e DATABASE_URL=postgresql://$${POSTGRES_USER:-bsil}:$${POSTGRES_PASSWORD:-bsil_local}@postgres:5432/bsil_test?schema=published \
		prisma-migrate
	docker compose exec -e POSTGRES_DB=bsil_test dagster-user-code pip install -e ".[test]" --quiet && \
	docker compose exec -e POSTGRES_DB=bsil_test dagster-user-code pytest tests/ -v -m "not spot_check"
	@echo "Validating published schema with Zod..."
	docker compose exec -e DATABASE_URL=postgresql://$${POSTGRES_USER:-bsil}:$${POSTGRES_PASSWORD:-bsil_local}@postgres:5432/bsil_test?schema=published \
		dagster-user-code sh -c "cd /opt/dagster/app/schemas && npm install --omit=dev --quiet && npx prisma generate --schema prisma/schema.prisma 2>/dev/null && cp -r packages/schemas/src/generated src/ && npx tsx src/validate-published.ts"

data/publish:
ifndef BETA
	$(error BETA is required. Use BETA=true for beta LA subset or BETA=false for all England)
endif
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j publish_data --tags '{"BETA": "$(BETA)"}'

data/spot-check:
	docker compose exec dagster-user-code pip install -e ".[test]" --quiet && \
	docker compose exec dagster-user-code python -m pytest tests/test_published_spot_checks.py -v

data/clean:
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j clean_data

data/export-app:
ifndef BETA
	$(error BETA is required. Use BETA=true for beta LAs only or BETA=false for all LAs)
endif
ifeq ($(origin METADATA),undefined)
	$(error METADATA is required. Use METADATA=true (include) or METADATA=false (exclude))
endif
	@git rev-parse HEAD > packages/data-pipeline/data/.git-commit
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j export_app_data --tags '{"BETA": "$(BETA)", "METADATA": "$(METADATA)"}'


data/load-sources:
	docker compose exec -e FIS_CSV_PATH=$${FIS_CSV_PATH:-/opt/dagster/app/source_data/family_information_services.csv} dagster-user-code dagster job execute -m bsil_pipeline.definitions -j load_source_data

data/scrape-ofsted:
ifndef BETA
	$(error BETA is required. Use BETA=true for beta LAs only or BETA=false for all LAs)
endif
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j scrape_ofsted_reports --tags '{"BETA": "$(BETA)"}'

data/scrape-la:
ifndef BETA
	$(error BETA is required. Use BETA=true for beta LAs only or BETA=false for all LAs)
endif
ifdef partition
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j scrape_la_providers --tags '{"dagster/partition": "$(partition)", "BETA": "$(BETA)"}'
else
	docker compose exec dagster-user-code dagster job backfill -m bsil_pipeline.definitions -j scrape_la_providers --all --noprompt --tags '{"BETA": "$(BETA)"}'
endif

data/export-parquet:
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j export_parquet_data

data/geocode-ofsted:
ifndef BETA
	$(error BETA is required. Use BETA=true for beta LAs only or BETA=false for all LAs)
endif
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j geocode_ofsted_places --tags '{"BETA": "$(BETA)"}'

data/geocode-la:
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j geocode_la_places

data/restore-parquet:
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j restore_parquet_data

data/posthog-sync:
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j posthog_sync

data/draft:
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j build_draft

data/complete:
	@git rev-parse HEAD > packages/data-pipeline/data/.git-commit
	docker compose exec dagster-user-code dagster job execute \
	  -m bsil_pipeline.definitions -j load_source_data \
	  --tags '{"CASCADE": "true"}'
	@echo " 👀  Monitor the pipeline to completion at: http://localhost:3000"
	@echo " 😴  Automations are likely to fail if your laptop sleeps (for mac users: caffeinate -dims)"
	@echo " 🛠️  Afterwards, if you're doing local development, make sure you rebuild the SIS container (make app/up is sufficient)"

data/asset:
ifndef name
	$(error name is required. Usage: make data/asset name=<asset_name>)
endif
	docker compose exec dagster-user-code dagster asset materialize -m bsil_pipeline.definitions --select $(name)

data/jupyter:
	docker compose $(COMPOSE_FILES) up -d --build jupyter
	@echo "Jupyter Lab: http://localhost:8888"

data/jupyter/open:
	open http://localhost:8888

data/prisma:
	@# Ensure shadow DB exists for migration diff
	@docker compose exec -T postgres psql -U $${POSTGRES_USER:-bsil} -tc \
		"SELECT 1 FROM pg_database WHERE datname='bsil_shadow'" | grep -q 1 || \
		docker compose exec -T postgres psql -U $${POSTGRES_USER:-bsil} -c "CREATE DATABASE bsil_shadow"
	@diff_sql=$$(npx prisma migrate diff \
		--from-migrations prisma/migrations \
		--to-schema-datamodel prisma/schema.prisma \
		--shadow-database-url "postgresql://$${POSTGRES_USER:-bsil}:$${POSTGRES_PASSWORD:-bsil_local}@localhost:5432/bsil_shadow?schema=published" \
		--script 2>&1); \
	if [ -z "$$diff_sql" ] || echo "$$diff_sql" | grep -q "empty migration"; then \
		echo "No migration needed — schema is up to date."; \
	else \
		echo "=== Migration diff ==="; \
		echo "$$diff_sql"; \
		echo ""; \
		read -p "Migration name (or empty to skip): " name; \
		if [ -n "$$name" ]; then \
			dir="prisma/migrations/$$(printf '%04d' $$(($$(ls -1d prisma/migrations/[0-9]* 2>/dev/null | wc -l) + 1)))_$$name"; \
			mkdir -p "$$dir"; \
			echo "$$diff_sql" > "$$dir/migration.sql"; \
			echo "Written to $$dir/migration.sql"; \
		fi; \
	fi
	@# Clean up shadow DB
	@docker compose exec -T postgres psql -U $${POSTGRES_USER:-bsil} -c "DROP DATABASE IF EXISTS bsil_shadow" > /dev/null
	@echo ""
	@echo "Regenerating Prisma client + Zod schemas..."
	npm run generate
	npm run build -w @bsil/schemas

# Push exported_data/app/ to the intermediary source-data bucket for use in image builds.
# Usage: make data/push-exported env=dev|preprod|prod
# Prereq: exported_data/app/ must be populated (run make data/export-app first).
data/push-exported: bsil/check-account
	@test -d exported_data/app || { echo "ERROR: exported_data/app/ not found. Run 'make data/export-app' first."; exit 1; }
	@echo "Uploading exported_data/app/ to s3://$(BSIL_SOURCE_BUCKET)/app/..."
	aws s3 sync exported_data/app/ s3://$(BSIL_SOURCE_BUCKET)/app/ \
		--delete \
		--no-progress
	@echo "Done."

# Pull from the intermediary source-data bucket into .docker-data/app/ for image builds.
# Usage: make data/fetch-exported env=dev|preprod|prod
data/fetch-exported: bsil/check-account
	@echo "Downloading s3://$(BSIL_SOURCE_BUCKET)/app/ to .docker-data/app/..."
	@mkdir -p .docker-data/app
	aws s3 sync s3://$(BSIL_SOURCE_BUCKET)/app/ .docker-data/app/ \
		--delete \
		--no-progress
	@echo "Done."

data/push-source:
	@aws sts get-caller-identity > /dev/null 2>&1 || { echo "ERROR: AWS credentials not configured. Run 'aws sso login' first."; exit 1; }
	@echo "Uploading source_data/ to s3://$${SOURCE_BUCKET}/beststartinlife/source_data/..."
	aws s3 sync source_data/ s3://$${SOURCE_BUCKET}/beststartinlife/source_data/ \
		--exclude "README.md" --exclude ".DS_Store" --exclude "parquet/*"
	@echo "Done."

data/fetch-source:
	@aws sts get-caller-identity > /dev/null 2>&1 || { echo "ERROR: AWS credentials not configured. Run 'aws sso login' first."; exit 1; }
	@echo "Downloading source_data/ from s3://$${SOURCE_BUCKET}/beststartinlife/source_data/..."
	@mkdir -p source_data
	aws s3 sync s3://$${SOURCE_BUCKET}/beststartinlife/source_data/ source_data/
	@echo "Done."

# data/push-s3: DEPRECATED — Atlas deployment no longer used.
# Was: compress + upload exported data to ten-ds-clean-data S3 bucket.

data/extract-la:
ifndef BETA
	$(error BETA is required. Use BETA=true for beta LAs only or BETA=false for all LAs)
endif
ifdef partition
	docker compose exec dagster-user-code dagster job execute -m bsil_pipeline.definitions -j extract_la_providers --tags '{"dagster/partition": "$(partition)", "BETA": "$(BETA)"}'
else
	docker compose exec dagster-user-code dagster job backfill -m bsil_pipeline.definitions -j extract_la_providers --all --noprompt --tags '{"BETA": "$(BETA)"}'
endif


# Frontend — build and deploy Vite app to S3 + invalidate CloudFront
# Usage: make frontend/deploy env=dev
#        make frontend/build  (local build only, no deploy)
# No local Node toolchain required — dist is extracted from the bsil-test image (built by bsil/build).
VITE_BUCKET = beststartinlife-$(env)-vite-build-outputs

frontend/build: bsil/build
	@docker rm bsil-frontend-extract 2>/dev/null || true
	docker create --name bsil-frontend-extract bsil-test
	@mkdir -p packages/app/dist
	docker cp bsil-frontend-extract:/app/packages/app/dist/. packages/app/dist/
	docker rm bsil-frontend-extract

# Upload built Vite dist to S3 without invalidating CloudFront.
# Called by frontend/deploy and prod/deploy-bsil.
frontend/upload: frontend/build
	@aws sts get-caller-identity > /dev/null 2>&1 || { echo "ERROR: AWS credentials not configured. Run 'aws sso login' first."; exit 1; }
	@echo "Syncing dist/ to s3://$(VITE_BUCKET)/..."
	aws s3 sync packages/app/dist/ s3://$(VITE_BUCKET)/ \
		--delete \
		--cache-control "public,max-age=31536000,immutable" \
		--exclude "index.html"
	aws s3 cp packages/app/dist/index.html s3://$(VITE_BUCKET)/index.html \
		--cache-control "no-cache,no-store,must-revalidate"
	@echo "Upload complete."

# Invalidate the frontend CloudFront cache across all distributions that serve this bucket.
# Usage: make frontend/invalidate env=dev
frontend/invalidate:
	@aws sts get-caller-identity > /dev/null 2>&1 || { echo "ERROR: AWS credentials not configured. Run 'aws sso login' first."; exit 1; }
	@echo "Invalidating CloudFront cache for frontend..."
	$(eval DIST_IDS := $(shell aws cloudfront list-distributions \
		--query "DistributionList.Items[?Origins.Items[?contains(DomainName, '$(VITE_BUCKET)')]].Id" \
		--output text))
	@if [ -z "$(DIST_IDS)" ]; then echo "WARNING: No CloudFront distributions found for $(VITE_BUCKET) — skipping invalidation."; \
	else for id in $(DIST_IDS); do \
		aws cloudfront create-invalidation --distribution-id $$id --paths "/*" > /dev/null && echo "Invalidation created for $$id."; \
	done; fi

# Build, upload and invalidate CloudFront.
# Usage: make frontend/deploy env=dev
frontend/deploy: frontend/upload frontend/invalidate
	@echo "Deploy complete."

app/test:
	cd packages/app && npm test

calculator/test:
	npm test -w @bsil/calculator

test: app/test calculator/test sis/test
	@echo "All local tests passed."

# Spatial Index Service
sis/test:
	cd packages/spatial-index-service && cargo test

sis/build:
	cd packages/spatial-index-service && cargo build --release

# Generate spatial_index.sis and sis_schema.json from spatial_index.parquet.
# Runs sis-preprocess inside the bsil-test image (built by bsil/build) — no local Rust toolchain needed.
# Must be run before cdn/push-provider-data and sis/lambda-bundle.
# Prereq: exported_data/app/spatial_index.parquet must exist (run make data/export-app first).
sis/preprocess: bsil/build
	@test -f exported_data/app/spatial_index.parquet || \
		(echo "ERROR: exported_data/app/spatial_index.parquet not found. Run 'make data/export-app' first." && exit 1)
	@set -e; \
	CID=$$(docker create bsil-test \
		sh -c "SIS_FILEPATH=/tmp/spatial_index.sis \
		       SIS_SCHEMA_JSON_PATH=/tmp/sis_schema.json \
		       SIS_BBOX_INFLATION=1 \
		       SIS_RESULT_LIMIT=500 \
		       sis-preprocess /tmp/spatial_index.parquet"); \
	docker cp exported_data/app/spatial_index.parquet $$CID:/tmp/spatial_index.parquet; \
	docker start -a $$CID; \
	docker cp $$CID:/tmp/spatial_index.sis exported_data/app/spatial_index.sis; \
	docker cp $$CID:/tmp/sis_schema.json exported_data/app/sis_schema.json; \
	docker rm $$CID
	@echo "Generated: exported_data/app/spatial_index.sis + sis_schema.json"

# Bundle the SIS Lambda zip using the lambda-builder Docker stage.
# Extracts the static musl sis-query binary and zips it with spatial_index.sis.
# Prereq: sis/preprocess must have been run (generates spatial_index.sis).
sis/lambda-bundle:
	@test -f exported_data/app/spatial_index.sis || \
		(echo "ERROR: exported_data/app/spatial_index.sis not found. Run 'make sis/preprocess' first." && exit 1)
	DOCKER_BUILDKIT=1 docker build --platform linux/amd64 --target lambda-builder -t bsil-lambda-builder .
	@mkdir -p packages/spatial-index-service/target/lambda-bundle
	@docker rm bsil-lambda-extract 2>/dev/null || true
	docker create --platform linux/amd64 --name bsil-lambda-extract bsil-lambda-builder
	docker cp bsil-lambda-extract:/usr/local/bin/sis-query-lambda \
		packages/spatial-index-service/target/lambda-bundle/bootstrap
	docker rm bsil-lambda-extract
	cp exported_data/app/spatial_index.sis \
		packages/spatial-index-service/target/lambda-bundle/spatial_index.sis
	cd packages/spatial-index-service/target/lambda-bundle && \
		zip -j ../sis-lambda.zip bootstrap spatial_index.sis
	@echo "Bundle: packages/spatial-index-service/target/sis-lambda.zip"

# Deploy SIS Lambda to a BSIL account.
# Usage: make sis/deploy env=dev
# Prereqs: sis/preprocess must have been run (generates spatial_index.sis).
sis/deploy: bsil/check-account sis/lambda-bundle
	@echo "Deploying SIS Lambda to beststartinlife-$(env)-spatial-index..."
	aws lambda update-function-code \
		--function-name beststartinlife-$(env)-spatial-index \
		--zip-file fileb://packages/spatial-index-service/target/sis-lambda.zip \
		--no-cli-pager
	@echo "SIS Lambda deploy complete."

delete-terraform:
	@echo "\033[0;31mWARNING: This will DELETE terraform resources in $(env) environment.\033[0m"
	@read -p "Type 'yes' to continue: " confirm && \
	if [ "$$confirm" != "yes" ]; then \
		echo "Operation cancelled." && exit 1; \
	fi
	@echo "Triggering delete-terraform workflow for $(env) environment... Please check actions tab for progress."
	@gh workflow run delete-terraform.yml -f environment=$(env)
