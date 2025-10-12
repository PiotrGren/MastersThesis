#!/bin/bash
sleep 60
USERS=${LOCUST_USERS:-30}
SPAWN_RATE=${LOCUST_SPAWN_RATE:-1}
TIME=${LOCUST_TIME:-5m}
LOCUST_CLASS=${LOCUST_CLASS:-WebsiteActiveUser}
locust -f /app/locustfile.py --headless -u $USERS -r $SPAWN_RATE --host=http://web:8080 -t $TIME $LOCUST_CLASS