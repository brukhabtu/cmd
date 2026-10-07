# How We (should) Use Story Points

Bruk Habtu, last updated Apr 22, 2026. Written as a wiki page for eBay Live.

A shared understanding for eBay Live. Story points are one of the most misused tools in agile practice - this is how we (should) use them, and why.

## A note on our starting point

A common convention - at eBay and elsewhere - is that one story point equals one day of work. This document is a deliberate departure from that convention. It's not a rejection of pointing itself, or of the hard work teams have put into their planning practices. It's an argument that the "points = days" shorthand throws away most of what makes story points useful, and that we can get more value out of the same ceremony by using them differently.

If you're reading this with "but 1 point = 1 day" in your head, that's the framing this document is in conversation with. Stick with it through the "What goes wrong when points equal days" section - that's where the specific failure modes of the current convention are laid out.

## What story points actually measure

A story point is an estimate of three things combined:

- **Complexity** - how intricate the work is, how many moving parts, how much interaction between components
- **Unknowns** - what we don't yet know about the problem, the domain, the tooling, or the integration surface
- **Risk** - what could go wrong, what external dependencies are in play, what failure modes are possible

This is the widely-accepted definition. Atlassian, Mountain Goat Software, and most mainstream agile sources agree: story points account for complexity, risk, and amount of work rather than hours or days, and they're a relative measure of effort, complexity, and uncertainty, not a proxy for time.

## Story points are not a measurement of time

This is the most important thing to internalize. A 5-pointer is not "five days." A 3-pointer is not "three days." Points and time are different units measuring different things.

Two stories with identical point estimates can take very different amounts of calendar time to finish. Two stories with very different point estimates can take the same amount of time. The popular teaching example: licking 1,000 stamps and performing a simple brain surgery take roughly the same time but are wildly different in complexity. Points capture the complexity-and-risk dimension; time is an output we observe, not an input we estimate.

The moment we equate points to days, the signal the points carry - complexity, unknowns, risk - collapses into a time commitment the team will then be graded on. That reliably corrupts the estimate.

## Why not just estimate time?

A reasonable question: if we ultimately care about whether work fits in a sprint, why not estimate hours or days directly? Because estimating time is actually harder than estimating points, and more prone to false precision.

**Time estimates demand information you don't have.** "Three days" requires predicting uninterrupted focus time, meeting load, incident risk, PR review queue speed, whether the person doing the work is senior or junior on the domain. None of that is about the work itself. Points sidestep all of it by asking a narrower, more answerable question: how complex and risky is this work, relative to other work we've done?

**Time estimates anchor to the estimator, not the work.** A senior's "three days" and a junior's "three days" are different measurements. Points are a team-level consensus about the work, which is stable regardless of who picks it up.

**Time estimates hide uncertainty inside a single number.** "Three days" doesn't tell you whether that's ±4 hours or ±2 weeks. Points - when we track the distribution of cycle times - make that uncertainty visible. An 8-pointer that historically swings from 4 days to 14 days carries its own honesty about how little we know.

**Time estimates invite false precision.** The moment we attach a time to a number, the brain slips into shortcuts that distort everything - a "three-day story" becomes an expectation rather than a relative measure. Points resist this. "Is it a 5 or an 8?" is a meaningful conversation about risk and complexity. "Is it 3 days or 4 days?" is noise.

## What goes wrong when points equal days

The "1 point = 1 day" convention feels harmless - it gives leadership something to plan against, and engineers a simple mental model. But it quietly eliminates most of what makes pointing valuable. Five specific failure modes, all of which are probably already happening:

1. **The estimate stops being an estimate.** When points are days, debating whether something is a 5 or an 8 is really just a negotiation about when it will be delivered. The complexity/risk conversation disappears because everyone is really arguing about commitment. The team loses the one thing pointing was supposed to create: a structured, shared conversation about what makes the work hard.

2. **Volatility becomes invisible.** When points are days, an 8-pointer is "eight days of work" and the team commits accordingly. The fact that 8-pointers historically swing from 4 to 14 days is information the system has thrown away. You can't see the range because you've collapsed it into a single number - and then you're surprised every time a story blows the sprint.

3. **Sandbagging and inflation are the stable equilibrium.** Engineers learn quickly that honest pointing gets them held to those numbers as deadlines, so they inflate. Leadership learns estimates are padded and discounts them. Both sides stop trusting the number. This is Goodhart's Law at work: when a measure becomes a target, it stops being a good measure. It's worst under the points-as-days convention because the number is directly interpretable as a commitment, so there's nowhere to hide honest uncertainty.

4. **Cross-team comparison becomes poisonous.** If every team treats 1 point as 1 day, point velocity becomes directly comparable across teams - exactly the thing points were designed to prevent. A team that points honestly (including risk and unknowns) looks slower than a team that points optimistically. The honest team gets punished; the optimistic team gets rewarded until they blow a deadline and everyone blames the engineers.

5. **The incentive to break work down disappears.** If points are days, there's no reason to split an 8-pointer into a 3, a 3, and a 2 - the "total time" looks the same. But as the distribution data shows, three small stories are dramatically more predictable than one big one. The points-as-days convention destroys the signal that should be pushing teams toward better practice: break work down, surface unknowns, protect the sprint.

The cost of all this is paid in missed commitments, blame cycles at retro, gradual erosion of trust in planning, and a team that spends more energy arguing about numbers than understanding work. The alternative isn't to stop pointing - it's to stop pretending the points are days.

## The real value is volatility, not the average

Over time, a team can derive an average cycle time for a given point value. After enough sprints, you'll probably see something like: "our 3-pointers average 2 days, our 5-pointers average 4 days." That's useful.

But the average is not the most valuable thing. The distribution is.

The reason: as stories get larger, the range of possible cycle times grows faster than the average does. A 3-pointer might land in 1-3 days almost every time - tight distribution, predictable. An 8-pointer might average 7 days but swing anywhere from 4 days to 14 days depending on which unknowns surface and how. Same average-to-points ratio; very different predictability.

It's the Cone of Uncertainty applied to story sizing. The variance in cycle time grows with story size - larger stories carry more variance, and more large stories in a sprint means more velocity variance and less reliable forecasting. It's why seasoned teams break work down aggressively: not because small stories are faster on average, but because small stories are more predictable.

So when I look at a story point estimate, the question I'm really asking is: how confident can we be that this will land inside the sprint? An 8-pointer that might take 14 days on a bad run is probably too volatile to bring into a two-week sprint, even if the average would fit. The risk of blowing the sprint is what matters, not the expected value. Here is an illustrative example:

<!-- The wiki page had an illustrative cycle-time distribution chart here. It was not saved with the text. -->

## What this means in practice

**At planning:**

- If a story lands at 8 or above, the default reflex should be to split it, not to bring it in. Large stories compound risk across the sprint.
- When we point, we discuss complexity, unknowns, and risk out loud - not "how many days." If someone asks "how long will this take?" the conversation should shift to "what makes this complex or risky, and can we reduce that first?"
- Spikes exist for a reason. If the unknowns dominate the estimate, the right move is often to spike first and estimate after.

**During the sprint:**

- A story stuck for longer than its size suggests is a signal that our unknowns were bigger than we thought. That's information, not failure. Surface it early.
- We don't re-estimate a story mid-sprint to "correct" the points. The original estimate captured what we knew at the time; the learning goes into better estimation next round.

**In retro:**

- Look at cycle time distribution per point size, not just averages. If our 5-pointers have a very wide range, something about how we size 5-pointers is broken - probably hidden unknowns.
- Stories that blew past their expected range are a goldmine for understanding what our estimates are missing.

## What story points are not for

- **Not a performance metric.** Measuring engineers on points delivered corrupts the estimate - teams inflate to hit targets, or sandbag to stay safe. This is Goodhart's Law in action: when a measure becomes a target, it ceases to be a good measure. We're evaluated on hitting the commitments we make together, not on raw point throughput.
- **Not comparable across teams.** Our 5 is not another team's 5. Points are a team-local unit of measure. Rolling them up across teams for "productivity" comparisons is meaningless.
- **Not a substitute for scoping.** Points don't replace understanding the work. They summarize a shared understanding we've already built through planning conversations.
- **Not a negotiation tool.** We don't adjust points because leadership wants more in the sprint. The points reflect the work; the sprint commitment reflects what we can responsibly take on.

## TL;DR

Story points estimate complexity, unknowns, and risk - not time. Their primary value is telling us how predictable a story's cycle time is likely to be, not what that cycle time will be. We use them to make sprint commitments we can actually hit, by keeping volatile work out of the sprint and breaking big work down before we commit to it.

## References

- Atlassian - overview of story points as a measure of complexity, risk, and effort
- Mike Cohn / Mountain Goat Software - argument for why risk and uncertainty belong in point estimates, not just complexity
- Liminal Arc - mathematical case that larger stories increase velocity variance and reduce predictability
- Zen Ex Machina - using cycle time distribution to validate whether point sizes are meaningful
- Agility at Scale - Goodhart's Law and the failure modes of treating velocity as a target
