# jobhunt

An end-to-end job search pipeline built around the four recommendations in the
architecture brief:

1. **Skip consumer job boards.** Jobs come straight from employer ATS APIs
   (Greenhouse, Lever, Ashby, Workday). These are public JSON endpoints published
   for embedding job boards, so there are no scrapers to break and no anti-bot walls.
2. **Tailor documents against a fixed schema.** Your master resume is a JSON Resume
   file that tailoring can never change. The LLM only proposes rephrasings that
   point back to your existing bullets, and a fact guard rejects any rewrite that
   adds a skill or number not in your own material.
3. **Find contacts through B2B data providers, not LinkedIn.** Hiring managers are
   looked up via Apollo.io and/or Hunter.io by company domain and target title.
4. **Send a small volume of authenticated cold email.** Sending is refused unless
   SPF, DKIM and DMARC are published. On top of that: a warm-up ramp, a per-domain
   daily cap (25 by default), randomised spacing between messages, one-click
   unsubscribe (RFC 8058), a suppression list, and an automatic pause when the
   bounce rate rises.

```
 ATS APIs ──► discover ──► score & filter ──► enrich (Apollo/Hunter)
                                   │
                                   ▼
 master_resume.json ──► tailor (LLM + fact guard) ──► PDF (WeasyPrint)
                                   │
                                   ▼
                     queue drafts ──► YOU review/approve ──► send (throttled SMTP)
                                                        └─► LinkedIn note (you send it by hand)
```

## LinkedIn: drafted, never automated

The brief recommends browser automation with stealth patches as a fallback for
LinkedIn. This project deliberately doesn't do that. Driving your account with
CDP masking and simulated mouse movement breaks LinkedIn User Agreement §8.2,
and LinkedIn actively detects it, so you'd be risking your real professional
profile. When a contact has a LinkedIn URL but no verified email, jobhunt drafts a
connection note under 300 characters and puts it in your review queue with
**Copy note** and **Open profile** buttons. You send it yourself, then mark it done.

## Quick start

```bash
cd job-outreach
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # WeasyPrint needs Pango: apt install libpango-1.0-0 libpangoft2-1.0-0

jobhunt init                       # creates config.yaml and .env
# edit config.yaml: companies to watch, filters, your resume path
# edit .env: LLM / Apollo / Hunter keys, SMTP for your outreach domain

jobhunt run                        # discover + enrich + tailor + queue
jobhunt serve                      # dashboard at http://localhost:8000
```

Everything also works without any API keys. In that mode discovery is live,
tailoring uses the offline deterministic engine (it reorders bullets and skills
by relevance and fills message templates), and you add contacts yourself.

### Finding a company's ATS board token

| ATS        | Careers URL looks like                                   | `ats`        | `board`                         |
|------------|----------------------------------------------------------|--------------|---------------------------------|
| Greenhouse | `boards.greenhouse.io/airbnb`                            | `greenhouse` | `airbnb`                        |
| Lever      | `jobs.lever.co/palantir`                                 | `lever`      | `palantir`                      |
| Ashby      | `jobs.ashbyhq.com/ramp`                                  | `ashby`      | `ramp`                          |
| Workday    | `nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite`  | `workday`    | `nvidia/5/NVIDIAExternalCareerSite` |

## Commands

| Command | What it does |
|---|---|
| `jobhunt discover` | Pull every posting from the configured boards, score it against your resume, and shortlist the ones that pass your filters. Safe to re-run. |
| `jobhunt enrich [--refresh]` | Look up target-title contacts at companies that have shortlisted jobs (Apollo first, then Hunter, then Hunter's email finder to fill gaps). |
| `jobhunt tailor [--job ID] [--limit N] [--offline]` | Build a tailored resume PDF, cover letter PDF, email pitch and LinkedIn note. |
| `jobhunt queue` | Create drafts: email when there's a verified address, otherwise a LinkedIn note. Each person is pitched for at most one role. |
| `jobhunt review` / `approve ID…` / `reject ID…` / `done ID…` | Review drafts from the terminal (the dashboard does the same). |
| `jobhunt check-domain [domain]` | Check SPF, DKIM, DMARC, MX and forward-confirmed reverse DNS. |
| `jobhunt send [--limit N]` | **Dry run**: writes `.eml` files to `data/output/outbox/` and leaves the database untouched. |
| `jobhunt send --live` | Real sending. Refuses to run if the domain isn't authenticated or the unsubscribe URL isn't public. |
| `jobhunt suppress EMAIL…` | Never contact these addresses. |
| `jobhunt status` | Pipeline counts and today's remaining send budget. |
| `jobhunt serve` | Dashboard, plus the public `/u/<token>` unsubscribe endpoint. |

## How the fact guard works

Tailoring never edits your resume directly. The tailored copy is rebuilt from the
master, and only three things can change: `basics.summary`, the order and wording
of `work[*].highlights`, and the order of `skills`.

- Every rewritten bullet must name the original bullet it rephrases. A rewrite is
  rejected (and the original wording kept) if it mentions a skill or number that
  isn't in **that original bullet**. That stops the LLM from, for example, moving
  "Kubernetes" from one job into a bullet about another.
- The summary, cover letter, pitch and LinkedIn note may only use skills and
  numbers that appear somewhere in your master resume.
- Skills can be reordered but never added. Unknown names in `skills_priority`
  are ignored.
- After tailoring, a structural diff checks that employers, titles, dates,
  education and certificates are byte-identical to the master. If anything
  differs, the build fails rather than producing an altered resume.
- Each job page lists what the guard rejected, and shows skills the posting
  wants that you don't have. Those are never added to your resume.

## Email deliverability checklist

1. Register a separate domain just for outreach (e.g. `janedoe-careers.com`).
   Never use `@gmail.com`, and never use your main domain.
2. Set up a mailbox on it (Google Workspace, Microsoft 365, Zoho, etc.) and
   publish SPF, DKIM and `_dmarc` (`p=none` at minimum).
3. Set `SENDER_EMAIL`, `DKIM_SELECTOR` and the `SMTP_*` values in `.env`, then run
   `jobhunt check-domain` until it prints `ready to send`.
4. Deploy the dashboard somewhere public and set `PUBLIC_BASE_URL`,
   `UNSUBSCRIBE_SECRET` and `DASHBOARD_PASSWORD`. The unsubscribe link in every
   email points there.
5. Let the warm-up ramp work: 5/day in week 1, then 10, 15 and 20, and the cap
   after that. Send once a day with **Send approved now** on the Sending page,
   or with `jobhunt send --live`.

Whatever sends the email and whatever serves `/u/<token>` must use the **same
database and the same `UNSUBSCRIBE_SECRET`**. Otherwise an unsubscribe recorded
by the web app would never reach the sender. The simplest way to guarantee that
is to run everything, sending included, from one deployment.

## Deploying the dashboard on Render

`render.yaml` defines a web service bound to `0.0.0.0:$PORT`. Render's filesystem
is ephemeral, so the blueprint mounts a persistent disk at `/var/data` for the
SQLite database and generated PDFs (disks need a paid instance type). Put your
`config.yaml` and master resume on that disk (for example with `render ssh`),
set the secrets marked `sync: false` in the Render dashboard, and do all
discovery, tailoring and sending from the hosted dashboard so there's only one
database.

If you'd rather not host anything, run `jobhunt serve` on your own machine and
expose it through a tunnel (with `DASHBOARD_PASSWORD` set, only `/u/*` and
`/healthz` are reachable without a password).

## Vercel front door

`vercel/` is a code-free Vercel project that rewrites every request to the
Render service, so the public URL can live on Vercel while the stateful app
(SQLite, background discovery and sending) stays on Render. Point
`PUBLIC_BASE_URL` on Render at the Vercel URL so unsubscribe links use it.
See `vercel/README.md`.

## Tests

```bash
pytest -q
```

The tests cover ATS response parsing for all four vendors, keyword scoring, the
fact guard (including adversarial LLM output), provider ranking, the DNS checks,
the throttle (warm-up, cap, bounces, re-contact window, dry run), unsubscribe
tokens and headers, a full discover-to-send run, and the dashboard (including
basic auth and one-click unsubscribe). Every HTTP call is mocked.
