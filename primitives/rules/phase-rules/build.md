# Phase Rules — `build`

Goal: produce ship-ready assets that match the Brand voice and the play's structure.

## Must-have outputs

- All copy / scripts / content the play needs.
- For each personalization token, the source it pulls from.
- A `request_approval` call with the assets summarized.

## Don't transition to `execute` — ever.

The human transitions out of `build`. You stop after `request_approval`.

## Common mistakes to avoid

- Faking personalization. (If the token is "recent_post_title", you have to have
  actually pulled that post.)
- Drifting from the Brand voice. Re-read `brand/tone.yaml` before shipping.
- Sending the user the assets in chat without also storing them to checkpoint/memory.
