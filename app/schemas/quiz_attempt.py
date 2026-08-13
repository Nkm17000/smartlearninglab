from pydantic import BaseModel

class AnswerRequest(BaseModel):
    question_id: str
    selected_answer: str

class QuizSubmitRequest(BaseModel):
    answers: list[AnswerRequest]
