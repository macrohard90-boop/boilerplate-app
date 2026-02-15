#!/usr/bin/env bash
# Interactive setup script for the Boilerplate Application.
# Usage: bash scripts/setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_TEMPLATE="$PROJECT_DIR/.env.template"
ENV_FILE="$PROJECT_DIR/.env"

echo "========================================"
echo "  Boilerplate App — Setup"
echo "========================================"
echo ""

# --- Prompts ---
read -rp "Application name [BoilerplateApp]: " APP_NAME
APP_NAME="${APP_NAME:-BoilerplateApp}"

read -rp "Domain (e.g., example.com) [localhost]: " DOMAIN
DOMAIN="${DOMAIN:-localhost}"

echo ""
echo "Template options:"
echo "  1) ecommerce  — Products, cart, orders, payments"
echo "  2) saas       — Plans, subscriptions, usage tracking"
read -rp "Choose template [1]: " TEMPLATE_CHOICE
case "${TEMPLATE_CHOICE:-1}" in
    2) APP_TEMPLATE="saas" ;;
    *) APP_TEMPLATE="ecommerce" ;;
esac

read -rp "PostgreSQL password [auto-generate]: " DB_PASSWORD
if [ -z "$DB_PASSWORD" ]; then
    DB_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    echo "  Generated: $DB_PASSWORD"
fi

# Generate secrets
JWT_SECRET=$(openssl rand -base64 48 | tr -d '/+=' | head -c 64)
SECRET_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 48)

echo ""
echo "--- Configuration ---"
echo "  App name:  $APP_NAME"
echo "  Domain:    $DOMAIN"
echo "  Template:  $APP_TEMPLATE"
echo ""

# --- Create .env ---
if [ -f "$ENV_FILE" ]; then
    read -rp ".env already exists. Overwrite? [y/N]: " OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
        echo "Keeping existing .env"
    else
        cp "$ENV_TEMPLATE" "$ENV_FILE"
    fi
else
    cp "$ENV_TEMPLATE" "$ENV_FILE"
fi

# Apply values to .env
sed -i "s|^APP_NAME=.*|APP_NAME=$APP_NAME|" "$ENV_FILE"
sed -i "s|^DOMAIN=.*|DOMAIN=$DOMAIN|" "$ENV_FILE"
sed -i "s|^APP_TEMPLATE=.*|APP_TEMPLATE=$APP_TEMPLATE|" "$ENV_FILE"
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASSWORD|" "$ENV_FILE"
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" "$ENV_FILE"
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" "$ENV_FILE"

if [ "$DOMAIN" != "localhost" ]; then
    sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=https://$DOMAIN|" "$ENV_FILE"
    sed -i "s|^BACKEND_URL=.*|BACKEND_URL=https://$DOMAIN|" "$ENV_FILE"
fi

echo ""
echo ".env created at $ENV_FILE"

# --- Build & Start ---
read -rp "Build and start Docker containers now? [Y/n]: " START_NOW
if [[ ! "${START_NOW:-Y}" =~ ^[Nn]$ ]]; then
    echo ""
    echo "Building Docker images..."
    docker compose -f "$PROJECT_DIR/docker-compose.yml" build

    echo ""
    echo "Starting containers..."
    docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d

    echo ""
    echo "Waiting for services to be healthy..."
    sleep 10

    # Health checks
    echo ""
    echo "--- Health Checks ---"
    if curl -sf http://localhost/api/health > /dev/null 2>&1; then
        echo "  API:      OK"
    else
        echo "  API:      WAITING (may take a moment to start)"
    fi

    if curl -sf http://localhost/ > /dev/null 2>&1; then
        echo "  Frontend: OK"
    else
        echo "  Frontend: WAITING (may take a moment to start)"
    fi

    echo ""
    echo "Services are starting. Run 'docker compose ps' to check status."
fi

echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Review and update .env with your Stripe, OAuth, and SMTP credentials"
echo "  2. Run 'docker compose up -d' if you didn't start containers above"
echo "  3. Visit http://${DOMAIN} to see the app"
echo "  4. API docs available at http://${DOMAIN}/api/docs"
echo ""
