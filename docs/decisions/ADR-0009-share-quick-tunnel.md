# ADR-0009: Share the live slide with students over a Cloudflare quick tunnel
Status: accepted (2026-10-06, user decision; verify round 4 step D)

**Context.** Students should be able to follow the live slide on their own devices, also outside the classroom
network. The app runs on the teacher's laptop (`127.0.0.1:8765`); no server, account or paid service is allowed.

**Decision.** `cloudflared tunnel --url http://127.0.0.1:<port>` (Cloudflare "quick tunnel": free, no account, a random
`https://….trycloudflare.com` address per run), started from /control (**Share with students**) by
`display/share.py`; the binary is downloaded once into `data/bin/` from Cloudflare's GitHub release. Students get
`/view` (viewer role: slides only, sends nothing). The tunnel's requests arrive from 127.0.0.1, so the server treats a
request as the teacher's only when it is from loopback, addressed to localhost and carries no proxy headers; every
other request needs a per-run teacher key (cookie, set by `/control?key=…` printed in the terminal) for `/control`,
`/display`, uploads and the control/display WebSocket roles.

**Consequences.** + Works through school NAT/firewalls; nothing to configure; stops with the lecture. − Quick tunnels
have no uptime guarantee and a new address each time (fine for one lecture); the slides pass through Cloudflare. A new
address must not be looked up through this computer's resolver before it exists (the "no such name" answer is cached
for minutes): the service waits for cloudflared's "Registered tunnel connection" and checks the name over
DNS-over-HTTPS before showing the link (runtime check 2026-10-06).
