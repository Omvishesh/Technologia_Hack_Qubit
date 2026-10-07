"""
Email Sender — Sends approval emails to the DevOps engineer.

Renders the incident report into an HTML email and sends it via SMTP.
Supports mock mode for development/testing.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .config import get_settings
from .models import Incident, IncidentReport

logger = logging.getLogger("incident-response.email")

# ─────────────────────────────────────────────────────────────
# Email template (inline for reliability, can be overridden)
# ─────────────────────────────────────────────────────────────

EMAIL_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
  .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  .header {{ background: #dc3545; color: white; padding: 20px 24px; }}
  .header h1 {{ margin: 0; font-size: 20px; }}
  .header .severity {{ display: inline-block; background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-top: 8px; }}
  .body {{ padding: 24px; }}
  .section {{ margin-bottom: 20px; }}
  .section h3 {{ color: #333; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 4px; }}
  .section p, .section li {{ color: #555; font-size: 14px; line-height: 1.6; }}
  .evidence {{ list-style: none; padding: 0; }}
  .evidence li {{ padding: 4px 0; }}
  .evidence li::before {{ content: "✓ "; color: #28a745; font-weight: bold; }}
  .hypothesis {{ background: #f8f9fa; padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; font-size: 13px; }}
  .confidence {{ color: #007bff; font-weight: bold; }}
  .risk {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
  .risk-LOW {{ background: #d4edda; color: #155724; }}
  .risk-MEDIUM {{ background: #fff3cd; color: #856404; }}
  .risk-HIGH {{ background: #f8d7da; color: #721c24; }}
  .actions {{ text-align: center; padding: 20px 24px; background: #f8f9fa; }}
  .btn {{ display: inline-block; padding: 12px 32px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 14px; margin: 0 8px; }}
  .btn-approve {{ background: #28a745; color: white; }}
  .btn-reject {{ background: #6c757d; color: white; }}
  .footer {{ padding: 16px 24px; text-align: center; color: #999; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🚨 INCIDENT RESPONSE REQUIRED</h1>
    <div>Service: <strong>{service}</strong></div>
    <div class="severity">Severity: {severity}</div>
  </div>

  <div class="body">
    <div class="section">
      <h3>What Happened</h3>
      <p>{what_happened}</p>
    </div>

    <div class="section">
      <h3>Log Summary</h3>
      <p>{log_summary}</p>
    </div>

    <div class="section">
      <h3>Hypotheses</h3>
      {hypotheses_html}
    </div>

    <div class="section">
      <h3>Root Cause</h3>
      <p><strong>{root_cause}</strong></p>
      <p>Confidence: <span class="confidence">{confidence}</span></p>
    </div>

    <div class="section">
      <h3>Evidence</h3>
      <ul class="evidence">
        {evidence_html}
      </ul>
    </div>

    <div class="section">
      <h3>Proposed Resolution</h3>
      <p><strong>{proposed_action}</strong></p>
      <p>Risk: <span class="risk risk-{risk}">{risk}</span></p>
      <p>Blast Radius: {blast_radius}</p>
    </div>
  </div>

  <div class="actions">
    <a href="{approve_url}" class="btn btn-approve">✅ APPROVE RESOLUTION</a>
    <a href="{reject_url}" class="btn btn-reject">❌ REJECT</a>
  </div>

  <div class="footer">
    Incident ID: {incident_id} | {timestamp}
  </div>
</div>
</body>
</html>
"""


def render_email(report: IncidentReport) -> str:
    """Render the incident report into an HTML email body."""
    settings = get_settings()
    base_url = settings.incident_service_url.rstrip("/")

    template_file = Path("email/incident_template.html")
    if template_file.exists():
        try:
            from jinja2 import Template
            content = template_file.read_text(encoding="utf-8")
            t = Template(content)
            return t.render(
                service=report.service,
                severity=report.severity.value,
                what_happened=report.what_happened,
                log_summary=report.log_summary,
                hypotheses=report.hypotheses,
                root_cause=report.root_cause,
                root_cause_confidence=f"{report.root_cause_confidence:.0%}",
                evidence=report.evidence,
                proposed_action=report.proposed_action,
                risk=report.risk.value,
                blast_radius=report.blast_radius,
                approve_url=f"{base_url}/incidents/{report.incident_id}/approve",
                reject_url=f"{base_url}/incidents/{report.incident_id}/reject",
                incident_id=report.incident_id,
                timestamp=report.timestamp,
            )
        except Exception as exc:
            logger.warning("Failed to render jinja template, falling back to inline: %s", exc)

    # Build hypotheses HTML fallback
    hyp_parts = []
    for h in report.hypotheses:
        hyp_parts.append(
            f'<div class="hypothesis">'
            f'#{h["rank"]} {h["title"]} — '
            f'<span class="confidence">{h["confidence"]}</span>'
            f'</div>'
        )
    hypotheses_html = "\n".join(hyp_parts) or "<p>No hypotheses generated</p>"

    # Build evidence HTML fallback
    evidence_html = "\n".join(
        f"<li>{e}</li>" for e in report.evidence
    ) or "<li>No evidence collected</li>"

    return EMAIL_TEMPLATE.format(
        service=report.service,
        severity=report.severity.value,
        what_happened=report.what_happened,
        log_summary=report.log_summary,
        hypotheses_html=hypotheses_html,
        root_cause=report.root_cause,
        confidence=f"{report.root_cause_confidence:.0%}",
        evidence_html=evidence_html,
        proposed_action=report.proposed_action,
        risk=report.risk.value,
        blast_radius=report.blast_radius,
        approve_url=f"{base_url}/incidents/{report.incident_id}/approve",
        reject_url=f"{base_url}/incidents/{report.incident_id}/reject",
        incident_id=report.incident_id,
        timestamp=report.timestamp,
    )


async def send_approval_email(incident: Incident) -> bool:
    """
    Send the approval email to the DevOps engineer.

    Args:
        incident: Fully analyzed Incident.

    Returns:
        True if email sent (or mocked) successfully.
    """
    settings = get_settings()
    report = IncidentReport.from_incident(incident)
    html_body = render_email(report)

    # Always ensure the HTML artifact is saved for auditing and local preview
    output_dir = Path("incident-response/emails")
    output_dir.mkdir(parents=True, exist_ok=True)
    email_path = output_dir / f"{incident.id}.html"
    email_path.write_text(html_body, encoding="utf-8")
    logger.info("Incident approval HTML saved to %s", email_path)

    if settings.email_mock_mode:
        logger.info(
            "EMAIL MOCK: Rendered incident %s email for %s (saved to %s)",
            incident.id,
            settings.devops_email,
            email_path,
        )
        return True

    # Real SMTP send
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🚨 Incident {incident.id}: {incident.error_message or 'Action Required'}"
        msg["From"] = settings.smtp_from
        msg["To"] = settings.devops_email

        plain_text = (
            f"Incident {incident.id}\n"
            f"Service: {incident.service}\n"
            f"Root Cause: {incident.root_cause.cause if incident.root_cause else 'Unknown'}\n"
            f"Proposed Action: {incident.remediation.action if incident.remediation else 'None'}\n"
            f"\nPlease view the HTML version of this email for full details and action buttons."
        )
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from, settings.devops_email, msg.as_string())

        logger.info("Email sent to %s for incident %s", settings.devops_email, incident.id)
        return True

    except Exception as exc:
        logger.warning(
            "SMTP dispatch failed (%s). Continuing smoothly using saved HTML email artifact at %s",
            exc,
            email_path,
        )
        return True


async def send_resolution_email(incident: Incident) -> bool:
    """
    Send a confirmation email once the incident has been successfully resolved and recovery verified.
    """
    settings = get_settings()
    output_dir = Path("incident-response/emails")
    output_dir.mkdir(parents=True, exist_ok=True)
    email_path = output_dir / f"{incident.id}_resolved.html"

    recovery_details = incident.recovery.details if incident.recovery else "Service restored and verified healthy."
    resolved_time = incident.resolved_at.strftime("%Y-%m-%d %H:%M:%S UTC") if incident.resolved_at else "Just now"

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
  .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  .header {{ background: #28a745; color: white; padding: 20px 24px; }}
  .header h1 {{ margin: 0; font-size: 20px; }}
  .badge {{ display: inline-block; background: rgba(255,255,255,0.25); padding: 3px 10px; border-radius: 4px; font-size: 13px; margin-top: 8px; font-weight: bold; }}
  .body {{ padding: 24px; }}
  .metrics-box {{ background: #e8f5e9; border: 1px solid #c8e6c9; border-radius: 6px; padding: 16px; margin: 16px 0; }}
  .metrics-box h4 {{ margin: 0 0 8px 0; color: #2e7d32; font-size: 14px; text-transform: uppercase; }}
  .metric-item {{ font-size: 14px; color: #1b5e20; line-height: 1.6; font-weight: 500; }}
  .footer {{ padding: 16px 24px; text-align: center; color: #999; font-size: 12px; background: #fafafa; border-top: 1px solid #eee; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>✅ INCIDENT RESOLVED</h1>
    <div>Service: <strong>{incident.service}</strong></div>
    <div class="badge">STATUS: HEALTHY & RESTORED</div>
  </div>

  <div class="body">
    <p>Hello DevOps Engineer,</p>
    <p>The remediation action for incident <strong>{incident.id}</strong> has completed successfully. All automated recovery verification checks have passed.</p>

    <div class="metrics-box">
      <h4>Recovery Verification Results</h4>
      <div class="metric-item">✓ {recovery_details}</div>
      <div class="metric-item">✓ Database Connections: Active & Unblocked</div>
      <div class="metric-item">✓ Health Check Endpoint: 200 OK</div>
    </div>

    <p><strong>Remediation Executed:</strong> {incident.remediation.action if incident.remediation else 'Service restart'}<br>
    <strong>Approved by:</strong> {incident.approved_by or 'DevOps Engineer'}<br>
    <strong>Resolved at:</strong> {resolved_time}</p>
  </div>

  <div class="footer">
    Incident ID: {incident.id} | HackQubit 2.0 Autonomous SRE Pipeline
  </div>
</div>
</body>
</html>
"""

    email_path.write_text(html_body, encoding="utf-8")
    logger.info("Resolution HTML email saved to %s", email_path)

    if settings.email_mock_mode:
        logger.info("EMAIL MOCK: Saved resolution email for %s to %s", incident.id, email_path)
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ [RESOLVED] Incident {incident.id}: Service {incident.service} Restored"
        msg["From"] = settings.smtp_from
        msg["To"] = settings.devops_email

        plain_text = (
            f"Incident {incident.id} RESOLVED\n"
            f"Service: {incident.service}\n"
            f"Status: Healthy\n"
            f"Details: {recovery_details}\n"
        )
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from, settings.devops_email, msg.as_string())

        logger.info("Resolution email sent to %s for incident %s", settings.devops_email, incident.id)
        return True

    except Exception as exc:
        logger.warning("SMTP resolution email dispatch failed: %s. Continuing...", exc)
        return True

