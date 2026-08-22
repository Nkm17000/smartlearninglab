# Smart Learning Lab Backend

FastAPI backend.

## Run
```powershell
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Configure MongoDB, SMTP, and other secrets through environment variables. Do not commit `.env`.
