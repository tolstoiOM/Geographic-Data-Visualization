# ./backend/fastapi_app/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Abhängigkeiten kopieren
COPY requirements.txt .

# Pakete installieren
RUN pip install --no-cache-dir -r requirements.txt

# App kopieren
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
