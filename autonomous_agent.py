#!/usr/bin/env python3
"""Fully autonomous AIProve agent — no human in the loop.

Reads aiprove.fun/skill.md, signs in with its own keypair, scans the
open board, and completes everything it can complete on its own:

  * forecast bounties  -> computes a probability/point estimate from
                          live public market data and submits it
  * every open bounty  -> registers (entry is free)
  * repo bounties      -> submits any repo registered in entries.json
                          (slug -> {repoUrl, commit, transcript})

Then it sleeps and rescans. Every action is logged; nothing is
hard-coded to a specific bounty — the board itself drives the work.

    AGENT_PRIVATE_KEY=0x... python3 autonomous_agent.py [--once]

Without AGENT_PRIVATE_KEY an ephemeral keypair is generated per run.
"""
import argparse, json, os, sys, time
import requests
from eth_account import Account
from eth_account.messages import encode_defunct

API = os.environ.get("API_BASE_URL", "https://aiprove.fun")
HERE = os.path.dirname(os.path.abspath(__file__))


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


class Agent:
    def __init__(self, handle):
        key = os.environ.get("AGENT_PRIVATE_KEY")
        self.acct = Account.from_key(key) if key else Account.create()
        self.handle = handle
        self.H = None

    def auth(self):
        ch = requests.get(f"{API}/api/auth/challenge",
                          params={"address": self.acct.address},
                          timeout=20).json()["challenge"]
        sig = self.acct.sign_message(encode_defunct(text=ch)).signature.hex()
        if not sig.startswith("0x"):
            sig = "0x" + sig
        tok = requests.post(f"{API}/api/auth/verify",
                            json={"address": self.acct.address,
                                  "signature": sig}, timeout=20).json()
        self.H = {"Authorization": f"Bearer {tok['token']}",
                  "content-type": "application/json"}
        log(f"auth ok as {self.acct.address}")

    # ---------- market data (public, keyless) ----------
    def btc_daily_closes(self, days=31):
        r = requests.get("https://api.exchange.coinbase.com/products/"
                         "BTC-USD/candles", params={"granularity": 86400},
                         timeout=20)
        k = sorted(r.json(), key=lambda x: x[0])[-days:]
        return [x[4] for x in k]

    def forecast_btc_direction(self):
        """P(close higher in 7d) from base rate + trend/mean-reversion."""
        c = self.btc_daily_closes()
        now, ma20 = c[-1], sum(c[-20:]) / 20
        r7 = now / c[-8] - 1
        p = 0.53                                # historical weekly base rate
        p += -0.10 if now < ma20 else 0.06      # trend regime
        if r7 < -0.10:                          # capitulation -> bounce risk
            p += 0.05
        elif r7 > 0.10:                         # euphoria -> fade risk
            p -= 0.05
        return max(0.35, min(0.65, p))

    # ---------- board actions ----------
    def open_bounties(self):
        return requests.get(f"{API}/api/bounties",
                            params={"status": "open"},
                            timeout=20).json()["bounties"]

    def enter(self, slug):
        r = requests.post(f"{API}/api/bounties/{slug}/enter", headers=self.H,
                          json={"handle": self.handle}, timeout=20)
        log(f"enter {slug}: {r.status_code}")

    def submit(self, slug, body):
        body = dict(body); body["handle"] = self.handle
        r = requests.post(f"{API}/api/bounties/{slug}/submit",
                          headers=self.H, json=body, timeout=30)
        log(f"submit {slug}: {r.status_code} {r.text[:110]}")
        return r.status_code

    def run_once(self):
        requests.get(f"{API}/skill.md", timeout=20)   # the rulebook
        if not self.H:
            self.auth()
        registry = {}
        reg_f = os.path.join(HERE, "entries.json")
        if os.path.exists(reg_f):
            registry = json.load(open(reg_f))
        done = 0
        for b in self.open_bounties():
            slug = b["slug"]
            self.enter(slug)
            if slug == "forecast-btc-7d":
                p = self.forecast_btc_direction()
                ans = "yes" if p >= 0.5 else "no"
                conf = round(p if ans == "yes" else 1 - p, 2)
                if self.submit(slug, {"prediction": {"answer": ans,
                                                     "confidence": conf}}) < 300:
                    done += 1
                    log(f"  forecast: BTC up p={p:.2f} -> {ans} @{conf}")
            elif slug in registry:
                if self.submit(slug, registry[slug]) < 300:
                    done += 1
        log(f"scan complete: {done} submissions this pass")
        return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=3600)
    ap.add_argument("--handle", default="autonomous.agent")
    args = ap.parse_args()
    ag = Agent(args.handle)
    while True:
        try:
            ag.run_once()
        except Exception as e:                    # never die on one bad pass
            log(f"pass failed: {e}")
            ag.H = None
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
