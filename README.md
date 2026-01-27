# UD-DSSA Email Mailing Service (PoC)

A lightweight, service-mode Python mailing tool for sending **personalized bulk emails** via **Resend**, with optional **AI-assisted drafting or polishing** using **OpenAI** or **DeepSeek**.

This project is designed as a **proof-of-concept (PoC)** for student organizations (e.g. UD-DSSA) to manage announcements, events, and opportunities safely—without Gmail SMTP or storing user credentials.

---

## Key Features

- 📧 Transactional email delivery via **Resend**
- 🧠 Optional AI support:
  - `ai_draft`: generate subject + body from a short intake
  - `ai_polish`: improve existing drafts
  - `manual`: send content as-is
- 👤 Per-recipient personalization using `{name}`
- 🔐 Optional **one-time passcode (OTP)** safety gate
- 👀 Mandatory **preview + explicit SEND confirmation**
- ⚙️ Pure Python (standard library + `requests`)
- 🧪 Service-mode only (no DIY SMTP, no Gmail passwords)

---

## Project Structure



```

marketing_email/
│
├── uddssa_mailer.py # Main mailing service script
├── .env # Environment variables (DO NOT COMMIT)
├── otp.txt # (Optional) one-time passcode gate
│
└── mailing_list/
├── emails.csv # Recipient list
├── subject.txt # Email subject (manual / polish modes)
└── body.txt # Email body (supports {name})

````

---


## Requirements

- Python **3.9+**
- Internet access
- A **Resend** account and API key
- *(Optional)* An **OpenAI** or **DeepSeek** API key for AI modes

Python dependency:
```bash
pip install requests


## Environment Setup

Create a .env file in marketing_email/:

# Required (email sending)
RESEND_API_KEY=your_resend_api_key
RESEND_FROM=DSSA <no-reply@bluehen-dssa.org>

# Optional (AI features)
AI_PROVIDER=openai          # or deepseek
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=...

# Optional overrides
# AI_PROVIDER defaults to "openai"

⚠️ Never commit .env or API keys to version control.

## Recipient List Format

mailing_list/emails.csv must contain an email column.
Name is optional but recommended.

name,email
Tony Stark,starkt@uddssa.com
Frodo Baggins,frodo@uddssa.com
,anonymous@uddssa.com

## Content Files (Manual / Polish Modes)
subject.txt
DataQuest × FinTech Hub 591 Collaboration

body.txt
Hi {name},

We’re excited to invite you to a collaborative session with DataQuest at FinTech Hub 591.

📅 Date: 26 January 2026  
🕒 Time: 3:00 PM  

Pizza and beverages will be provided.

Best,  
UD-DSSA

## Usage

Run from the project root:

python marketing_email/uddssa_mailer.py

## Content Modes

### 1. Manual (no AI)
python marketing_email/uddssa_mailer.py --content-mode manual


Uses subject.txt and body.txt exactly as written.

### 2. AI Polish (default)
python marketing_email/uddssa_mailer.py --content-mode ai_polish


Optional tone:

--tone formal
--tone casual
--tone friendly-professional

### 3. AI Draft (guided intake)
python marketing_email/uddssa_mailer.py --content-mode ai_draft --tone formal


You’ll be prompted for:

event type

audience

topic

date / time / location

call-to-action

The AI returns JSON-validated subject and body.

## Safety & Controls
Preview + Confirmation

Before sending:

A full preview is shown

You must type SEND to proceed

Anything else cancels the run.

## Optional OTP Gate

If otp.txt exists in the project directory:

You’ll be prompted for a one-time code

The file is deleted after successful entry

Useful for shared machines or officer handoffs.

## Personalization

Use {name} anywhere in body.txt.

Example:

Hi {name},


Becomes:

Hi Gandalf,


If {name} is missing, the script automatically prepends:

Hi {name},

## Common Errors

| Error               | Cause                     | Fix                   |
|--------------------|---------------------------|-----------------------|
| Missing RESEND_API_KEY | `.env` not loaded          | Add key to `.env`     |
| No recipients found | Bad CSV headers            | Use `name,email`     |
| AI JSON parse error | Model returned non-JSON    | Retry / change model |
| 429 quota error     | AI billing not enabled     | Use manual mode      |


## AI output is forced to valid JSON

Hard rules ensure:

non-spammy subject

professional tone

{name} greeting

AI usage is optional — mailing works without it

## Intended Scope (PoC)

This project is not a full marketing platform. It intentionally avoids:

HTML templates

tracking pixels

analytics

background queues

It is designed for:

student organizations

controlled mailing lists

officer-run announcements

## Author

Tunmbi Okediran
PhD Student, Financial Services Analytics
University of Delaware

UD-DSSA Mailing Service – Proof of Concept
