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

test: test_setup test_certtransparency test_frontend test_signing test_get_openvpn_config test_pki_tool start_docker check_services_ready test_browser get_docker_logs

test_after_docker: test_setup test_certtransparency test_frontend test_signing test_get_openvpn_config test_pki_tool check_services_ready test_browser get_docker_logs

just_test_e2e: start_docker check_services_ready test_browser get_docker_logs

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
	@echo "➡️ Pushing images to the container registry..."
	@bash -x -c 'images=$$(docker compose -f tests/docker-compose.yml config | grep "image:" | awk "{print \$$2}" | sort -u | grep "openvpn-manager" | tr "\n" " ") ; for image in $$images ; do echo "Processing $$image" ; docker tag $$image $$(echo $$image | cut -d: -f1):$$(date +%Y%m%d-%H%M%S) ; docker push $$(echo $$image | cut -d: -f1):$$(date +%Y%m%d-%H%M%S) ; docker push $$image ; done'
	@echo "✅ Pushed"

rebuild_docker_and_push: rebuild_docker push_docker_images

check_services_ready:
	@echo "⏳ Running pre-flight service readiness tests..."
	@bash -c "cd tests && pytest pre-flight-tests/ -v" 2>&1 | tee suite_test_results/pre_flight.$(timestamp).log

# The following tests are all unit, functional and integration tests local to the services or tools themselves
test_certtransparency:
	@echo "📋 Checking certtransparency service"
	@bash -c "cd services/certtransparency && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/certtransparency.$(timestamp).log

test_frontend:
	@echo "📋 Checking frontend service"
	@bash -c "cd services/frontend         && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/frontend.$(timestamp).log

test_signing:
	@echo "📋 Checking signing service"
	@bash -c "cd services/signing          && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/signing.$(timestamp).log


test_get_openvpn_config:
	@echo "📋 Checking get_openvpn_config tool"
	@bash -c "cd tools/get_openvpn_config  && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/get_config.$(timestamp).log

test_pki_tool:
	@echo "📋 Checking pki_tool"
	@bash -c "cd tools/pki_tool            && PYTHONPATH=. TRACE=true pytest tests --cov" 2>&1 | ts | tee suite_test_results/generate_pki.$(timestamp).log

test_browser:
	@echo "📋 Running end-to-end tests with Playwright"
	@bash -c "cd tests                     && pytest end-to-end/ -v --browser chromium" 2>&1 | ts | tee suite_test_results/e2e_tests.$(timestamp).log

get_docker_logs:
	@echo "🔍 Pulling docker logs, excluding /health lines"
	@bash -c "cd tests                     && docker compose logs | grep -v '/health'" 2>&1 | tee suite_test_results/docker.$(timestamp).log

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