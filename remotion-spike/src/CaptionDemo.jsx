import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";

// Mirrors web/src/caption.js's captionSample("en") + PhonePreview.jsx's
// "highlight" animation — same word list, same highlight logic, same bottom
// gradient math as app/effects.py's _gradient_bands (bottom_gradient effect).
// The point of this spike: this ONE component is what both the in-app
// <Player> preview and `remotion render` would consume — there is no second
// implementation to drift out of sync with.
const WORDS = ["Make", "it", "go", "viral"];
const HIGHLIGHT_IDX = 3;
const MS_PER_WORD = 620;

function activeWordIndex(frameMs) {
  return Math.floor(frameMs / MS_PER_WORD) % WORDS.length;
}

export function CaptionDemo() {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const active = activeWordIndex(ms);

  // Bottom gradient scrim — same shape as effects.py's bottom_gradient (a dark
  // scrim rising from the bottom, for caption legibility), authored once here
  // as a CSS gradient instead of ffmpeg drawbox bands.
  const gradientHeightPct = 35;
  const gradientStrength = 0.75;

  // Glow — a soft bloom pulsing behind the active word, standing in for
  // effects.py's highlight-bloom. Driven by the SAME frame clock as the
  // caption animation, which is the property that's impossible to guarantee
  // when preview (CSS) and export (ffmpeg) are two separate implementations.
  const glowPulse = interpolate(ms % 1200, [0, 600, 1200], [0.35, 0.85, 0.35]);

  return (
    <AbsoluteFill style={{ background: "linear-gradient(160deg, #0b0c0e 0%, #16181c 100%)" }}>
      <AbsoluteFill
        style={{
          background: `linear-gradient(to top, rgba(0,0,0,${gradientStrength}), rgba(0,0,0,0) ${gradientHeightPct}%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0, right: 0, top: height * 0.42,
          display: "flex", justifyContent: "center", gap: 14,
          fontFamily: "system-ui, sans-serif", fontWeight: 800,
          fontSize: width * 0.09, textShadow: "0 3px 10px rgba(0,0,0,.6)",
        }}
      >
        {WORDS.map((w, i) => (
          <span
            key={w}
            style={{
              color: i === active ? "#caff33" : "#ffffff",
              filter: i === active ? `drop-shadow(0 0 ${18 * glowPulse}px rgba(202,255,51,${glowPulse}))` : "none",
              transition: "none",
            }}
          >
            {i === HIGHLIGHT_IDX ? w : w}
          </span>
        ))}
      </div>
      <div
        style={{
          position: "absolute", left: 24, bottom: 24, color: "rgba(255,255,255,.55)",
          fontFamily: "ui-monospace, monospace", fontSize: 16,
        }}
      >
        frame {frame} · {ms.toFixed(0)}ms
      </div>
    </AbsoluteFill>
  );
}
