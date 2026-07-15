import { registerRoot, Composition } from "remotion";
import { CaptionDemo } from "./CaptionDemo.jsx";

export const RemotionRoot = () => (
  <Composition
    id="CaptionDemo"
    component={CaptionDemo}
    durationInFrames={90}
    fps={30}
    width={1080}
    height={1920}
  />
);

registerRoot(RemotionRoot);
