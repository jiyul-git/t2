# Bounded stream writes and B33 review

## Confirmed transport defect

The v85 progress mailbox publishes an event before writing it to the stream,
but the socket had no write timeout. A reader that stops consuming can block
the gameplay thread indefinitely at `wfile.write` or `flush`. Later events,
the final state and release of the gameplay lock then never occur.

`verify_stream_write_timeout.py` fills a real socket pair without consuming
from its peer. Before this change it fails with `stalled socket write still
blocks gameplay`. After this change stream headers and writes have a two-second
socket timeout. Transport failure does not cancel the engine action; messages
continue to be published to the progress mailbox. The existing client can
recover through progress or its state refresh without reposting the action.

This reproduces a transport defect. It does **not** establish that it caused
the 25-second interval in the 13:52 Samsung Browser recording. Intended bot
deadlines and CPU time must still be compared with the production hand trace.

## B33: profile reproduction, not a production snapshot

The recording and public archive show HERO HAND 32, SB B33 with Qh Tc:
raise 2300 preflop, bet 2600 into 5400 on 3d 5c 2c, call HERO's raise to
7900, then check both 9c turn and 9s river. The extra call is 5300 and
the final flop pot is 21200 (25% immediate pot odds).

The scheduled initial field uses a deterministic seed derived from event ID
`standard:1791518400` (2026-10-09 13:00 KST), seed `1532363101`, 99 bots,
hero_pid=-1. The current test3 generation path reproduces this initial B33:

* temper: aggression 3.3, looseness 5.9, gamble 1.6, discipline 6.2,
  consistency 4.6, attention 0.1, adaptability 3.4 (0–10 scales).
* concepts: cbet_flop 5.8, barrel_turn 2.1, barrel_river 3.4,
  potcontrol 6.9, outs 7.3, potodds 6.8, range_read 6.5,
  range_reconstruction 7.6, line_interpretation 4.6,
  bluffcatch_flop 6.2, blocker 2.6.
* derived label STUDIED_TAG; overall_skill rounded to 4.8.

These are reconstructed **initial** values, conditional on the operating
server using the same profile-generation code/rules. They are not a read of
the archived production profile or its tilt-adjusted decision values.
Low gamble and adequate discipline do not support attributing the call to
recklessness without its trace. Low attention is a candidate, not a finding.
No strategic coefficients or persona values are changed by this patch.

## Verification and deployment

Bounded socket/header test, progress HTTP retention/presence test, client
blocked-header/de-duplication test and existing resume/zero-bank tests pass.
The server source compiles. Production deployment remains pending SSH login.
