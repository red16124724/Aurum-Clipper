// A lightweight phone-frame chrome around an ALREADY-RENDERED clip. Unlike
// PhonePreview (which composites a live, still-editable look), the clip file
// here already has its captions/effects/crop baked in — so this just plays
// it back inside the same phone bezel for a consistent look across screens.
export default function ClipPhone({ src, filename }) {
  return (
    <div className="phone clip-phone">
      <div className="phone-screen">
        <div className="island" />
        <video src={src} controls preload="metadata" playsInline title={filename} />
      </div>
    </div>
  );
}
