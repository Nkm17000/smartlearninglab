# Smart Learning Lab Backend

## Run
```bash
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## AI configuration
Set `AI_API_KEY` + `AI_BASE_URL` + `AI_MODEL` in `.env` for generative AI. Groq-compatible configuration is also supported with `GROQ_API_KEY` and `GROQ_MODEL`.

Important AI endpoints:
- POST `/api/v1/ai/tutor/rag`
- GET `/api/v1/ai/coach`
- POST `/api/v1/ai/personalized-quiz`
- POST `/api/v1/ai/study-plan`
- GET `/api/v1/career/roadmap`
- POST `/api/v1/ai/mock-interview`
- GET `/api/v1/search`
