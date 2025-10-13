FROM node:20

WORKDIR /app

# Nur package-Dateien kopieren, um npm install zu cachen
COPY package*.json ./

# Install all dependencies including devDependencies
RUN npm install

# Keine COPY . .  ← das übernimmt das Volume im Compose
EXPOSE 5173

# Wichtige Umgebungsvariablen
ENV VITE_HOST=0.0.0.0
ENV CHOKIDAR_USEPOLLING=true
ENV WATCHPACK_POLLING=true

# Startbefehl
CMD ["npm", "run", "dev"]
