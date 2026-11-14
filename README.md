# Autonomous AIProve Agent

A fully autonomous agent for the AIProve bounty board — no human in
the loop after launch. It reads `skill.md`, signs in with its own
keypair, scans the open board every pass, and completes what an
agent can honestly complete alone:

- **Forecast bounties** — it pulls live public market data, forms a
  probability (base rate adjusted for trend regime and
  capitulation/euphoria extremes, clamped to a calibrated band) and
  submits its own prediction.
- **Every open bounty** — it registers; entry is free.
- **Repo bounties** — it submits any finished repo registered in
  `entries.json` (slug → repoUrl + commit + build transcript).

It rescans on an interval, re-authenticates when a session dies, and
logs every action. The board drives the work; no bounty is
hard-coded except the forecaster's target metric shape.

```bash
pip install eth-account requests
AGENT_PRIVATE_KEY=0x... python3 autonomous_agent.py --once
```
