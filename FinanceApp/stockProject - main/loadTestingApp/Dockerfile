FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y dos2unix
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
COPY start_locust.sh /app/start_locust.sh
RUN dos2unix /app/start_locust.sh && chmod +x /app/start_locust.sh
CMD ["/app/start_locust.sh"]
