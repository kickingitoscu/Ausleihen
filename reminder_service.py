import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import certifi
from dotenv import load_dotenv
import db

# Load environment variables from .env
load_dotenv()

# --- GMAIL SMTP CONFIGURATION VIA .ENV ---
MOCK_MODE = False  # Disabled for production/final stages
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
SCHOOL_ADMIN_EMAIL = os.getenv("SCHOOL_ADMIN_EMAIL", SENDER_EMAIL)


def send_email_notification(to_email: str, subject: str, body: str, cc_email: str = None) -> bool:
    """Sends an email via Gmail SMTP bypassing local firewall SSL interception with optional CC."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("❌ Missing SENDER_EMAIL or SENDER_PASSWORD in .env file.")
        return False

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject

    # Build recipient list for SMTP dispatch
    recipients = [to_email]
    if cc_email:
        msg['Cc'] = cc_email
        recipients.append(cc_email)

    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        # Bypass LANCOM LCOS FX firewall SSL interception
        context = ssl._create_unverified_context()

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())

        cc_info = f" (CC: {cc_email})" if cc_email else ""
        print(f"✅ Email successfully sent to {to_email}{cc_info}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Gmail Authentication Failed: Check your 16-character App Password. Details: {e}")
    except smtplib.SMTPConnectError as e:
        print(f"❌ Connection Failed: Could not reach {SMTP_SERVER}:{SMTP_PORT}. Details: {e}")
    except Exception as e:
        print(f"❌ Email error: {e}")

    return False

def check_upcoming_reminders():
    """Checks for items due within the next 3 hours (runs once per item)."""
    due_items = db.get_due_bookings()

    if not due_items:
        print("✅ [3-Hour Check] No upcoming items due in the next 3 hours.")
        return

    print(f"⚠️ [3-Hour Check] Found {len(due_items)} item(s) requiring return reminders!")

    for booking in due_items:
        booking_id = booking["booking_id"]
        item_title = booking["item_title"]
        serial = booking["serial_number"]
        renter_name = booking["user_name"]
        renter_email = booking["user_email"]
        end_time = booking["end_time"]

        subject = f"⏰ Erinnerung zur Rückgabe: {item_title} ({serial}) bald fällig"
        body_user = (
            f"Guten Tag {renter_name},\n\n"
            f"Dies ist eine automatische Erinnerung daran, dass Ihre Mietrückgabe bald fällig ist:\n"
            f"  • Artikel: {item_title}\n"
            f"  • Inventarnummer: {serial}\n"
            f"  • Zur rechten Zeit: {end_time}\n\n"
            f"Bitte geben Sie diesen Artikel rechtzeitig zurück. Falls niemand im Büro ist, gehen Sie bitte zu Technische Leitung."
        )

        if send_email_notification(renter_email, subject, body_user, cc_email="hausmeister@waldorfschule-nuernberg.de"):
            db.mark_reminder_sent(booking_id)


def check_overdue_rentals():
    """Checks for past-due items and alerts both the renter and library staff."""
    overdue_items = db.get_overdue_bookings()

    if not overdue_items:
        print("✅ [Überfälligkeitsprüfung] Keine überfälligen Artikel, für die eine E-Mail-Benachrichtigung aussteht.")
        return

    print(f"🚨 [Überfälligkeitsprüfung] Gefunden {len(overdue_items)} überfällige(r) Artikel!")

    for booking in overdue_items:
        booking_id = booking["booking_id"]
        item_title = booking["item_title"]
        serial = booking["serial_number"]
        renter_name = booking["user_name"]
        renter_email = booking["user_email"]
        end_time = booking["end_time"]

        # 1. Email to Renter
        subject_user = f"🚨 Mahnung: {item_title} ({serial})"
        body_user = (
            f"Guten Tag {renter_name},\n\n"
            f"Unsere Unterlagen zeigen, dass der folgende Artikel überfällig ist:\n"
            f"  • Artikel: {item_title}\n"
            f"  • Inventarnummer: {serial}\n"
            f"  • War fällig am: {end_time}\n\n"
            f"Bitte geben Sie diesen Artikel umgehend zurück."
        )
        send_user = send_email_notification(renter_email, subject_user, body_user, cc_email="hausmeister@waldorfschule-nuernberg.de")

        # 2. Email to Library Staff
        subject_admin = f"🚨 MITTEILUNG AN DAS PERSONAL: Überfällige Ausrüstung - {renter_name}"
        body_admin = (
            f"Mahnung wegen überfälliger Miete\n\n"
            f"Der folgende Artikel hat seine Rückgabefrist überschritten und ist noch ausgeliehen:\n"
            f"  • Artikel: {item_title} (`{serial}`)\n"
            f"  • Mieter*in: {renter_name} ({renter_email})\n"
            f"  • Ursprünglicher Fälligkeitstermin: {end_time}\n"
        )
        send_admin = send_email_notification(SCHOOL_ADMIN_EMAIL, subject_admin, body_admin, cc_email="hausmeister@waldorfschule-nuernberg.de")

        if send_user and send_admin:
            db.mark_overdue_email_sent(booking_id)


def run_automated_check():
    """Runs both checks during scheduled cron executions."""
    check_upcoming_reminders()
    check_overdue_rentals()


check_and_send_reminders = run_automated_check

if __name__ == "__main__":
    run_automated_check()