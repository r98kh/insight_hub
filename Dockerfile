FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1  

WORKDIR /app

RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./src/ /app/

RUN mkdir -p /app/logs /app/media /app/static

RUN chmod +x /app/manage.py

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
