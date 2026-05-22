import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


GMAIL_SENDER = os.getenv("GMAIL_SENDER", "michelemasi.legal@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT = "michelemasi.legal@gmail.com"


def _send(subject: str, body_html: str) -> None:
    if not GMAIL_APP_PASSWORD:
        print(f"[email] GMAIL_APP_PASSWORD non configurata — email non inviata: {subject}")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_SENDER, RECIPIENT, msg.as_string())


def notify_new_upload(
    filename: str,
    user_name: str,
    user_email: str,
    valido: bool | None,
    sintesi: str,
    upload_id: str,
) -> None:
    esito = "✅ VALIDO" if valido is True else ("❌ NON VALIDO" if valido is False else "⚠️ INCERTO")
    subject = f"Nuovo patto caricato — {esito} — {filename[:40]}"
    body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#1a1714;background:#f3efe7;padding:24px">
      <h2 style="color:#1e3a6b">Nuovo patto caricato su pattodinconcorrenza.it</h2>
      <table style="border-collapse:collapse;width:100%;max-width:560px">
        <tr><td style="padding:8px;font-weight:bold">Data/Ora</td><td style="padding:8px">{datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr>
        <tr><td style="padding:8px;font-weight:bold">File</td><td style="padding:8px">{filename}</td></tr>
        <tr><td style="padding:8px;font-weight:bold">Utente</td><td style="padding:8px">{user_name or '—'}</td></tr>
        <tr><td style="padding:8px;font-weight:bold">Email</td><td style="padding:8px">{user_email or '—'}</td></tr>
        <tr><td style="padding:8px;font-weight:bold">Esito AI</td><td style="padding:8px"><strong>{esito}</strong></td></tr>
      </table>
      <h3 style="color:#1e3a6b;margin-top:24px">Sintesi analisi</h3>
      <p style="background:#fff;padding:16px;border-left:4px solid #1e3a6b;border-radius:4px">{sintesi}</p>
      <p style="margin-top:24px;font-size:13px;color:#5a544c">
        Upload ID: {upload_id}<br>
        Per visualizzare il documento accedi al <a href="https://pattodinconcorrenza.it/admin.html">pannello admin</a>.
      </p>
    </body></html>
    """
    _send(subject, body)


def notify_contact(name: str, email: str, tipo: str, messaggio: str) -> None:
    subject = f"Richiesta di contatto — {tipo} — {name}"
    body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#1a1714;background:#f3efe7;padding:24px">
      <h2 style="color:#1e3a6b">Nuova richiesta di contatto da pattodinconcorrenza.it</h2>
      <table style="border-collapse:collapse;width:100%;max-width:560px">
        <tr><td style="padding:8px;font-weight:bold">Nome</td><td style="padding:8px">{name}</td></tr>
        <tr><td style="padding:8px;font-weight:bold">Email</td><td style="padding:8px">{email}</td></tr>
        <tr><td style="padding:8px;font-weight:bold">Tipo</td><td style="padding:8px">{tipo}</td></tr>
      </table>
      <h3 style="color:#1e3a6b;margin-top:24px">Messaggio</h3>
      <p style="background:#fff;padding:16px;border-left:4px solid #c8262b;border-radius:4px;white-space:pre-wrap">{messaggio}</p>
    </body></html>
    """
    _send(subject, body)
