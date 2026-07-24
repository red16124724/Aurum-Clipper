import Music from "../../components/Music.jsx";
import PhonePreview from "../../components/PhonePreview.jsx";

// Screen 5 — Background Music. Kept as its own step (separate from Effects)
// so each screen stays focused on one decision at a time.
export default function Screen5Music({
  tracks, musicTrack, musicVolume, musicDuck, musicStart, musicSuggest,
  onTrack, onVolume, onDuck, onStart, onMusicUpload, onRefreshMusic,
  studio, language, media, sourceReady, aspect, fit, barText, signature, setSig, videoRef,
  onBack, onNext,
}) {
  return (
    <div className="wizard-screen">
      <div className="w3-grid">
        <div className="w3-left">
          <Music tracks={tracks} track={musicTrack} volume={musicVolume} duck={musicDuck} musicStart={musicStart} suggest={musicSuggest}
            onTrack={onTrack} onVolume={onVolume} onDuck={onDuck} onStart={onStart}
            onUpload={onMusicUpload} onRefresh={onRefreshMusic} />
        </div>

        <div className="w3-right">
          <PhonePreview cfg={studio.cfg} cinematic={studio.cinematic} language={language} media={media}
            preparing={!media && sourceReady} aspect={aspect} fit={fit} barText={barText}
            signature={signature} setSig={setSig} videoRef={videoRef}
            overrides={studio.overrides} setOverride={studio.setOverride} />
        </div>
      </div>

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack}>← Back to effects</button>
        <button className="btn btn-primary" onClick={onNext}>Next →</button>
      </div>
    </div>
  );
}
