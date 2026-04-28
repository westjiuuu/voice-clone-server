# 🚀 TTS API 로컬 배포 가이드 (ngrok)

> 로컬 FastAPI 서버를 외부에서 접근 가능한 URL로 공개하는 방법입니다.

---

## 📋 사전 준비

- Python 가상환경 (`.venv`) 및 TTS 패키지 설치 완료
- `C:\tts\` 폴더에 `server.py` 파일 존재

---

## STEP 1. FastAPI 패키지 설치

터미널에서 아래 명령어 실행:

```
C:\tts\.venv\Scripts\pip.exe install fastapi uvicorn python-multipart
```

---

## STEP 2. ngrok 설치

### 2-1. zip 파일 다운로드

아래 링크에서 Windows용 ngrok 다운로드:

```
https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip
```

> ⚠️ Microsoft Store 버전 사용 금지 (버그 있음)

### 2-2. 압축 해제

1. 다운로드된 `ngrok-v3-stable-windows-amd64.zip` 우클릭
2. **"모두 압축 풀기"** 클릭
3. 압축 해제 경로를 `C:\tts\` 로 지정
4. `C:\tts\ngrok.exe` 파일이 생성되면 완료

### 2-3. ngrok 회원가입 및 토큰 등록

1. [https://ngrok.com](https://ngrok.com) 에서 무료 회원가입
2. 로그인 후 대시보드에서 **authtoken** 복사
3. 터미널에서 아래 명령어 실행 (토큰 붙여넣기):

```
C:\tts\ngrok.exe config add-authtoken 여기에_토큰_붙여넣기
```

---

## STEP 3. 서버 실행 (터미널 2개 필요)

### 터미널 1 — FastAPI 서버 시작

```
cd C:\tts
.\.venv\Scripts\uvicorn.exe server:app --host 0.0.0.0 --port 8000
```

아래 메시지가 뜨면 서버 정상 실행:

```
✅ 모델 로딩 완료! (device: cuda)
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 터미널 2 — ngrok 실행

```
C:\tts\ngrok.exe http 8000
```

아래처럼 Forwarding URL이 뜨면 성공:

```
Session Status    online
Forwarding        https://xxxx.ngrok-free.app -> http://localhost:8000
```

---

## STEP 4. API 테스트

### 4-1. Swagger UI 

```
http://localhost:8000/docs
```

또는 ngrok URL로도 접근 가능:

```
https://xxxx.ngrok-free.app/docs
```

**사용 방법:**

1. `/tts` 항목 클릭
2. **"Try it out"** 버튼 클릭
3. `text` 입력란에 텍스트 작성
4. `speaker_wav` 에서 WAV 파일 선택
5. **"Execute"** 클릭 → 하단에 음성 파일 다운로드 버튼 생성 ✅


---

### 4-2. API 테스트 (Postman)

| 항목 | 값 |
|------|-----|
| Method | `POST` |
| URL | `https://xxxx.ngrok-free.app/tts` |
| Body 타입 | `form-data` |

**Body 파라미터:**

| KEY | TYPE | VALUE |
|-----|------|-------|
| `text` | Text | 생성할 텍스트 입력 |
| `speaker_wav` | File | 참조 음성 WAV 파일 선택 |

Send 클릭 → 음성 파일(.wav) 다운로드 완료 ✅

---

## STEP 5. 백엔드 코드에서 호출하기

```python
import requests

response = requests.post(
    "https://xxxx.ngrok-free.app/tts",
    data={"text": "안녕하세요"},
    files={"speaker_wav": open("목소리.wav", "rb")}
)

with open("output.wav", "wb") as f:
    f.write(response.content)
```

---

## ⚠️ 주의사항

- PC가 꺼지거나 터미널을 닫으면 URL이 끊깁니다
- **터미널 2개를 항상 동시에 켜둬야 합니다** (FastAPI + ngrok)
