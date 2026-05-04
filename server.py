from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import torch
from TTS.api import TTS
from pydub import AudioSegment
import uuid, os, json
from typing import Optional
import boto3
from botocore.exceptions import BotoCoreError, ClientError

app = FastAPI()

# ── S3 설정 로딩 ──────────────────────────────────────────────────────────
_cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(_cfg_path, "r") as f:
    _cfg = json.load(f)

s3_client = boto3.client(
    "s3",
    region_name           = _cfg["region"],
    aws_access_key_id     = _cfg["aws_access_key_id"],
    aws_secret_access_key = _cfg["aws_secret_access_key"],
)
S3_BUCKET = _cfg["bucket"]
S3_REGION = _cfg["region"]
print(f"✅ S3 연결: bucket={S3_BUCKET} / region={S3_REGION}")


def upload_to_s3(local_path: str, s3_key: str) -> str:
    """로컬 파일을 S3에 업로드하고 public URL 반환"""
    s3_client.upload_file(
        local_path, S3_BUCKET, s3_key,
        ExtraArgs={"ContentType": "audio/wav"},
    )
    url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
    return url


# ── 모델 로딩 (서버 시작 시 1회) ─────────────────────────────────────────
print("🔄 TTS 모델 로딩 중...")
device = "cuda" if torch.cuda.is_available() else "cpu"

# XTTS v2 — 음성 클론(reference wav) 및 내장 화자(preset) 모두 지원
tts_clone = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# 기본 제공 화자 (preset 모드 또는 샘플 음성 없을 때 폴백)
PRESET_VOICES = {
    "female": "Claribel Dervla",
    "male":   "Abrahan Mack",
}
DEFAULT_GENDER = "female"  # 폴백 기본 성별: "female" 또는 "male"

print(f"✅ 모델 로딩 완료! (device: {device})")
print(f"   기본 화자: {PRESET_VOICES[DEFAULT_GENDER]} ({DEFAULT_GENDER})")


# ── 에러 코드 ─────────────────────────────────────────────────────────────
ERROR_CODES = {
    "INVALID_INPUT":               "입력 파라미터 오류",
    "VIDEO_ACCESS_FAILED":         "영상 파일 접근 불가",
    "VIDEO_DECODE_FAILED":         "영상 디코딩 실패",
    "STT_FAILED":                  "음성 인식 실패",
    "HIGHLIGHT_EXTRACTION_FAILED": "하이라이트 추출 실패",
    "VIDEO_EDIT_FAILED":           "클립 편집 실패",
    "TTS_REFERENCE_AUDIO_INVALID": "음성 샘플 불량",
    "TTS_GENERATION_FAILED":       "TTS 생성 실패",
    "SUBTITLE_RENDER_FAILED":      "자막 렌더링 실패",
    "MUSIC_SELECTION_FAILED":      "음악 선택 실패",
    "MUSIC_MIX_FAILED":            "음악 믹싱 실패",
    "FINAL_RENDER_FAILED":         "최종 MP4 렌더링 실패",
    "UPLOAD_RESULT_FAILED":        "결과 파일 업로드 실패",
}

def error_response(code: str, detail: str = "", status_code: int = 400):
    """표준 에러 응답 반환"""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error_code": code,
            "error_message": ERROR_CODES.get(code, code),
            "detail": detail,
        }
    )


# ── 웹 UI ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
    <head>
        <title>TTS 서버</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 640px; margin: 80px auto; padding: 20px; }
            input, textarea, select { width: 100%; padding: 10px; margin: 8px 0; box-sizing: border-box; font-size: 15px; }
            button { background: #4CAF50; color: white; padding: 12px 24px; border: none; cursor: pointer; font-size: 16px; border-radius: 6px; }
            button:hover { background: #45a049; }
            #result { margin-top: 20px; }
            label { font-weight: bold; }
            .hint { color: #888; font-size: 13px; margin-top: -6px; margin-bottom: 6px; }
        </style>
    </head>
    <body>
        <h2>🎙️ TTS 음성 생성기</h2>
        <form id="ttsForm">
            <label>텍스트 입력</label>
            <textarea name="text" rows="4" placeholder="여기에 텍스트를 입력하세요..."></textarea>

            <label>TTS 모드</label>
            <select name="mode" id="modeSelect" onchange="togglePreset()">
                <option value="voice_clone">voice_clone (참조 음성 복제)</option>
                <option value="preset">preset (기본 음성)</option>
                <option value="disabled">disabled (TTS 스킵)</option>
            </select>

            <div id="presetSection" style="display:none">
                <label>기본 음성 선택</label>
                <select name="preset_voice_id">
                    <option value="female">여성 — Claribel Dervla</option>
                    <option value="male">남성 — Abrahan Mack</option>
                </select>
            </div>

            <div id="cloneSection">
                <label>참조 음성 파일 (WAV) — voice_clone 모드 전용</label>
                <p class="hint">파일 없으면 자동으로 기본 여성 음성으로 전환됩니다.</p>
                <input type="file" name="speaker_wav" accept=".wav">
            </div>

            <label>재생 속도 (speed)</label>
            <input type="number" name="speed" value="1.0" min="0.5" max="2.0" step="0.1">

            <button type="submit">🎵 음성 생성</button>
        </form>
        <div id="result"></div>

        <script>
            function togglePreset() {
                const mode = document.getElementById('modeSelect').value;
                document.getElementById('presetSection').style.display = mode === 'preset' ? 'block' : 'none';
                document.getElementById('cloneSection').style.display  = mode === 'voice_clone' ? 'block' : 'none';
            }
            document.getElementById('ttsForm').onsubmit = async (e) => {
                e.preventDefault();
                document.getElementById('result').innerHTML = '⏳ 생성 중...';
                const formData = new FormData(e.target);
                const res = await fetch('/tts', { method: 'POST', body: formData });
                const data = await res.json().catch(() => ({}));
                if (res.ok && data.success) {
                    if (data.skipped) {
                        document.getElementById('result').innerHTML = '<p>⏭️ TTS 스킵됨</p>';
                    } else {
                        document.getElementById('result').innerHTML =
                            '<p>✅ 완료!</p>' +
                            '<audio controls src="' + data.tts_audio_url + '"></audio>' +
                            '<p><small><a href="' + data.tts_audio_url + '" target="_blank">S3 URL 열기</a></small></p>';
                    }
                } else {
                    document.getElementById('result').innerHTML =
                        '❌ 오류 [' + (data.error_code || '?') + ']: ' + (data.error_message || '') +
                        (data.detail ? '<br><small>' + data.detail + '</small>' : '');
                }
            };
        </script>
    </body>
    </html>
    """


# ── TTS API ───────────────────────────────────────────────────────────────
@app.post("/tts")
async def generate_speech(
    text: str = Form(...),
    mode: str = Form("voice_clone"),               # voice_clone | preset | disabled
    enabled: bool = Form(True),                    # false → TTS 스킵
    speed: float = Form(1.0),                      # 합성 속도
    speaker_wav: Optional[UploadFile] = File(None),        # 선택 사항
    preset_voice_id: Optional[str] = Form(None),           # "male" | "female" | 화자명 직접 입력
):
    # ── 입력 검증 ──────────────────────────────────────────────────────────
    if not text or not text.strip():
        return error_response("INVALID_INPUT", "text가 비어 있습니다.")

    if mode not in ("voice_clone", "preset", "disabled"):
        return error_response("INVALID_INPUT", f"알 수 없는 mode 값: {mode}")

    # ── TTS 비활성화 처리 ──────────────────────────────────────────────────
    if not enabled or mode == "disabled":
        return JSONResponse(content={
            "success": True,
            "skipped": True,
            "tts_audio_url": None,
            "message": "TTS 단계 스킵 (disabled)",
        })

    tmp_id = uuid.uuid4()
    ref_path   = f"/tmp/tts_{tmp_id}_ref.wav"
    clean_path = f"/tmp/tts_{tmp_id}_clean.wav"
    out_path   = f"/tmp/tts_{tmp_id}_output.wav"

    try:
        # ── voice_clone 모드 ────────────────────────────────────────────────
        if mode == "voice_clone":
            has_reference = speaker_wav is not None and speaker_wav.filename

            if has_reference:
                # reference audio 저장 & 전처리
                try:
                    with open(ref_path, "wb") as f:
                        f.write(await speaker_wav.read())
                    audio = AudioSegment.from_file(ref_path)
                    audio = audio.set_frame_rate(22050).set_channels(1)
                    audio.export(clean_path, format="wav")
                except Exception as e:
                    return error_response("TTS_REFERENCE_AUDIO_INVALID", str(e))

                # 음성 클론 TTS 생성
                try:
                    tts_clone.tts_to_file(
                        text=text,
                        speaker_wav=clean_path,
                        language="ko",
                        file_path=out_path,
                        speed=speed,
                    )
                except Exception as e:
                    return error_response("TTS_GENERATION_FAILED", str(e), status_code=500)

            else:
                # ── 샘플 음성 없음 → 기본 화자로 폴백 ───────────────────
                fallback = PRESET_VOICES[DEFAULT_GENDER]
                print(f"⚠️  reference audio 없음 → 기본 화자({fallback})로 폴백")
                try:
                    tts_clone.tts_to_file(
                        text=text,
                        speaker=fallback,
                        language="ko",
                        file_path=out_path,
                        speed=speed,
                    )
                except Exception as e:
                    return error_response("TTS_GENERATION_FAILED", str(e), status_code=500)

        # ── preset 모드 ─────────────────────────────────────────────────────
        elif mode == "preset":
            # "male" / "female" 단축키 또는 화자명 직접 지정, 없으면 기본 성별
            if preset_voice_id in PRESET_VOICES:
                speaker = PRESET_VOICES[preset_voice_id]       # "male" / "female"
            elif preset_voice_id:
                speaker = preset_voice_id                       # 화자명 직접 지정
            else:
                speaker = PRESET_VOICES[DEFAULT_GENDER]        # 기본값
            try:
                tts_clone.tts_to_file(
                    text=text,
                    speaker=speaker,
                    language="ko",
                    file_path=out_path,
                    speed=speed,
                )
            except Exception as e:
                return error_response("TTS_GENERATION_FAILED", str(e), status_code=500)

        # ── S3 업로드 ──────────────────────────────────────────────────────
        s3_key = f"tts/{tmp_id}.wav"
        try:
            tts_audio_url = upload_to_s3(out_path, s3_key)
            print(f"✅ S3 업로드 완료: {tts_audio_url}")
        except (BotoCoreError, ClientError) as e:
            return error_response("UPLOAD_RESULT_FAILED", str(e), status_code=500)

        return JSONResponse(content={
            "success": True,
            "tts_audio_url": tts_audio_url,
        })

    finally:
        # 임시 파일 정리
        for path in [ref_path, clean_path, out_path]:
            if os.path.exists(path):
                os.remove(path)