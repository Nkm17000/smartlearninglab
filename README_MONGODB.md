# MongoDB configuration

No separate `MONGODB_DB` variable is required.

Put the database name directly in `MONGODB_URI`:

```env
MONGODB_URI=mongodb+srv://username:password@smartstudylab.juh84i5.mongodb.net/smart_learning_lab
JWT_SECRET_KEY=your-long-secret
CORS_ORIGINS=*
```

The backend uses `get_default_database()`, so the database name must be present
at the end of the URI (`/smart_learning_lab`).

Local run:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Render start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
