#!/bin/bash

# Ensure the script stops on any error
set -e

# Sprawdzenie, czy przekazano argument nazwy pliku (parametr)
if [ "$#" -eq 1 ]; then
  output_file="logdatabase_test$1.sql"
else
  output_file="logdatabase_dump.sql"
fi

# Pull and start only the logdatabase service
echo "Starting the logdatabase service using Docker Compose..."
docker-compose -f docker-compose.generated.yml up -d db_test
sleep 10
# Wait for the logdatabase to be healthy
echo "Waiting for the logdatabase to be healthy..."
docker-compose -f docker-compose.generated.yml ps db_test

# Find the container ID or name of the logdatabase service
container_id=$(docker ps --filter "name=db_test" --format "{{.ID}}")

# Check if the container is running
if [ -z "$container_id" ]; then
  echo "Error: logdatabase container is not running."
  exit 1
fi

# Dump the database to a SQL file with a dynamic name
echo "Dumping the logdatabase to a SQL file: $output_file"
docker exec -t "$container_id" pg_dump -U postgres -d test_stock -t '\"stockApp_cpu\"' -t '\"stockApp_tradelog\"' -t '\"stockApp_trafficlog\"' -t '\"stockApp_marketlog\"' > "$output_file"

# Check if the dump was successful
if [ $? -eq 0 ]; then
  echo "Database dump successful! The SQL file is saved as $output_file."
else
  echo "Error: Failed to dump the database."
  exit 1
fi

echo "Logdatabase service and dump process completed."