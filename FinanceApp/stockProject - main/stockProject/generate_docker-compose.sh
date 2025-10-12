#!/bin/bash

# Sprawdzenie, czy przekazano prawidłową liczbę parametrów
if [ "$#" -ne 7 ]; then
    echo "Użycie: $0 <number_of_users> <users_spawn_rate> <test_time> <users clasess> <transation_time> <traffic_time_request> <number_of_trade_container>"
    exit 1
fi

LOCUST_USERS=$1
LOCUST_SPAWN_RATE=$2
LOCUST_TIME=$3
LOCUST_CLASS=$4
TRANSACTION_TIME=$5
TIME_BETWEEN_REQUESTS=$6
NUM_TRADE=$7

cat <<EOL > docker-compose.generated.yml
services:
  db:
    command: -c 'max_connections=2000'
    image: postgres:14
    environment:
      POSTGRES_DB: stock
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "6543:5432"
    networks:
      - gielda_network
  redis:
    image: redis:latest
    networks:
      - gielda_network
    ports:
      - "6379:6379"

  db_test:
    image: postgres:14
    command: -c 'max_connections=2000'
    networks:
      - gielda_network
    environment:
      POSTGRES_DB: test_stock
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_test_data:/var/lib/postgresql/data
    ports:
      - "6544:5432"

  web:
    build: .
    command: 
      sh -c 
      "python manage.py makemigrations &&
      python manage.py migrate &&
      python manage.py migrate --database=test &&
      python manage.py collectstatic --noinput &&
      gunicorn stockProject.wsgi:application --bind 0.0.0.0:8080"
    volumes:
      - .:/app
    ports:
      - "8080:8080"
    depends_on:
      - db
      - redis
      - db_test
    environment:
      ENV_ID: "web"
      TRANSACTION_TIME: "$TRANSACTION_TIME"
    networks:
      - gielda_network
  
  celery_worker_schedule_transactions:
    build: .
    command: 
      celery -A stockProject worker -l info -Q transactions -P gevent     
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
      - db_test
    networks:
      - gielda_network
    environment:
      ENV_ID: "celery_worker_schedule_transactions"
      TRANSACTION_TIME: "$TRANSACTION_TIME"

  celery_worker_execute_transactions:
    build: .
    command:
      celery -A stockProject worker -l info -P gevent
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
      - db_test
    networks:
      - gielda_network
    environment:
      ENV_ID: "celery_worker_execute_transactions"
      TRANSACTION_TIME: "$TRANSACTION_TIME"
    deploy:
      replicas: $NUM_TRADE #  worker dedykowany do przetwarzania transakcji

  monitor:
    build: ./monitor
    environment:
      DB_HOST: db_test
      DB_NAME: test_stock
      DB_USER: postgres
      DB_PASSWORD: postgres
    volumes:
      - ./monitor:/app
      - /var/run/docker.sock:/var/run/docker.sock  # Udostępnienie Docker sock
    depends_on:
      - db
      - db_test
    networks:
      - gielda_network
    command: ["python", "/app/monitor.py"]

  celery_worker_balance_updates:
    build: .
    command:      
      celery -A stockProject worker -l info -Q balance_updates -P gevent
    volumes:
      - .:/app
    networks:
      - gielda_network
    environment:
      ENV_ID: "celery_worker_balance_updates"
      TRANSACTION_TIME: "$TRANSACTION_TIME"
    depends_on:
      - db
      - redis
      - db_test

  celery_worker_stock_rates:
    build: .
    command:
      celery -A stockProject worker -l info -Q stock_rates -P gevent
    volumes:
      - .:/app
    networks:
      - gielda_network
    environment:
      ENV_ID: "celery_worker_stock_rates"
      TRANSACTION_TIME: "$TRANSACTION_TIME"
    depends_on:
      - db
      - redis
      - db_test

  celery_worker_expire_offers:
    build: .
    command:      
      celery -A stockProject worker -l info -Q expire_offers -P gevent
    volumes:
      - .:/app
    networks:
      - gielda_network
    environment:
      ENV_ID: "celery_worker_expire_offers"
      TRANSACTION_TIME: "$TRANSACTION_TIME"
    depends_on:
      - db
      - redis
      - db_test

  celery_beat:
    build: .
    command:
      celery -A stockProject beat --loglevel=info
    volumes:
      - .:/app
    networks:
      - gielda_network
    environment:
      ENV_ID: "celery_beat"
      TRANSACTION_TIME: "$TRANSACTION_TIME"
    depends_on:
      - db
      - redis
      - db_test

  locust:
    build: ../loadTestingApp  # ścieżka do nowego projektu
    command: /app/start_locust.sh
    networks:
      - gielda_network
    environment:
      ENV_ID: "locust"
      LOCUST_USERS: $LOCUST_USERS
      LOCUST_SPAWN_RATE: $LOCUST_SPAWN_RATE
      LOCUST_TIME: $LOCUST_TIME
      LOCUST_CLASS: $LOCUST_CLASS
      TIME_BETWEEN_REQUESTS: $TIME_BETWEEN_REQUESTS
    depends_on:
      - web
      - db
      - db_test

volumes:
  postgres_data:
  postgres_test_data:
networks:
  gielda_network:
    driver: bridge
EOL

echo "Plik docker-compose.generated.yml został wygenerowany."

# Uruchomienie kontenerów za pomocą docker-compose
docker-compose -f docker-compose.generated.yml up -d

# Sprawdzenie, czy kontenery zostały poprawnie uruchomione
if [ $? -eq 0 ]; then
    echo "Kontenery zostały pomyślnie uruchomione."
else
    echo "Wystąpił błąd podczas uruchamiania kontenerów."
fi
