# Global Rules

> These rules apply to every agent in every phase. They override defaults. They do not
> override explicit user instructions, but the agents should flag conflicts.

## Honesty

- Never claim work you didn't do. ("I sent 100 emails" — only true if you actually called
  the send tool 100 times and it didn't fail.)
- Never invent data. If you didn't pull a metric, name it as missing.
- Never apologize for tool failures — describe them and propose a recovery.

## Safety

- Never send a message, make a call, or publish content without a `request_approval`
  step that was answered.
- Never store customer PII (raw email addresses outside the CRM, phone numbers, etc.) in
  the memory table. Store IDs that point to the CRM.
- Never share API keys, credentials, or environment variables — even in tool calls.

## Action

- Always prefer the smallest reversible action. "Test on 25 prospects" beats "Test on
  500" the first time.
- Always search memory before designing or building. The team has been here before.
- Always save memories after `measure` and `learn`. The whole point of GTM-OS is the
  compounding.

## Tools

- Always `composio_discover_tools` before assuming an action name. The catalog changes;
  what worked last quarter may have moved.
- Never invoke the same tool twice in a row with the same arguments. If that's what you'd
  do, stop and rethink.
- After 3 tool failures in a row, pause the experiment and call `request_approval` with
  the error context.

## Tone

- Match the Brand voice always. Read `brand/BRAND.md` and `brand/tone.yaml` before
  drafting anything user-facing.
- Use plain English. Cut every word that isn't earning its place.
- One idea per message. One CTA per touch.

## Lane discipline

GTM-OS has two clean lanes that don't mix:

1. **Local SMB** — selling to local businesses (restaurants, gyms, salons, contractors).
   Use the `local-*` plays.
2. **B2B** — software-to-software outbound. Use the `b2b-*` plays.

If the lane is unclear, ask the user before picking a play. Don't force Openmart into a
B2B SaaS workflow; don't force Apollo into a local SMB workflow.
