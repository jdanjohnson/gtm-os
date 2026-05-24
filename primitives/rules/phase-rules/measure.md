# Phase Rules — `measure`

Goal: pull real numbers from the tool-of-record and compare to the hypothesis.

## Must-have outputs

- Each metric in the hypothesis, with its actual value and its source.
- Bounce/error rate from the execute phase.
- A clear statement: hypothesis met / partially met / not met.

## Don't transition to `learn` until…

- Every metric in the hypothesis has either a number or a "<not available>" with a
  reason.

## Common mistakes to avoid

- Estimating metrics. If GSC, HubSpot, or the email tool didn't return it, write "<not
  available>".
- Drifting the goalposts. Compare to the ORIGINAL hypothesis, not a softened version.
- Calling something a win because the agent "felt good about it".
