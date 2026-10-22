"""Notificaciones: Telegram y email (si hay credenciales en variables de entorno).

Sin credenciales configuradas, la función registra en el log y devuelve False
(dashboard siempre disponible como canal mínimo).
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def telegram(text: str) -> bool:
    """Envía por Telegram con token/chat de env; False si falta conf. o falla."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        logger.info("Telegram sin configurar; el reporte queda en dashboard")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        import httpx  # noqa: PLC0415

        resp = httpx.post(url, json={"chat_id": chat, "text": text}, timeout=30)
        if resp.status_code >= 400:
            logger.error("Telegram respondió %s", resp.status_code)
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram falló: %s", exc)
        return False


def email(text: str, subject: str = "PickMaster — reporte") -> bool:
    """Envía con SMTP (SSL 465). Necesita PICKMASTER_SMTP_* en env."""
    host = settings.smtp_host if hasattr(settings, "smtp_host") else ""
    if not host:
        logger.info("SMTP sin configurar; el reporte queda en dashboard")
        return False
    to = os.environ.get("PICKMASTER_SMTP_TO", "")
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = "pickmaster@notif.local"
    msg["To"] = to or msg["From"]
    try:
        with smtplib.SMTP_SSL(
            host, int(getattr(settings, "smtp_port", 465))
        ) as server:
            login = os.environ.get("PICKMASTER_SMTP_USER", "")
            password = os.environ.get("PICKMASTER_SMTP_TOKEN", "")
            if login and password:
                server.login(login, password)
            server.sendmail(msg["From"], [msg["To"]], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("SMTP falló: %s", exc)
        return False


def notify(text: str, channel: str = "dashboard") -> bool:
    """Canal pedido, o desplegándose al dashboard + extras si está disponible."""
    sent = False
    if channel in {"telegram", "all"}:
        sent = telegram(text) or sent
    if channel in {"email", "all"}:
        sent = email(text) or sent
    if not sent:
        logger.info("Notificación (canal=%s): %s", channel, text.splitlines()[0])
    return sent
