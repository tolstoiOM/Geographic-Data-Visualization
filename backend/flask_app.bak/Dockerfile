# Backup of original backend/flask_app/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Restliche App kopieren
COPY . .

# Port freigeben
EXPOSE 5000

# Flask starten
CMD ["python", "app.py"]
