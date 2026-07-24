import Cinematic from "../../components/Cinematic.jsx";
import SignaturePane from "../../components/SignaturePane.jsx";
import PhonePreview from "../../components/PhonePreview.jsx";

// Screen 4 — Cinematic Effects. Colour grade, gradients, glow, vignette,
// grain, letterbox bars, plus the signature/watermark overlay — all the
// "extra visual enhancement" controls live here, away from the core caption
// styling on Screen 3.
export default function Screen4Effects({
  studio, language, media, sourceReady, aspect, fit, barText, signature, setSig, videoRef,
  onBack, onNext,
}) {
  return (
    <div className="wizard-screen">
      <div className="w3-grid">
        <div className="card w3-left">
          <div className="card-h"><h2>Cinematic effects</h2></div>
          <div className="studio-pane" style={{ padding: "16px 0 0" }}>
            <Cinematic cinematic={studio.cinematic} setCine={studio.setCine} resetCine={studio.resetCine} />
          </div>
          <div className="card-h" style={{ marginTop: 22 }}><h2>Signature / watermark</h2></div>
          <div className="studio-pane" style={{ padding: "16px 0 0" }}>
            <SignaturePane sig={signature} setSig={setSig} />
          </div>
        </div>

        <div className="w3-right">
          <PhonePreview cfg={studio.cfg} cinematic={studio.cinematic} language={language} media={media}
            preparing={!media && sourceReady} aspect={aspect} fit={fit} barText={barText}
            signature={signature} setSig={setSig} videoRef={videoRef}
            overrides={studio.overrides} setOverride={studio.setOverride} />
        </div>
      </div>

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn btn-primary" onClick={onNext}>Next →</button>
      </div>
    </div>
  );
}
