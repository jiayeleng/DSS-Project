import { useState } from "react";
import NextButton from "./NextButton";
import ManifestationScene from "./ManifestationScene";
import PoemScene from "./PoemScene";
import SceneBackground from "./SceneBackground";
import HomeButton from "./HomeButton";

const SCENES = [ManifestationScene, PoemScene];

export default function OpeningScreen({ onNext, onHome }) {
  const [scene, setScene] = useState(0);

  function handleNext() {
    if (scene < SCENES.length - 1) {
      setScene((s) => s + 1);
    } else {
      onNext();
    }
  }

  return (
    <div className="screen opening-screen">
      {/* background layers — stay mounted throughout all scenes */}
      <div className="opening-bg" />
      <SceneBackground />

      {/* persistent HUD */}
      <HomeButton onClick={onHome} />
      <div className="q-hud q-hud--tr">
        <span className="q-hud-label">DSS</span>
        <span className="q-hud-dot" />
      </div>

      {/* one scene visible at a time via explicit conditional */}
      {SCENES.map((Scene, i) =>
        i === scene ? (
          <div className="opening-scene" key={i}>
            <Scene />
          </div>
        ) : null
      )}

      <div className="screen-next" key={scene}>
        <NextButton onClick={handleNext} />
      </div>
    </div>
  );
}
