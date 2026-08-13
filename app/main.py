from fastapi import FastAPI

app = FastAPI(
    title="Smart Learning Lab API",
    description="Backend API for Smart Learning Lab",
    version="1.0.0"
)


@app.get("/")
def welcome():
    return {
        "message": "Welcome to Smart Learning Lab 🚀",
        "status": "success"
    }


@app.get("/api/welcome")
def api_welcome():
    return {
        "message": "Welcome to Smart Learning Lab API 🎓",
        "status": "success",
        "version": "1.0.0"
    }