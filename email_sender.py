"""
Sends the wildlife sighting bulletin via Gmail with all media files attached.
Uses Python's built-in smtplib — no extra packages needed.

Gmail setup (one-time):
  1. Enable 2-Step Verification on your Google account
  2. Go to myaccount.google.com → Security → App Passwords
  3. Create an App Password (select "Mail" + "Other")
  4. Use that 16-character password as EMAIL_APP_PASSWORD
"""

import logging
import mimetypes
import os
import smtplib
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send(
    from_email: str,
    app_password: str,
    to_email: str,
    bulletin: str,
    media_paths: list[str],
) -> None:
    date_str = datetime.now(tz=timezone.utc).strftime("%d %b %Y")
    subject = f"🌿 Wildlife Sighting Update — {date_str}"

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    # Plain-text body
    msg.attach(MIMEText(bulletin, "plain", "utf-8"))

    # Attach each media file
    attached = 0
    for path in media_paths:
        if not os.path.exists(path):
            continue
        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            mime_type = "application/octet-stream"
        main_type, sub_type = mime_type.split("/", 1)
        with open(path, "rb") as f:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=Path(path).name,
        )
        msg.attach(part)
        attached += 1
        logger.debug("Attached: %s", Path(path).name)

    logger.info("Sending email with %d attachment(s) to %s…", attached, to_email)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(from_email, app_password)
        smtp.sendmail(from_email, to_email, msg.as_bytes())

    logger.info("Email sent — subject: %s", subject)
