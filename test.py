# server.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
import torch
from TTS.api import TTS
from pydub import AudioSegment
import uuid, os

app = FastAPI()
device = "cuda" if torch.cuda.is_available() else "cpu"
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)


@app.post("/tts")
async def generate_speech(
        text: str = Form(...),
        speaker_wav: UploadFile = File(...)
):
    # 업로드된 reference wav 저장
    ref_path = f"/tmp/{uuid.uuid4()}.wav"
    with open(ref_path, "wb") as f:
        f.write(await speaker_wav.read())

    # 오디오 전처리
    audio = AudioSegment.from_file(ref_path)
    audio = audio.set_frame_rate(22050).set_channels(1)
    clean_path = ref_path.replace(".wav", "_clean.wav")
    audio.export(clean_path, format="wav")

    # TTS 생성
    out_path = f"/tmp/{uuid.uuid4()}_output.wav"
    tts.tts_to_file(text=text, speaker_wav=clean_path, language="ko", file_path=out_path)

    return FileResponse(out_path, media_type="audio/wav")