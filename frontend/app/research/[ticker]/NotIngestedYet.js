"use client";

import { useState } from "react";
import Link from "next/link";
import { startResearch } from "../../../lib/api";
import ProgressModal from "../../components/ProgressModal";

const TICKER_RE = /^[A-Za-z0-9]{1,6}$/;
// Heuristic for obviously-fake tickers (all same character, contains forbidden
// SEC patterns). Doesn't replace a real EDGAR allowlist but catches the most
// common fat-finger / demo-typo failure mode without paying the price of
// shipping the 11k-entry SEC ticker list to the client.
const JUNK_RE = /^(.)\1{1,}$|^(XXX|ZZZ|TEST|AAAA|JUNK|NULL)/i;

export default function NotIngestedYet({ ticker }) {
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [confirmed, setConfirmed] = useState(false);

  const valid = TICKER_RE.test(ticker);
  const looksJunk = valid && JUNK_RE.test(ticker || "");

  const launch = async () => {
    if (!valid) {
      setError(`'${ticker}' is not a valid ticker. Expected 1–6 letters or digits (e.g. NVDA).`);
      return;
    }
    if (looksJunk && !confirmed) {
      setError(
        `'${ticker}' looks like a placeholder, not a real ticker. Running the pipeline still spends API credits. Click "Run anyway" to confirm.`
      );
      setConfirmed(true);
      return;
    }
    setError(null);
    try {
      const res = await startResearch(ticker);
      setRun({ ticker, runId: res.run_id, cached: !!res.cached });
    } catch (err) {
      setError(`Backend rejected the request: ${err.message || err}`);
    }
  };

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
      <p className="font-mono text-xs uppercase tracking-[0.4em] text-foreground/40">
        No cached diligence for
      </p>
      <h1 className="mt-3 font-display text-5xl font-black tracking-tight sm:text-6xl">
        {ticker}
      </h1>
      <p className="mt-5 max-w-xl text-center font-mono text-sm text-foreground/70">
        The pipeline has not run on this ticker yet. Kick it off now — fetch
        the 10-K, 10-Q, fundamentals, autonomously pick the earnings-call
        audio, then run five adversarial agents. About six minutes end-to-end.
      </p>

      {!valid ? (
        <p className="mt-4 font-mono text-xs text-destructive">
          {`'${ticker}' doesn’t look like a valid ticker. Expected 1–6 letters or digits.`}
        </p>
      ) : null}

      {valid && looksJunk ? (
        <p className="mt-4 max-w-md text-center font-mono text-xs text-yellow-300">
          ⚠ &apos;{ticker}&apos; looks like a placeholder — running the
          pipeline still spends real API credits.
        </p>
      ) : null}

      <button
        type="button"
        onClick={launch}
        disabled={!valid}
        className={`mt-7 inline-flex h-12 items-center justify-center rounded-md px-6 font-mono text-sm font-semibold tracking-wide text-background transition-all duration-200 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50 ${
          looksJunk && !confirmed
            ? "bg-yellow-500 text-background"
            : "bg-accent"
        }`}
      >
        {looksJunk && !confirmed
          ? `Run anyway on ${ticker}`
          : `Run diligence on ${ticker}`}
      </button>

      {error ? (
        <p className="mt-4 font-mono text-xs text-destructive">{error}</p>
      ) : null}

      <Link
        href="/"
        className="mt-10 font-mono text-xs uppercase tracking-[0.3em] text-foreground/45 hover:text-foreground"
      >
        ← back home
      </Link>

      {run ? (
        <ProgressModal
          ticker={run.ticker}
          runId={run.runId}
          cached={run.cached}
          onClose={() => setRun(null)}
        />
      ) : null}
    </main>
  );
}
