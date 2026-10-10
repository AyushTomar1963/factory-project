# Vercel front door

This Vercel project has no code of its own. It rewrites every request to the
FastAPI app on Render (`https://jobhunt-outreach.onrender.com`), so the public
URL is on Vercel while the app and its background workers stay on Render.
Vercel serverless functions can't hold those: they have no long-running threads.

- Basic auth, form POSTs, file uploads, redirects, PDFs and the `/u/<token>`
  unsubscribe endpoint all pass straight through the rewrite.
- Set `PUBLIC_BASE_URL` on the Render service to the Vercel URL so unsubscribe
  links in emails point at the Vercel domain.
- If the Render service name changes, update the destination in `vercel.json`.

## Auto emailer cron

`vercel.json` schedules a daily `GET /cron/tick` (Hobby plans only allow daily
crons). Set the same `CRON_SECRET` here as on Render; Vercel then sends it as
`Authorization: Bearer <CRON_SECRET>`, which the app checks:

```bash
npx vercel env add CRON_SECRET production
```

The daily run is a backstop. For steady sending, also add a job at
[cron-job.org](https://cron-job.org) every 15 minutes hitting
`https://<your-vercel-domain>/cron/tick?key=<CRON_SECRET>`; it also keeps the
free Render instance awake.

Deploy with:

```bash
cd job-outreach/vercel
npx vercel deploy --prod
```
