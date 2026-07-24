import { Icons } from "../../components/Icons.jsx";
import ClipPhone from "../../components/ClipPhone.jsx";

// Screen 6 — Final Export. Reframe already re-renders each clip immediately,
// so there's no heavy render pass left here — just a wrap-up summary of the
// finished clips (with a proper download/copy-link) and a way to start over.
export default function Screen6Export({ clips, onBack, onRestart }) {
  function downloadAll() {
    clips.forEach((c, i) => {
      setTimeout(() => {
        const a = document.createElement("a");
        a.href = c.url; a.download = c.filename || `clip-${i + 1}.mp4`;
        document.body.appendChild(a); a.click(); a.remove();
      }, i * 400);
    });
  }

  return (
    <div className="wizard-screen">
      <div className="card">
        <div className="card-h">
          <h2>All done — {clips.length} clip{clips.length === 1 ? "" : "s"} ready</h2>
          <button className="btn btn-primary" onClick={downloadAll}><Icons.download /> Download all</button>
        </div>
        <div className="clips">
          {clips.map((c) => (
            <div className="clip" key={c.index}>
              <ClipPhone src={c.url} filename={c.filename} />
              <div className="meta">
                <h3>{c.title}</h3>
                <div className="sub">{(c.end - c.start).toFixed(1)}s · {c.start.toFixed(1)}–{c.end.toFixed(1)}s</div>
                <div className="acts">
                  <a href={c.url} download={c.filename || ""}>Download</a>
                  <button onClick={() => navigator.clipboard.writeText(location.origin + c.url)}><Icons.link /> Copy link</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack}>← Back to review</button>
        <button className="btn btn-primary" onClick={onRestart}><Icons.bolt /> Create another video</button>
      </div>
    </div>
  );
}
