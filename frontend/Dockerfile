FROM node:20-alpine

WORKDIR /app

# Abhängigkeiten kopieren und installieren
COPY package*.json ./
RUN npm install

# App kopieren
COPY . .

# Port für Vue Dev Server
EXPOSE 5173

# Startbefehl
CMD ["npm", "run", "serve", "--", "--host", "0.0.0.0"]
