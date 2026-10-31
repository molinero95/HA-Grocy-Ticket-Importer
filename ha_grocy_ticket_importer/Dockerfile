FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3 py3-pip nginx && python3 -m venv /venv && /venv/bin/pip install --no-cache-dir flask python-dotenv gunicorn websocket-client
COPY nginx.conf /etc/nginx/http.d/default.conf
COPY run.sh /run.sh
COPY addon_bootstrap.py /app/addon_bootstrap.py
COPY config.yaml /app/addon_config.yaml
COPY extract.py importer.py barcode_stock.py product_images.py web.py shopping_sync.py shopping_sync_adapters.py shopping_sync_runtime.py shopping_sync_worker.py shopping_sync_events.py /app/
WORKDIR /app
RUN chmod 755 /run.sh && mkdir -p /data/receipts
CMD ["/run.sh"]
