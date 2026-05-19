from gtts import gTTS
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def get_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()


def create_slide(text, slide_no, save_folder, subject="AI Lecture"):

    bg_path = os.path.join(STATIC_DIR, "background.png")
    logo_path = os.path.join(STATIC_DIR, "logo.png")
    teacher_path = os.path.join(STATIC_DIR, "teacher.png")

    if os.path.exists(bg_path):
        img = Image.open(bg_path).resize((1280, 720)).convert("RGB")
    else:
        img = Image.new("RGB", (1280, 720), color=(245, 245, 255))

    draw = ImageDraw.Draw(img)

    text_font = get_font(30)
    small_font = get_font(24)

    draw.rounded_rectangle(
        (50, 95, 880, 620),
        radius=25,
        fill=(255, 255, 255),
        outline=(210, 210, 210),
        width=2
    )

    draw.text(
        (60, 650),
        f"Slide {slide_no}",
        fill=(80, 80, 80),
        font=small_font
    )

    if os.path.exists(logo_path):
        logo = Image.open(logo_path).resize((40, 40)).convert("RGBA")
        img.paste(logo, (40, 20), logo)

    if os.path.exists(teacher_path):
        teacher = Image.open(teacher_path).resize((280, 390)).convert("RGBA")
        img.paste(teacher, (930, 245), teacher)

    y = 125
    lines = textwrap.wrap(text, width=42)

    for line in lines[:13]:
        draw.text((85, y), line, fill=(0, 0, 0), font=text_font)
        y += 38

    slides_folder = os.path.join(save_folder, "slides")
    os.makedirs(slides_folder, exist_ok=True)

    slide_path = os.path.join(slides_folder, f"slide_{slide_no}.png")
    img.save(slide_path)

    return slide_path


def create_video(notes, lang="en", subject="AI Lecture", save_folder="static"):

    os.makedirs(save_folder, exist_ok=True)

    audio_path = os.path.join(save_folder, "notes_audio.mp3")
    output_video = os.path.join(save_folder, "lecture_video.mp4")

    tts = gTTS(text=notes, lang=lang)
    tts.save(audio_path)

    parts = textwrap.wrap(notes, width=300)
    parts = parts[:6]

    if len(parts) == 0:
        parts = ["No notes available."]

    audio = AudioFileClip(audio_path)

    slide_duration = audio.duration / len(parts)

    clips = []

    for i, part in enumerate(parts, start=1):
        slide_path = create_slide(
            part,
            i,
            save_folder,
            subject
        )

        clip = ImageClip(slide_path).with_duration(slide_duration)
        clips.append(clip)

    final_clip = concatenate_videoclips(clips)
    final_clip = final_clip.with_audio(audio)

    final_clip.write_videofile(output_video, fps=24)

    audio.close()
    final_clip.close()

    time.sleep(1)

    if os.path.exists(audio_path):
        os.remove(audio_path)

    return output_video