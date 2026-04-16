import SceneBackground from "./SceneBackground";
import HomeButton from "./HomeButton";

export default function QuestionScreen({
  question,
  options,
  onAnswer,
  onHome,
  questionNumber,
  totalQuestions,
}) {
  return (
    <div className="screen question-screen">
      <SceneBackground />

      {/* HUD corners */}
      <HomeButton onClick={onHome} />
      <div className="q-hud q-hud--tr">
        <span className="q-hud-label">DSS</span>
        <span className="q-hud-dot" />
      </div>
      <div className="q-hud q-hud--br">
        <span className="q-hud-square" />
      </div>

      {/* Central visual — swap per question later */}
      <div className="q-visual">
        <video
          className="q-visual-video"
          src="/assets/question_video_sample.mp4"
          autoPlay
          loop
          muted
          playsInline
        />
      </div>

      {/* Bottom panel */}
      <div className="q-panel">
        <div className="q-panel-inner">
          <p className="question-meta">
            {questionNumber} / {totalQuestions}
          </p>
          <p className="q-question">{question}</p>
          <div className="q-options">
            {options.map((option) => (
              <button
                key={option.value}
                className="q-option"
                onClick={() => onAnswer(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
