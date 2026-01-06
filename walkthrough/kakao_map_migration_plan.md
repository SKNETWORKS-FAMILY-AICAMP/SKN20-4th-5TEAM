# 계획: 카카오 지도 API로 전환

이 계획은 프론트엔드 지도 서비스를 네이버에서 카카오로 교체하는 단계를 설명합니다.

## 제안된 변경 사항

### [프론트엔드 (Django/JS)]

#### [수정] [settings.py](file:///d:/SKN20-4th-5TEAM/frontend/frontend/settings.py)
- `KAKAO_MAP_API_KEY` 설정을 추가하여 템플릿에서 사용할 수 있도록 합니다.

#### [수정] [views.py](file:///d:/SKN20-4th-5TEAM/frontend/main/views.py)
- 템플릿 컨텍스트에 `kakao_map_api_key`를 추가하여 전달합니다.

#### [수정] [shelter.html](file:///d:/SKN20-4th-5TEAM/frontend/templates/shelter.html)
- 네이버 지도 스크립트를 주석 처리하고 카카오 지도 SDK 스크립트를 추가합니다.

#### [수정] [shelter.js](file:///d:/SKN20-4th-5TEAM/frontend/static/js/shelter.js)
- `naver.maps` 의존성을 `kakao.maps`로 전면 교체합니다.
- 로드뷰 및 마커 로직을 카카오 방식에 맞춰 재구현합니다.

## 검증 계획
- 지도 노출 확인
- 현위치 마커 확인
- 대피소 검색 결과 마커 표시 확인
- 로드뷰(거리뷰) 연동 확인
