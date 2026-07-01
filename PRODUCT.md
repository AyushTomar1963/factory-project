# Product

## Register

product

## Users

Factory floor workers and QC inspectors at Rushab Industries. They use tablets or phones on the production line to log incoming quality checks on parts. Admins are plant managers who monitor yield, defects, and inspection history.

## Product Purpose

Digitize IQC (incoming quality control) inspections: scan or enter a part, capture lot intake details, rate parameters as GO / NO GO / DOUBTFUL, and log pass/hold/fail decisions to a central PostgreSQL backend. Failed parts trigger AI-generated defect categories for management reporting.

Admins maintain a **product master** (part numbers + custom inspection parameters), supplier registry, and user accounts — no spreadsheet setup required on the floor.

## Brand Personality

Industrial, trustworthy, efficient. Blue-indigo factory identity tied to Rushab Industries. Confident without being flashy — built for gloved hands and bright factory floors.

## Anti-references

- Generic SaaS landing-page aesthetics (cream backgrounds, glassmorphism, gradient text)
- Overly playful or consumer-app styling on the worker flow
- Dark-mode-only dashboards that are hard to read on the floor
- Requiring Google Sheets IDs or external spreadsheet setup at login

## Design Principles

1. **Floor-first** — large tap targets, clear status colors (green/amber/red), minimal steps per inspection.
2. **One task per screen** — worker flow is linear: stage → part → intake → rate → decide.
3. **Status is color** — GREEN / YELLOW / RED must be instantly recognizable without reading labels.
4. **Admin clarity** — dashboards prioritize yield and defect trends over decoration.
5. **Reuse over rewrite** — UI changes go through shared components and tokens in `frontend/src/components/` and `frontend/src/index.css`.

## Accessibility & Inclusion

- WCAG AA contrast on body text and status buttons
- `prefers-reduced-motion` respected in global CSS
- Support Hindi and English in defect remarks
- Password fields with show/hide toggle
