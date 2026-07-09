FROM node:20-slim

WORKDIR /app

# Copy package files and install dependencies first for layer caching
COPY package.json package-lock.json ./
RUN npm install

# Copy the rest of the frontend application code
COPY . .

EXPOSE 5173

# Start command (host 0.0.0.0 is required for Vite inside Docker)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
