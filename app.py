"""Streamlit entry point for AI Interview Coach.

Run with: streamlit run app.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

import streamlit as st

from agents.evaluator_agent import evaluate_answer
from agents.interviewer_agent import generate_question
from agents.report_agent import build_report
from config.settings import get_api_key
from services.database_service import load_history, save_interview
from services.speech_service import voice_available, voice_message
from utils.validators import validate_answer


ROLES = ["Python Developer", "AI/ML Engineer", "Data Analyst", "React Developer", "MERN Developer", "Full Stack Developer"]
QUESTION_COUNTS = [5, 10, 15]


def initialise_state() -> None:
    """Set defaults once so every rerun has a complete interview state."""
    defaults: dict[str, Any] = {
        "screen": "home",
        "started": False,
        "candidate_name": "",
        "role": ROLES[0],
        "experience": "0–2 years",
        "difficulty": "Medium",
        "interview_type": "Technical",
        "total_questions": 5,
        "question_number": 0,
        "question": "",
        "previous_questions": [],
        "evaluations": [],
        "answers": [],
        "last_evaluation": None,
        "saved": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_interview() -> None:
    st.session_state.started = False
    st.session_state.question_number = 0
    st.session_state.question = ""
    st.session_state.previous_questions = []
    st.session_state.evaluations = []
    st.session_state.answers = []
    st.session_state.last_evaluation = None
    st.session_state.saved = False
    st.session_state.screen = "home"


def start_interview() -> None:
    st.session_state.started = True
    st.session_state.screen = "interview"
    st.session_state.question_number = 1
    st.session_state.previous_questions = []
    st.session_state.evaluations = []
    st.session_state.answers = []
    st.session_state.last_evaluation = None
    st.session_state.saved = False
    st.session_state.question = generate_question(
        st.session_state.role, st.session_state.experience, st.session_state.difficulty,
        st.session_state.interview_type, [], 0,
    )


def next_question() -> None:
    number = st.session_state.question_number + 1
    st.session_state.question_number = number
    st.session_state.question = generate_question(
        st.session_state.role, st.session_state.experience, st.session_state.difficulty,
        st.session_state.interview_type, st.session_state.previous_questions, number - 1,
    )
    st.session_state.last_evaluation = None


def submit_answer(answer: str) -> None:
    valid, message = validate_answer(answer)
    if not valid:
        st.error(message)
        return
    evaluation = evaluate_answer(st.session_state.question, answer.strip(), st.session_state.role)
    st.session_state.evaluations.append(evaluation)
    st.session_state.answers.append({"question": st.session_state.question, "answer": answer.strip()})
    st.session_state.previous_questions.append(st.session_state.question)
    st.session_state.last_evaluation = evaluation
    st.session_state.difficulty = _adjust_difficulty(st.session_state.difficulty, evaluation.score)
    if st.session_state.question_number >= st.session_state.total_questions:
        st.session_state.screen = "report"
        save_current_interview()


def _adjust_difficulty(current: str, score: float) -> str:
    levels = ["Easy", "Medium", "Hard"]
    position = levels.index(current)
    return levels[min(position + 1, 2)] if score > 8 else levels[max(position - 1, 0)] if score < 5 else current


def save_current_interview() -> None:
    if st.session_state.saved:
        return
    report = build_report(st.session_state.evaluations)
    save_interview({
        "id": datetime.now(timezone.utc).isoformat(),
        "date": datetime.now().strftime("%d %b %Y"),
        "candidate_name": st.session_state.candidate_name,
        "role": st.session_state.role,
        "interview_type": st.session_state.interview_type,
        "questions_answered": len(st.session_state.evaluations),
        "overall": report["overall"],
        "report": report,
    })
    st.session_state.saved = True


def inject_styles() -> None:
    st.markdown("""<style>
    .stApp { background: #09111f; color: #e9edf5; }
    [data-testid="stHeader"] { background: rgba(0,0,0,0); }
    [data-testid="stSidebar"] { background: #101b30; border-right: 1px solid #263653; }
    .hero { padding: 3.5rem 0 2rem; max-width: 820px; }
    .eyebrow { color: #7dd3fc; font-size: .78rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    h1 { font-size: clamp(2.2rem, 5vw, 4rem) !important; line-height: 1.06 !important; letter-spacing: -.05em; }
    .subtle { color: #aab8d1; font-size: 1.08rem; line-height: 1.65; }
    .panel { background: linear-gradient(145deg, #15233d, #0f1a2e); border: 1px solid #2b3b59; border-radius: 18px; padding: 1.35rem; min-height: 125px; }
    .question-card { background: linear-gradient(135deg, #182b4b, #12213a); border: 1px solid #35527d; border-radius: 20px; padding: 1.7rem; margin: 1rem 0; }
    .question-card p { font-size: 1.3rem; line-height: 1.55; margin: .4rem 0 0; }
    .score { color: #67e8f9; font-size: 2.2rem; font-weight: 750; }
    .stButton > button, .stFormSubmitButton > button { border-radius: 10px; font-weight: 650; min-height: 2.7rem; }
    .stFormSubmitButton > button { background: #38bdf8; color: #082033; border: 0; width: 100%; }
    div[data-testid="stMetric"] { background: #111e34; border: 1px solid #2b3b59; border-radius: 13px; padding: .8rem; }
    </style>""", unsafe_allow_html=True)


def sidebar() -> None:
    with st.sidebar:
        st.title("◈ Coach")
        st.caption("Practice with intent")
        st.divider()
        if st.session_state.started:
            st.progress(len(st.session_state.evaluations) / st.session_state.total_questions)
            st.caption(f"{len(st.session_state.evaluations)} of {st.session_state.total_questions} responses evaluated")
            st.caption(f"Difficulty: **{st.session_state.difficulty}**")
            if st.button("End and view report", use_container_width=True):
                if st.session_state.evaluations:
                    st.session_state.screen = "report"
                    save_current_interview()
                    st.rerun()
        else:
            st.caption("Your interview settings")
            st.session_state.candidate_name = st.text_input("Your name", value=st.session_state.candidate_name, placeholder="Alex Morgan")
            st.session_state.role = st.selectbox("Target role", ROLES, index=ROLES.index(st.session_state.role))
            st.session_state.experience = st.selectbox("Experience", ["0–2 years", "3–5 years", "6+ years"], index=["0–2 years", "3–5 years", "6+ years"].index(st.session_state.experience))
            st.session_state.interview_type = st.radio("Interview focus", ["Technical", "HR"], horizontal=True, index=0 if st.session_state.interview_type == "Technical" else 1)
            st.session_state.difficulty = st.select_slider("Starting difficulty", ["Easy", "Medium", "Hard"], value=st.session_state.difficulty)
            st.session_state.total_questions = st.select_slider("Questions", QUESTION_COUNTS, value=st.session_state.total_questions)
            recent = load_history()[:3]
            if recent:
                with st.expander("Recent practice"):
                    for record in recent:
                        st.caption(f"**{record.get('overall', 0)}%** · {record.get('role', 'Interview')} · {record.get('date', '')}")
        st.divider()
        st.caption("AI mode: " + ("Gemini connected" if get_api_key() else "Offline practice mode"))
        if st.session_state.started and st.button("Start over", type="secondary", use_container_width=True):
            reset_interview()
            st.rerun()


def home() -> None:
    st.markdown("<div class='hero'><div class='eyebrow'>Your personal interview rehearsal</div><h1>Practice answers that make an impression.</h1><p class='subtle'>A focused, adaptive interview simulation for your next role. Get thoughtful feedback after every answer and leave with an actionable plan.</p></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for column, title, copy in ((c1, "01 · Simulate", "Role-specific questions tailored to your level."), (c2, "02 · Reflect", "Clear feedback across substance and delivery."), (c3, "03 · Improve", "A concise report that directs your next practice.")):
        with column:
            st.markdown(f"<div class='panel'><strong>{title}</strong><br><br><span class='subtle'>{copy}</span></div>", unsafe_allow_html=True)
    st.write("")
    if not get_api_key():
        st.info("You are in offline practice mode. Add `GOOGLE_API_KEY` to `.env` to enable Gemini-powered questions and evaluation.")
    if st.button("Begin my interview →", type="primary", use_container_width=True):
        if not st.session_state.candidate_name.strip():
            st.session_state.candidate_name = "Candidate"
        start_interview()
        st.rerun()


def interview() -> None:
    completed = len(st.session_state.evaluations)
    st.markdown(f"<div class='eyebrow'>{st.session_state.role} · {st.session_state.interview_type} interview</div><h2>Question {st.session_state.question_number} of {st.session_state.total_questions}</h2>", unsafe_allow_html=True)
    safe_question = escape(st.session_state.question)
    st.markdown(f"<div class='question-card'><span class='eyebrow'>Take a moment to think</span><p>{safe_question}</p></div>", unsafe_allow_html=True)
    if st.session_state.last_evaluation is None:
        with st.form("answer_form", clear_on_submit=True):
            answer = st.text_area("Your response", height=210, placeholder="Structure your answer: context, action, and outcome…", label_visibility="collapsed")
            submitted = st.form_submit_button("Evaluate my answer")
        if submitted:
            submit_answer(answer)
            st.rerun()
        if not voice_available():
            st.caption("⌁ " + voice_message())
    else:
        e = st.session_state.last_evaluation
        st.success("Answer evaluated")
        left, right = st.columns([1, 2])
        with left:
            st.markdown(f"<div class='panel'><span class='eyebrow'>Response score</span><div class='score'>{e.score:.1f}<small>/10</small></div></div>", unsafe_allow_html=True)
        with right:
            st.markdown("#### Coach's note")
            st.write(e.feedback)
            st.caption("Next focus: " + e.improvement_suggestion)
        if st.session_state.question_number < st.session_state.total_questions:
            if st.button("Continue to next question →", type="primary"):
                next_question()
                st.rerun()
        else:
            if st.button("View my report →", type="primary"):
                st.session_state.screen = "report"
                save_current_interview()
                st.rerun()


def report() -> None:
    report_data = build_report(st.session_state.evaluations)
    st.markdown("<div class='eyebrow'>Interview complete</div><h1>Your practice report</h1>", unsafe_allow_html=True)
    st.caption(f"{st.session_state.candidate_name} · {st.session_state.role} · {len(st.session_state.evaluations)} answers")
    a, b, c, d = st.columns(4)
    a.metric("Overall", f"{report_data['overall']}%")
    b.metric("Technical", f"{report_data['technical']}%")
    c.metric("Communication", f"{report_data['communication']}%")
    d.metric("Completeness", f"{report_data['completeness']}%")
    st.write("")
    left, right = st.columns(2)
    with left:
        st.markdown("### What worked")
        for item in report_data["strengths"] or ["You completed a full practice session."]:
            st.success(item)
        st.markdown("### Build next")
        for item in report_data["weaknesses"] or ["Keep practicing clear, structured answers."]:
            st.warning(item)
    with right:
        st.markdown("### Recommended focus")
        for item in report_data["topics"] or ["Use examples that connect concepts to outcomes."]:
            st.info(item)
        st.markdown("### Coach summary")
        st.write(report_data["summary"])
    if st.button("Practice another interview", type="primary"):
        reset_interview()
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="AI Interview Coach", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
    initialise_state()
    inject_styles()
    sidebar()
    if st.session_state.screen == "interview" and st.session_state.started:
        interview()
    elif st.session_state.screen == "report" and st.session_state.evaluations:
        report()
    else:
        home()


if __name__ == "__main__":
    main()
