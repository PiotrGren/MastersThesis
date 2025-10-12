import time
import docker
import psycopg2
import threading
from datetime import datetime
import os

time.sleep(30)
# Konfiguracja połączenia z bazą danych
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port="5432"
)
cursor = conn.cursor()

# Połączenie z Dockerem
client = docker.from_env()

def calculateCpuPercentage(stats):
    cpuDelta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
    systemDelta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
    if systemDelta > 0.0 and cpuDelta > 0.0:
        cpuPercentage = (cpuDelta / systemDelta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
    else:
        cpuPercentage = 0.0
    return cpuPercentage

def logContainerUsage(container):    
    while True:
        timestamp = datetime.now()
        stats = container.stats(stream=False)
        cpuPercentage = calculateCpuPercentage(stats)
        memoryUsage = stats['memory_stats']['usage'] / (1024 * 1024)
        sqlInsert = """
        INSERT INTO "stockApp_cpu" (timestamp, "cpuUsage", "memoryUsage", "contenerId")
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sqlInsert, (timestamp, cpuPercentage, memoryUsage, container.name))
        conn.commit()
        time.sleep(2)

def logResourceUsage():
    threads = []
    for container in client.containers.list():
        thread = threading.Thread(target=logContainerUsage, args=(container,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    logResourceUsage()
