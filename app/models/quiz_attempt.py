from pydantic import BaseModel

class QuizAnswerModel(BaseModel):
    question_id: str
    selected_answer: str
    is_correct: bool

class QuizAttemptModel(BaseModel):
    user_id: str
    quiz_id: str
    total_questions: int
    correct_answers: int
    wrong_answers: int
    score: float
    passed: bool
