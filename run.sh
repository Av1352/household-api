#!/usr/bin/env bash
# One command to set up and run the Household API.
#   chmod +x run.sh && ./run.sh
set -e
cd "$(dirname "$0")"

# 1. Virtual environment
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2. Dependencies
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 3. Load .env if present
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# 4. Generate a token on first run if none exists
if [ -z "${APP_TOKEN:-}" ]; then
  APP_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  echo "APP_TOKEN=$APP_TOKEN" >> .env
  echo "Generated a new APP_TOKEN and saved it to .env"
fi
export APP_TOKEN
export DB_PATH="${DB_PATH:-household.db}"

echo "---------------------------------------------"
echo "Token   : $APP_TOKEN"
echo "Database: $DB_PATH"
echo "Running : http://0.0.0.0:8000   (docs at /docs)"
echo "---------------------------------------------"

exec uvicorn app:app --host 0.0.0.0 --port 8000
