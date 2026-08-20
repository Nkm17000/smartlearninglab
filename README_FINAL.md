# Smart Learning Lab — Final Platform Backend

This release extends the previous platform with the remaining platform foundation:

- lesson resource/video/PDF URL management
- video watch-position tracking and completion
- richer question-type validation
- test attempt history and review
- gamification endpoint (XP, level, badges)
- Expo/device-token registration for push infrastructure
- email verification token workflow
- course-grounded retrieval tutor endpoint
- speaking-practice evaluation from transcript (STT provider can be connected separately)
- detailed admin operational analytics
- admin audit-log read endpoint

## Environment

Keep the existing MongoDB-only configuration. No separate MongoDB database variable is required:

`MONGODB_URI=mongodb+srv://.../smart_learning_lab`

Optional AI/provider, SMTP, OAuth and push credentials from the existing `.env.example` remain supported.

## Start

```powershell
pip install -r requirements.txt
python seed_admin.py
python seed_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Important production integrations

The backend deliberately keeps external vendor credentials optional. The retrieval tutor works without a paid LLM by returning course-grounded source snippets. To produce generated answers, connect your preferred LLM provider inside `app/api/advanced.py`.

The speaking endpoint evaluates a transcript. Connect an STT service (for example an Expo-compatible speech-to-text provider) to turn microphone audio into a transcript before calling `/api/v1/speaking/evaluate`.

Push-token registration is included; sending push notifications requires an Expo push service worker/job or another push provider.
