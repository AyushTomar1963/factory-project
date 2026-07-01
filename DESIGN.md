---
name: Rushab Industries QA Portal
description: Factory IQC inspection UI — blue-indigo industrial, mobile-first worker flow
colors:
  brand-50: "#eff6ff"
  brand-100: "#dbeafe"
  brand-600: "#2563eb"
  brand-700: "#1d4ed8"
  indigo-700: "#4338ca"
  ink: "#0f172a"
  ink-muted: "#64748b"
  pass: "#16a34a"
  hold: "#f59e0b"
  fail: "#dc2626"
typography:
  display:
    fontFamily: "system-ui, sans-serif"
    fontWeight: 900
    fontSize: "1.875rem"
  body:
    fontFamily: "system-ui, sans-serif"
    fontWeight: 400
    fontSize: "0.875rem"
  label:
    fontFamily: "system-ui, sans-serif"
    fontWeight: 700
    fontSize: "0.75rem"
rounded:
  card: "1rem"
  button: "0.75rem"
spacing:
  panel: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.brand-600}"
    textColor: "#ffffff"
    rounded: "{rounded.button}"
    padding: "12px 16px"
  button-gradient:
    backgroundColor: "{colors.brand-700}"
    textColor: "#ffffff"
    rounded: "{rounded.card}"
    padding: "20px 16px"
---

# Design System: Rushab Industries QA Portal

## 1. Overview

**Creative North Star: "The Trusted Line Station"**

A mobile-first factory QC terminal: white surfaces, blue-indigo brand gradients on primary actions, and traffic-light status semantics. Density is moderate — enough information for lot traceability without overwhelming floor workers.

**Key Characteristics:**
- Blue-indigo gradient headers and primary CTAs
- `rounded-2xl` cards with soft blue-tinted shadows
- GREEN / AMBER / RED as the only inspection status vocabulary
- `max-w-md` worker column vs `max-w-6xl` admin layout

## 2. Colors

### Primary
- **Rushab Blue** (#1d4ed8): Headers, primary buttons, focus rings
- **Line Indigo** (#4338ca): Gradient endpoints on CTAs and page headers

### Neutral
- **Floor White** (#ffffff): Panel backgrounds
- **Mist Blue** (#eff6ff): Page backgrounds and tinted cards
- **Ink** (#0f172a): Headings and body text

### Status
- **Pass Green** (#16a34a): PASS decisions and GREEN ratings
- **Hold Amber** (#f59e0b): HOLD / YELLOW marginal states
- **Fail Red** (#dc2626): FAIL decisions and RED ratings

## 3. Typography

**Display Font:** system-ui (900 weight for page titles)
**Body Font:** system-ui (400–700 for labels and forms)

### Hierarchy
- **Display** (900, 1.875rem): "Rushab IQC Hub", admin page title
- **Title** (700–900, 1.125–1.25rem): Section headings, part names
- **Label** (700, 0.75rem uppercase optional): Form field labels
- **Body** (400–600, 0.875rem): Form inputs, table cells

## 4. Elevation

Flat-by-default panels with soft tinted shadows on cards (`--shadow-card`, `--shadow-login`). Depth comes from border tints (`border-brand-100`) and hover lift (`-translate-y-0.5`) on interactive elements — not heavy drop shadows.

## 5. Components

### Buttons
- **Primary:** `Button` variant `primary` — solid brand-600
- **Gradient CTA:** variant `gradient` — brand-700 → indigo-700, used for scan and confirm actions
- **Decision:** variants `pass`, `hold`, `fail` for overall inspection outcome
- **Ghost:** variant `ghost` — admin header logout on gradient background

### Cards
- **Panel:** `Panel` — main worker content container
- **Card:** bordered white surface for intake and parameter blocks

### Forms
- **FormField + Input/Select/Textarea** — consistent `p-3`, `border-2`, `rounded-lg`, brand focus ring

### Status
- **StatusBadge** — pill badges for log table (GREEN/YELLOW/RED)
- **Rating buttons** — three-column grid per parameter from `RATING_OPTIONS` constant

## 6. Do's and Don'ts

### Do:
- **Do** use shared components from `frontend/src/components/` for all new UI
- **Do** use design tokens in `frontend/src/index.css` `@theme` block
- **Do** keep worker layout at `max-w-md` for one-handed tablet use

### Don't:
- **Don't** add Google Sheet ID fields — backend uses PostgreSQL
- **Don't** inline one-off Tailwind button styles — extend `Button` variants
- **Don't** use generic SaaS cream backgrounds or glassmorphism
- **Don't** put business logic back into `App.jsx` — use hooks in `frontend/src/hooks/`
