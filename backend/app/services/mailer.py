"""Outgoing email. Without SMTP_HOST configured, messages are logged instead
of sent, so local development needs no mail server. SMTP_HOST=sendmail hands
messages to the host's own mail program (/usr/sbin/sendmail), as on cPanel."""
from __future__ import annotations

import logging
import smtplib
import ssl
import subprocess  # noqa: S404 - fixed path, no shell, message on stdin
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger("app.mail")
SENDMAIL = "/usr/sbin/sendmail"


def send_mail(to: str, subject: str, body: str) -> None:
    """Never raises: a mail failure must not undo a booking or a submission."""
    s = get_settings()
    if not to:
        return
    if not s.smtp_host:
        log.info("Mail (SMTP not configured, not sent)", extra={"mail_to": to, "mail_subject": subject})
        return
    msg = EmailMessage()
    msg["From"] = s.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if s.smtp_host == "sendmail":
        # The host's own MTA (cPanel/Exim): no credentials needed; recipients come from the headers
        try:
            subprocess.run([SENDMAIL, "-t", "-i"], input=msg.as_bytes(), check=True, timeout=30,  # noqa: S603
                           capture_output=True)
            log.info("Mail sent", extra={"mail_to": to, "mail_subject": subject, "transport": "sendmail"})
        except Exception:
            log.exception("Mail delivery failed", extra={"mail_to": to, "mail_subject": subject, "transport": "sendmail"})
        return
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        log.info("Mail sent", extra={"mail_to": to, "mail_subject": subject})
    except Exception:
        log.exception("Mail delivery failed", extra={"mail_to": to, "mail_subject": subject})


def notify_hotel(subject: str, body: str) -> None:
    send_mail(get_settings().hotel_notify_email, subject, body)
