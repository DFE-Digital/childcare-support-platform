.PHONY: build checkov

ENV ?= development

build:
	az bicep build --file bicep/main.bicep

checkov:
	docker run --rm -v $(CURDIR):/workdir -w /workdir bridgecrew/checkov -d bicep -f bicep/environments/$(ENV).params.json
