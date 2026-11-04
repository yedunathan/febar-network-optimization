# Role-play presenter notes: Northstar out-of-route freight (4 slides, ~5 minutes)

**Audience you're role-playing to:** the VP Supply Chain (executive sponsor), with the Director of Transportation in the room.
**Your goal:** agreement on a 90-day pilot and a date for the baseline workshop.

---

## Slide 1: The problem (≈ 75 seconds)

**Open with the outcome, not the technology:**
"Thanks for the time. I'll keep this to about five minutes and leave most of our time for your questions. In short: over the last twelve months about **$23.6 million** of your freight went to moves your own supply plan never asked for. That's roughly **30 cents of every freight dollar**."

**Talk track:**
- "About **a third of your cases**, 35%, moved on a lane that wasn't in that month's plan."
- "Not all of that is bad. **More than 40% of those moves were actually cheaper.** That's exactly why it's hard to manage: your team sees 1,068 lanes with off-plan moves and can't tell which ones are costing money."
- "And it shows up late. Finance sees one freight variance **four to six weeks** after the truck has moved, with no lane, no product and no root cause attached. That's because the plan, the freight system and the ledger don't agree on plant codes, product numbers or even currency."

**Check-in question (pause and let them answer):**
"Does that match what you're seeing? How does your team find these today, and how long does it take?"

**If they push back** ("Our freight variance isn't that big"):
"That's fair. The variance nets the cheaper moves against the costly ones. Net, it's about $16.7M; gross, it's $23.6M. The gross number is what's recoverable, because the cheaper moves you'd keep."

---

## Slide 2: The solution, creating visibility (≈ 75 seconds)

**Transition:** "So the first thing we set out to fix was visibility: seeing the costly moves the next day instead of the next quarter."

**Talk track:**
- "We built **one trusted view of every lane**. Every lane, product and month is labelled planned, out-of-route or never shipped, and priced against what the plan said it should cost."
- "Then we **ranked it by dollars, not volume**. A machine-learning model predicts which off-plan moves will cost more, and by how much. The top 20% of lanes hold over half the leakage, so instead of 1,068 lanes your planners start with **40 lanes worth about $10 million a year**."
- "For each of those 40, generative AI writes the action in plain English: reroute to the planned DC, or fix the supply plan. It names an owner and the dollars at stake. Your planner approves, rejects or snoozes it in one click, and the decision is logged."
- "And anyone can ask Genie, *'which lanes leak the most this month?'*, and get the answer with the SQL behind it."

**The insight to land (slow down here):**
"The most important thing we found: **two-thirds of those dollars trace back to a stale supply plan, not to carriers.** So this is a planning conversation, not a rate negotiation."

**Check-in question:**
"Director, if your team had this 40-lane list every morning, what would stop them from acting on it?"

---

## Slide 3: The architecture (≈ 60 seconds; keep it business-level)

**Transition:** "Quickly, how it works, because it's one platform rather than six tools stitched together."

**Talk track:**
- "**Lakeflow** pulls in the raw ERP, supply-plan and freight extracts and fixes the mismatches automatically, with data-quality checks on every run."
- "**Unity Catalog** governs every layer. Contract rates are masked, tables are certified, and you can trace any number back to its source."
- "The **ML model** and the **Gen AI** recommendations run on those same governed tables. The model scored **0.92 AUC on months it had never seen**, so it holds up on new data."
- "**Lakebase** serves the queue to the app in milliseconds and records every planner decision. **Genie** and the **app** put it in front of the business."
- "The whole flow runs as **one job in about twelve minutes**, and no data is copied out to other tools."

**If they ask** "Can we trust the AI's recommendations?":
"The AI only sees that one lane's facts. It can't invent data, and it has to answer in a fixed format: action, owner and dollars. Every recommendation is stored and reviewable, and your planner makes the final call."

**If they ask** "What does IT need to do?":
"Read access to three extracts you already produce. Everything runs serverless in your Databricks workspace, under your existing governance."

---

## Slide 4: Call to action and next steps (≈ 75 seconds)

**Transition:** "So here's what I'd propose."

**Talk track:**
- "A **90-day pilot** on three origins: Drummondville, McAllen and Joliet. They cover seven of the top ten lanes in the queue."
- "If we capture half of the queued leakage, that's **$5.2 million a year** and **6.7% off your cost per case**. Even the conservative case is $2.6 million."
- "We'll hold ourselves to clear criteria: **80% of queued lanes actioned within a week**, **at least 25% less leakage** on the pilot lanes, and a baseline Finance signs off on."
- "From you I need three things: **you as sponsor**, **read access to the production extracts**, and **one transportation planner and one supply planner for about two hours a week**."

**The ask (be direct, then stop talking):**
"Can we book the baseline workshop with Finance and Logistics for **next week**? I'd suggest Tuesday or Thursday."

**If they hesitate** ("We need to think about it" / "Budget is tight"):
"Understood. What would you need to see to be confident? We can start with just the baseline workshop. It costs a couple of hours and gives Finance a validated leakage number either way."

**Close:** summarise in one line: "So: $23.6M of hidden leakage, a 40-lane list your team can act on tomorrow, and a 90-day pilot to prove $5M a year. Next step is the workshop next week."

---

## Delivery checklist for the recording

- **Lead with the business outcome and the customer's KPIs** (cost per case, freight-to-sales, OOR rate), not product names. Mention Databricks features only on slide 3.
- **Quantify everything** and **pause for a beat after each big number** ($23.6M, $10.3M, $5.2M).
- **Speak to both personas:** dollars and P&L to the VP, workload and actionability to the Director.
- **Ask, then listen.** Use the check-in questions and acknowledge the answer before continuing ("That's helpful. That's exactly why…").
- **Handle objections calmly:** acknowledge → evidence → bridge back to the pilot.
- **Finish with a specific ask and date**, then stop talking.
- **Pace:** about 140 words per minute and about 5 minutes total. Cut filler words ("um", "so", "basically", "kind of"), and keep sentences short.
- **Be honest about the data:** if asked, say "this prototype uses a synthetic dataset modelled on a frozen-foods network; the pilot re-baselines on your real data."
