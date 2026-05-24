# Phase Rules — `execute`

Goal: send the assets to the list, respecting channel rules and rate limits, and log
everything so `measure` has clean data.

## Must-have outputs

- Sends recorded with timestamps, recipient ID (NOT raw email), result (sent / bounced /
  failed).
- After the batch is done, a one-paragraph summary memory: "Sent N / target. K bounces.
  J replies in the first 24h. Notable patterns: …".

## Don't transition to `measure` until…

- The full target volume has been sent (or you've hit a stop condition).
- Outcomes from the first N hours have been captured.

## Common mistakes to avoid

- Sending without an answered `request_approval`.
- Exceeding channel rate limits in `channel-rules/`.
- Retrying after a hard failure (e.g. 5xx from the email provider) without backing off
  and notifying.
- Storing raw PII in memory.
