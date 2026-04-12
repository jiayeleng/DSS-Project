import { useMemo, useState } from "react";
import SplashScreen from "./components/SplashScreen";
import OpeningScreen from "./components/OpeningScreen";
import QuestionScreen from "./components/QuestionScreen";
import LoadingScreen from "./components/LoadingScreen";
import ResultsScreen from "./components/ResultsScreen";
import { fetchJobs } from "./api";
import "./App.css";

const QUESTIONS = [
  {
    key: "lifeSystems",
    question: "Which living systems draw your attention?",
    options: [
      { label: "Flora", value: "plants" },
      { label: "Fauna", value: "animals" },
      { label: "Environmental", value: "environmental systems" },
    ],
  },
  {
    key: "habitatDomain",
    question: "Where does your attention tend to stabilize?",
    options: [
      { label: "Grounded in Soil", value: "land" },
      { label: "Moving with Tides", value: "water" },
      { label: "Carried by Air", value: "air" },
    ],
  },
  {
    key: "circadianPhase",
    question: "When is your perception most reliable?",
    options: [
      { label: "Under Sun", value: "day" },
      { label: "Under Moon", value: "night" },
    ],
  },
  {
    key: "operationalSetting",
    question: "Where do you maintain optimal function?",
    options: [
      { label: "Within Shelter", value: "indoor" },
      { label: "In Open Field", value: "field work" },
    ],
  },
  {
    key: "interactionMode",
    question: "How do you approach other species?",
    options: [
      { label: "Witness", value: "observe" },
      { label: "Assist", value: "help" },
      { label: "Direct Contact", value: "touch" },
    ],
  },
];

const SCREENS = {
  SPLASH: "splash",
  OPENING: "opening",
  QUESTION: "question",
  LOADING: "loading",
  RESULTS: "results",
};

const BATCH_SIZE = 8;

export default function App() {
  const [screen, setScreen] = useState(SCREENS.SPLASH);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [allJobs, setAllJobs] = useState([]);
  const [batchIndex, setBatchIndex] = useState(0);
  const [transitioning, setTransitioning] = useState(false);

  const totalBatches = Math.max(1, Math.ceil(allJobs.length / BATCH_SIZE));

  const currentBatchJobs = useMemo(() => {
    const start = batchIndex * BATCH_SIZE;
    return allJobs.slice(start, start + BATCH_SIZE);
  }, [allJobs, batchIndex]);

  function transition(next) {
    setTransitioning(true);
    setTimeout(() => {
      next();
      setTransitioning(false);
    }, 350);
  }

  function handleStart() {
    transition(() => setScreen(SCREENS.OPENING));
  }

  function handleOpeningNext() {
    transition(() => {
      setQuestionIndex(0);
      setScreen(SCREENS.QUESTION);
    });
  }

  async function handleAnswer(option) {
    const currentQuestion = QUESTIONS[questionIndex];
    const newAnswers = { ...answers, [currentQuestion.key]: option };
    setAnswers(newAnswers);

    if (questionIndex < QUESTIONS.length - 1) {
      // advance directly — QuestionScreen handles its own content fade via key remount
      setQuestionIndex((i) => i + 1);
    } else {
      setTransitioning(true);
      setTimeout(async () => {
        setScreen(SCREENS.LOADING);
        setTransitioning(false);
        try {
          const result = await fetchJobs(newAnswers);
          setAllJobs(result);
          setBatchIndex(0);
        } catch (err) {
          console.error("Failed to fetch jobs:", err);
          setAllJobs([]);
          setBatchIndex(0);
        }
        setTransitioning(true);
        setTimeout(() => {
          setScreen(SCREENS.RESULTS);
          setTransitioning(false);
        }, 350);
      }, 350);
    }
  }

  function handleRestart() {
    transition(() => {
      setAnswers({});
      setAllJobs([]);
      setBatchIndex(0);
      setQuestionIndex(0);
      setScreen(SCREENS.SPLASH);
    });
  }

  function handleNextBatch() {
    setBatchIndex((index) => Math.min(index + 1, totalBatches - 1));
  }

  function handlePreviousBatch() {
    setBatchIndex((index) => Math.max(index - 1, 0));
  }

  return (
    <div className={`app-wrapper ${transitioning ? "fading" : ""}`}>
      {screen === SCREENS.SPLASH && (
        <SplashScreen onStart={handleStart} />
      )}
      {screen === SCREENS.OPENING && (
        <OpeningScreen onNext={handleOpeningNext} onHome={handleRestart} />
      )}
      {screen === SCREENS.QUESTION && (
        <QuestionScreen
          key={questionIndex}
          question={QUESTIONS[questionIndex].question}
          options={QUESTIONS[questionIndex].options}
          onAnswer={handleAnswer}
          onHome={handleRestart}
        />
      )}
      {screen === SCREENS.LOADING && <LoadingScreen />}
      {screen === SCREENS.RESULTS && (
        <ResultsScreen
          jobs={currentBatchJobs}
          onRestart={handleRestart}
          onHome={handleRestart}
          onNextBatch={handleNextBatch}
          onPreviousBatch={handlePreviousBatch}
          batchIndex={batchIndex}
          totalBatches={totalBatches}
        />
      )}
    </div>
  );
}
