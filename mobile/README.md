# 매매일지 iOS 앱 (React Native / Expo)

기존 Streamlit 웹앱과 같은 데이터(Turso DB)를 사용하는 **진짜 네이티브 iOS 앱**입니다.
Mac 없이 Windows에서 개발하고, 빌드는 Expo의 클라우드 macOS 빌드 서비스(EAS Build)가
대신 해줍니다.

## 구조

```
stock-trading-log-tracker/
├── app.py, db.py, analytics.py, ...   # 기존 Streamlit 웹앱
├── api_server.py                      # 이 앱이 호출하는 REST API (FastAPI)
├── requirements-api.txt               # API 서버 의존성
└── mobile/                            # 이 폴더 - iOS/Android 앱 (Expo)
```

`api_server.py`는 기존 `db.py`/`analytics.py`/`price_data.py`를 그대로 재사용하므로,
Streamlit 앱과 이 iOS 앱은 **같은 매매 기록(같은 Turso DB)** 을 공유합니다.

현재 MVP 범위: **매매일지(추가/수정/삭제) + 성과분석(보유 종목, 실현/평가손익, 승률)**.
배당금/목표가·손절가/노트 탭은 아직 없습니다 (다음 단계).

## 1. API 서버 배포

앱이 인터넷 어디서든 접속하려면 `api_server.py`를 배포해야 합니다 (로컬 PC에서만
띄우면 같은 와이파이에서만 접속 가능).

### 옵션 A: Render.com (무료 티어, 추천)

1. Render 대시보드에서 "New Web Service" → 이 GitHub 레포 연결
2. Build Command: `pip install -r requirements-api.txt`
3. Start Command: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`
4. Environment Variables:
   - `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` (Streamlit 앱에서 쓰던 것과 동일하게)
   - `API_KEY` (아무 임의의 문자열 - 앱과 서버가 이 값으로 인증. 설정하지 않으면 인증 없이 열림)
5. 배포되면 `https://xxxx.onrender.com` 같은 주소가 생김 - 이걸 앱 설정 탭에 입력

무료 티어는 일정 시간 요청이 없으면 서버가 잠들어서, 앱에서 첫 요청이 몇 초 느릴 수
있습니다. 불편하면 유료 플랜이나 Fly.io 등으로 바꿀 수 있습니다.

### 옵션 B: 로컬 PC + 같은 와이파이 (테스트용)

```bash
pip install -r requirements-api.txt
export TURSO_DATABASE_URL=...   # 안 쓰면 로컬 SQLite 파일 사용
export TURSO_AUTH_TOKEN=...
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

PC의 로컬 IP(예: `192.168.0.5`)를 앱 설정 탭에 `http://192.168.0.5:8000`로 입력.
외부망(다른 와이파이/모바일 데이터)에서는 접속 안 됨 - 배포 전 빠른 확인용.

## 2. 앱 개발 환경 (Windows에서도 가능)

```bash
cd mobile
npm install
npx expo start
```

QR 코드가 뜨면 아이폰에 **Expo Go** 앱(App Store에서 무료 설치)을 깔고 스캔하면
실제 아이폰에서 바로 실행됩니다 - Mac도, 빌드도 필요 없습니다. 개발 중 코드를
고치면 앱이 자동으로 갱신됩니다 (Hot Reload).

앱을 열면:
1. **설정** 탭에서 위에서 배포한 API 서버 주소(및 API Key)를 입력하고 "연결 테스트"
2. **매매일지** 탭에서 우측 하단 `+` 버튼으로 매매 기록 추가/수정/삭제
3. **성과분석** 탭에서 보유 종목별 평가손익, 총 실현손익, 승률 확인

## 3. 진짜 앱 아이콘으로 설치하기 (App Store 없이)

Expo Go 없이 이 앱만 따로 설치하고 싶다면 "개발 빌드"를 만들면 됩니다 (Apple Developer
계정 없이도 가능, 7일마다 재설치 필요 - 무료 Apple ID 기준). 필요하면 알려주시면
EAS Build 설정을 추가해드릴게요.

## 4. App Store에 정식 제출하기

전제 조건: **Apple Developer Program 가입** (연 $99, https://developer.apple.com/programs/).
Mac 없이도 아래 과정은 전부 Windows에서 가능합니다 - 실제 컴파일은 Expo의 클라우드
macOS가 대신 해줍니다.

```bash
npm install -g eas-cli
eas login                     # Expo 계정 (무료 가입)
eas build:configure           # 최초 1회, eas.json 생성
eas build --platform ios      # 클라우드에서 .ipa 빌드 (Apple Developer 계정 로그인 필요)
eas submit --platform ios     # 빌드된 .ipa를 App Store Connect에 제출
```

첫 `eas build`를 실행하면 Apple 인증서/프로비저닝 프로파일을 EAS가 자동으로
만들어줄지 물어봅니다 (권장: 예). 이후 App Store Connect에서 스크린샷, 앱 설명 등을
채우고 심사 제출하면 됩니다.

진행하기 전에 `app.json`의 `ios.bundleIdentifier`(현재 `com.example.stocktradingjournal`)를
본인 소유의 고유한 값으로 바꿔야 합니다 (예: `com.<본인영문이름>.stocktradingjournal`).

## 참고: 왜 이 구조인가

- Xcode는 macOS 전용이라 Windows에서 직접 컴파일할 수 없습니다 (Apple 정책).
- React Native(Expo)로 개발하면 코드는 Windows/Linux 어디서든 작성 가능하고,
  실제 iOS 빌드만 Expo의 클라우드 macOS 빌드 서비스(EAS Build)가 대신 처리합니다.
- 결과물은 웹뷰를 감싼 껍데기 앱이 아니라 실제 컴파일된 네이티브 앱이라 App Store
  심사(가이드라인 4.2 "최소 기능")에도 정상적으로 제출할 수 있습니다.
