# HarborWise: 3-minute pitch script

About 430 words, which takes roughly 3 minutes at a calm pace. **Bold** marks a word to stress.

---

### Slide 1: HarborWise (0:00–0:15)
Hi, we’re HarborWise. Ships today rush to port, only to sit and wait. We built a system that tells a ship **when its berth will be free**, and **how fast to sail** to get there just in time.

### Slide 2: The problem (0:15–0:35)
Right now, a ship sails at full speed so it arrives as early as possible. But if the berth is still taken, it drops anchor and waits. When we replayed late 2019, **more than half** of arriving ships had to wait, about **fifteen and a half hours** on average. And nobody gives the captain a forecast of when the berth will actually free up.

### Slide 3: Why it matters (0:35–0:55)
That matters because fuel use climbs with the **cube** of speed. Sail just **10% slower**, and the trip uses about **19% less fuel**. Every tonne of fuel is about **three tonnes of CO₂**. So rushing in only to wait means paying twice: extra fuel to get there early, then time and money at anchor.

### Slide 4: The data (0:55–1:15)
We used a public dataset of every ship stop in the Caribbean and Gulf of Mexico in 2019: **one and a half million** port calls. Most are tugs and harbour craft, so we rebuilt real berth stays and focused on **container and cruise ships**, about **twenty-one thousand visits**. They run on schedules, so they’re predictable. Tankers and bulk carriers still get a model, but we label it lower confidence.

### Slide 5: How it works (1:15–1:45)
It works in four steps. **One**, we see which ships are at the berth and how long they’ve been there. **Two**, gradient-boosted models forecast when the berth frees, as a range, not a single guess. They use time already alongside, the ship’s own past stays, how busy the port is, and even tugs arriving, using **only what’s known at that moment**. **Three**, we test every speed and weigh fuel, the ship’s time, and the risk of the berth sitting empty. **Four**, the captain gets a speed, an arrival time, the expected wait, and the fuel and CO₂ saved.

### Slide 6: Model results (1:45–2:10)
Does it work? For container and cruise ships, our best model is off by about **5.2 hours**. Using the port’s usual time is off by 7.1, so we’re **26% more accurate**. Cruise ships are the standout: **more than half** are predicted within an hour. And our ranges are honest: when we say there’s a 90% chance the berth is free, it was free **89%** of the time. All of this was tested on two months the model never saw.

### Slide 7: Impact (2:10–2:35)
In a replay of real berth traffic, HarborWise cut waiting at anchor by **21%**. Per arrival, it saved about **three tonnes of fuel**, **nine tonnes of CO₂**, and about **$1,550**, even after charging for arriving a little later. That’s about **half** of what a perfect forecast could save. These are simulated savings, not measured ones.

### Slide 8: Limits and next steps (2:35–3:00)
We want to be upfront: real anchorage waits and cargo plans aren’t in public data, and tankers and bulk carriers are harder to predict. Next, we’d add port schedules, a live ship-tracking feed, and a pilot with one container or cruise terminal.

**HarborWise: arrive when the berth is ready.** Thank you.

---

## Likely judge questions

| Question | Answer |
|---|---|
| Why not under an hour of error? | Departure depends on cargo and crane plans that aren’t in public data. Cruise ships, which keep timetables, already get under an hour for more than half of arrivals. |
| Are the savings real? | They’re simulated with estimated engine figures. The next step is to confirm them with real fuel logs. |
| Does it work in new ports? | For container and cruise ships, yes: 12.4 h average error against 15.4 h for the baseline in ports held out of training. |
| How do you avoid cheating with future data? | Every feature uses only what was observable at prediction time, and automated tests check that. |
