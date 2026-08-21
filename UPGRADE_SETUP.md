# Smart Learning Lab — AI Feature Upgrade

This package keeps the existing project structure and adds the requested 10-feature AI/product layer.

## Student features

1. AI Personal Learning Coach
2. AI-generated personalized quizzes
3. AI Study Plan
4. Career / Skill Roadmap
5. AI Mock Interview
6. Global search
7. Offline lesson-completion queue + sync

## Admin features

4. PDF → complete AI course blueprint + save as draft
5. At-risk student detection
8. AI Course Health Checker

## Install

### Backend

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
npm install
npx expo install expo-document-picker
npm start
```

`expo-document-picker` is used by Admin → AI Intelligence for PDF upload.

## Important implementation notes

- PDF extraction is real and uses `pypdf`.
- The PDF course generator creates an editable course blueprint from extracted text. It does not require an external LLM provider.
- Global search uses dependency-free token scoring. For true vector/semantic search, replace the search implementation with your existing RAG/vector infrastructure.
- AI Tutor already supports an optional `OPENAI_API_KEY`; these new features use deterministic fallbacks so the app still works without an external AI key.
- Offline sync currently queues lesson completion locally and syncs it through `/api/v1/offline/sync` when connectivity returns.
- Do not commit `.env`, API keys, MongoDB credentials, or signing keys.
