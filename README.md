<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=220&color=0:FF6B6B,50:4ECDC4,100:45B7D1&text=SKN20-4TH-5TEAM&fontSize=50&fontColor=FFFFFF&section=header&desc=Advanced%20RAG%20Disaster%20Response%20System&descSize=18" />
</p>

<p align="center">
  🚨 <strong>민방위 대피시설 + 재난 행동요령 데이터 기반 Advanced RAG 시스템</strong><br>
  <sub>SK Networks Family 20기 — 4TH 5TEAM | <b>프론트앤드 중점,,,?</b></sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Frontend-Django-092E20?style=for-the-badge&logo=django&logoColor=white"/>
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/Map-Kakao_Maps-FFCD00?style=for-the-badge&logo=kakao&logoColor=black"/>
  <img src="https://img.shields.io/badge/Route-T_Map-00B4E7?style=for-the-badge"/>
</p>

---

## 🔄 3rd 프로젝트 대비 주요 변경 사항

> **이 프로젝트는 3rd 프로젝트를 기반으로 전면적인 아키텍처 개편 및 기능 고도화를 수행했습니다.**

| 구분 | 3rd 프로젝트 | 4th 프로젝트 (현재) |
|------|-------------|-------------------|
| **아키텍처** | 단일 FastAPI + HTML | **Backend/Frontend 분리 (MSA)** |
| **프론트엔드** | 단일 HTML 파일 | **Django 템플릿 + 정적 파일 분리** |
| **지도 API** | Naver Maps | **Kakao Maps (전면 전환)** |
| **로드뷰** | Naver Panorama | **Kakao Roadview** |
| **길찾기 API** | 카카오 모빌리티 (자동차) | **T Map 보행자 경로 API** |
| **UI/UX** | 기본 UI | **슬라이딩 패널 + 애니메이션 + 봇 아바타** |
| **의도 분류** | 8개 카테고리 | **8개 + Intent 응답 필드 추가** |
| **성능 측정** | 없음 | **LangGraph/API 처리 시간 측정** |

---

## 👥 팀 구성

| <img src="./image/쿼카.jpeg" width="150"> <br> 문창교 |  <img src="./image/dak.jpeg" width="150"> <br> 권규리 |  <img src="./image/rich.jpeg" width="150"> <br> 김황현 |  <img src="./image/loopy.jpeg" width="150"> <br> 김효빈 |  <img src="./image/ham.jpeg" width="150"> <br> 이승규 |
|:------:|:------:|:------:|:------:|:------:|
| <a href="https://github.com/mck1902"><img src="https://img.shields.io/badge/GitHub-mck1902-blue?logo=github"></a> | <a href="https://github.com/gyur1eek"><img src="https://img.shields.io/badge/GitHub-gyur1eek-yellow?logo=github"></a> | <a href="https://github.com/hyun2kim"><img src="https://img.shields.io/badge/GitHub-khyun2kim-green?logo=github"></a> | <a href="https://github.com/kimobi"><img src="https://img.shields.io/badge/GitHub-kimobi-pink?logo=github"></a> | <a href="https://github.com/neobeauxarts"><img src="https://img.shields.io/badge/GitHub-neobeauxarts-lightblue?logo=github"></a> |

---

## 💻 기술 스택

| 분류 | 사용 기술 |
|------|-----------|
| **언어** | ![Python](https://img.shields.io/badge/Python-3776AB.svg?style=flat&logo=python&logoColor=white) Python 3.13 |
| **프론트엔드** | ![Django](https://img.shields.io/badge/Django-092E20.svg?style=flat&logo=django&logoColor=white) Django (템플릿 엔진)<br>![HTML5](https://img.shields.io/badge/HTML5-E34F26.svg?style=flat&logo=html5&logoColor=white) HTML5<br>![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E.svg?style=flat&logo=javascript&logoColor=black) JavaScript (ES6+)<br>![TailwindCSS](https://img.shields.io/badge/Tailwind-06B6D4.svg?style=flat&logo=tailwindcss&logoColor=white) TailwindCSS |
| **백엔드** | ![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?style=flat&logo=fastapi&logoColor=white) FastAPI (포트 8001) |
| **AI 프레임워크** | ![LangChain](https://img.shields.io/badge/LangChain-1E8C7E.svg?style=flat&logo=chainlink&log
# 백엔드
pip install -r backend/requirements.txt

# 프론트엔드
pip install -r frontend/requirements.txt
```

### 3️⃣ VectorDB (ChromaDB)

> ✅ **이미 존재하는 `chroma_db/` 폴더 사용 **

```
SKN20-4TH-5TEAM/
└── chroma_db/                    ← 이미 임베딩 완료된 DB 포함
    ├── chroma.sqlite3
    └── c41f94b5-.../
```

| 항목 | 내용 |
|------|------|
| **대피소 데이터** | 17,292개 민방위 대피시설 |
| **재난 행동요령** | 자연재난 8종 + 사회재난 5종 |
| **임베딩 모델** | OpenAI `text-embedding-3-small` |
| **검색 방식** | Hybrid (Vector 60-70% + BM25 30-40%) |

### 4️⃣ 서버 실행

```bash
# 터미널 1: Backend (FastAPI)
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# 터미널 2: Frontend (Django)
cd frontend
python manage.py runserver 0.0.0.0:8000
```

### 5️⃣ 접속

- **Frontend**: http://localhost:8000
- **Backend API Docs**: http://localhost:8001/docs

---

## 🔧 API 엔드포인트

### `POST /api/location/extract` ⭐ 메인 API

**Request:**
```json
{
  "query": "강남역 근처인데 지진 났어"
}
```

**Response:**
```json
{
  "success": true,
  "location": "강남역",
  "coordinates": [37.4979, 127.0276],
  "shelters": [
    {
      "name": "강남역지하상가",
      "address": "서울 강남구 강남대로 지하396",
      "lat": 37.4979,
      "lon": 127.0276,
      "distance": 0.12,
      "capacity": 5000
    }
  ],
  "total_count": 3,
  "message": "🚨 강남역 근처 지진 발생 시 대응 가이드\n\n📍 가장 가까운 대피소 3곳\n...",
  "intent": "hybrid_location_disaster"  // ⭐ 4th에서 추가
}
```

### `GET /api/shelters/nearest`

GPS 좌표 기반 가장 가까운 대피소 검색

### `GET /api/directions` ⭐ 신규 (T Map)

**Query Parameters:**
- `origin`: 출발지 좌표 (lon,lat)
- `destination`: 도착지 좌표 (lon,lat)

**Response:** GeoJSON 형식의 보행자 경로

---

## 🎨 UI/UX 기능 총정리

### 📐 레이아웃 & 구조

| 기능 | 설명 | 구현 위치 |
|------|------|----------|
| **반응형 2분할 레이아웃** | 지도(7) : 채팅(3) 비율의 Flexbox 구조 | `shelter.html` |
| **헤더 영역** | 타이틀 + 사이렌 아이콘 + LLM 상태 배지 | `shelter.html` |
| **지도 영역** | Kakao Maps 전체화면 지도 | `shelter.html`, `shelter.js` |
| **로드뷰 영역** | 클릭 시 하단 50% 확장되는 Kakao Roadview | `shelter.html`, `shelter.js` |
| **채팅 영역** | 스크롤 가능한 대화 히스토리 | `shelter.html` |
| **컨트롤 패널** | GPS 버튼, 입력창, 전송 버튼, 클리어 버튼 | `shelter.html` |

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🚨 재난 안전 챗봇                                        [LLM ON] 🤖  │
├───────────────────────────────────────────┬─────────────────────────────┤
│                                           │  🛡️ 대피소 도우미           │
│                                           │  안녕하세요! 대피소를       │
│              🗺️ 지도 영역                 │  검색해드립니다.            │
│              (Kakao Maps)                 │                             │
│                                           │  👤 강남역 근처 대피소      │
│                                           │                             │
│                                           │  🛡️ 검색 결과입니다...      │
├───────────────────────────────────────────┼─────────────────────────────┤
│              📷 로드뷰 영역               │  [📍 현위치] [🗑️]           │
│              (클릭 시 확장)               │  [입력창...        ] [전송] │
└───────────────────────────────────────────┴─────────────────────────────┘
이미지 여따가 넣읍시다!
```

---

### 🗺️ 지도 & 마커 기능

| 기능 | 설명 | 함수/코드 |
|------|------|----------|
| **현위치 마커** | GPS 기반 파란색 "📍 현재 위치" 오버레이 | `createUserMarker()` |
| **검색 위치 마커** | 검색한 장소에 파란색 위치명 오버레이 | `showMapWithMultipleShelters()` |
| **대피소 마커** | 검색 결과 대피소들에 기본 마커 표시 | `showMapWithMultipleShelters()` |
| **정보창 (InfoWindow)** | 마커 클릭 시 대피소 상세 정보 팝업 | `kakao.maps.InfoWindow` |
| **지도 범위 자동 조정** | 모든 마커가 보이도록 `setBounds()` | `showMapWithMultipleShelters()` |
| **로드뷰 연동** | 지도/마커 클릭 시 해당 위치 로드뷰 표시 | `panorama.setPanoId()` |

---

### 💬 채팅 인터페이스

| 기능 | 설명 | 함수/코드 |
|------|------|----------|
| **사용자 메시지** | 우측 정렬, 빨간색 배경 말풍선 | `addMessage("user", ...)` |
| **봇 메시지** | 좌측 정렬, 흰색 배경 + 아바타 | `addMessage("bot", ...)` |
| **결과 메시지** | 좌측 정렬, 초록색 테두리 강조 | `addMessage("bot", ..., true)` |
| **봇 아바타** | 정지 이미지 → 최신 메시지만 GIF 애니메이션 | `bot2.png`, `bot2_talking_v2.gif` |
| **채팅창 클리어** | 🗑️ 버튼으로 대화 초기화 | `clearChatWindow()` |
| **자동 스크롤** | 새 메시지 시 최하단으로 스크롤 | `chatWindow.scrollTop` |

---

### 🚶 길찾기 & 경로 안내 ⭐ 4th 강화

| 기능 | 설명 | 함수/코드 |
|------|------|----------|
| **T Map 보행자 경로** | 걸어서 대피소까지 최적 경로 | `drawRoute()` |
| **경로 폴리라인** | 파란색 실선으로 경로 시각화 | `kakao.maps.Polyline` |
| **출발/도착 마커** | S(초록), E(빨강) 원형 오버레이 | `CustomOverlay` |
| **이동 애니메이션** | 🚶 아이콘이 경로 따라 이동 | `animateMovingArrow()` |
| **방향 자동 반전** | 진행 방향에 따라 좌우 반전 | `scaleX(-1)` / `scaleX(1)` |

---

### 📋 슬라이딩 패널 (길찾기 상세) ⭐ 4th 신규

```
┌─────────────────────────────────────────────────────┐
│ 🚶 길찾기 상세 안내                          [X]   │
├─────────────────────────────────────────────────────┤
│     총 거리              │       소요 시간         │
│     1.2km                │         15분            │
├─────────────────────────────────────────────────────┤
│  ① 직진하여 강남대로로 진입                         │
│     → 200m 이동                                     │
│  ② 우회전하여 테헤란로로 진입                       │
│     → 150m 이동                                     │
│  ③ 목적지 도착                                      │
├─────────────────────────────────────────────────────┤
│  [AD] MCK 맥북 구함                                 │
└─────────────────────────────────────────────────────┘
여따가 광고랑 그 길찾기 이미지 넣읍시다!
```

| 기능 | 설명 | 함수/코드 |
|------|------|----------|
| **토글 버튼** | 🛣️ 버튼으로 패널 열기/닫기 | `toggleNavDrawer()` |
| **슬라이드 애니메이션** | `translate-x` 기반 좌측 슬라이드 | `transition-transform` |
| **요약 정보** | 총 거리(km), 소요 시간(분) | `nav-summary` |
| **단계별 안내** | 번호 + 설명 + 이동 거리 | `nav-list` |
| **커스텀 스크롤바** | 초록색 테마 스크롤바 | `.custom-scrollbar` |

---

### ✨ 애니메이션 효과

| 애니메이션 | 설명 | CSS Keyframes |
|------------|------|---------------|
| **사이렌 경광등** | 🚨 아이콘 3D 회전 + 빛 번쩍 효과 | `@keyframes real-siren` |
| **걷는 아이콘** | 🚶 아이콘 좌우 흔들림 | `@keyframes walking` |
| **봇 말하기** | 아바타 확대/축소 + 살짝 기울임 | `@keyframes bot-talking` |
| **LLM 배지 펄스** | ON 상태 시 깜빡임 | `animate-pulse` (Tailwind) |


---

### 🎛️ 상태 표시 & 컨트롤

| 기능 | 설명 | 구현 |
|------|------|------|
| **LLM 상태 배지** | ON(초록)/규칙기반(주황)/OFF(회색) | `updateLlmBadge()` |
| **버튼 비활성화** | 로딩 중 반투명 + `cursor: not-allowed` | `.disabled-control` |
| **로드뷰 닫기 버튼** | ✕ 버튼으로 로드뷰 숨김 | `hidePanorama()` |

---

## ⚙️ LangGraph Agent 구조

```
[사용자 쿼리]
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  Intent Classifier Node                                         │
│  └─ 8개 카테고리 분류 (키워드 우선 매칭 → LLM 폴백)              │
│     ├─ hybrid_location_disaster (위치 + 재난)                   │
│     ├─ shelter_info (시설명 검색)                               │
│     ├─ shelter_search (위치 기반 검색)                          │
│     ├─ shelter_count (개수 통계)                                │
│     ├─ shelter_capacity (수용인원 기준)                         │
│     ├─ disaster_guideline (행동요령)                            │
│     ├─ general_knowledge (일반 지식)                            │
│     └─ general_chat (일상 대화)                                 │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  Query Rewrite Node                                              │
│  └─ BM25 최적화: 조사 제거, 핵심 키워드 추출, 동의어 추가         │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  Agent Node → 7개 Tools 선택                                    │
│  ├─ search_shelter_by_location (Kakao API + Haversine)          │
│  ├─ search_shelter_by_name (시설명 검색)                        │
│  ├─ search_location_with_disaster (복합 검색)                   │
│  ├─ count_shelters (통계)                                       │
│  ├─ search_shelter_by_capacity (수용인원 필터)                  │
│  ├─ search_disaster_guideline (하이브리드 검색)                 │
│  └─ answer_general_knowledge (LLM 직접 응답)                    │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
[structured_data + message 응답]
```

---

## 📊 성능 지표

```
[성능지표 등등등] 
```

---

## 📊 성능 측정 결과

```
[API 요청 시작] 
```

---

## 🌱 향후 개선 계획

- [ ] Docker Compose로 원클릭 배포
- [ ] 실시간 재난 알림 Push 연동
- [ ] 카테고리별 대피소 필터링 (장애인, 유아, 반려동물)
- [ ] 다국어 지원 (영어, 중국어, 일본어)
- [ ] RAG 평가 지표 적용 (RAGAS)
- [ ] 음성 입력/출력 지원

---

## 📝 라이선스

이 프로젝트는 SK Networks Family 20기 AI 교육 과정의 일환으로 제작되었습니다.

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=120&color=0:FF6B6B,50:4ECDC4,100:45B7D1&section=footer" />
</p>
