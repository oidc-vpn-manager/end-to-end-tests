SHELL := /bin/bash
timestamp := $$(date +%H%M)

# Default target
help: ## Show this help message
	@echo "OpenVPN Management Service"
	@echo "=========================="
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

fetch:
	@echo "⬇️ Pulling main in all submodules"
	@git submodule foreach bash -c "git checkout main && git pull"
	@echo "✅ Done"

test: test_setup test_certtransparency test_frontend test_signing test_get_openvpn_config test_pki_tool rebuild_docker check_services_ready test_browser

test_after_docker: test_setup test_certtransparency test_frontend test_signing test_get_openvpn_config test_pki_tool check_services_ready test_browser

just_test_e2e: rebuild_docker check_services_ready test_browser

just_test_without_e2e: test_setup test_certtransparency test_frontend test_signing test_get_openvpn_config test_pki_tool

reset_tests:
	@echo "🧹 Flush old test results"
	@rm -f suite_test_results/*

test_setup:
	@echo "🔍 Ensuring results directory is created (suite_test_results)"
	@mkdir -p suite_test_results
	@echo "🔍 Installing Python dependencies from all requirements.txt files"
	@failed_installs="" ; \
	find . -name "requirements*.txt" -not -path "*/\.*" -not -path "*/tiny-oidc/*" | sort | while read f; do \
		echo "  📦 pip install -r $$f" ; \
		out=$$(pip install -q -r "$$f" 2>&1) ; rc=$$? ; \
		if [ $$rc -ne 0 ]; then \
			failed_pkgs=$$(echo "$$out" | grep "^ERROR: No matching distribution found for" | sed 's/ERROR: No matching distribution found for //') ; \
			echo "$$out" | grep "^ERROR:" >&2 ; \
			echo "  ⚠️  Could not install from $$f: $$failed_pkgs" ; \
		fi ; \
	done ; true
	@echo "🔍 Installing playwright"
	@playwright install chromium

start_docker: set_oidc_url
	@echo "📦 Building and starting all services with docker-compose..."
	@bash -c "source tests/.env.tinyoidc 2>/dev/null || true ; cd tests && docker compose up -d --build"

rebuild_docker: set_oidc_url ## Clean rebuild all containers (removes volumes)
	@echo "🔄 Performing clean rebuild of all containers..."
	@cd tests && docker compose down --volumes
	@bash -c "source tests/.env.tinyoidc 2>/dev/null || true ; cd tests && docker compose up --build -d"
	@echo "✅ Clean rebuild complete"

rebuild_docker_images:
	@echo "🔄 Performing rebuild of all images..."
	@cd tests && docker compose build
	@echo "✅ Clean rebuild complete"

push_docker_images: rebuild_docker_images
	@echo "📦 Tagging and pushing all repos"
	@bash -c '\
		set -e -u -E -o pipefail ; \
		source .fn.semver_bump.sh ; \
		export timestamp=$$(date +"%Y%m%d-%H%M%S") ; \
		export datestamp=$$(date +"%Y%m%d") ; \
		echo "🔍 Processing oidc-vpn-manager images with contexts..." ; \
		services=$$(docker compose -f tests/docker-compose.yml config --format json | jq -r ".services | to_entries[] | select(.value.image | contains(\"oidc-vpn-manager\")) | select(.value.build.context) | \"\(.value.image)|\(.value.build.context)\"" | sort -u) ; \
		for service in $$services ; \
		do \
			export image="$$(echo $$service | cut -d"|" -f1)" ; \
			export context="$$(echo $$service | cut -d"|" -f2)" ; \
			export reponame="$$(echo $$image | cut -d: -f1)" ; \
			echo "" ; \
			echo "📁 Processing: $$image (context: $$context)" ; \
			\
			pushd "$$context" >/dev/null || continue ; \
			if git tag --points-at HEAD | grep -q . ; then \
				export semver="$$(git tag --points-at HEAD | head -n1)" ; \
				echo "⏭️  No changes since $$semver - skipping" ; \
				popd >/dev/null ; \
				continue ; \
			fi ; \
			semver_bump "$$context" ; \
			export semver="$$(git tag --points-at HEAD | head -n1)" ; \
			echo "✅ Using new tag: $$semver" ; \
			popd >/dev/null ; \
			\
			export major="$$(echo $$semver | cut -d. -f1)" ; \
			export minor="$$(echo $$semver | cut -d. -f2)" ; \
			echo "🐳 Tagging $$image -> $$reponame:$$timestamp, $$reponame:$$semver" ; \
			docker tag "$$image" "$$reponame:$$timestamp" ; \
			docker tag "$$image" "$$reponame:$$semver" ; \
			docker tag "$$image" "$$reponame:$${major}.$${minor}" ; \
			docker tag "$$image" "$$reponame:$${major}" ; \
			echo "📤 Pushing $$reponame:$$timestamp, $$reponame:$$semver, $$image" ; \
			docker push "$$reponame:$$timestamp" ; \
			docker push "$$reponame:$$semver" ; \
			docker push "$$reponame:$${major}.$${minor}" ; \
			docker push "$$reponame:$${major}" ; \
			docker push "$$image" ; \
			\
			export component="$$(echo $$reponame | awk -F/ "{print \$$NF}")" ; \
			echo "📝 Updating Helm values: $$component -> $$semver" ; \
			sed -i "/repository: $$component$$/{n;s/tag: .*/tag: $$semver/}" deploy/with-helm/oidc-vpn-manager/values.yaml ; \
		done ; \
		echo "" ; \
		echo "✅ Finished processing all images" \
	'
	@echo "✅ Pushed"

rebuild_docker_and_push: rebuild_docker push_docker_images

push_docker_rc: rebuild_docker_images ## Build and push RC-tagged images (no helm bump)
	@bash -c '\
		set -e -u -E -o pipefail ; \
		source .fn.semver_bump.sh ; \
		echo "🔍 Processing oidc-vpn-manager images for RC release..." ; \
		services=$$(docker compose -f tests/docker-compose.yml config --format json | jq -r ".services | to_entries[] | select(.value.image | contains(\"oidc-vpn-manager\")) | select(.value.build.context) | \"\(.value.image)|\(.value.build.context)\"" | sort -u) ; \
		for service in $$services ; \
		do \
			export image="$$(echo $$service | cut -d"|" -f1)" ; \
			export context="$$(echo $$service | cut -d"|" -f2)" ; \
			export reponame="$$(echo $$image | cut -d: -f1)" ; \
			echo "" ; \
			echo "📁 Processing: $$image (context: $$context)" ; \
			\
			pushd "$$context" >/dev/null || continue ; \
			current_tag=$$(git tag -l --no-column 2>/dev/null | grep -E "^v[0-9]+\.[0-9]+\.[0-9]+$$" | sort -V | tail -n 1) ; \
			if [ -z "$$current_tag" ]; then \
				current_tag="" ; \
			fi ; \
			next_semver=$$(generate_next_semver "$$current_tag" "$${BUMP:-patch}") ; \
			echo "🔸 Current: $${current_tag:-none} -> Next: $$next_semver" ; \
			\
			last_rc=$$(git tag -l "$${next_semver}-rc*" 2>/dev/null | sed "s/.*-rc//" | sort -n | tail -n 1) ; \
			next_rc=$$(( $${last_rc:-0} + 1 )) ; \
			rc_tag="$${next_semver}-rc$${next_rc}" ; \
			echo "🏷️  RC tag: $$rc_tag" ; \
			\
			git tag -a "$$rc_tag" -m "Release candidate $$rc_tag" ; \
			echo "✅ Created git tag: $$rc_tag" ; \
			popd >/dev/null ; \
			\
			echo "🐳 Tagging $$image -> $$reponame:$$rc_tag" ; \
			docker tag "$$image" "$$reponame:$$rc_tag" ; \
			echo "📤 Pushing $$reponame:$$rc_tag" ; \
			docker push "$$reponame:$$rc_tag" ; \
		done ; \
		echo "" ; \
		echo "✅ Finished pushing all RC images" \
	'

bump_chart: ## Bump the Helm chart version and appVersion (patch)
	@bash -c '\
		set -e -u -E -o pipefail ; \
		source .fn.semver_bump.sh ; \
		chart_file="deploy/with-helm/oidc-vpn-manager/Chart.yaml" ; \
		current_chart_version=$$(sed -n "s/^version: //p" "$$chart_file") ; \
		new_chart_version=$$(generate_next_semver "$$current_chart_version" "$${BUMP:-patch}" | sed "s/^v//") ; \
		echo "🔸 Chart version: $$current_chart_version -> $$new_chart_version" ; \
		sed -i "s/^version: .*/version: $$new_chart_version/" "$$chart_file" ; \
		sed -i "s/^appVersion: .*/appVersion: \"$$new_chart_version\"/" "$$chart_file" ; \
		pushd deploy/with-helm/ ; \
		git add oidc-vpn-manager/Chart.yaml oidc-vpn-manager/values.yaml ; \
		git commit -m "Bump chart to $$new_chart_version" ; \
		git tag -a $$new_chart_version -m "Auto-tagged as part of release process" ; \
		popd ; \
		echo "✅ Updated $$chart_file" \
	'

push_chart: ## Package and push Helm chart to GHCR
	@bash -c '\
		set -e -u -E -o pipefail ; \
		chart_dir="deploy/with-helm/oidc-vpn-manager" ; \
		chart_version=$$(sed -n "s/^version: //p" "$$chart_dir/Chart.yaml") ; \
		echo "📦 Packaging Helm chart v$$chart_version..." ; \
		helm package "$$chart_dir" ; \
		echo "📤 Pushing to oci://ghcr.io/oidc-vpn-manager/deploy-with-helm..." ; \
		if ! gh auth status --json hosts --jq '"'"'.hosts."github.com"[0].scopes'"'"' | grep -q '"'"'write:packages'"'"'; then echo "Adding permission to write packages" ; gh auth refresh -s write:packages ; fi ; \
		gh auth token | helm registry login ghcr.io -u "$$(gh auth status --jq '"'"'.hosts."github.com"[0].login'"'"' --json hosts)" --password-stdin ; \
		helm push "oidc-vpn-manager-$${chart_version}.tgz" oci://ghcr.io/oidc-vpn-manager/deploy-with-helm ; \
		rm -f "oidc-vpn-manager-$${chart_version}.tgz" ; \
		echo "✅ Pushed oidc-vpn-manager:$$chart_version" \
	'

release_chart: ## Atomic bump + push chart with rollback on failure
	@bash -c '\
		set -e -u -E -o pipefail ; \
		source .fn.semver_bump.sh ; \
		chart_file="deploy/with-helm/oidc-vpn-manager/Chart.yaml" ; \
		chart_dir="deploy/with-helm/oidc-vpn-manager" ; \
		\
		current_chart_version=$$(sed -n "s/^version: //p" "$$chart_file") ; \
		new_chart_version=$$(generate_next_semver "$$current_chart_version" "$${BUMP:-patch}" | sed "s/^v//") ; \
		echo "🔸 Chart version: $$current_chart_version -> $$new_chart_version" ; \
		\
		sed -i "s/^version: .*/version: $$new_chart_version/" "$$chart_file" ; \
		sed -i "s/^appVersion: .*/appVersion: \"$$new_chart_version\"/" "$$chart_file" ; \
		pushd deploy/with-helm/ ; \
		git add oidc-vpn-manager/Chart.yaml oidc-vpn-manager/values.yaml ; \
		git commit -m "Bump chart to $$new_chart_version" ; \
		git tag -a $$new_chart_version -m "Auto-tagged as part of release process" ; \
		popd ; \
		echo "✅ Committed chart $$new_chart_version" ; \
		\
		echo "📦 Packaging Helm chart v$$new_chart_version..." ; \
		helm package "$$chart_dir" ; \
		echo "📤 Pushing to oci://ghcr.io/oidc-vpn-manager/deploy-with-helm..." ; \
		if ! gh auth status --json hosts --jq '"'"'.hosts."github.com"[0].scopes'"'"' | grep -q '"'"'write:packages'"'"'; then echo "Adding permission to write packages" ; gh auth refresh -s write:packages ; fi ; \
		gh auth token | helm registry login ghcr.io -u "$$(gh auth status --jq '"'"'.hosts."github.com"[0].login'"'"' --json hosts)" --password-stdin ; \
		if helm push "oidc-vpn-manager-$${new_chart_version}.tgz" oci://ghcr.io/oidc-vpn-manager/deploy-with-helm ; then \
			rm -f "oidc-vpn-manager-$${new_chart_version}.tgz" ; \
			echo "✅ Pushed oidc-vpn-manager:$$new_chart_version" ; \
		else \
			echo "❌ Chart push failed — rolling back version bump" ; \
			rm -f "oidc-vpn-manager-$${new_chart_version}.tgz" ; \
			pushd deploy/with-helm/ ; \
			git tag -d "$$new_chart_version" 2>/dev/null || true ; \
			git reset --hard HEAD~1 ; \
			popd ; \
			echo "🔄 Rolled back to chart version $$current_chart_version" ; \
			exit 1 ; \
		fi \
	'

release: push_docker_images release_chart ## Full release: build, tag, push images + chart, push all git repos
	@echo "📤 Pushing all git repos..."
	@git submodule foreach git push
	@git submodule foreach git push --tags
	@git push
	@git push --tags
	@echo "✅ Release complete"

rc_release: push_docker_rc ## RC release: build and push RC-tagged images, push all git repos
	@echo "📤 Pushing all git repos..."
	@git submodule foreach git push
	@git submodule foreach git push --tags
	@git push
	@git push --tags
	@echo "✅ RC release complete"

check_services_ready:
	@echo "⏳ Running pre-flight service readiness tests..."
	@bash -c "cd tests && pytest pre-flight-tests/ -v" 2>&1 | tee suite_test_results/pre_flight.$(timestamp).log ; \
	if [ $${PIPESTATUS[0]} -ne 0 ]; then \
		echo "" ; \
		echo "❌ PRE-FLIGHT TESTS FAILED - Test suite cannot proceed" ; \
		echo "❌ Please check suite_test_results/pre_flight.$(timestamp).log for details" ; \
		echo "" ; \
		exit 1 ; \
	fi
	@echo "✅ Pre-flight tests passed - proceeding with test suite"

# The following tests are all unit, functional and integration tests local to the services or tools themselves
test_certtransparency:
	@echo "📋 Checking certtransparency service"
	@rm -f suite_test_results/certtransparency.log
	@bash -c "cd services/certtransparency && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/certtransparency.log | tee suite_test_results/certtransparency.$(timestamp).log ; \
	if [ $${PIPESTATUS[0]} -ne 0 ]; then \
		echo "" ; \
		echo "❌ CERTTRANSPARENCY TESTS FAILED" ; \
		echo "❌ Please check suite_test_results/certtransparency.$(timestamp).log for details" ; \
		echo "" ; \
		exit 1 ; \
	fi
	@echo "✅ Certificate Transparency tests passed"

test_frontend:
	@echo "📋 Checking frontend service"
	@rm -f suite_test_results/frontend.log
	@bash -c "cd services/frontend         && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/frontend.log | tee suite_test_results/frontend.$(timestamp).log ; \
	if [ $${PIPESTATUS[0]} -ne 0 ]; then \
		echo "" ; \
		echo "❌ FRONTEND TESTS FAILED" ; \
		echo "❌ Please check suite_test_results/frontend.$(timestamp).log for details" ; \
		echo "" ; \
		exit 1 ; \
	fi
	@echo "✅ Frontend tests passed"

test_signing:
	@echo "📋 Checking signing service"
	@rm -f suite_test_results/signing.log
	@bash -c "cd services/signing          && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/signing.log | tee suite_test_results/signing.$(timestamp).log ; \
	if [ $${PIPESTATUS[0]} -ne 0 ]; then \
		echo "" ; \
		echo "❌ SIGNING SERVICE TESTS FAILED" ; \
		echo "❌ Please check suite_test_results/signing.$(timestamp).log for details" ; \
		echo "" ; \
		exit 1 ; \
	fi
	@echo "✅ Signing service tests passed"


test_get_openvpn_config:
	@echo "📋 Checking get_openvpn_config tool"
	@rm -f suite_test_results/get_config.log
	@bash -c "cd tools/get_openvpn_config  && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/get_config.log | tee suite_test_results/get_config.$(timestamp).log ; \
	if [ $${PIPESTATUS[0]} -ne 0 ]; then \
		echo "" ; \
		echo "❌ GET_OPENVPN_CONFIG TOOL TESTS FAILED" ; \
		echo "❌ Please check suite_test_results/get_config.$(timestamp).log for details" ; \
		echo "" ; \
		exit 1 ; \
	fi
	@echo "✅ get_openvpn_config tool tests passed"

test_pki_tool:
	@echo "📋 Checking pki_tool"
	@rm -f suite_test_results/generate_pki.log
	@bash -c "cd tools/pki_tool            && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/generate_pki.log | tee suite_test_results/generate_pki.$(timestamp).log ; \
	if [ $${PIPESTATUS[0]} -ne 0 ]; then \
		echo "" ; \
		echo "❌ PKI_TOOL TESTS FAILED" ; \
		echo "❌ Please check suite_test_results/generate_pki.$(timestamp).log for details" ; \
		echo "" ; \
		exit 1 ; \
	fi
	@echo "✅ pki_tool tests passed"

test_browser:
	@echo "📋 Running end-to-end tests with Playwright"
	@rm -f suite_test_results/e2e_tests.log
	@bash -c "cd tests                     && pytest end-to-end/ -v --browser chromium" 2>&1 | ts | tee suite_test_results/e2e_tests.log | tee suite_test_results/e2e_tests.$(timestamp).log ; \
	if [ $${PIPESTATUS[0]} -ne 0 ]; then \
		echo "" ; \
		echo "❌ END-TO-END TESTS FAILED" ; \
		echo "❌ Please check suite_test_results/e2e_tests.$(timestamp).log for details" ; \
		echo "" ; \
		exit 1 ; \
	fi
	@echo "✅ End-to-end tests passed"

get_docker_logs:
	@echo "🔍 Pulling docker logs, excluding /health lines"
	@rm -f suite_test_results/docker.log
	@bash -c "cd tests                     && docker compose logs | grep -v '/health'" 2>&1 | tee suite_test_results/docker.log | tee suite_test_results/docker.$(timestamp).log

createmigrations: ## Create database migrations for all services
	@echo "🔄 Creating database migrations for all services"
	@echo "📋 Creating migration for certtransparency service"
	@bash -c 'cd services/certtransparency && TEMP_DB_CT="$$(mktemp)" && touch "$$TEMP_DB_CT" && export PYTHONPATH=. FLASK_SECRET_KEY="secret-key" SECRET_KEY="secret-key" ENVIRONMENT=development DEV_DATABASE_URI="sqlite:///$$TEMP_DB_CT" && flask --app app.app:create_app db upgrade && flask --app app.app:create_app db migrate -m 'Auto-generated migration' && rm -f "$$TEMP_DB_CT"'
	@echo "📋 Creating migration for frontend service"
	@bash -c 'cd services/frontend && TEMP_DB_FE="$$(mktemp)" && touch "$$TEMP_DB_FE" && export PYTHONPATH=. FERNET_ENCRYPTION_KEY="enc-key" FLASK_SECRET_KEY="secret-key" ENVIRONMENT=development DEV_DATABASE_URI="sqlite:///$$TEMP_DB_FE" && flask --app app.app:create_app db upgrade && flask --app app.app:create_app db migrate -m 'Auto-generated migration' && rm -f "$$TEMP_DB_FE"'
	@echo "✅ Done creating migrations"

set_oidc_url: ## Set OIDC_DISCOVERY_URL for local tiny-oidc via nip.io
	@bash -c '\
		LOCAL_IP=$$(ip route get 1.1.1.1 2>/dev/null | awk "/src/ {for(i=1;i<=NF;i++) if (\$$i==\"src\") print \$$(i+1)}") ; \
		if [ -z "$$LOCAL_IP" ]; then \
			echo "❌ Could not detect local IP address from default route" ; \
			exit 1 ; \
		fi ; \
		echo "export OIDC_DISCOVERY_URL=http://tiny-oidc.$${LOCAL_IP}.nip.io:8000/.well-known/openid-configuration" > tests/.env.tinyoidc ; \
		echo "🔑 Written to tests/.env.tinyoidc:" ; \
		cat tests/.env.tinyoidc ; \
	'

cacheclear: ## Clear Python cache files
	@echo "🧹 Removing Cache Files"
	@bash -c "find . -type d -name __pycache__ -exec rm -Rf '{}' +"
	@bash -c "find . -type d -name .pytest_cache -exec rm -Rf '{}' +"