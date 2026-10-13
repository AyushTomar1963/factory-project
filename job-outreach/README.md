# jobhunt — internship auto-emailer

jobhunt finds people who are hiring **summer and winter interns**, writes a
resume tailored to each one, and emails them directly. No job portals, no
"Easy Apply": your resume lands in a real person's inbox.

| | |
|---|---|
| Dashboard (Vercel) | https://jobhunt-outreach.vercel.app |
| Dashboard (GitHub Pages) | https://ayushtomar1963.github.io/factory-project/ (after enabling Pages, see [below](#frontend-on-github-pages)) |
| Backend API (Render) | https://jobhunt-outreach.onrender.com |

Sign in with your `DASHBOARD_PASSWORD`. The free Render server sleeps when
idle, so the first page load can take up to a minute; the dashboard shows a
"waking up" banner and retries on its own.

---

## Contents

1. [How it works](#how-it-works)
2. [Architecture](#architecture)
3. [Setup, step by step](#setup-step-by-step)
4. [Environment variables](#environment-variables)
5. [Running locally](#running-locally)
6. [Deploying](#deploying)
7. [Command line](#command-line)
8. [Sending safely](#sending-safely)
9. [Project layout](#project-layout)
10. [Tests](#tests)

---

## How it works

Every cycle runs these steps. You can run them one at a time from the
dashboard, or let the autopilot do it.

1. **Find leads** (Apify). Three sources, each switchable on the Targeting page:

   | Source | What it searches | Who gets emailed |
   |---|---|---|
   | `hiring_posts` | Google for LinkedIn posts like *"hiring Summer 2027 intern"* | The person who wrote the post, plus decision makers at their company |
   | `linkedin_jobs` | LinkedIn internship listings, used only to learn who's hiring | The job poster if listed, then founders, CTO and engineering managers |
   | `companies` | Your own list of companies (`Razorpay, razorpay.com`) | Founders, CTO, engineering leads and recruiters there |

   All scraping runs inside Apify. Nothing logs into your LinkedIn account.

2. **Find who to email** (Apollo and/or Hunter). Looks up work emails and a
   confidence score for each person. When nobody has a findable email, a
   LinkedIn connection note is drafted for you to send by hand.

3. **Tailor your resume** (LLM + fact guard). For each lead, your master resume
   is reordered and reworded toward what they're hiring for, and a short pitch
   and cover letter are written. The fact guard rejects any rewrite that adds a
   skill or number that isn't in your original resume, and the build fails if a
   school, employer, title or date changes.

4. **Draft emails.** One initial email per person, ever, with the tailored PDF
   attached. With auto-send off (the default), drafts wait for you on the
   **Emails** page.

5. **Send slowly.** Approved emails go out over your SMTP account with a
   warm-up ramp, a daily cap and random gaps between messages.

6. **Watch the inbox** (IMAP). Replies stop follow-ups; bounces are added to
   the suppression list. One threaded follow-up goes out after a few days of
   silence.

---

## Architecture

```
            Browser
               │
   ┌───────────┴────────────┐
   │                        │
Vercel                 GitHub Pages
(React dashboard)      (same React dashboard)
   │  /api/* is rewritten      │  calls the API directly;
   │  to Render (same origin,  │  the backend allows *.github.io
   │  so no CORS)              │  via CORS
   └───────────┬────────────┘
               ▼
        Render web service (FastAPI)  ◄── cron-job.org pings /cron/tick
               │
   ┌───────────┼──────────────┬──────────────┬──────────────┐
Postgres     Apify      Apollo / Hunter     LLM API      SMTP / IMAP
(your data)  (leads)    (emails)            (tailoring)  (send / replies)
```

- **Backend** (`jobhunt/`): Python 3.12 + FastAPI. Serves the JSON API under
  `/api`, the cron endpoint `/cron/tick`, and the public unsubscribe links
  `/u/<token>`. It also still serves a simple server-rendered dashboard at `/`.
- **Frontend** (`frontend/`): React 19 + Vite + Tailwind CSS. It holds no data
  and no keys, and only talks to the backend.
- **Auth**: the dashboard sends `DASHBOARD_PASSWORD` as a Bearer token, stored
  in the browser's localStorage. `/cron/tick` is protected by `CRON_SECRET`.
- **Storage**: Postgres when `DATABASE_URL` is set, otherwise a local SQLite
  file.

---

## Setup, step by step

### 1. Make your data permanent

Render's disk is wiped on every deploy, so the app needs a database.

1. In the Render dashboard, open the Postgres database and copy its
   **Internal Database URL**.
2. Open the web service → **Environment**, add `DATABASE_URL`, paste the URL,
   and save. Render restarts the service.

Free Render Postgres expires after 30 days. Upgrade it, or point
`DATABASE_URL` at a free Neon or Supabase database, before then.

### 2. Get your API keys

| Service | Where | Used for |
|---|---|---|
| Apify | console.apify.com → Settings → Integrations | Finding leads (pay per result) |
| Apollo and/or Hunter | apollo.io → Settings → API; hunter.io → API | Finding emails |
| An LLM | OpenAI, or Groq for free (`https://api.groq.com/openai/v1`, model `llama-3.3-70b-versatile`) | Importing and tailoring your resume |
| An email account | Google Workspace, Zoho Mail, etc. on a **separate outreach domain** | Sending and reply detection |

Add each key on the Render service under **Environment** (names are in
[Environment variables](#environment-variables)). Set `PUBLIC_BASE_URL` to
`https://jobhunt-outreach.vercel.app` so unsubscribe links work.

### 3. Set up the dashboard

1. **Resume crafter**: upload your resume PDF (or paste the text) and click
   **Import**. Check the preview, fix anything in the editor, and click
   **Save**. Until you do, the app uses a fake example resume.
2. **Targeting & autopilot**: set seasons, roles and locations, optionally list
   companies to cold-email, pick lead sources, and save. The checklist on the
   right shows which keys are still missing.
3. **Sending & replies**: click **Check** under Domain health. The required
   checks (SPF, DKIM, DMARC) must pass before anything is sent.

### 4. Do a first run by hand

1. **Overview** → **Run full cycle**, and wait for it to finish.
2. **Internship leads**: open a few to see the tailored PDF, pitch and contacts.
3. **Emails**: edit or reject drafts you don't like, then **Approve all**.
4. **Sending & replies** → **Send approved**.

### 5. Turn on autopilot

Create a free job on [cron-job.org](https://cron-job.org) that opens this URL
every 10–15 minutes:

```
https://jobhunt-outreach.vercel.app/cron/tick?key=<CRON_SECRET>
```

Each ping wakes the server, checks the inbox, sends a few approved emails,
and starts a new cycle when one is due (every 24 hours by default). Once you
trust the drafts, turn on **Send without asking** in Targeting.

**Daily routine:** open the dashboard, approve new drafts on **Emails**, and
read replies on **Sending & replies**.

---

## Environment variables

All of these live on the backend (Render). The frontend never sees them. See
`.env.example` for a full template.

| Variable | Required | Purpose |
|---|---|---|
| `DASHBOARD_PASSWORD` | yes | Password for the dashboard and API |
| `CRON_SECRET` | yes | Protects `/cron/tick` |
| `UNSUBSCRIBE_SECRET` | yes | Signs unsubscribe links |
| `PUBLIC_BASE_URL` | yes | Public URL used in unsubscribe links |
| `DATABASE_URL` | when hosted | Postgres connection string |
| `APIFY_TOKEN` | yes | Lead discovery |
| `APOLLO_API_KEY` / `HUNTER_API_KEY` | at least one | Finding emails |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | recommended | Any OpenAI-compatible API. Without it, tailoring uses a simpler built-in engine and resume import is disabled |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_SSL` | to send | Your outreach mailbox |
| `SENDER_EMAIL`, `SENDER_NAME` | to send | The From address. Its domain is the one checked for SPF/DKIM/DMARC |
| `DKIM_SELECTOR` | to send | Your provider's DKIM selector (Google uses `google`) |
| `IMAP_HOST` (+ `IMAP_USERNAME`, `IMAP_PASSWORD`) | recommended | Reply and bounce detection. Login defaults to the SMTP credentials |
| `SENDER_POSTAL_ADDRESS` | optional | Postal address in the email footer |
| `CORS_ORIGIN_REGEX` | optional | Overrides which sites may call the API directly (default: `*.vercel.app`, `*.github.io`, `localhost`) |

---

## Running locally

Backend:

```bash
git clone https://github.com/AyushTomar1963/factory-project && cd factory-project/job-outreach
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"     # PDF output needs Pango: apt install libpango-1.0-0 libpangoft2-1.0-0
jobhunt init                # creates config.yaml and .env; fill in .env
jobhunt serve               # API + simple dashboard on http://localhost:8000
```

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173, proxies /api to localhost:8000
```

Set `BACKEND_URL` to point the dev proxy at a different backend, e.g.
`BACKEND_URL=https://jobhunt-outreach.onrender.com npm run dev`.

---

## Deploying

### Backend on Render

`render.yaml` is a Render Blueprint for the web service and a free Postgres
database, with `rootDir: job-outreach`. Create it from the Render dashboard
(**New → Blueprint**), then fill in the variables marked `sync: false`. The service binds to `0.0.0.0:$PORT`
and exposes `/healthz` for health checks.

### Frontend on Vercel

```bash
cd frontend
npx vercel deploy --prod
```

Set the Vercel project's root directory to `job-outreach/frontend`. `frontend/vercel.json`
rewrites `/api/*`, `/u/*`, `/cron/*` and `/healthz` to the Render service, so
the browser only ever talks to the Vercel domain. If your Render URL is not
`jobhunt-outreach.onrender.com`, change it there. It also defines a daily Vercel
cron as a backstop.

### Frontend on GitHub Pages

`.github/workflows/jobhunt-pages.yml` (at the repository root) builds the
dashboard with `npm run build:pages` on every push to `master` or
`cursor/job-outreach-system-655c` that touches `job-outreach/frontend/`, and
publishes the result to the `cursor/gh-pages-655c` branch.

One-time setup: **Settings → Pages → Build and deployment → Deploy from a
branch → `cursor/gh-pages-655c` / (root)**. The site is then
`https://ayushtomar1963.github.io/factory-project/`.

GitHub Pages can't forward requests, so this build calls the Render API
directly. Override the target with `VITE_API_BASE` if your backend URL differs.
A copy of `index.html` is published as `404.html` so refreshing any page works.

---

## Command line

Everything in the dashboard is also available from the terminal.

| Command | What it does |
|---|---|
| `jobhunt import-resume FILE` | Import your resume (PDF, text or JSON Resume) as the master |
| `jobhunt discover` | Find internship leads from the enabled sources |
| `jobhunt enrich [--limit N]` | Find people and emails for new leads |
| `jobhunt tailor [--lead ID] [--limit N] [--offline]` | Build the tailored resume PDF, cover letter, pitch and LinkedIn note |
| `jobhunt queue` | Draft emails (or LinkedIn notes when there's no email) |
| `jobhunt followups` | Queue one follow-up for unanswered emails |
| `jobhunt run` | `discover` + `enrich` + `tailor` + `queue` |
| `jobhunt autopilot [--cycle] [--loop MIN]` | One autopilot tick, or keep ticking every MIN minutes |
| `jobhunt review` / `approve ID…` / `reject ID…` / `done ID…` | Review drafts |
| `jobhunt send [--live] [--limit N]` | Send approved emails. Without `--live` it's a dry run that writes `.eml` files to `data/outbox/` |
| `jobhunt check-replies` | Scan the inbox for replies and bounces |
| `jobhunt check-domain [DOMAIN]` | Check SPF, DKIM, DMARC, MX and reverse DNS |
| `jobhunt suppress EMAIL…` | Never contact these addresses |
| `jobhunt status` | Counts and today's remaining send budget |
| `jobhunt serve` | Run the web server |

---

## Sending safely

Cold email that lands in spam is worse than none, so these rules are enforced
in code, not just recommended:

- Nothing is sent unless SPF, DKIM and DMARC are published for the sender domain.
- Warm-up: 5 emails a day in week 1, then 10, 15 and 20, then the daily cap (25).
- Random gaps of 20–60 seconds between messages.
- One-click unsubscribe (RFC 8058), a visible opt-out line, and a suppression list.
- The same person is never emailed again within 90 days, and gets at most one
  follow-up, threaded as a reply.
- Sending pauses automatically if the bounce rate goes above 5%.

Use a separate domain just for outreach (for example `yourname-careers.com`),
never your personal Gmail or your main domain.

---

## Project layout

```
jobhunt/
  web.py            FastAPI app: auth, CORS, cron, unsubscribe, server-rendered pages
  api.py            JSON API used by the React dashboard (/api/...)
  pipeline.py       discover → enrich → tailor → queue
  autopilot.py      the /cron/tick scheduler
  sources.py        Apify lead sources
  enrich.py         Apollo / Hunter email lookup
  crafter.py        resume import (PDF/text → JSON Resume)
  tailor.py         per-lead tailoring and the fact guard
  render.py         HTML/PDF rendering (WeasyPrint)
  mailer.py         SMTP sending, warm-up, IMAP reply/bounce detection
  deliverability.py SPF / DKIM / DMARC checks
  db.py             SQLite / Postgres storage
  cli.py            the `jobhunt` command
  templates/        resume, cover letter and dashboard templates
frontend/
  src/api.ts        API client (auth, retries while Render wakes up)
  src/ui.tsx        shared UI components
  src/pages/        Overview, Resume, Targeting, Leads, LeadDetail, Emails, Sending
  vercel.json       Vercel rewrites to the backend
tests/              pytest suite; every external HTTP call is mocked
render.yaml         Render Blueprint
.env.example        all environment variables
```

---

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

The suite mocks every HTTP call. It covers the Apify sources and filtering,
Apollo and Hunter lookups, the fact guard (including adversarial LLM output),
resume import, the send throttle, follow-up threading, reply and bounce
detection, a full discover-to-send autopilot run, the JSON API, and auth and
CORS. Set `TEST_DATABASE_URL` to run it against Postgres.
