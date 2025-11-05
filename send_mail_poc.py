import smtplib
import csv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import getpass
from pathlib import Path
import sys
import time

#=============================================
# User input
#=============================================

print("Email Mass Sender - Proof of Concept")
sender_email = input("Enter your email address: ")
app_password = getpass.getpass("Enter your 16-character App Password: ")

#=============================================
# Unified path for different OS
#=============================================

base_dir = Path(__file__).parent.resolve()
mail_dir = base_dir / "mailing_list"

csv_file = mail_dir / "emails.csv"
subject_file = mail_dir / "subject.txt"
body_file = mail_dir / "body.txt"

# Check that all required files exist
for file in [csv_file, subject_file, body_file]:
    if not file.exists():
        print(f"Missing required file: {file}")
        sys.exit(1)

#=============================================
# Load mailing list
#=============================================

recipients = []
with csv_file.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row.get("name", "").strip()
        email = row.get("email", "").strip()
        if email:
            recipients.append({"name": name, "email": email})

if not recipients:
    print("No recipients found in the mailing list!")
    sys.exit(1)

#=============================================
# Email content
#=============================================

with subject_file.open(encoding="utf-8") as f:
    subject = f.read().strip()

with body_file.open(encoding="utf-8") as f:
    body = f.read().strip()

#=============================================
# Send email
#=============================================

try:
    print(f"\nSending email to {len(recipients)} recipients. Please wait...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        for recipient in recipients:
            # Personalize body using {name} placeholder
            personalized_body = body.replace("{name}", recipient["name"] or "there")

            # Create new message for each recipient
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = recipient["email"]
            msg["Subject"] = subject
            msg.attach(MIMEText(personalized_body, "plain", "utf-8"))

            # Send email to individual recipient
            server.sendmail(sender_email, recipient["email"], msg.as_string())
            print(f"Sent to {recipient['name'] or recipient['email']}")
            time.sleep(1)  # Add small delay between emails

    print("\nAll emails sent successfully!")
except Exception as e:
    print(f"Something went wrong: {e}")
