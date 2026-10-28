#!/bin/sh
# Ecra virtual + noVNC (protegido por VNC_PASSWORD) + vigia.
set -e

Xvfb :99 -screen 0 1280x1000x24 -nolisten tcp >/dev/null 2>&1 &

if [ -n "$VNC_PASSWORD" ]; then
    x11vnc -storepasswd "$VNC_PASSWORD" /tmp/vncpass >/dev/null 2>&1
    x11vnc -display :99 -forever -shared -rfbauth /tmp/vncpass -rfbport 5900 -localhost -quiet &
    websockify --web /usr/share/novnc 6080 localhost:5900 &
    echo "noVNC ativo na porta 6080 (palavra-passe: VNC_PASSWORD, so os primeiros 8 caracteres contam)"
    echo "O ecra fica PRETO ate o bot abrir o browser (so durante uma verificacao ou marcacao)"
else
    echo "AVISO: VNC_PASSWORD vazio -> noVNC desligado; desafios de imagem do CAPTCHA nao poderao ser resolvidos"
fi

exec python watch.py
