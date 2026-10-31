FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3 py3-pip nginx && python3 -m venv /venv && /venv/bin/pip install --no-cache-dir flask python-dotenv gunicorn
COPY nginx.conf /etc/nginx/http.d/default.conf
COPY run.sh /run.sh
COPY addon_bootstrap.py /app/addon_bootstrap.py
COPY extract.py importer.py barcode_stock.py product_images.py web.py /app/
WORKDIR /app
RUN chmod 755 /run.sh && mkdir -p /data/receipts
CMD ["/run.sh"]
