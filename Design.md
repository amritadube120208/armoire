# Design.md — Smart Wardrobe & AI Recommendation System
### Product & UI/UX Design Specification

> "CHECK ALL EXISTING IDEAS OF THIS SOLUTION AND THEN MAKE MINE BETTER THAN THEM IN EVERY ASPECT."

## 0. UX Gaps in Existing Products (what we're designing against)

- **Whering / Acloset:** powerful but feature-dense; new users report feeling overwhelmed, and auto-tagging errors are surfaced without an easy inline-correct flow.
- **Alta:** the styling engine adapts to feedback but doesn't show *why* — no visible reasoning or confidence.
- **Stylebook:** manual-only — zero AI assistance, high setup friction.
- **Cladwell:** paid gate on core features, capsule-only mental model limits everyday flexibility.
- **Across the board:** none of them clearly show the user *why* a recommended outfit was chosen (weather? occasion? color match?), and none are honest on-screen about image-enhancement limitations — enhancement just "happens" with no user control.

**Our differentiators, baked into every screen below:**
1. Every recommendation shows a **"Why this outfit"** breakdown (weather / occasion / color / style / personalization scores).
2. Image enhancement is **opt-in and transparent** — before/after preview, explicit confidence, and a plain-language explanation of what enhancement can and cannot fix.
3. Onboarding is **progressive** — a usable wardrobe with 5 items beats an empty state gated behind a 20-item minimum.

---

## 1. Design Philosophy

**Visual identity:** modern, premium, minimal, fashion-editorial — closer to a boutique lookbook than a utility app. Generous whitespace, photography-first (the clothes are the content), quiet UI chrome.

### Color system
| Token | Value (example) | Use |
|---|---|---|
| `--bg-base` | `#FAFAF8` (warm off-white) | App background |
| `--bg-surface` | `#FFFFFF` | Cards, sheets |
| `--ink-900` | `#171614` | Primary text |
| `--ink-500` | `#6B6862` | Secondary text |
| `--accent` | `#2E5339` (deep botanical green) | Primary actions, selected states — distinct from the pink/purple that saturates this category (Whering, Alta) |
| `--accent-soft` | `#DCE7DD` | Accent backgrounds, chips |
| `--warn` | `#B4592A` | Low-confidence AI flags, quality warnings |
| `--error` | `#B3261E` | Errors |
| `--success` | `#3C7A4F` | Confirmations |
| Dark mode | mirrored tokens with `--bg-base: #14140F` etc. | Full dark-mode support from MVP, not bolted on later |

**Rationale:** a warm neutral base + single confident accent color keeps clothing photography (which spans every color) visually dominant, rather than competing with a busy brand palette.

### Typography
- **Display/headers:** a humanist serif or high-contrast sans (e.g., "Fraunces" or "Söhne") for an editorial feel on landing/marketing surfaces and outfit reveal moments.
- **UI/body:** a clean geometric sans (e.g., "Inter" or "General Sans") for everything functional — forms, lists, buttons — for maximum legibility at small sizes.
- Scale: 12/14/16/20/24/32/48px steps, 1.5 line-height for body, 1.15 for large display.

### Spacing & layout
- 8px base grid. Card padding 16–24px. Section gaps 32–48px. Consistent 4/8/12/16/24/32/48/64 spacing scale used everywhere (Tailwind's default scale maps directly).

### Components
- **Cards:** soft 12–16px corner radius, 1px hairline border (`--ink-900` at 8% opacity) instead of heavy drop shadows — flat, premium, print-catalog feel.
- **Buttons:** primary (filled accent), secondary (outline), ghost (text-only for low-emphasis actions). Minimum 44×44px touch target.
- **Icons:** single-weight line icon set (Lucide) throughout — never mix icon styles.
- **Animations/micro-interactions:** short (150–250ms), ease-out. Clothing cards get a subtle lift+shadow on hover/press. Outfit reveal uses a staggered fade-up (garment by garment) rather than an instant dump — reinforces the "curated" feeling. All motion respects `prefers-reduced-motion` (see Accessibility).

---

## 2. Main Screens

### 1. Landing Page
- **Purpose:** convert visitors, explain the core loop (upload → AI understands → get outfits) in under 10 seconds.
- **Layout:** full-bleed hero image grid of real outfit combinations, headline + one-line value prop, single CTA ("Build your wardrobe"). Below: 3-step "how it works" strip, then a differentiation strip ("See why every outfit was picked — not just what") directly addressing the opacity gap in competitors.
- **Components:** hero, 3-step explainer cards, testimonial/social-proof (post-launch), footer.
- **States:** N/A (static marketing page); loading skeleton for hero imagery on slow connections.

### 2. Login / Signup
- **Purpose:** low-friction account creation.
- **Layout:** centered card, email+password or Google OAuth button, toggle between login/signup.
- **Components:** form fields (React Hook Form + Zod validation), OAuth button, error banner.
- **User actions:** submit, switch mode, "forgot password."
- **Data displayed:** none until authenticated.
- **Empty/loading/error states:** inline field validation errors; loading spinner on submit button (disabled during request); top-of-form error banner for auth failures (e.g., "incorrect password") without leaking whether the email exists (security).

### 3. Onboarding
- **Purpose:** get the user to a usable wardrobe fast — this is where most competitors lose people to setup fatigue.
- **Layout:** 3-step wizard: (1) style preferences (quick tap-to-select style tags: minimal, streetwear, formal, etc.), (2) location/units for weather, (3) upload your first 3–5 items with a clear "you can add more later" reassurance.
- **Components:** progress indicator (step 1/3), style-tag chip grid, location autocomplete, drag-and-drop/camera upload zone.
- **User actions:** select tags, grant location, upload photos, skip-for-now on any step.
- **Empty state:** if user skips photo upload, dashboard shows a friendly "your wardrobe is empty" prompt instead of blocking access.
- **Loading:** per-photo upload progress bars.
- **Error:** upload failure shows retry inline, doesn't block the other photos in the batch.

### 4. Home / Dashboard
- **Purpose:** the daily-use screen — "what should I wear today."
- **Layout:** top card = today's weather + a single hero recommended outfit with "Why this outfit" expandable breakdown; below, horizontal scroll of alternate outfit options; below that, quick links (wardrobe, saved outfits, occasion picker).
- **Components:** weather chip, hero outfit card, outfit carousel, quick-action tiles.
- **User actions:** tap outfit for detail, swap an individual item within the outfit, change occasion, save/like/dismiss.
- **Data displayed:** current weather, top recommendation + score breakdown, 2–4 alternates.
- **Empty state:** if wardrobe has <3 usable items for the weather/occasion, show "add a few more items to unlock recommendations" with a direct upload CTA rather than a broken/empty recommendation.
- **Loading:** skeleton outfit cards while weather + recommendation calls resolve (parallelized, not sequential, to keep load fast).
- **Error:** if weather API fails, fall back to occasion-only recommendations with a visible "weather unavailable" notice (see `Backend.md` Error Handling).

### 5. My Wardrobe
- **Purpose:** browse/search/manage the full digital closet.
- **Layout:** grid of clothing cards (image, category chip, color swatch), filter/sort bar (category, color, season, "most worn," "never worn"), search.
- **Components:** filter chips, sort dropdown, clothing card grid, floating "add item" button.
- **User actions:** filter, search, tap item for details, multi-select for bulk actions (delete, tag).
- **Empty state:** first-time empty wardrobe vs. filtered-to-empty ("no black tops — clear filters?") are two distinct copy states.
- **Loading:** skeleton grid.
- **Error:** failed image thumbnails show a placeholder + retry icon rather than a broken image.

### 6. Add Clothing
- **Purpose:** the upload → AI-understand flow (full detail in section 4 below).
- **Layout:** camera/upload zone → processing state → review/confirm screen with editable AI-suggested attributes.
- **Components:** upload dropzone, camera capture (mobile), processing progress stepper, attribute review form (category, color, pattern, season, formality — all pre-filled by AI, all editable).
- **User actions:** upload, retake, edit any AI-suggested field, confirm/save.
- **Empty/loading/error:** covered in detail in Section 4 (AI Image Enhancement UX) and Section 3 (Wardrobe UX).

### 7. Clothing Details
- **Purpose:** view/edit a single item, see its usage history.
- **Layout:** large photo (with original/enhanced toggle if enhancement was applied), attribute list, "worn X times / last worn [date]," outfits containing this item, edit/delete actions.
- **Components:** image viewer, attribute chips (editable), usage stats, related-outfits list.
- **States:** loading skeleton; delete confirmation dialog (destructive action guard).

### 8. Image Enhancement Screen
- **Purpose:** transparently handle blurry/low-quality uploads. Full flow in Section 4.
- **Layout:** side-by-side or slider before/after comparison, plain-language quality explanation, accept/retake/proceed-anyway actions.

### 9. Outfit Recommendation (full-screen)
- **Purpose:** the core "show me outfits" experience, expanded from the dashboard's hero card.
- **Layout:** filter bar (occasion, weather auto-applied, "surprise me" shuffle), swipeable/scrollable outfit cards, each with a "Why this outfit" expandable panel showing the scoring breakdown (see Pipeline 7 in `Backend.md` — this UI renders those exact scores).
- **Components:** occasion selector, outfit card (garment thumbnails laid out flat-lay style), score breakdown accordion, like/dislike/save/wear buttons.
- **User actions:** swap an item, like/dislike (feeds Pipeline 8), save to favorites, mark as worn today.
- **Empty state:** insufficient wardrobe coverage for chosen occasion → explicit message + suggestion of what category to add ("add a jacket to unlock cold-weather formal outfits").
- **Loading:** skeleton cards while the scoring engine runs (target <2s; see Performance in `Backend.md`).
- **Error:** recommendation engine failure falls back to "recently worn combinations" rather than a blank screen.

### 10. Weather-Based Recommendation
- **Purpose:** a focused view when the user taps the weather chip specifically.
- **Layout:** expanded weather detail (temp, feels-like, precipitation, wind) at top, outfits filtered/scored primarily on weather-fit below, each card shows a small "weather match" badge (e.g., "great for rain").
- **User actions/states:** same interaction pattern as Outfit Recommendation, scoped to weather as primary driver.

### 11. Occasion-Based Recommendation
- **Purpose:** user explicitly picks an occasion (interview, date, gym, wedding, etc.).
- **Layout:** occasion grid/list (icon + label) → outfit results scoped to that occasion's dress-code rules, weather still factored as a secondary score.
- **States:** same pattern; empty state explains which dress-code requirement wasn't met (e.g., "no formal shoes in your wardrobe yet").

### 12. Outfit Details
- **Purpose:** full view of one specific outfit (whether recommended or self-built).
- **Layout:** flat-lay style arrangement of all items, full score breakdown, "worn on [dates]" history, edit (swap item), save/share, delete.
- **States:** loading skeleton; confirmation on delete.

### 13. Saved Outfits
- **Purpose:** favorites/collection view.
- **Layout:** grid of saved outfit cards, filter by occasion/season, sort by most recent/most worn.
- **Empty state:** "no saved outfits yet" with a CTA back to recommendations.

### 14. Profile
- **Purpose:** identity, stats, style profile summary.
- **Layout:** avatar/name, wardrobe stats (total items, most-worn category, cost-per-wear if tracked), style tag summary, edit-profile link.
- **States:** loading skeleton for stats aggregation.

### 15. Preferences / Settings
- **Purpose:** control style preferences, units, notifications, privacy, account.
- **Layout:** grouped settings list: Style Preferences (tags, favorite colors, disliked combinations), Units (°C/°F, location), Notifications, Privacy & Data (download my data, delete account), Account (email, password, logout).
- **User actions:** update any setting (auto-saved with a subtle confirmation toast), request data export/deletion.
- **States:** save-confirmation toast per field; destructive actions (delete account) require typed confirmation.

---

## 3. Wardrobe UX — Upload Flow

```
Upload photo
   → AI processes image (quality check runs first, silently)
       → IF quality too low: route to Image Enhancement Screen (Section 4)
       → IF quality acceptable: continue
   → Background removal + clothing detection (auto, ~1-2s, shown as a progress stepper)
   → Category prediction (top/bottom/dress/outerwear/shoes/accessory) — shown as an editable suggestion, not a locked fact
   → Attribute prediction (color auto via k-means — high confidence, shown as fact;
                            pattern/material/formality — shown as "AI suggests" with confidence indicator, always editable)
   → User reviews/edits on one screen, taps "Save"
   → Item added to Wardrobe library, appears immediately in "My Wardrobe" grid
```

**Categories (MVP):** Tops, Bottoms, Dresses, Outerwear, Shoes, Accessories.
**Extensibility:** category is a lookup table, not a hardcoded enum in the UI — new categories (e.g., "Activewear," "Swimwear," "Sleepwear") can be added without a frontend redeploy, satisfying the brief's "allow future categories" requirement.

---

## 4. Recommendation UX

```
User opens app
   → Weather detected (from saved location, refreshed on app open, cached ~30min)
   → Occasion: defaults to "Everyday/Casual" unless user selects one
   → Wardrobe analyzed (server-side, filtered to clean/wearable items)
   → Candidate outfits generated (combinatorial, bounded — see Backend.md Pipeline 7)
   → Each candidate scored across weather / occasion / color / style / personalization / diversity
   → Top-ranked outfits displayed, each with an expandable score breakdown
```

**Presentation principle:** never show a bare ranked list with no explanation. Every outfit card has a one-line summary ("Great for today's 14°C and light rain, matches your casual style") generated from the top 1–2 contributing score factors, with a tap-to-expand full breakdown — this is the single biggest UX gap we identified versus Alta/Acloset/Whering.

---

## 5. AI Image Enhancement UX

```
Upload blurry/low-quality image
   → Deterministic quality check (blur score, resolution, lighting) — instant, no AI cost yet
   → IF quality acceptable: skip straight to classification, no enhancement screen shown (don't interrupt the happy path)
   → IF quality borderline/poor:
        → Show Image Enhancement Screen
        → Run enhancement model (upscale/deblur)
        → Display ORIGINAL vs. ENHANCED side-by-side (or slider)
        → Plain-language caption: "We sharpened this image. Very blurry or low-light photos may still be hard to classify accurately — you can always edit details manually."
        → User choice: [Use enhanced] [Use original] [Retake photo]
   → Continue to classification using the chosen version
```

**Critical honesty constraint (per brief):** the UI must never imply the AI "recovered" detail that wasn't in the original photo. Enhancement copy always frames the action as *sharpening/upscaling what's there*, never *reconstructing what's missing*. If quality remains too low even after enhancement for confident classification, the review screen shows category/attribute fields **empty and required** rather than a low-confidence guess presented as fact — the user fills them in manually. This realistic limitation is stated directly in the UI, not hidden.

---

## 6. Responsive Design

| Breakpoint | Layout behavior |
|---|---|
| Mobile (<640px) | Single column, bottom tab bar (Home / Wardrobe / Add / Recommendations / Profile), full-screen modals instead of side panels, camera capture is the primary upload method. |
| Tablet (640–1024px) | 2-column wardrobe grid, side-sheet modals instead of full-screen, persistent top nav. |
| Desktop (>1024px) | 3–4 column wardrobe grid, persistent left sidebar nav, hover states enabled, drag-and-drop upload emphasized over camera. |

All layouts share the same component set and design tokens — no separate "mobile design" maintained independently, just responsive Tailwind breakpoints on shared components.

---

## 7. Accessibility

- **Contrast:** all text meets WCAG AA (4.5:1 body, 3:1 large text) against both light and dark backgrounds — verified against the color tokens in Section 1.
- **Keyboard navigation:** full tab order through forms, upload dropzone, and outfit cards; visible focus rings (`--accent` outline, never removed via `outline: none` without a replacement).
- **Screen readers:** every clothing image has generated alt text combining category + color + pattern (e.g., "Navy striped cotton shirt"); score breakdowns are readable as structured text, not just a visual chart.
- **Font sizing:** respects OS/browser text-size settings (relative `rem` units throughout, no fixed px text that ignores zoom).
- **Touch targets:** minimum 44×44px for all interactive elements, especially on the mobile clothing grid where cards are dense.
- **Reduced motion:** `prefers-reduced-motion: reduce` disables the staggered outfit-reveal animation and card-hover transitions, replacing them with instant state changes.

---

**Next document:** see `Backend.md` for the complete architecture and pipelines that power every screen above.
