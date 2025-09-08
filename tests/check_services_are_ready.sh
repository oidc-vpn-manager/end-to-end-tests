#!/bin/bash

set -e

fails=0

# Count running services
running_certtransparency=0
running_frontend=0
running_signing=0
running_tiny_oidc=0

for service in $(docker compose ps --services --filter "status=running")
do
    [ "$service" == "certtransparency" ] && running_certtransparency=1
    [ "$service" == "frontend" ] && running_frontend=1
    [ "$service" == "signing" ] && running_signing=1
    [ "$service" == "tiny-oidc" ] && running_tiny_oidc=1
done

if (( running_certtransparency + running_frontend + running_signing + running_tiny_oidc == 4 ))
then
    echo "✅ All services running"
else
    echo "⚠️ Not all services running:"
    [ "$running_certtransparency" -eq 0 ] && echo "  ❌ certtransparency"
    [ "$running_frontend" -eq 0 ] && echo "  ❌ frontend"
    [ "$running_signing" -eq 0 ] && echo "  ❌ signing"
    [ "$running_tiny_oidc" -eq 0 ] && echo "  ❌ tiny-oidc"
    exit 1
fi

# Test Flask CLI commands for the frontend service
# TODO: Add the same tests for all of the services (certtransparency, frontend, signing)
echo "✅ Testing Flask CLI availability..."
docker compose exec -T frontend flask --help > /dev/null
echo "   Frontend Flask CLI: OK"

echo "✅ Testing database migration status..."
docker compose exec -T frontend flask db current
echo "   Database migrations: OK"

echo "✅ Testing Flask routes..."
docker compose exec -T frontend flask routes | head -10
echo "   Flask routes: OK"

# Test service endpoints from host
echo "✅ Testing frontend service accessibility..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80/ || echo "")
if [ "$response" = "302" ] || [ "$response" = "200" ]
then
    echo "   Frontend service: OK (HTTP $response)"
else
    echo "   ⚠️  Frontend service: WARN (HTTP $response)"
    fails=$(( fails + 1 ))
fi

echo "✅ Testing certificate transparency service..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8800/health || echo "")
if [ "$response" = "200" ]
then
    echo "   Certificate Transparency: OK (HTTP $response)"
else
    echo "   ⚠️  Certificate Transparency: WARN (HTTP $response)"
    fails=$(( fails + 1 ))
fi


echo "✅ Testing tiny-oidc service..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "")
if [ "$response" = "200" ]
then
    echo "   Tiny OIDC: OK (HTTP $response)"
else
    echo "   ⚠️  Tiny OIDC: WARN (HTTP $response)"
    fails=$(( fails + 1 ))
fi

echo ""
echo "🔐 Testing Authentication Flow..."
echo "-----------------------------------"

echo "✅ Testing OIDC discovery endpoint..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/.well-known/openid-configuration || echo "")
if [ "$response" = "200" ]
then
    echo "   OIDC Discovery: OK (HTTP $response)"
else
    echo "   ⚠️  OIDC Discovery: WARN (HTTP $response)"
    fails=$(( fails + 1 ))
fi

echo "✅ Testing frontend auth redirect..."
auth_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80/auth/login || echo "")
if [ "$auth_response" = "200" ]
then
    echo "   Frontend auth page: OK (HTTP $auth_response)"
elif [ "$auth_response" = "302" ]
then
    echo "   Frontend auth page: OK (HTTP $auth_response)"
else
    echo "   ⚠️  Frontend auth page: WARN (HTTP $auth_response)"
    fails=$(( fails + 1 ))
fi

echo "✅ Testing database connectivity from frontend via Flask shell..."
# TODO: Add the same test for all of the services (certtransparency, frontend, signing)
db_test=$(docker compose exec -T frontend python3 -c "
import sys
sys.path.append('/usr/src/app')
try:
    from app.app import create_app
    app = create_app()
    with app.app_context():
        from app import db
        result = db.session.execute(db.text('SELECT 1')).scalar()
        if result == 1:
            print('DATABASE_OK')
        else:
            print('DATABASE_ERROR: Unexpected result')
except Exception as e:
    print(f'DATABASE_ERROR: {e}')
" 2>/dev/null)

if [[ "$db_test" == *"DATABASE_OK"* ]]
then
    echo "   Database connectivity: OK"
else
    echo "   ⚠️  Database connectivity: WARN"
    echo "   Details: $db_test"
    fails=$(( fails + 1 ))
fi

if [ "$fails" -gt 0 ]
then
    echo "$fails Failures."
    exit 1
fi