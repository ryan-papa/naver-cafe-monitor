FROM node:22-slim AS build

WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
ARG PUBLIC_API_URL=/naver-cafe-monitoring
ENV PUBLIC_API_URL=${PUBLIC_API_URL}
RUN npm run build && npm prune --omit=dev

FROM node:22-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends wget \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --home /app --shell /usr/sbin/nologin app \
    && mkdir -p /app \
    && chown -R app:app /app

WORKDIR /app
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=4321

COPY --from=build --chown=app:app /app/dist ./dist
COPY --from=build --chown=app:app /app/package.json ./package.json
COPY --from=build --chown=app:app /app/node_modules ./node_modules

USER app:app
EXPOSE 4321
CMD ["node", "dist/server/entry.mjs"]
