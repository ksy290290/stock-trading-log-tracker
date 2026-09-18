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

레포 루트에 `render.yaml`(Blueprint)을 만들어뒀습니다. Render 대시보드에서 계정 생성 후
"New" → "Blueprint" → 이 GitHub 레포 선택하면 위 서비스 설정(빌드/시작 명령)이 자동으로
채워집니다. 이 단계는 Render 계정이 필요해서 대신 해드릴 수 없고, 직접 로그인해서
진행하셔야 합니다.

1. https://dashboard.render.com → "New" → "Blueprint" → `ksy290290/stock-trading-log-tracker` 선택
2. 환경변수 입력 (자동으로 입력창이 뜸):
   - `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` (Streamlit 앱에서 쓰던 것과 동일하게 - Turso
     대시보드 또는 `.streamlit/secrets.toml`에서 확인 가능)
   - `API_KEY` (아무 임의의 문자열 - 앱과 서버가 이 값으로 인증. 비워두면 인증 없이 열림)
3. 배포되면 `https://xxxx.onrender.com` 같은 주소가 생김 - 이걸 앱 설정 탭에 입력

Blueprint 없이 수동으로 하고 싶다면 "New Web Service"로 직접 만들고 Build/Start
Command만 `render.yaml`에 적힌 값을 그대로 입력해도 됩니다.

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

## 3. 내 아이폰에 진짜 앱으로 설치하기 (EAS Build, 나 혼자 쓰는 용도)

**정정**: 이전에 "무료 Apple ID로도 개발 빌드 설치 가능"이라고 안내했는데, 그건 Mac +
Xcode로 USB 연결해서 로컬 설치할 때만 해당되는 얘기였습니다. Mac이 없어서 EAS의
클라우드 빌드 서비스로 실제 아이폰에 설치 가능한 `.ipa`를 만들려면, App Store에 올리지
않고 **나 혼자 쓰는 용도라 해도 Apple Developer Program(연 $99, https://developer.apple.com/programs/)
가입이 필요**합니다. 실제 기기용 프로비저닝 프로파일 발급 자체가 유료 계정 기능이라
이 부분은 우회할 방법이 없습니다 (Expo Go 안에서만 쓴다면 계속 무료입니다).

`eas.json`은 이미 만들어뒀습니다 (`development`/`preview`/`production` 3가지 빌드
프로필). 나 혼자 매일 쓰는 용도로는 개발 서버 연결이 필요 없는 **`preview` 프로필**을
추천합니다 (`development`은 코딩하면서 실시간으로 갱신해보는 용도라 PC에서 `npx expo start`가
켜져 있어야 합니다).

```bash
npm install -g eas-cli
eas login                             # Expo 계정 (무료 가입)
eas device:create                     # 내 아이폰을 EAS에 등록 (링크가 뜨면 아이폰 사파리에서 열기)
eas build --platform ios --profile preview
```

처음 실행하면 Apple 계정 로그인과 인증서/프로비저닝 프로파일 자동 생성 여부를 물어봅니다
(권장: 예). 빌드가 끝나면 QR 코드/링크가 뜨는데, 아이폰 사파리로 열어서 설치하면
홈 화면에 진짜 앱 아이콘으로 들어갑니다. 프로비저닝 프로파일은 보통 1년 유효합니다.

진행하기 전에 `app.json`의 `ios.bundleIdentifier`(현재 `com.example.stocktradingjournal`)를
본인 소유의 고유한 값으로 바꾸는 걸 권장합니다 (예: `com.<본인영문이름>.stocktradingjournal`).

## 4. App Store에 정식 제출하기 (나중에, 필요해지면)

위 3번 단계와 똑같은 Apple Developer Program 계정을 그대로 씁니다. 프로필만
`production`으로 바꿔서 빌드하고 제출하면 됩니다.

```bash
eas build --platform ios --profile production
eas submit --platform ios --profile production
```

빌드가 끝나면 App Store Connect(https://appstoreconnect.apple.com)에서 스크린샷,
앱 설명 등을 채우고 심사 제출하면 됩니다.

## 참고: 왜 이 구조인가

- Xcode는 macOS 전용이라 Windows에서 직접 컴파일할 수 없습니다 (Apple 정책).
- React Native(Expo)로 개발하면 코드는 Windows/Linux 어디서든 작성 가능하고,
  실제 iOS 빌드만 Expo의 클라우드 macOS 빌드 서비스(EAS Build)가 대신 처리합니다.
- 결과물은 웹뷰를 감싼 껍데기 앱이 아니라 실제 컴파일된 네이티브 앱이라 App Store
  심사(가이드라인 4.2 "최소 기능")에도 정상적으로 제출할 수 있습니다.
