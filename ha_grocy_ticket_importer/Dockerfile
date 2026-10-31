FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install --global npm@11 && npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3 py3-pip nginx && python3 -m venv /venv && /venv/bin/pip install --no-cache-dir flask python-dotenv gunicorn websocket-client pillow
COPY --from=frontend-build /build/dist /app/frontend_dist
COPY api_*.py duplicate_candidates.py merge_audit.py stock_commands.py purchase_units.py /app/
COPY nginx.conf /etc/nginx/http.d/default.conf
COPY run.sh /run.sh
COPY addon_bootstrap.py /app/addon_bootstrap.py
COPY config.yaml /app/addon_config.yaml
COPY extract.py importer.py barcode_stock.py product_images.py web.py shopping_sync.py shopping_sync_adapters.py shopping_sync_runtime.py shopping_identity_sync.py shopping_identity_runtime.py shopping_sync_worker.py shopping_sync_events.py generic_catalog.py variant_catalog.py catalog_audit.py shopping_match_queue.py /app/
WORKDIR /app
RUN chmod 755 /run.sh && mkdir -p /data/receipts
CMD ["/run.sh"]
