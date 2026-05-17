"use client";

import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { useWavesurfer } from "@wavesurfer/react";
import { apiUrl } from "../../../lib/api";

// Distinct waveform/UI colour per speaker — 6 colours cycle, since
// Speechmatics rarely produces more than that on an earnings call.
const SPEAKER_COLORS = [
  "#22C55E", // S1 — host
  "#60A5FA", // S2
  "#F472B6",
  "#FBBF24",
  "#A78BFA",
  "#F87171",
];

function speakerColor(label) {
  if (!label) return SPEAKER_COLORS[0];
  const n = parseInt(String(label).replace(/^S/i, ""), 10);
  if (!Number.isFinite(n)) return SPEAKER_COLORS[0];
  return SPEAKER_COLORS[(n - 1) % SPEAKER_COLORS.length];
}

// Tier label → short badge text + accent class for the provenance header.
//
// T1 was previously labelled "Verified primary", which overstated what
// the system actually checks: a token-overlap between the YouTube
// uploader name and the issuer name. The system does NOT confirm
// YouTube's verified-channel checkmark or any cryptographic identity.
// Renamed to "Issuer-named" to avoid implying verification we cannot
// back up.
//
// T4 was previously rendered in a MUTED foreground/15 color, which
// inverted the warning semantics — the LEAST trustworthy tier looked
// the calmest on the dashboard. Now uses the destructive accent so the
// user sees the warning at a glance.
const TIER_BADGE = {
  T1_verified_primary:    { short: "T1", text: "Issuer-named",         accent: "bg-accent/20 text-accent border-accent/40" },
  T2_trusted_aggregator:  { short: "T2", text: "Trusted aggregator",   accent: "bg-sky-500/20 text-sky-300 border-sky-500/40" },
  T3_editorial_aggregator:{ short: "T3", text: "Editorial aggregator", accent: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40" },
  T4_unverified:          { short: "T4", text: "Unverified",            accent: "bg-destructive/20 text-destructive border-destructive/50" },
};

// Reject URLs that are not http(s) — defence-in-depth against a poisoned
// yt-dlp result containing `javascript:` or `data:` schemes that React
// would otherwise pass through into `<a href>`.
function safeHref(url) {
  if (typeof url !== "string") return null;
  if (!/^https?:\/\//i.test(url)) return null;
  return url;
}

const TranscriptPlayer = forwardRef(function TranscriptPlayer(
  { ticker, words, audioSource },
  ref
) {
  const containerRef = useRef(null);
  const audioUrl = apiUrl(`/api/research/${ticker}/audio`);
  const badge = audioSource?.tier ? TIER_BADGE[audioSource.tier] : null;

  const { wavesurfer, isReady, isPlaying, currentTime } = useWavesurfer({
    container: containerRef,
    url: audioUrl,
    waveColor: "rgba(248, 250, 252, 0.25)",
    progressColor: "var(--color-accent, #22C55E)",
    cursorColor: "var(--color-accent, #22C55E)",
    barWidth: 2,
    barRadius: 2,
    barGap: 1,
    height: 64,
    normalize: true,
  });

  const [activeIdx, setActiveIdx] = useState(-1);
  const wordRefs = useRef([]);
  const scrollBoxRef = useRef(null);

  // Build a sorted list of {start_time, idx} for binary-search lookups —
  // 10k words means re-scanning every frame is wasteful.
  const timeIndex = useMemo(() => {
    return words
      .filter((w) => typeof w.start_time === "number")
      .map((w) => ({ t: w.start_time, idx: w.idx }))
      .sort((a, b) => a.t - b.t);
  }, [words]);

  // Find the word whose start_time is just before currentTime.
  useEffect(() => {
    if (!isReady || !timeIndex.length) return;
    let lo = 0;
    let hi = timeIndex.length - 1;
    let best = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (timeIndex[mid].t <= currentTime) {
        best = timeIndex[mid].idx;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    if (best !== activeIdx) {
      setActiveIdx(best);
      const el = wordRefs.current[best];
      if (el && scrollBoxRef.current) {
        const box = scrollBoxRef.current.getBoundingClientRect();
        const rect = el.getBoundingClientRect();
        if (rect.top < box.top + 40 || rect.bottom > box.bottom - 40) {
          el.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
    }
  }, [currentTime, isReady, timeIndex, activeIdx]);

  function onPlay() {
    if (!wavesurfer) return;
    wavesurfer.playPause();
  }

  function seek(word) {
    if (!wavesurfer || typeof word.start_time !== "number") return;
    const dur = wavesurfer.getDuration();
    if (!dur) return;
    wavesurfer.setTime(Math.max(0, word.start_time - 0.05));
    if (!isPlaying) wavesurfer.play();
  }

  // When the claim-chip seek arrives before wavesurfer has loaded the
  // audio (judges click within the first ~600ms), queue the request and
  // apply it as soon as isReady flips true. Cleared after one apply so a
  // late-mount doesn't yank the user away from a position they have
  // since changed by hand.
  const pendingSeekRef = useRef(null);
  useEffect(() => {
    if (!isReady || !wavesurfer || pendingSeekRef.current === null) return;
    const t = pendingSeekRef.current;
    pendingSeekRef.current = null;
    if (!wavesurfer.getDuration?.()) return;
    wavesurfer.setTime(Math.max(0, t - 0.05));
    wavesurfer.play?.();
  }, [isReady, wavesurfer]);

  useImperativeHandle(
    ref,
    () => ({
      seek(seconds, { autoplay = true } = {}) {
        if (typeof seconds !== "number" || !Number.isFinite(seconds)) return;
        if (!wavesurfer || !wavesurfer.getDuration?.()) {
          pendingSeekRef.current = seconds;
          return;
        }
        wavesurfer.setTime(Math.max(0, seconds - 0.05));
        if (autoplay && !isPlaying) wavesurfer.play?.();
      },
      play() {
        if (!wavesurfer || isPlaying) return;
        wavesurfer.play?.();
      },
    }),
    [wavesurfer, isPlaying]
  );

  // Group adjacent words by speaker into paragraphs for readability.
  const paragraphs = useMemo(() => groupBySpeaker(words), [words]);

  return (
    <div className="space-y-4">
      {audioSource ? (
        <div className="rounded-md border border-border/40 bg-background/30 px-4 py-3 text-xs font-mono">
          <div className="flex flex-wrap items-center gap-2 text-foreground/70">
            <span className="uppercase tracking-[0.25em] text-foreground/40">Source</span>
            {(() => {
              const href = safeHref(audioSource.url);
              return href ? (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-foreground hover:text-accent"
                >
                  {audioSource.uploader || href}
                </a>
              ) : (
                <span className="font-semibold text-foreground">{audioSource.uploader}</span>
              );
            })()}
            {badge ? (
              <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${badge.accent}`}>
                {badge.short} · {badge.text}
              </span>
            ) : null}
            {typeof audioSource.score === "number" ? (
              <span className="text-foreground/45">score {audioSource.score}</span>
            ) : null}
            {audioSource.candidates_considered?.length ? (
              <span className="text-foreground/45">
                · {audioSource.candidates_considered.length} candidate{audioSource.candidates_considered.length === 1 ? "" : "s"} considered
              </span>
            ) : null}
          </div>
          {audioSource.title ? (
            <p className="mt-1 text-foreground/55">{audioSource.title}</p>
          ) : null}
        </div>
      ) : null}
      <div className="rounded-md border border-border/40 bg-background/40 p-3">
        <div ref={containerRef} className="w-full" />
        <div className="mt-3 flex items-center justify-between">
          <button
            onClick={onPlay}
            disabled={!isReady}
            className="rounded-md border border-accent/50 bg-accent/15 px-4 py-1.5 font-mono text-sm font-semibold text-accent hover:bg-accent/25 disabled:opacity-40"
          >
            {isPlaying ? "❚❚ pause" : "▶ play"}
          </button>
          <span className="font-mono text-xs text-foreground/60">
            {fmt(currentTime)} {isReady && wavesurfer ? `/ ${fmt(wavesurfer.getDuration())}` : ""}
          </span>
        </div>
      </div>

      <div
        ref={scrollBoxRef}
        className="max-h-[420px] overflow-y-auto rounded-md border border-border/40 bg-background/30 p-4 font-mono text-[13px] leading-relaxed"
      >
        {paragraphs.map((para, pi) => (
          <p key={pi} className="mb-4">
            <span
              className="mr-2 inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.2em]"
              style={{
                color: speakerColor(para.speaker),
                background: `${speakerColor(para.speaker)}1f`,
                border: `1px solid ${speakerColor(para.speaker)}40`,
              }}
            >
              {para.speaker} · {fmt(para.start_time)}
            </span>
            {para.words.map((w) => {
              const isActive = w.idx === activeIdx;
              const isPunct = w.type === "punctuation";
              return (
                <span
                  key={w.idx}
                  ref={(el) => (wordRefs.current[w.idx] = el)}
                  onClick={() => !isPunct && seek(w)}
                  className={
                    isPunct
                      ? "text-foreground/70"
                      : `cursor-pointer rounded px-0.5 transition-colors ${
                          isActive
                            ? "bg-accent/30 text-foreground"
                            : "text-foreground/75 hover:bg-accent/15 hover:text-foreground"
                        }`
                  }
                >
                  {isPunct ? w.content : ` ${w.content}`}
                </span>
              );
            })}
          </p>
        ))}
      </div>
    </div>
  );
});

export default TranscriptPlayer;

function groupBySpeaker(words) {
  const out = [];
  let current = null;
  for (const w of words) {
    if (!current || current.speaker !== w.speaker) {
      current = {
        speaker: w.speaker,
        start_time: w.start_time,
        words: [],
      };
      out.push(current);
    }
    current.words.push(w);
  }
  return out;
}

function fmt(t) {
  if (!Number.isFinite(t)) return "0:00";
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
