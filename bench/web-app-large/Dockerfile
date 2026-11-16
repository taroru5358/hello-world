# ビルド用ステージ: 依存インストール → Vite ビルド
FROM node:24-slim AS build
WORKDIR /app
# lockfile だけ先にコピーして npm ci のレイヤーをソース変更から切り離す（BuildKit キャッシュが効く形）
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# 配信用ステージ: 静的ファイルだけを nginx で配る
FROM nginx:1.31.8-alpine
COPY --from=build /app/dist /usr/share/nginx/html
