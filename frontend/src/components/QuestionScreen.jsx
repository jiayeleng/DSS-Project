export default function QuestionScreen({ question, options, onAnswer, questionNumber, totalQuestions }) {
  return (
    <div className="screen question-screen">
      <div className="question-content">
        <p className="question-meta">{questionNumber} / {totalQuestions}</p>
        <p className="question-text">{question}</p>
        <div className="options-row">
          {options.map((option) => (
            <button
              key={option}
              className="btn btn-option"
              onClick={() => onAnswer(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
