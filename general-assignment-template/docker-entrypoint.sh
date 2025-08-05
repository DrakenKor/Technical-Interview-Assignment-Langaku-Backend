#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
  sleep 1
done

echo "Database is ready!"

# Run migrations
echo "Running migrations..."
uv run manage.py migrate

# Start the server
echo "Starting Django server..."
exec "$@"
