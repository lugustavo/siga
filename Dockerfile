FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

# Xvfb + noVNC: o browser corre "com ecra" dentro do contentor para que possas resolver
# o desafio de imagens do reCAPTCHA remotamente (http://<host>:6080/vnc.html).
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py slots.py notify.py pin.py bot.py watch.py search_config.yaml entrypoint.sh ./
RUN chmod +x entrypoint.sh && mkdir -p /app/data

ENV DATA_DIR=/app/data CONFIG_DIR=/app/config DISPLAY=:99
EXPOSE 6080

CMD ["./entrypoint.sh"]
