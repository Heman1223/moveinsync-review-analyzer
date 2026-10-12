# Raising MoveInSync's Play Store rating: what to fix, and what to do first

**To:** MoveInSync Product, Engineering and Customer Experience
**From:** Heman Sharma · FDE intern case study · 12 Oct 2026
**Live dashboard:** https://moveinsync-review-analyzer.streamlit.app · **Code and data:** github.com/Heman1223/moveinsync-review-analyzer

---

## The answer in three lines

1. **MoveInSync is already the best-rated employee-transport app on Google Play** (4.64★; the other six average 3.05★). The remaining gap to consumer leaders like Uber (4.73★) is small.
2. **The biggest gap with your direct competitor is replies, not the product.** Routematic answers **100%** of its recent 1–2★ reviews; MoveInSync answers **1%**. This costs no engineering time to fix.
3. **The product work that matters most right now:** stop the app wrongly blocking users as "not installed from Play Store", fix the booking flow, and finish fixing OTP delivery.

---

## Why the rating is where it is

**Two groups rate the app.** 114,869 people have rated it; most only tapped a star, and those ratings are mostly 5★. The 2,857 people who wrote a review in the last 12 months average **3.83★**, and **24%** gave 1★. Written reviews are what prospective users, and the HR teams who buy MoveInSync, actually read.

**That gap is normal, and MoveInSync's written reviews are good for the category.** I measured 11 apps the same way (newest 500 reviews each). Written reviews sit about 1★ below the store rating for 10 of the 11. MoveInSync's newest written reviews (3.78★) are level with Uber (3.73★) and Rapido (3.77★), and ahead of Routematic (3.56★).

**What stands out is silence.** MoveInSync replied to about 97% of 1–2★ reviews in 2023, 38% in 2024, 7% in 2025 and **1% in 2026**. In the last 12 months, 743 of 772 unhappy reviews got no answer. Replies seem to work: of the reviewers who edited their review after getting a reply, **13 of 22 now show 4–5★**. I can't see their original rating, so this suggests replies help but doesn't prove it.

**What people complain about** (846 complaints in the last 12 months, sorted by keyword rules plus an AI model for the reviews the rules missed):

| Issue | Share of complaints, last 12 months | Last 90 days | Biggest specific problem (last 90 days) |
|---|---|---|---|
| App stability | 17% | **23%, rising** | Wrongly blocked as "not installed from Play Store" / rooted phone (26%) |
| Booking and schedule | 14% | 16% | Booking fails or the steps are confusing (66%) |
| Login, OTP and session | 17% | 10%, falling | OTP not received or slow (47%); logged out too often (26%) |
| Tracking, ETA and map | 10% | 9% | Cab location wrong or not updating (56%) |
| Repeated prompts | 5% | 7% | Forced trip rating; transport policy shown every time |

About two-thirds of complaints are about the app itself rather than cabs or drivers, so they are in MoveInSync's own control.

**Releases matter.** Versions 12.10–12.12 (Feb–May 2026) averaged **4.05★** with 20% 1★. The latest, v12.19, is at 3.58★ with 32% 1★. That's only 102 reviews so far, so it could still be chance, but it's worth watching. The 12.10–12.12 numbers also show that the targets below are achievable with the current product.

---

## What to do, in order

### Week 1–2: no-code and small fixes

| # | Action | Owner | Effort | Target |
|---|---|---|---|---|
| 1 | **Restart replying to every 1–2★ review within 48 hours.** Use the dashboard's reply assistant: a ready-made reply for each specific problem, checked by a person, posted in Play Console. | Support team | Low | Reply rate 4% → **80%** of new 1–2★ reviews |
| 2 | **Show the transport policy only when it changes**, and **make the trip rating skippable** (never block trip details behind it). | Mobile app team | 1/5 | Complaints about prompts down by half |
| 3 | **Ask for Play Store ratings at a good moment:** after an on-time trip, using Google's in-app review prompt, not after every ride. Never ask "do you like the app?" first: Google forbids filtering who gets the prompt. | Product | 1/5 | Fewer "rating pop-up" complaints |

### Next 30 days: the biggest app problems

| # | Action | Owner | Effort | Check first in your own data | Target |
|---|---|---|---|---|---|
| 4 | **Fix the false "not installed from Play Store" / rooted-phone block**, and reword the message so users know what to do. | Mobile app team (security) | 2/5 | Integrity-check logs: which phones and versions it blocks | False blocks near zero; stability complaints back to ~14% |
| 5 | **Find where OTPs get lost.** Measure delivery by channel and operator, add a backup channel, auto-read the SMS code. | App team + SMS provider | 3/5 | OTP send/deliver/verify logs by operator | OTP delivery ≥ 98% |
| 6 | **Stop logging people out** on brief network drops or after updates. | App + login/backend team | 3/5 | Session-expiry logs by app version | Forced-logout complaints halved |

### 60–90 days

| # | Action | Owner | Effort | Target |
|---|---|---|---|---|
| 7 | **Measure each step of booking** (open → choose → confirm → booked), fix where people give up, and compare with the older one-step flow users say was easier. | Product + app team | 3/5 | Booking completion rate up; booking complaints down |
| 8 | **Release in stages** (5% → 20% → 100%) and pause if crashes or 1★ reviews rise versus the previous version. | App team + release | 2/5 | No release worse than the one before |
| 9 | **Show "updated x min ago" on the cab location**, and check how often the driver app (Partner Lite) sends GPS. | Tracking + driver app team | 3/5 | Fewer "location wrong" complaints |

**Overall targets for 90 days:**
- written-review 1★ share from 25% to **≤ 20%**
- written-review average from 3.80★ to **≥ 4.0★** (v12.10–12.12 already reached 4.05★)
- reply rate **≥ 80%**
- store rating held at **4.64★ or better**

---

## How you'll know it's working

The dashboard answers "How are our Play Store ratings?" every week without anyone asking:
- **Every Monday** it fetches new reviews, re-measures the competitors, and writes a one-page digest: status (OK / WATCH / ALERT), what changed, what to fix next, and three quotes.
- **When a fix ships**, mark it on the dashboard. It then compares complaints about that issue per 100 reviews before and after, and says "improving", "no clear change" or "too early". Reviews lag behind fixes, so the next issue moves up meanwhile.
- **Today's status is WATCH:** stability complaints are rising, unhappy reviewers aren't getting replies, and v12.19 may be worse.

## Assumptions and limits

- Reviews describe experiences, not proven causes. Each action lists what to check in MoveInSync's own data before building.
- I can only read written reviews; star-only ratings are visible as totals.
- Data comes from public Google Play pages via an unofficial tool; Google can change those pages.
- Issue sorting is right about 75% of the time on 100 reviews I held back for checking (90% counting a review's second issue). The ranking is robust to that; individual labels aren't perfect.
- Effort scores are my judgement. Targets are estimates, not forecasts.
- Scope: the employee app (99% of reviews). The driver app, Partner Lite, has too few reviews (23 in a year) to analyse; it has none answered either.
- 12 complaints in the last year mention safety (for example, a driver misbehaving with a woman employee). They are listed in the dashboard for someone to read; they aren't ranked by volume.
