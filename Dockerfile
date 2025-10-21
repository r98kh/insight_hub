FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1  

WORKDIR /app

# Install PostgreSQL client tools
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .

RUN pip install -r requirements.txt

COPY ./src/ /app/

CMD ["gunicorn", "src.wsgi:application", "--bind", "0.0.0.0:8000"]
