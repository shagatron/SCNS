FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package.json
COPY tests/e2e/package.json tests/e2e/package.json
RUN --mount=type=secret,id=ca_bundle \
    if [ -f /run/secrets/ca_bundle ]; then \
      NODE_EXTRA_CA_CERTS=/run/secrets/ca_bundle npm ci; \
    else npm ci; fi
COPY frontend frontend
COPY tests/e2e tests/e2e
# Invented unit-test JSON is needed by TypeScript only in this build stage.
COPY data/demo/indoor/synthetic-ground.json data/demo/indoor/synthetic-ground.json
RUN npm run build --workspace frontend
FROM nginx:1.28-alpine
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
