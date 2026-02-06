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
	@echo "🔍 Installing playwright"
	@playwright install chromium

start_docker:
	@echo "📦 Building and starting all services with docker-compose..."
	@cd tests && docker compose up -d --build

rebuild_docker: ## Clean rebuild all containers (removes volumes)
	@echo "🔄 Performing clean rebuild of all containers..."
	@cd tests && docker compose down --volumes
	@cd tests && docker compose up --build -d
	@echo "✅ Clean rebuild complete"

rebuild_docker_images:
	@echo "🔄 Performing rebuild of all images..."
	@cd tests && docker compose build
	@echo "✅ Clean rebuild complete"

push_docker_images: rebuild_docker_images
	@echo "📦 Tagging and pushing all repos"
	@bash -x -c '\
		set -e -u -E -o pipefail ; \
		source .fn.semver_bump.sh ; \
		export timestamp=$$(date +"%Y%m%d-%H%M%S") ; \
		export datestamp=$$(date +"%Y%m%d") ; \
		echo "🔍 Processing oidc-vpn-manager images with contexts..." ; \
		services=$$(docker compose -f tests/docker-compose.yml config --format json | jq -r ".services | to_entries[] | select(.value.image | contains(\"oidc-vpn-manager\")) | \"\(.value.image)|\(.value.build.context)\"" | sort -u) ; \
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
				echo "✅ Using existing tag: $$semver" ; \
			else \
				semver_bump "$$context" ; \
				export semver="$$(git tag --points-at HEAD | head -n1)" ; \
				echo "✅ Using new tag: $$semver" ; \
			fi ; \
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
		done ; \
		echo "" ; \
		echo "✅ Finished processing all images" \
	'
	@echo "✅ Pushed"

rebuild_docker_and_push: rebuild_docker push_docker_images

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

cacheclear: ## Clear Python cache files
	@echo "🧹 Removing Cache Files"
	@bash -c "find . -type d -name __pycache__ -exec rm -Rf '{}' +"
	@bash -c "find . -type d -name .pytest_cache -exec rm -Rf '{}' +"