import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv("e:/HackQubit/.env")

smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
smtp_port = int(os.getenv("SMTP_PORT", 587))
smtp_user = os.getenv("SMTP_USERNAME")
smtp_pass = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
to_email = os.getenv("DEVOPS_EMAIL", "omvishesh123@gmail.com")
from_email = os.getenv("SMTP_FROM", smtp_user)

print("Attempting SMTP connection...")
print(f"Host: {smtp_host}:{smtp_port}")
print(f"From: {from_email}")
print(f"To: {to_email}")

msg = MIMEMultipart("alternative")
msg["Subject"] = "🚨 [TEST] HackQubit Incident Alert System - SMTP Connected!"
msg["From"] = from_email
msg["To"] = to_email

html_content = """
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; border: 1px solid #e1e4e8; border-radius: 8px; max-width: 550px; margin: 0 auto;">
  <h2 style="color: #28a745; margin-top: 0;">✅ SMTP Email Dispatch Active!</h2>
  <p>Hello DevOps Engineer,</p>
  <p>This confirms that <strong>HackQubit 2.0 Multi-Agent Incident Response System</strong> has successfully authenticated with Gmail SMTP.</p>
  <div style="background: #f6f8fa; padding: 12px 16px; border-radius: 6px; margin: 16px 0; font-size: 14px;">
    <strong>Sender:</strong> """ + str(from_email) + """<br>
    <strong>Recipient:</strong> """ + str(to_email) + """<br>
    <strong>Status:</strong> Ready for real-time incident approvals
  </div>
  <p style="color: #586069; font-size: 13px;">You will receive high-priority alerts with Approve & Reject buttons whenever backend anomalies are detected.</p>
</div>
"""

msg.attach(MIMEText(html_content, "html"))

try:
    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, to_email, msg.as_string())
    print("SUCCESS: Test email delivered successfully!")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")

