FROM node:20-alpine as build

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm install

# Copy application files
COPY . .

# Set build argument for API URL
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL

# Build-time variables (Railway passes service variables whose names
# match an ARG into Dockerfile builds). VITE_* values are baked into
# the JS bundle at build time, so they must be declared here; a plain
# runtime ENV would be too late. The anon key is publishable by design
# (the browser needs it); never put a secret key in an ARG.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

# Build the frontend application
RUN npm run build

# Use Nginx to serve the built application
FROM nginx:alpine

# Copy built assets from the previous stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx. Railway injects $PORT at runtime and routes traffic to
# it, so rewrite the listen line at container start (exec-form CMD
# cannot expand $PORT). Locally (docker compose) PORT is unset and
# 80 is kept. The rewrite is idempotent: a restarted container no
# longer contains the literal "listen 80;" line.
CMD ["sh", "-c", "sed -i \"s/listen 80;/listen ${PORT:-80};/\" /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
