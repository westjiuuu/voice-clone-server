from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
import torch
from TTS.api import TTS
from pydub import AudioSegment
import uuid, os

app = FastAPI()

# 모델 로딩 (서버 시작할 때 한 번만)
print("🔄 TTS 모델 로딩 중...")
device = "cuda" if torch.cuda.is_available() else "cpu"
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
print(f"✅ 모델 로딩 완료! (device: {device})")

# 웹 UI (브라우저에서 바로 테스트 가능)
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
    <head>
        <title>TTS 서버</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 80px auto; padding: 20px; }
            input, textarea { width: 100%; padding: 10px; margin: 8px 0; box-sizing: border-box; font-size: 16px; }
            button { background: #4CAF50; color: white; padding: 12px 24px; border: none; cursor: pointer; font-size: 16px; border-radius: 6px; }
            button:hover { background: #45a049; }
            #result { margin-top: 20px; }
        </style>
    </head>
    <body>
        <h2>🎙️ TTS 음성 생성기</h2>
        <form id="ttsForm">
            <label>텍스트 입력:</label>
            <textarea name="text" rows="4" placeholder="여기에 텍스트를 입력하세요..."></textarea>

            <label>참조 음성 파일 (WAV):</label>
            <input type="file" name="speaker_wav" accept=".wav">

            <button type="submit">🎵 음성 생성</button>
        </form>
        <div id="result"></div>

        <script>
            document.getElementById('ttsForm').onsubmit = async (e) => {
                e.preventDefault();
                document.getElementById('result').innerHTML = '⏳ 생성 중...';
                const formData = new FormData(e.target);
                const res = await fetch('/tts', { method: 'POST', body: formData });
                if (res.ok) {
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    document.getElementById('result').innerHTML =
                        '<p>✅ 완료!</p><audio controls src="' + url + '"></audio>';
                } else {
                    document.getElementById('result').innerHTML = '❌ 오류: ' + await res.text();
                }
            };
        </script>
    </body>
    </html>
    """

# TTS API 엔드포인트
@app.post("/tts")
async def generate_speech(
    text: str = Form(...),
    speaker_wav: UploadFile = File(...)
):
    tmp_id = uuid.uuid4()
    ref_path = f"C:/tts/tmp_{tmp_id}.wav"
    clean_path = f"C:/tts/tmp_{tmp_id}_clean.wav"
    out_path = f"C:/tts/tmp_{tmp_id}_output.wav"

    try:
        # 업로드된 reference wav 저장
        with open(ref_path, "wb") as f:
            f.write(await speaker_wav.read())

        # 오디오 전처리
        audio = AudioSegment.from_file(ref_path)
        audio = audio.set_frame_rate(22050).set_channels(1)
        audio.export(clean_path, format="wav")

        # TTS 생성
        tts.tts_to_file(
            text=text,
            speaker_wav=clean_path,
            language="ko",
            file_path=out_path
        )

        return FileResponse(out_path, media_type="audio/wav", filename="output.wav")

    finally:
        # 임시 파일 정리
        for path in [ref_path, clean_path]:
            if os.path.exists(path):
                os.remove(path)
