---
name: page-design-review
description: Quick design-only review of one landing or funnel page (GoHighLevel preview links, live pages, any builder) on desktop and mobile — layout, spacing, hierarchy, first-screen/CTA placement, form polish, images, proof, consistency and mobile behaviour — delivered as the team's client feedback document (clickable summary of numbered fixes, yellow-marked screenshots, Critical / High / Medium / Polish tiers plus "Change now" / "Confirm first" tags) in HTML + PDF, saved in the client's OS folder. No scoring, no audit scale, no test opt-ins or purchases, no pixel/speed/legal checks; that's the funnel-audit skill. Use when the user says "quick design audit", "design review", "design feedback", "audit this page from a design perspective", "look at the design of this page", "give feedback on this page like we did for <client>", or shares a page URL and asks for design notes, from any folder.
---

# Page design review

A fast, design-only pass on **one page** (or a whole funnel: then ONE consolidated report for all its pages, fixes numbered across pages and the summary grouped by page), written as feedback a page builder can act
on. It is **not** the funnel audit: no audit scale or score, no test sign-ups or purchases, no pixel, speed or legal
page checks, no copy rewrite. If the user wants any of that, point them to `funnel-audit`.

Typical time: 10–15 minutes per page. Keep the report short; 10–20 fixes is normal.

## 1. Set up (1 minute)

1. **Which client?** Work out from the user's words which client OS folder this belongs in (`COGA/<Client>/` or
   `COGA/<Client> OS/`). If it's unclear, ask with clickable options (one question).
2. Read that folder's `CLAUDE.md`, `design/design-system.md` (brand colours, fonts, live styles) and skim
   `brain/01-client-profile.md` for her/his approved proof figures. Also apply the user's memory rules for that
   client (e.g. banned photos, photo gaze direction, "no Provely", GHL review exclusions).
3. **Where it goes:** if the page belongs to an existing `funnels/<name>/` folder, use its `qa/`. Otherwise create
   `funnels/<page-name>-<mon>-<year>/` with a short `README.md` (what the page is, preview URL, a QA table) and add
   a row to `funnels/README.md`. Don't claim who built the page unless you know.

## 2. Capture (2 minutes)

```
python ~/.claude/skills/page-design-review/scripts/capture.py "<URL>" --out "<scratchpad>/<page>"
```

It writes desktop (1440×900) and mobile (390×844, 2× pixels) full-page shots, first-screen shots, slices to look
at, `text.txt`, and `facts.json` (headings + sizes + line counts, every button/link and where it goes, form
button position vs. first screen, sideways scroll, fonts in use, images with natural width). Pixels and form
posts are blocked.

**Look at every slice** (`desktop-s00.jpg…`, `mobile-s00.jpg…`) and both `*-fold.png`. Crop and zoom
(PIL) anything small you're unsure about (icons in fields, odd spacing, stray characters) before calling it a
fault. GHL forms are often in an iframe, so `form_submit_y` can be `None`; read the button position off the
screenshot instead.

## 3. What to look for

Go section by section, desktop then mobile. Only flag what a visitor would notice or what costs sign-ups.

- **First screen:** is the form button (or a CTA) visible on a 900px laptop screen and close on a phone? Headline
  size/line count (desktop H1 > ~3 lines or mobile > ~4 lines is usually too big). Is the host's face visible?
- **Hierarchy & type:** one clear headline, readable body (≥16px mobile), consistent heading styles, no orphan
  words, button text on one line on mobile.
- **Spacing & alignment:** uneven gaps (especially inside forms), empty columns next to tall elements, cards in a
  row with different heights, centered lists with ragged icons, elements that hug or overlap edges.
- **Form:** field order and required marks, broken/odd icons, consent and privacy lines placed sensibly, stray
  wrapper boxes or backgrounds behind the button, "your info is safe" line.
- **Images:** flattering host photo/thumbnail (smiling, eyes toward the copy), sharp (natural width ≥ shown
  width), no banned photos, logos as real logos (not text pills), badges not covering faces.
- **Buttons & links:** every CTA goes somewhere sensible (`facts.json` → `clicks`), consistent button wording/style,
  fake "play" buttons that are really links are clear about what happens.
- **Proof:** testimonials laid out evenly with photo + name + role; "featured on" and credentials easy to scan;
  figures match the client's approved numbers (flag a mismatch, don't rewrite copy).
- **Consistency:** matches the client's design system or other live funnels; if not, add one "Confirm first" item
  asking whether the new look is intended.
- **Typos & glitches you can see:** stray spaces/punctuation, text cut off, text hidden on mobile that shows on
  desktop.
- **Footer:** legal links present (Privacy, Terms, Earnings disclaimer where income is discussed), disclaimers
  readable.
- **Mobile only:** sideways scroll, section order (what moves above/below the form), tap targets, swipe rows,
  sticky bars covering content.

Also list 3–5 things that already work ("keep it"), so the builder knows what not to touch.

Give every fix a tier and an action (see "Fix buckets" below). Never invent facts, figures, testimonials or assets; ask for them via "Confirm first"
and add the question to the client's `brain/06-open-items.md` if it's a real open question.

## Fix buckets (same in funnel-audit and page-design-review, user rule 2026-11-10)

Every fix gets two labels, written together like **"Critical · Confirm first"**:

1. **Tier, how serious it is:**
   - **Critical**: stops a launch, a sale or a sign-up, or shows visitors something wrong. Examples: a broken
     button, form or checkout; a wrong price, date or link; a checkout that is live before the offer opens; a page
     that loses sign-ups; legally wrong text. Fix before launch.
   - **High**: the page works but clearly loses conversions or trust. Examples: no proof on a sales page, the
     CTA/form far below the first screen, the host missing from the page, hard-to-read text, a step with nothing
     to click.
   - **Medium**: consistency and clarity. Examples: names, times or footers that differ between pages, a missing
     ™, uneven card layouts.
   - **Polish**: small visual details. Examples: lone words, spacing, glow lines, stray characters.
2. **Action, can we do it now:** **Change now** (ready to apply) or **Confirm first** (needs a decision, a fact
   or an asset).

Summary tables list fixes Critical → High → Medium → Polish; the numbers on the screenshots stay tied to their
position on the page. Funnel audit only: tracking/pixel items keep the chip "Highlight · not a launch blocker" and
OK-as-is notes keep "Note · OK as is".

## 4. Mark up the screenshots

Write a `marks.json` (format in `scripts/mark.py`) with one yellow number per fix at the exact spot, plus a yellow
box around the area. Desktop fixes are `1, 2, 3…`; mobile-only fixes are `M1, M2…`. Desktop markers use
desktop-full.png pixels (= CSS px); mobile uses mobile-full.png pixels (CSS px × 2). Crop desktop into 2–3 images
(hero, middle, bottom) and mobile into 2 (hero, rest). Then:

```
python ~/.claude/skills/page-design-review/scripts/mark.py marks.json --cap "<scratchpad>/<page>" --out "<funnel>/qa/shots/design-feedback"
```

Open each output image and check every marker sits on the right thing; fix and re-run if not.

## 5. Write the report

Copy `assets/example-feedback.html` (a finished real example; its screenshots don't load from the skill folder,
use it for structure and wording) to `<funnel>/qa/design-feedback.html` and replace
the content, keeping its structure and CSS:

1. Title "<Page name>: Design Feedback", sub-line with client · page/offer · review date · "Design only".
2. Cover box: page URL + an honest 2–3 sentence overall verdict naming the main issue.
3. "How to read this" (summary rows are clickable, yellow numbers match screenshots, tag legend).
4. **Summary table**: one row per fix with its tier and action, sorted Critical → Polish within each group, grouped "DESKTOP PAGE (also applies on mobile)" then "MOBILE ONLY", each
   row linking to its item, with Where and Status.
5. "What already works (keep it)".
6. One section per screenshot (page break before each): the image, then the items for that image. Each item:
   number, short title, tag, what's wrong in one or two plain sentences, and exactly what to do. For a text glitch
   show **Current** / **Change to** boxes. Every item has a "↑ Back to summary" link.
7. Mobile sections use the side-by-side layout (`.row` with image left, items right).

Writing style: plain words, short sentences, concrete numbers ("about 330px of empty space", "button at ~1,370px
on a 900px screen"), no design jargon without explanation. Written for the page builder and the client team.

Then make the PDF and check it:

```
python ~/.claude/skills/page-design-review/scripts/to_pdf.py "<funnel>/qa/design-feedback.html" "<funnel>/qa/<Client> - <Page> - Design Feedback (<Mon D>).pdf" --sheet "<scratchpad>/sheet.png"
```

Look at the sheet: no blank pages, images not cut off, summary fits.

## 6. Hand over

Reply short: where the HTML and PDF are (clickable paths), the fix count, the top 3 fixes in one line each, and
any "Confirm first" questions. Don't paste the whole report into chat. Don't publish, email or push anything
unless the user asks.
