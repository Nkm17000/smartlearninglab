"""Enterprise learning intelligence services."""
from datetime import datetime, timezone
from typing import Any, Dict, List

def _pct(value: float) -> int:
    return max(0, min(100, round(value)))

def course_health(course: Dict[str, Any]) -> Dict[str, Any]:
    completion = float(course.get("completion_rate", 0))
    engagement = float(course.get("engagement_rate", 0))
    quiz = float(course.get("quiz_quality", course.get("average_score", 0)))
    content = float(course.get("content_quality", 80))
    score = _pct(completion*.25 + engagement*.25 + quiz*.25 + content*.25)
    recs: List[str] = []
    if completion < 60: recs.append("Review lessons with the highest drop-off.")
    if engagement < 60: recs.append("Add shorter activities and checkpoints.")
    if quiz < 65: recs.append("Increase assessment coverage for weak topics.")
    if content < 70: recs.append("Run an editorial/content-quality review.")
    if not recs: recs.append("Course health is strong; continue monitoring weekly.")
    return {"score": score, "dimensions": {
        "completion": _pct(completion), "engagement": _pct(engagement),
        "assessment_quality": _pct(quiz), "content_quality": _pct(content)},
        "recommendations": recs, "generated_at": datetime.now(timezone.utc).isoformat()}

def student_risk(student: Dict[str, Any]) -> Dict[str, Any]:
    score = float(student.get("average_score", 0))
    completion = float(student.get("completion_rate", 0))
    inactive = int(student.get("inactive_days", 0))
    failed = int(student.get("failed_quizzes", 0))
    risk, reasons = 0, []
    if inactive >= 7: risk += 40; reasons.append(f"No activity for {inactive} days")
    elif inactive >= 3: risk += 20; reasons.append(f"Low recent activity ({inactive} days)")
    if score < 50: risk += 35; reasons.append(f"Average score {score:.0f}%")
    elif score < 65: risk += 20; reasons.append(f"Average score {score:.0f}%")
    if completion < 30: risk += 20; reasons.append(f"Course completion {completion:.0f}%")
    if failed >= 3: risk += 15; reasons.append(f"{failed} failed quizzes")
    risk = _pct(risk)
    return {"risk_score": risk, "level": "HIGH" if risk >= 65 else "MEDIUM" if risk >= 35 else "LOW", "reasons": reasons}

def personalized_plan(profile: Dict[str, Any]) -> Dict[str, Any]:
    goal = profile.get("goal", "Professional growth")
    weak = profile.get("weak_topics", []) or ["Review recent lessons", "Practice with quizzes"]
    return {"goal": goal, "minutes_per_day": int(profile.get("minutes_per_day", 30)),
            "phases": [
                {"name":"Diagnose","days":3,"items":["Baseline assessment","Identify weak topics"]},
                {"name":"Strengthen","days":14,"items":weak[:4]},
                {"name":"Apply","days":7,"items":["Practice test","Mock interview","Revision"]}]}
