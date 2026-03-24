import { useState } from "react";
import SplashScreen from "./components/SplashScreen";
import OpeningScreen from "./components/OpeningScreen";
import QuestionScreen from "./components/QuestionScreen";
import LoadingScreen from "./components/LoadingScreen";
import ResultsScreen from "./components/ResultsScreen";
import { fetchJobs } from "./api";
import "./App.css";

const QUESTIONS = [
  {
    key: "livingSystem",
    question: "Which living systems draw your attention?",
    options: ["Flora", "Fauna", "Atmosphere"],
  },
  {
    key: "attention",
    question: "Where does your attention settle?",
    options: ["Ground", "Current", "Drift"],
  },
  {
    key: "perception",
    question: "When is your perception most reliable?",
    options: ["Under Sun", "Under Moon"],
  },
  {
    key: "function",
    question: "Where do you function most effectively?",
    options: ["Shelter", "Exposure"],
  },
  {
    key: "approach",
    question: "How do you approach other species?",
    options: ["Witness", "Assist", "Contact"],
  },
];

const SCREENS = {
  SPLASH: "splash",
  OPENING: "opening",
  QUESTION: "question",
  LOADING: "loading",
  RESULTS: "results",
};

export default function App() {
  const [screen, setScreen] = useState(SCREENS.SPLASH);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [jobs, setJobs] = useState([]);
  const [transitioning, setTransitioning] = useState(false);

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
      transition(() => setQuestionIndex((i) => i + 1));
    } else {
      setTransitioning(true);
      setTimeout(async () => {
        setScreen(SCREENS.LOADING);
        setTransitioning(false);
        try {
          const result = await fetchJobs(newAnswers);
          setJobs(result);
        } catch (err) {
          console.error("Failed to fetch jobs:", err);
          setJobs([]);
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
      setJobs([]);
      setQuestionIndex(0);
      setScreen(SCREENS.SPLASH);
    });
  }

  async function handleRefresh() {
    setScreen(SCREENS.LOADING);
    try {
      const result = await fetchJobs(answers);
      setJobs(result);
    } catch (err) {
      console.error("Failed to refresh jobs:", err);
    }
    setScreen(SCREENS.RESULTS);
  }

  return (
    <div className={`app-wrapper ${transitioning ? "fading" : ""}`}>
      {screen === SCREENS.SPLASH && (
        <SplashScreen onStart={handleStart} />
      )}
      {screen === SCREENS.OPENING && (
        <OpeningScreen onNext={handleOpeningNext} />
      )}
      {screen === SCREENS.QUESTION && (
        <QuestionScreen
          key={questionIndex}
          questionNumber={questionIndex + 1}
          totalQuestions={QUESTIONS.length}
          question={QUESTIONS[questionIndex].question}
          options={QUESTIONS[questionIndex].options}
          onAnswer={handleAnswer}
        />
      )}
      {screen === SCREENS.LOADING && <LoadingScreen />}
      {screen === SCREENS.RESULTS && (
        <ResultsScreen jobs={jobs} answers={answers} onRestart={handleRestart} onRefresh={handleRefresh} />
      )}
    </div>
  );
}
