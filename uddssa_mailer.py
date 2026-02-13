"""
This script is used to send marketing emails to the mailing list.
It uses the Resend API to send the emails.
It uses either DeepSeek or OpenAI to generate/polish the subject and body (controlled by AI_PROVIDER).

Usage:
python marketing_email/uddssa_mailer.py --content-mode manual
python marketing_email/uddssa_mailer.py --content-mode ai_polish
python marketing_email/uddssa_mailer.py --content-mode ai_draft --tone formal
"""

import csv
import os
import sys
import time
import json
import requests
from pathlib import Path
import argparse

# ============================================================
# Helpers
# ============================================================

def die(msg: str, code: int = 1) -> None:
    print(msg)
    sys.exit(code)

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()

def load_recipients(csv_path: Path) -> list[dict]:
    recipients = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or row.get("Name") or row.get(" full_name") or row.get("full_name") or "").strip()
            email = (row.get("email") or row.get("email ") or row.get(" email") or row.get("Email")
                     or row.get("email address") or row.get("email address ") or "").strip()
            if email:
                recipients.append({"name": name, "email": email})
    return recipients

def load_env_file(env_path: Path) -> None:
    """
    Minimal .env loader:
    - Reads KEY=VALUE lines
    - Ignores blanks and comments (#)
    - Sets os.environ if not already set
    """
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)

def require_otp_if_present(base_dir: Path) -> None:
    """
    Minimal OTP gate:
    - If otp.txt exists in base_dir, require user to enter it.
    - If correct, delete otp.txt (one-time).
    - If otp.txt doesn't exist, no OTP required.
    """
    otp_file = base_dir / "otp.txt"
    if not otp_file.exists():
        return

    expected = otp_file.read_text(encoding="utf-8").strip()
    if not expected:
        die("otp.txt exists but is empty. Remove it or put a valid OTP inside.")

    entered = input("Enter one-time passcode (OTP): ").strip()
    if entered != expected:
        die("Invalid OTP. Aborting.")

    otp_file.unlink()
    print("OTP verified (one-time). Proceeding...\n")

# ============================================================
# AI: Provider-aware generate/polish returning (subject, body)
# ============================================================

def ai_generate_subject_body(
    provider: str,
    api_key: str,
    mode: str,
    tone: str,
    user_prompt: str,
    draft_subject: str | None = None,
    draft_body: str | None = None,
    model: str | None = None,
) -> tuple[str, str]:

    provider = (provider or "openai").strip().lower()

    if mode not in {"ai_draft", "ai_polish"}:
        die(f"Invalid AI mode: {mode}")

    # System rules: force JSON-only output + enforce {name} greeting
    system_rules = f"""
You are helping draft an email for a university data science student association (UD-DSSA).
Tone: {tone}.
Requirements:
- Output MUST be valid JSON with exactly these keys: "subject", "body".
- "subject": short, clear, not spammy (avoid ALL CAPS, too many !!!).
- "body": plain text email body, friendly and professional. Emojis are allowed but keep it tasteful (0–3).
- Keep body under ~220 words unless user asks otherwise.
- Include a call-to-action and relevant details.
- The body MUST start with exactly: "Hi {{name}},"
- Avoid exaggerated marketing claims.
Return ONLY JSON. No markdown. No commentary.
""".strip()

    if mode == "ai_draft":
        user_msg = f"""
Create a fresh email subject and body based on this request:

{user_prompt}

Remember: return ONLY JSON with keys "subject" and "body".
""".strip()
    else:
        user_msg = f"""
Improve the following email while preserving meaning and facts.
Make it clearer, better structured, and aligned with the tone.

DRAFT SUBJECT:
{draft_subject or ""}

DRAFT BODY:
{draft_body or ""}

Return ONLY JSON with keys "subject" and "body".
""".strip()

    if provider == "openai":
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        use_model = model or "gpt-4.1-mini"
        payload = {
            "model": use_model,
            "input": [
                {"role": "system", "content": system_rules},
                {"role": "user", "content": user_msg},
            ],
            "store": False,
        }

    elif provider == "deepseek":
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        use_model = model or "deepseek-chat"
        payload = {
            "model": use_model,
            "messages": [
                {"role": "system", "content": system_rules},
                {"role": "user", "content": user_msg},
            ],
        }

    else:
        die(f"Unknown AI provider: {provider}")

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        die(f"{provider} API error ({r.status_code}): {r.text}")

    data = r.json()

    raw = ""
    if provider == "openai":
        text_parts = []
        for out in data.get("output", []) or []:
            for c in out.get("content", []) or []:
                if isinstance(c, dict) and "text" in c:
                    text_parts.append(str(c["text"]))
        raw = "\n".join(text_parts).strip()
    elif provider == "deepseek":
        try:
            raw = (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            raw = ""

    if not raw:
        die(f"{provider} returned no text output. Aborting.\nRaw response:\n{json.dumps(data, indent=2)[:2000]}")

    try:
        obj = json.loads(raw)
        subject = str(obj["subject"]).strip()
        body = str(obj["body"]).strip()
    except Exception:
        die(
            "Could not parse AI output as JSON.\n"
            "Tip: ensure the model is instructed to output ONLY JSON.\n\n"
            f"Raw output:\n{raw}"
        )

    if not subject or not body:
        die("AI returned empty subject/body. Aborting.")

    return subject, body

# ============================================================
# Resend
# ============================================================

def resend_send_one(
    resend_api_key: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    text_body: str,
) -> tuple[bool, str]:
    headers = {"Authorization": f"Bearer {resend_api_key}", "Content-Type": "application/json"}
    payload = {"from": from_addr, "to": [to_addr], "subject": subject, "text": text_body}
    r = requests.post("https://api.resend.com/emails", headers=headers, json=payload, timeout=60)
    if r.status_code == 200:
        return True, r.text
    return False, r.text

# ============================================================
# Main (Service Mode Only)
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="UD-DSSA Mailing Service (Resend) with optional AI drafting/polishing."
    )

    parser.add_argument(
        "--content-mode",
        choices=["ai_draft", "ai_polish", "manual"],
        default="ai_polish",
        help="ai_draft: AI writes subject/body from your prompt. ai_polish: AI improves subject.txt/body.txt. manual: use subject.txt/body.txt as-is.",
    )

    parser.add_argument(
        "--tone",
        default="friendly-professional",
        help="Tone for AI modes (e.g., formal, casual, fun, friendly-professional).",
    )

    parser.add_argument(
        "--ai-model",
        default="",
        help="Optional override model name (OpenAI: gpt-4.1-mini; DeepSeek: deepseek-chat). Leave blank to use provider default.",
    )

    parser.add_argument("--sleep", type=float, default=0.5, help="Delay between sends (seconds).")

    args = parser.parse_args()

    base_dir = Path(__file__).parent.resolve()
    load_env_file(base_dir / ".env")

    mail_dir = base_dir / "mailing_list"
    csv_file = mail_dir / "emails.csv"
    subject_file = mail_dir / "subject.txt"
    body_file = mail_dir / "body.txt"

    require_otp_if_present(base_dir)

    for f in [csv_file, subject_file, body_file]:
        if not f.exists():
            die(f"Missing required file: {f}")

    recipients = load_recipients(csv_file)
    if not recipients:
        die("No recipients found in the mailing list!")

    # Helpful warning if names missing
    missing_names = sum(1 for r in recipients if not r["name"])
    if missing_names:
        print(f"Note: {missing_names} recipient(s) have no name in CSV. They'll be greeted as 'there'.\n")

    resend_api_key = os.getenv("RESEND_API_KEY")
    if not resend_api_key:
        die("Missing RESEND_API_KEY environment variable (set it in .env).")

    from_addr = os.getenv("RESEND_FROM") or "DSSA <no-reply@bluehen-dssa.org>"
    print("Running in Service Mode: sending from UD-DSSA sender via Resend.\n")

    subject = read_text(subject_file)
    body_template = read_text(body_file)

    if args.content_mode in {"ai_draft", "ai_polish"}:
        provider = (os.getenv("AI_PROVIDER") or "openai").strip().lower()

        if provider == "deepseek":
            ai_key = os.getenv("DEEPSEEK_API_KEY")
        else:
            provider = "openai"
            ai_key = os.getenv("OPENAI_API_KEY")

        if not ai_key:
            die(
                "Missing AI key for AI mode.\n"
                f"For provider={provider}, set the appropriate key in .env:\n"
                "- OpenAI: OPENAI_API_KEY=\n"
                "- DeepSeek: DEEPSEEK_API_KEY=\n"
            )

        model_override = (args.ai_model or "").strip() or None

        if args.content_mode == "ai_draft":
            print("\n--- Email Builder (quick intake) ---")
            kind = input("Type (event/opportunity/announcement): ").strip()
            audience = input("Audience (e.g., UD students, DSSA members): ").strip()
            topic = input("Main topic/title (1 line): ").strip()
            details = input("Key details (date/time/location/deadline): ").strip()
            cta = input("Call-to-action (RSVP link / form / 'reply to this email'): ").strip()
            contact = input("Contact person + email (optional): ").strip()
            extras = input("Anything else to include (optional): ").strip()

            user_prompt = f"""
Write an email for UD-DSSA.

TYPE: {kind}
AUDIENCE: {audience}
TOPIC: {topic}
DETAILS: {details}
CTA: {cta}
CONTACT: {contact}
NOTES: {extras}

Return ONLY JSON with keys "subject" and "body".
The body MUST start with: "Hi {{name}},"
Keep it clear, non-spammy, and under ~200 words.
Use at most 2 emojis total.
""".strip()

            subject, body_template = ai_generate_subject_body(
                provider=provider,
                api_key=ai_key,
                mode="ai_draft",
                tone=args.tone,
                user_prompt=user_prompt,
                model=model_override,
            )
        else:
            subject, body_template = ai_generate_subject_body(
                provider=provider,
                api_key=ai_key,
                mode="ai_polish",
                tone=args.tone,
                user_prompt="",
                draft_subject=subject,
                draft_body=body_template,
                model=model_override,
            )

    # --- Hard guarantee: ensure greeting contains {name} (applies to ALL modes) ---
    if "{name}" not in body_template:
        body_template = "Hi {name},\n\n" + body_template

    # --- Preview + explicit confirmation ---
    print("\n================== PREVIEW ==================")
    print(f"FROM: {from_addr}")
    print(f"SUBJECT: {subject}")
    print("--------------------------------------------")
    sample_name = recipients[0]["name"] or "there"
    sample_body = body_template.replace("{name}", sample_name)
    print(sample_body)
    print("============================================\n")

    confirm = input("Type SEND to approve and send to the mailing list (anything else cancels): ").strip()
    if confirm != "SEND":
        die("Cancelled. No emails were sent.", code=0)

    print(f"\nSending email to {len(recipients)} recipients via Resend. Please wait...")

    sent = 0
    failed = 0

    for rcp in recipients:
        personalized_body = body_template.replace("{name}", rcp["name"] or "there")

        ok, resp_text = resend_send_one(
            resend_api_key=resend_api_key,
            from_addr=from_addr,
            to_addr=rcp["email"],
            subject=subject,
            text_body=personalized_body,
        )

        if ok:
            sent += 1
            print(f"Sent to {rcp['name'] or rcp['email']}")
        else:
            failed += 1
            print(f"FAILED to {rcp['email']}: {resp_text}")

        time.sleep(args.sleep)

    print(f"\nDone. Sent={sent}, Failed={failed}")

if __name__ == "__main__":
    main()