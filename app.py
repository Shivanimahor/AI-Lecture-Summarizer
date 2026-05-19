from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
import re
import random
import time
import fitz
import whisper
from transformers import pipeline
from reportlab.pdfgen import canvas
from video_maker import create_video

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "uploads"
USERS_FILE = "users.txt"
SAVED_NOTES_FOLDER = "saved_notes"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SAVED_NOTES_FOLDER, exist_ok=True)
os.makedirs("static", exist_ok=True)

if not os.path.exists(USERS_FILE):
    open(USERS_FILE, "w").close()

feedbacks = []

whisper_model = whisper.load_model("base")
summarizer = pipeline(
    "summarization",
    model="facebook/bart-large-cnn"
)


def save_user(username, password):
    with open(USERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{username},{password}\n")


def user_exists(username):
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            data = line.strip().split(",")

            if len(data) == 2 and data[0] == username:
                return True

    return False


def check_user(username, password):
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            data = line.strip().split(",")

            if (
                len(data) == 2
                and data[0] == username
                and data[1] == password
            ):
                return True

    return False


def read_text_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def read_pdf_file(file_path):
    text = ""

    pdf = fitz.open(file_path)

    for page in pdf:
        text += page.get_text() + "\n"

    pdf.close()

    return text


def transcribe_file(file_path):
    result = whisper_model.transcribe(file_path)
    return result["text"]


def clean_text(text):
    text = text.replace("\n", " ")

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"Thank ?you.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Q\.\s*\d+", " ", text)
    text = re.sub(r"Q\d+\.", " ", text)
    text = re.sub(r"[•]", "", text)

    return text.strip()


def split_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)

    return [
        s.strip()
        for s in sentences
        if len(s.strip()) > 25
    ]


def generate_summary(text):

    if not text.strip():
        return "No summary generated."

    text = clean_text(text)

    chunks = [
        text[i:i + 1000]
        for i in range(0, len(text), 1000)
    ]

    summaries = []

    for chunk in chunks[:3]:

        result = summarizer(
            chunk,
            max_length=100,
            min_length=30,
            do_sample=False
        )

        summaries.append(
            result[0]["summary_text"]
        )

    return "\n\n".join(summaries)


def generate_notes(text):

    if not text.strip():
        return "No notes generated."

    text = clean_text(text)

    sentences = split_sentences(text)

    notes = ["Important Notes:\n"]

    for sentence in sentences[:12]:
        notes.append(f"• {sentence}")

    return "\n\n".join(notes)


def save_notes_pdf(notes, pdf_path):

    c = canvas.Canvas(pdf_path)

    text = c.beginText(40, 800)

    for line in notes.split("\n"):

        if text.getY() < 50:

            c.drawText(text)

            c.showPage()

            text = c.beginText(40, 800)

        text.textLine(line[:95])

    c.drawText(text)

    c.save()


def generate_quiz_data(text):

    if not text.strip():
        return []

    text = clean_text(text)

    sentences = split_sentences(text)

    if len(sentences) < 4:
        return []

    quiz_data = []

    used_questions = set()

    for sentence in sentences:

        if len(quiz_data) == 10:
            break

        if sentence in used_questions:
            continue

        words = sentence.split()

        if len(words) < 6:
            continue

        correct = " ".join(words[-4:])

        wrong_options = []

        pool = sentences.copy()

        random.shuffle(pool)

        for opt in pool:

            if opt != sentence:

                wrong_text = " ".join(opt.split()[:4])

                if (
                    wrong_text != correct
                    and wrong_text not in wrong_options
                ):
                    wrong_options.append(wrong_text)

            if len(wrong_options) == 3:
                break

        if len(wrong_options) < 3:
            continue

        options = wrong_options + [correct]

        random.shuffle(options)

        quiz_data.append({
            "question": sentence,
            "options": options,
            "answer": correct
        })

        used_questions.add(sentence)

    return quiz_data


@app.route("/signup", methods=["GET", "POST"])
def signup():

    message = ""

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        if username == "" or password == "":

            message = "Please fill all fields."

        elif user_exists(username):

            message = "User already exists."

        else:

            save_user(username, password)

            return redirect(url_for("login"))

    return render_template(
        "signup.html",
        message=message
    )


@app.route("/login", methods=["GET", "POST"])
def login():

    message = ""

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        if check_user(username, password):

            session["username"] = username

            return redirect(url_for("index"))

        else:

            message = "Invalid username or password."

    return render_template(
        "login.html",
        message=message
    )


@app.route("/logout")
def logout():

    session.pop("username", None)

    session.pop("quiz_data", None)

    return redirect(url_for("login"))


@app.route("/feedback", methods=["POST"])
def feedback():

    if "username" not in session:
        return redirect(url_for("login"))

    user_feedback = request.form.get(
        "feedback",
        ""
    ).strip()

    rating = request.form.get("rating", "0")

    if user_feedback:

        feedbacks.append({
            "username": session["username"],
            "rating": rating,
            "feedback": user_feedback
        })

    return redirect(url_for("index"))


@app.route("/download_notes")
def download_notes():

    if "username" not in session:
        return redirect(url_for("login"))

    notes = request.args.get("data", "")

    if not notes.strip():
        return "No notes available"

    file_path = os.path.join(
        SAVED_NOTES_FOLDER,
        f"notes_{int(time.time())}.pdf"
    )

    save_notes_pdf(notes, file_path)

    return send_file(file_path, as_attachment=True)


@app.route("/", methods=["GET", "POST"])
def index():

    if "username" not in session:
        return redirect(url_for("login"))

    transcript = ""
    summary = ""
    notes = ""
    quiz_data = []
    error = ""
    score = None

    video_ready = os.path.exists(
        "static/lecture_video.mp4"
    )

    if request.method == "POST":

        file = request.files.get("lecture_file")

        subject = request.form.get(
            "subject",
            "General"
        ).strip()

        if subject == "":
            subject = "General"

        want_summary = request.form.get(
            "generate_summary"
        )

        want_notes = request.form.get(
            "create_notes"
        )

        want_quiz = request.form.get(
            "generate_quiz"
        )

        want_video = request.form.get(
            "generate_video"
        )

        video_language = request.form.get(
            "video_language",
            "en"
        )

        want_transcript = request.form.get(
            "show_transcript"
        )

        if not file or file.filename == "":

            error = "Please choose a file."

            return render_template(
                "index.html",
                transcript=transcript,
                summary=summary,
                notes=notes,
                quiz_data=quiz_data,
                error=error,
                score=score,
                feedbacks=feedbacks,
                video_ready=video_ready,
                username=session["username"]
            )

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            file.filename
        )

        file.save(file_path)

        try:

            ext = os.path.splitext(
                file.filename
            )[1].lower()

            if ext == ".txt":

                transcript = read_text_file(file_path)

            elif ext == ".pdf":

                transcript = read_pdf_file(file_path)

            elif ext in [
                ".mp3",
                ".wav",
                ".m4a",
                ".mp4"
            ]:

                transcript = transcribe_file(file_path)

            else:

                error = "Unsupported file format."

            if transcript.strip():

                original_transcript = transcript

                if want_summary:

                    summary = generate_summary(
                        original_transcript
                    )

                if want_notes or want_video:

                    notes = generate_notes(
                        original_transcript
                    )

                    subject_folder = os.path.join(
                        SAVED_NOTES_FOLDER,
                        subject
                    )

                    if os.path.exists(subject_folder):

                        error = "Subject already exists"

                        return render_template(
                            "index.html",
                            transcript=transcript,
                            summary=summary,
                            notes=notes,
                            quiz_data=quiz_data,
                            error=error,
                            score=score,
                            feedbacks=feedbacks,
                            video_ready=video_ready,
                            username=session["username"]
                        )

                    os.makedirs(
                        subject_folder,
                        exist_ok=True
                    )

                    pdf_file = os.path.join(
                        subject_folder,
                        f"notes_{int(time.time())}.pdf"
                    )

                    save_notes_pdf(
                        notes,
                        pdf_file
                    )

                if want_video:

                    create_video(
                        notes,
                        video_language,
                        subject,
                        subject_folder
                    )

                    video_ready = True

                if want_quiz:

                    quiz_data = generate_quiz_data(
                        original_transcript
                    )

                    session["quiz_data"] = quiz_data

                if not want_transcript:
                    transcript = ""

            else:

                if error == "":
                    error = "No readable text found."

        except Exception as e:

            error = str(e)

    return render_template(
        "index.html",
        transcript=transcript,
        summary=summary,
        notes=notes,
        quiz_data=quiz_data,
        error=error,
        score=score,
        feedbacks=feedbacks,
        video_ready=video_ready,
        username=session["username"]
    )


@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():

    if "username" not in session:
        return redirect(url_for("login"))

    quiz_data = session.get("quiz_data", [])

    score_count = 0

    for i, item in enumerate(quiz_data):

        selected = request.form.get(
            f"answer_{i}"
        )

        item["selected"] = selected

        if selected == item["answer"]:
            score_count += 1

    score = f"{score_count}/{len(quiz_data)}"

    video_ready = os.path.exists(
        "static/lecture_video.mp4"
    )

    return render_template(
        "index.html",
        transcript="",
        summary="",
        notes="",
        quiz_data=quiz_data,
        error="",
        score=score,
        feedbacks=feedbacks,
        video_ready=video_ready,
        username=session["username"]
    )


if __name__ == "__main__":
    app.run(debug=True)