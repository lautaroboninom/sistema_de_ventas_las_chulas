import logging
import smtplib
import socket
import ssl

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail

logger = logging.getLogger("security.mail")


def _setting(name, default=""):
    try:
        return getattr(settings, name, default)
    except ImproperlyConfigured:
        return default


def _compact_reason(value, max_len=240):
    raw = str(value or "").strip().replace("\n", " ").replace("\r", " ")
    if len(raw) <= max_len:
        return raw
    return f"{raw[: max_len - 3]}..."


def _smtp_failure_payload(error_code, detail, hint, status=502):
    return {
        "ok": False,
        "sent": False,
        "status": int(status),
        "error_code": str(error_code or "smtp_error"),
        "detail": str(detail or "No se pudo enviar el correo."),
        "hint": str(hint or "").strip(),
    }


def _classify_smtp_exception(exc):
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return _smtp_failure_payload(
            "smtp_auth_failed",
            "No se pudo autenticar contra el servidor SMTP.",
            "Revisa usuario y clave SMTP en la configuracion.",
            status=502,
        )

    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return _smtp_failure_payload(
            "smtp_recipient_rejected",
            "El servidor SMTP rechazo el destinatario.",
            "Verifica que el email del usuario sea valido.",
            status=502,
        )

    if isinstance(exc, smtplib.SMTPSenderRefused):
        return _smtp_failure_payload(
            "smtp_sender_rejected",
            "El servidor SMTP rechazo el remitente configurado.",
            "Verifica DEFAULT_FROM_EMAIL y el remitente validado en Brevo.",
            status=502,
        )

    if isinstance(exc, smtplib.SMTPDataError):
        return _smtp_failure_payload(
            "smtp_data_rejected",
            "El proveedor SMTP rechazo el contenido del correo.",
            "Revisa autenticacion de dominio (DKIM/DMARC) y politicas del proveedor.",
            status=502,
        )

    if isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)):
        return _smtp_failure_payload(
            "smtp_connection_failed",
            "No se pudo conectar con el servidor SMTP.",
            "Verifica host, puerto y conectividad de red.",
            status=502,
        )

    if isinstance(exc, (socket.timeout, TimeoutError)):
        return _smtp_failure_payload(
            "smtp_timeout",
            "El servidor SMTP no respondio a tiempo.",
            "Reintenta en unos minutos y revisa conectividad.",
            status=504,
        )

    if isinstance(exc, socket.gaierror):
        return _smtp_failure_payload(
            "smtp_dns_failed",
            "No se pudo resolver el host SMTP.",
            "Verifica el valor de EMAIL_HOST.",
            status=502,
        )

    if isinstance(exc, ssl.SSLError):
        return _smtp_failure_payload(
            "smtp_tls_failed",
            "Fallo la negociacion TLS con el servidor SMTP.",
            "Verifica EMAIL_USE_TLS/EMAIL_USE_SSL y certificados.",
            status=502,
        )

    return _smtp_failure_payload(
        "smtp_send_failed",
        "Fallo el envio de correo por un error inesperado.",
        "Revisa logs del backend para mas detalle.",
        status=502,
    )


def send_mail_checked(subject, text_body, recipient_email, *, html_body=None, from_email=None):
    to_email = (recipient_email or "").strip()
    sender = (from_email or _setting("DEFAULT_FROM_EMAIL", "") or "").strip()
    backend_name = (_setting("EMAIL_BACKEND", "") or "").strip()

    if not to_email:
        return _smtp_failure_payload(
            "smtp_recipient_missing",
            "No se pudo enviar porque falta el destinatario.",
            "Carga un email valido en el usuario.",
            status=400,
        )

    if not sender:
        return _smtp_failure_payload(
            "smtp_sender_missing",
            "No se pudo enviar porque falta DEFAULT_FROM_EMAIL.",
            "Configura DEFAULT_FROM_EMAIL en el backend.",
            status=500,
        )

    try:
        delivered = int(
            send_mail(
                subject,
                text_body,
                sender,
                [to_email],
                html_message=html_body,
                fail_silently=False,
            )
            or 0
        )
    except Exception as exc:
        payload = _classify_smtp_exception(exc)
        reason = _compact_reason(exc)
        if reason:
            payload["reason"] = reason
        logger.warning(
            "mail_delivery_failed backend=%s to=%s code=%s reason=%s",
            backend_name,
            to_email,
            payload["error_code"],
            reason or payload["detail"],
        )
        return payload

    if delivered < 1:
        payload = _smtp_failure_payload(
            "smtp_not_confirmed",
            "El proveedor SMTP no confirmo el envio del correo.",
            "Revisa estado del proveedor y credenciales SMTP.",
            status=502,
        )
        logger.warning(
            "mail_delivery_unconfirmed backend=%s to=%s delivered=%s",
            backend_name,
            to_email,
            delivered,
        )
        return payload

    logger.info(
        "mail_delivery_sent backend=%s to=%s delivered=%s",
        backend_name,
        to_email,
        delivered,
    )
    return {
        "ok": True,
        "sent": True,
        "status": 200,
        "detail": "Mail enviado correctamente.",
        "delivered": delivered,
    }
