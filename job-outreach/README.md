# jobhunt: internship auto emailer

Finds people and companies taking **winter and summer interns**, crafts a
tailored resume for each one, and emails them directly. No application portals.

```
 LinkedIn hiring posts ─┐                         ┌─► founders / eng leads / recruiters
 LinkedIn intern listings ─► leads ─► find people ┤   (Apollo, Hunter)
 your company list ─────┘     (Apify)             └─► post author's own email
                                   │
 your resume (PDF) ─► Resume crafter ─► per-lead resume + pitch (LLM + fact guard) ─► PDF
                                   │
                     drafts ─► auto-approve (verified emails) or you ─► throttled SMTP send
                                   │
                     inbox (IMAP): replies stop follow-ups, bounces get suppressed
                                   │
                     one threaded follow-up after N days with no reply
```

## Where leads come from

| Source | How | Who gets emailed |
|---|---|---|
| `hiring_posts` | Google search for `site:linkedin.com/posts hiring intern "Summer 2027" "<role>"` via the Apify Google Search actor | The person who wrote the post (their work email via Apollo), plus decision makers at their company |
| `linkedin_jobs` | LinkedIn internship listings (`f_E=1`) via an Apify actor. Used only to learn who's hiring interns; we never apply through the listing | The job poster if listed, then founders, CTO and engineering managers at that company |
| `companies` | Your own list ("Razorpay, razorpay.com" or a domain), entered on the Targeting page | Founders, CTO, engineering leads, recruiters there |

All scraping runs inside Apify. Nothing logs into your LinkedIn account, and
LinkedIn messages are never automated. When someone has no findable email, a
connection note is drafted for you to send by hand.

## Resume crafter

Upload your resume PDF (or paste the text) on **Resume crafter**. The LLM
converts it to JSON Resume, and anything in the result that isn't in your
original text is flagged for you to check. Edit the JSON there, preview it, and
download a general internship resume PDF. Students get Education, Skills and
Projects first.

For every lead, a tailored copy is built from that master:

- bullets are reordered and reworded toward what they're hiring for;
- a rewrite is rejected if it mentions a skill or number that isn't in **that
  original bullet**, and the summary, pitch and cover letter may only use skills
  and numbers that appear somewhere in your resume;
- skills are reordered, never added;
- a structural diff guarantees that schools, employers, titles and dates are
  unchanged, and the build fails if anything differs.

## Auto emailer

Free hosts sleep and kill long-running loops, so the emailer is driven by a
**tick**. Something external calls `/cron/tick` every ~15 minutes. Each tick:

1. checks the inbox over IMAP: replies stop follow-ups, bounce notices suppress
   the address;
2. every `cycle_every_hours`, runs a full cycle: find leads, find people, craft
   up to `tailor_per_cycle` resumes, and draft emails;
3. queues follow-ups that are due and, if **auto-send** is on, approves drafts
   to verified addresses (or confidence at or above `min_email_confidence`);
4. sends up to `per_tick` emails, within the warm-up ramp and the daily cap.

With auto-send off (the default), everything is drafted and waits for you on
**Emails**, where there's an **Approve all** button.

Trigger options:

- [cron-job.org](https://cron-job.org), free, every 15 minutes:
  `https://<host>/cron/tick?key=<CRON_SECRET>`. Recommended; it also keeps a
  free Render instance awake.
- The Vercel cron in `frontend/vercel.json` (daily backstop; sends
  `Authorization: Bearer <CRON_SECRET>`).
- Locally: `jobhunt autopilot --loop 15`.

## Keys you need

| Variable | For | Notes |
|---|---|---|
| `APIFY_TOKEN` | finding leads | console.apify.com → Settings → Integrations. Pay-per-result; start with `max_results_per_query` around 20 |
| `APOLLO_API_KEY` and/or `HUNTER_API_KEY` | finding emails | Apollo matches post authors by LinkedIn URL; Hunter fills gaps |
| `LLM_API_KEY` (+ `LLM_BASE_URL`, `LLM_MODEL`) | resume import and tailoring | any OpenAI-compatible API (OpenAI, Groq, OpenRouter, Gemini's OpenAI endpoint) |
| `SMTP_*`, `SENDER_EMAIL`, `SENDER_NAME`, `DKIM_SELECTOR` | sending | a dedicated outreach domain with SPF, DKIM and DMARC published |
| `IMAP_HOST` | reply detection | login defaults to the SMTP credentials |
| `DATABASE_URL` | persistence | Postgres. Without it, data lives in SQLite and is lost on every redeploy of a free host |
| `CRON_SECRET`, `DASHBOARD_PASSWORD`, `UNSUBSCRIBE_SECRET`, `PUBLIC_BASE_URL` | security and links | `PUBLIC_BASE_URL` must be public so unsubscribe links work |

## Quick start (local)

```bash
cd job-outreach
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # WeasyPrint needs Pango: apt install libpango-1.0-0 libpangoft2-1.0-0
jobhunt init                       # creates config.yaml and .env; fill in .env
jobhunt import-resume my-resume.pdf
jobhunt serve                      # dashboard at http://localhost:8000
```

## Commands

| Command | What it does |
|---|---|
| `jobhunt import-resume FILE` | Import your resume (PDF, text or JSON Resume) as the master |
| `jobhunt discover` | Find internship leads from the enabled sources. Safe to re-run |
| `jobhunt enrich [--limit N]` | Find people and emails for new leads |
| `jobhunt tailor [--lead ID] [--limit N] [--offline]` | Craft the per-lead resume PDF, cover letter, pitch and LinkedIn note |
| `jobhunt queue` | Draft emails (or LinkedIn notes when there's no email). One initial email per person, ever |
| `jobhunt followups` | Queue one follow-up for unanswered emails |
| `jobhunt run` | discover + enrich + tailor + queue |
| `jobhunt autopilot [--cycle] [--loop MIN]` | One auto-emailer tick, or keep ticking |
| `jobhunt review` / `approve ID…` / `reject ID…` / `done ID…` | Review drafts from the terminal |
| `jobhunt check-replies` | Scan the inbox for replies and bounces |
| `jobhunt check-domain [domain]` | Check SPF, DKIM, DMARC, MX and forward-confirmed reverse DNS |
| `jobhunt send [--live] [--limit N]` | Send approved emails. A dry run (writes `.eml` files to `data/outbox/`) unless `--live` |
| `jobhunt suppress EMAIL…` | Never contact these addresses |
| `jobhunt status` | Counts and today's remaining send budget |
| `jobhunt serve` | Dashboard, `/cron/tick`, and the public `/u/<token>` unsubscribe endpoint |

## Sending safely

Cold email that lands in spam is worse than none, so these are enforced in code:

- sending is refused unless SPF, DKIM and DMARC are published for the sender domain;
- a warm-up ramp of 5/day in week 1, then 10, 15 and 20, then the daily cap (25);
- randomised spacing between messages;
- RFC 8058 one-click unsubscribe, a visible opt-out line, and a suppression list;
- no new thread with the same person within 90 days, and at most one follow-up,
  threaded with `In-Reply-To`;
- an automatic pause if the hard-bounce rate goes above 5%.

Use a separate domain just for outreach (e.g. `alexrivera-careers.com`), never
`@gmail.com` and never your main address's domain.

## Hosting

`render.yaml` defines the web service plus a free Postgres database. Render's
filesystem is ephemeral, so `DATABASE_URL` is what keeps your resume, leads,
sent history and suppression list across deploys. Free Render Postgres expires
after 30 days; upgrade it or point `DATABASE_URL` at another Postgres (Neon,
Supabase) before then.

## Frontend (Vercel)

`frontend/` is a React + Vite + Tailwind dashboard that talks to the JSON API
under `/api` (see `jobhunt/api.py`). On Vercel, `frontend/vercel.json` rewrites
`/api/*`, `/u/*`, `/cron/*` and `/healthz` to the Render service, so the browser
only ever talks to its own origin and CORS never comes into play. The backend
also sends CORS headers for `*.vercel.app` and `localhost` (override with
`CORS_ORIGIN_REGEX`) in case you set `VITE_API_BASE` to call Render directly.

Sign in with `DASHBOARD_PASSWORD`; the app sends it as a Bearer token. The
server-rendered dashboard on Render keeps working too.

```bash
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev   # proxies /api to a local `jobhunt serve`
npx vercel deploy --prod                       # set the Vercel root directory to job-outreach/frontend
```

If your Render URL differs from `jobhunt-outreach.onrender.com`, change it in
`frontend/vercel.json`.

## Tests

```bash
pytest -q
```

The tests mock every HTTP call. They cover the Apify sources and filtering, Apollo
and Hunter enrichment (including resolving a post author), the fact guard (including
adversarial LLM output), resume import, the throttle, follow-up threading, reply and
bounce detection, a full discover-to-send autopilot run, and the dashboard (resume
crafter, targeting, cron auth, basic auth, one-click unsubscribe).
