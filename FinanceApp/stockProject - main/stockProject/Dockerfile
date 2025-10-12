FROM python:3.10-slim

# Ustawienie zmiennej środowiskowej, aby zapobiec błędowi „Input is not a tty”
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y postgresql-client

COPY . /app/

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "stockProject.wsgi:application"]
