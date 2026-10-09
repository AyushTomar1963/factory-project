# Vercel front door

This Vercel project has no code of its own. It rewrites every request to the
FastAPI app on Render (`https://jobhunt-outreach.onrender.com`), so the public
URL is on Vercel while the app, its SQLite database and the background
send/discovery workers stay on Render. Vercel serverless functions can't hold
those: they have no persistent disk and no long-running threads.

- Basic auth, form POSTs, redirects, PDFs and the `/u/<token>` unsubscribe
  endpoint all pass straight through the rewrite.
- Set `PUBLIC_BASE_URL` on the Render service to the Vercel URL so unsubscribe
  links in emails point at the Vercel domain.
- If the Render service name changes, update the destination in `vercel.json`.

Deploy with:

```bash
cd job-outreach/vercel
npx vercel deploy --prod
```
