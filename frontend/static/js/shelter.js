/* ═══════════════════════════════════════════════════════════════════
 * 전역 변수 및 상수
 * ═══════════════════════════════════════════════════════════════════ */

// API 주소 (Django에서 주입)
// const API_BASE_URL = window.FASTAPI_URL || 'http://127.0.0.1:8443'; // 기존 설정
const API_BASE_URL = window.FASTAPI_URL || 'http://127.0.0.1:8001'; // 2026-01-06: 기본 포트를 8001로 수정

let USE_LLM = false;
let API_AVAILABLE = false;

// 지도 및 마커 전역 변수
let map, panorama;
let userMarker = null;
let markers = [];
let infoWindows = [];
let currentPath = null; // 2026-01-06: 현재 지도에 그려진 경로(Polyline)
let routeMarkers = [];  // 2026-01-06: 길찾기 출발/도착 지점 마커 관리
let currentUserPosition = null;

/**
 * [2026-01-06 추가] 슬라이딩 패널 제어 (열기/닫기)
 */
function toggleNavDrawer() {
    const drawer = document.getElementById('nav-drawer');
    if (!drawer) return;

    const isHidden = drawer.classList.contains('-translate-x-full');
    if (isHidden) {
        openNavDrawer();
    } else {
        closeNavDrawer();
    }
}

function openNavDrawer() {
    const drawer = document.getElementById('nav-drawer');
    const toggleBtn = document.getElementById('nav-toggle-btn');
    if (drawer) drawer.classList.remove('-translate-x-full');
    // 패널 열릴 때 토글 버튼에 '열림' 상태 표시 가능 (선택적)
}

function closeNavDrawer() {
    const drawer = document.getElementById('nav-drawer');
    if (drawer) drawer.classList.add('-translate-x-full');
}

/**
 * [2026-01-06 제거] 기존 팝업 닫기 함수를 슬라이딩 패널 시나리오에 응용
 */
function hideNavigationPanel() {
    closeNavDrawer();
}

// DOM 요소
const chatWindow = document.getElementById('chat-window');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const geoBtn = document.getElementById('geo-btn');
const initialMessageEl = document.getElementById('initial-message');

// [2026-01-06 수정] 슬라이딩 패널 연동
const navSummary = document.getElementById('nav-summary');
const navList = document.getElementById('nav-list');
const navToggleBtn = document.getElementById('nav-toggle-btn');

// 상수
const EARTH_RADIUS = 6371;


/* ═══════════════════════════════════════════════════════════════════
 * 유틸리티 함수
 * ═══════════════════════════════════════════════════════════════════ */

function safeLatLng(lat, lon) {
    const a = Number(lat);
    const b = Number(lon);
    if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
    // return new naver.maps.LatLng(a, b); // 2026-01-06 주석 처리
    return new kakao.maps.LatLng(a, b);
}

/**
 * 각도를 라디안으로 변환
 */
const toRad = deg => deg * Math.PI / 180;

/**
 * Haversine 공식으로 두 좌표 간 거리 계산 (km)
 */
function haversine(lat1, lon1, lat2, lon2) {
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 +
        Math.sin(dLon / 2) ** 2 *
        Math.cos(toRad(lat1)) *
        Math.cos(toRad(lat2));
    return EARTH_RADIUS * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}


/* ═══════════════════════════════════════════════════════════════════
 * UI 관련 함수
 * ═══════════════════════════════════════════════════════════════════ */

/**
 * 파노라마 표시
 */
function showPanorama() {
    const mapDiv = document.getElementById('map');
    const panoContainer = document.getElementById('pano-container'); // 2026-01-06: 부모 컨테이너 참조
    const placeholder = document.getElementById('pano-placeholder');
    const closeBtn = document.getElementById('pano-close-btn');

    if (mapDiv && panoContainer) {
        mapDiv.style.height = '50%';
        panoContainer.style.height = '50%'; // 부모 높이 조절
        if (placeholder) placeholder.style.display = 'none';
        if (closeBtn) closeBtn.classList.remove('hidden');
        console.log('📷 로드뷰 표시');
    }
}

/**
 * 파노라마(로드뷰) 숨김
 */
function hidePanorama() {
    const mapDiv = document.getElementById('map');
    const panoContainer = document.getElementById('pano-container'); // 2026-01-06: 부모 컨테이너 참조
    const placeholder = document.getElementById('pano-placeholder');
    const closeBtn = document.getElementById('pano-close-btn');

    if (mapDiv && panoContainer) {
        mapDiv.style.height = '100%';
        panoContainer.style.height = '0%'; // 부모 높이 조절

        // 2026-01-06: 카카오 로드뷰는 setVisible을 지원하지 않으므로 주석 처리
        // if (panorama) panorama.setVisible(false); 

        if (placeholder) placeholder.style.display = 'flex';
        if (closeBtn) closeBtn.classList.add('hidden');
        console.log('🗺️ 로드뷰 숨김');
    }
}

/**
 * 채팅창 클리어
 */
function clearChatWindow() {
    while (chatWindow.children.length > 1) {
        chatWindow.removeChild(chatWindow.lastChild);
    }
    hidePanorama();
    console.log('💬 채팅창 클리어 완료');
}

/**
 * 컨트롤 버튼 활성화/비활성화
 */
function setControlsDisabled(disabled) {
    [sendBtn, geoBtn, chatInput].forEach(element => {
        element.disabled = disabled;
        if (disabled) {
            element.classList.add("disabled-control");
        } else {
            element.classList.remove("disabled-control");
        }
    });
}

/**
 * LLM 상태 배지 업데이트
 */
function updateLlmBadge() {
    const badge = document.getElementById('llm-status');
    if (API_AVAILABLE && USE_LLM) {
        badge.className = "llm-badge llm-on";
        badge.textContent = "🤖 LLM ON";
    } else if (API_AVAILABLE) {
        badge.className = "llm-badge llm-off";
        badge.textContent = "📍 규칙 기반";
    } else {
        badge.className = "llm-badge llm-off";
        badge.textContent = "📂 로컬 모드";
    }
}

/**
 * 채팅 메시지 추가
 */
function addMessage(sender, text, isResult = false) {
    const wrap = document.createElement('div');
    const box = document.createElement('div');

    if (sender === "user") {
        wrap.className = "flex justify-end";
        box.className = "bg-red-100 text-gray-900 p-3 rounded-2xl rounded-tr-none max-w-[80%] shadow-sm";
        box.innerHTML = text;
    } else {
        wrap.className = "flex justify-start";
        if (isResult) {
            box.style.backgroundColor = "#22c55e";
            box.style.color = "#FFFFFF";
            box.className = "p-3 rounded-2xl rounded-tl-none max-w-[90%] shadow-lg";
            box.innerHTML = `<p class="font-bold text-lg mb-1">📍 대피소 검색 결과</p>${text}`;
        } else {
            box.className = "bg-gray-100 text-gray-800 p-3 rounded-2xl rounded-tl-none max-w-[80%] shadow-sm";
            box.innerHTML = `<p class="font-semibold mb-1">🛡️ 대피소 도우미</p>${text}`;
        }
    }

    wrap.appendChild(box);
    chatWindow.appendChild(wrap);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

/**
 * 모든 정보창 닫기
 */
function closeAllInfoWindows() {
    infoWindows.forEach(window => window.close());
    infoWindows = [];
}


/* ═══════════════════════════════════════════════════════════════════
 * API 통신 함수
 * ═══════════════════════════════════════════════════════════════════ */

/**
 * API 상태 확인
 */
async function checkApiStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/status`);
        if (response.ok) {
            const data = await response.json();
            API_AVAILABLE = true;
            USE_LLM = data.llm_available;
        }
    } catch (error) {
        API_AVAILABLE = false;
        USE_LLM = false;
    }
    updateLlmBadge();
}

/**
 * LLM으로 위치 추출
 */
async function extractLocationWithLLM(query) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/location/extract`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, use_llm: USE_LLM })
        });
        return response.ok ? await response.json() : null;
    } catch (error) {
        return null;
    }
}

/**
 * 좌표로 가까운 대피소 검색
 */
async function searchSheltersByCoordinates(lat, lon) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/shelters/nearest?lat=${lat}&lon=${lon}&k=5`);
        if (!response.ok) return null;
        const data = await response.json();
        return data.shelters || [];
    } catch (error) {
        return null;
    }
}


/* ═══════════════════════════════════════════════════════════════════
 * 지도 관련 함수 (2026-01-06: 카카오 지도로 전면 교체)
 * ═══════════════════════════════════════════════════════════════════ */

/**
 * 지도 초기화
 */
function initializeMap() {
    // 2026-01-06: Naver Maps -> Kakao Maps
    // if (typeof naver === 'undefined') {
    //     console.error('Naver Maps API가 로드되지 않았습니다.');
    //     return;
    // }
    if (typeof kakao === 'undefined') {
        console.error('Kakao Maps API가 로드되지 않았습니다.');
        return;
    }

    const mapContainer = document.getElementById('map');
    // const defaultCenter = new naver.maps.LatLng(37.5665, 126.9780);
    const defaultCenter = new kakao.maps.LatLng(37.5665, 126.9780);

    // map = new naver.maps.Map("map", {
    //     center: defaultCenter,
    //     zoom: 12,
    //     minZoom: 8,
    //     maxZoom: 18
    // });
    const mapOption = {
        center: defaultCenter,
        level: 5 // 카카오는 zoom 대신 level 사용 (숫자가 클수록 멀어짐)
    };

    map = new kakao.maps.Map(mapContainer, mapOption);

    // 파노라마 초기화
    try {
        // panorama = new naver.maps.Panorama("pano", {
        //     position: defaultCenter,
        //     pov: { pan: 0, tilt: 0, fov: 100 },
        //     visible: false
        // });
        const roadviewContainer = document.getElementById('pano');
        panorama = new kakao.maps.Roadview(roadviewContainer);
        console.log('로드뷰 초기화 완료');
    } catch (error) {
        console.warn('로드뷰 초기화 실패:', error);
    }

    // 지도 클릭 이벤트
    // naver.maps.Event.addListener(map, "click", function (e) {
    //     closeAllInfoWindows();

    //     if (panorama) {
    //         const clickedPos = e.coord;
    //         showPanorama();
    //         panorama.setPosition(clickedPos);
    //         panorama.setVisible(true);
    //         console.log('파노라마 위치 업데이트:', clickedPos.toString());
    //     }
    // });
    kakao.maps.event.addListener(map, "click", function (mouseEvent) {
        closeAllInfoWindows();

        if (panorama) {
            const clickedPos = mouseEvent.latLng;
            const roadviewClient = new kakao.maps.RoadviewClient();

            roadviewClient.getNearestPanoId(clickedPos, 50, function (panoId) {
                if (panoId) {
                    showPanorama();
                    panorama.setPanoId(panoId, clickedPos);
                    console.log('로드뷰 위치 업데이트:', clickedPos.toString());
                } else {
                    console.log('주변에 가용한 로드뷰가 없습니다.');
                    hidePanorama();
                }
            });
        }
    });

    // 현위치 자동 표시
    getCurrentPosition();
}

/**
 * 현재 위치 가져오기
 */
function getCurrentPosition() {
    if (!navigator.geolocation) {
        console.warn('브라우저에서 위치 정보를 지원하지 않습니다.');
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const userLat = position.coords.latitude;
            const userLon = position.coords.longitude;
            // const userPosition = new naver.maps.LatLng(userLat, userLon);
            const userPosition = new kakao.maps.LatLng(userLat, userLon);

            currentUserPosition = {
                lat: userLat,
                lon: userLon,
                position: userPosition
            };

            map.setCenter(userPosition);
            // map.setZoom(14);
            map.setLevel(4);

            createUserMarker(userPosition, userLat, userLon);
            console.log('현위치 표시 완료:', userLat, userLon);
        },
        (error) => {
            console.warn('현위치 가져오기 실패:', error.message);
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 300000
        }
    );
}

/**
 * 사용자 위치 마커 생성
 */
function createUserMarker(userPosition, userLat, userLon) {
    // 2026-01-06: Naver Maps -> Kakao Maps (CustomOverlay로 구현)
    // userMarker = new naver.maps.Marker({
    //     map: map,
    //     position: userPosition,
    //     icon: {
    //         content: `<div style="background:#4299E1;color:white;padding:6px 10px;border-radius:12px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3);">📍 현재 위치</div>`,
    //         anchor: new naver.maps.Point(50, 60)
    //     }
    // });
    if (userMarker) userMarker.setMap(null);

    const content = `
        <div style="background:#4299E1;color:white;padding:6px 10px;border-radius:12px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3); font-size:12px;">
            📍 현재 위치
        </div>`;

    userMarker = new kakao.maps.CustomOverlay({
        position: userPosition,
        content: content,
        yAnchor: 1.5
    });

    userMarker.setMap(map);

    // const userInfoWindow = new naver.maps.InfoWindow({
    //     content: `
    //         <div style="padding:15px;min-width:200px;">
    //             <div style="font-weight:bold;color:#1f2937;margin-bottom:8px;">📍 현재 위치</div>
    //             <div style="color:#6b7280;font-size:13px;">
    //                 위도: ${userLat.toFixed(6)}<br>
    //                 경도: ${userLon.toFixed(6)}
    //             </div>
    //         </div>
    //     `
    // });

    // naver.maps.Event.addListener(userMarker, "click", () => {
    //     closeAllInfoWindows();
    //     userInfoWindow.open(map, userMarker);
    //     infoWindows.push(userInfoWindow);

    //     if (panorama) {
    //         showPanorama();
    //         panorama.setPosition(userPosition);
    //         panorama.setVisible(true);
    //     }
    // });
}

/**
 * 지도를 현위치로 리셋
 */
function resetMapToCurrentLocation() {
    if (!map || !currentUserPosition) return;

    markers.forEach(marker => marker.setMap(null));
    markers = [];
    closeAllInfoWindows();

    map.setCenter(currentUserPosition.position);
    // map.setZoom(14);
    map.setLevel(4);

    if (!userMarker || !userMarker.getMap()) {
        createUserMarker(
            currentUserPosition.position,
            currentUserPosition.lat,
            currentUserPosition.lon
        );
    }

    console.log('지도를 현위치로 리셋:', currentUserPosition.lat, currentUserPosition.lon);
}

/**
 * 여러 대피소를 지도에 표시
 */
function showMapWithMultipleShelters(centerLat, centerLon, shelters, locationName) {
    // 2026-01-06: Naver Maps -> Kakao Maps
    // if (typeof naver === 'undefined') return;
    if (typeof kakao === 'undefined') return;

    // const center = new naver.maps.LatLng(centerLat, centerLon);
    const center = new kakao.maps.LatLng(centerLat, centerLon);

    // if (!map) {
    //     map = new naver.maps.Map("map", { center, zoom: 14 });
    //     naver.maps.Event.addListener(map, "click", closeAllInfoWindows);
    // } else {
    //     map.setCenter(center);
    //     map.setZoom(14);
    // }
    map.setCenter(center);
    map.setLevel(5);


    closeAllInfoWindows();
    // if (userMarker) userMarker.setMap(null); // 사용자 마커는 CustomOverlay이므로 null로 설정하지 않음
    markers.forEach(marker => marker.setMap(null));
    markers = [];

    // 검색 위치 마커 (기존 사용자 마커를 재활용하거나 새로 생성)
    // 2026-01-06: Naver Maps -> Kakao Maps (CustomOverlay로 구현)
    // userMarker = new naver.maps.Marker({
    //     map,
    //     position: center,
    //     icon: {
    //         content: `<div style="background:#4299E1;color:white;padding:6px 10px;border-radius:12px;font-weight:bold;">📍 ${locationName}</div>`,
    //         anchor: new naver.maps.Point(50, 60)
    //     }
    // });
    if (userMarker) userMarker.setMap(null); // 기존 사용자 마커 숨김
    const searchLocationContent = `
        <div style="background:#4299E1;color:white;padding:6px 10px;border-radius:12px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3); font-size:12px;">
            📍 ${locationName}
        </div>`;
    userMarker = new kakao.maps.CustomOverlay({
        position: center,
        content: searchLocationContent,
        yAnchor: 1.5
    });
    userMarker.setMap(map);


    // const bounds = new naver.maps.LatLngBounds(center, center);
    const bounds = new kakao.maps.LatLngBounds();
    bounds.extend(center);

    // 대피소 마커 생성
    shelters.forEach((shelter, index) => {
        // const position = safeLatLng(shelter.lat, shelter.lon);
        // if (!position) return;
        const position = new kakao.maps.LatLng(shelter.lat, shelter.lon);
        bounds.extend(position);

        // const marker = new naver.maps.Marker({
        //     map,
        //     position: position,
        //     icon: index === 0 ? {
        //         url: "https://maps.google.com/mapfiles/ms/icons/red-dot.png"
        //     } : undefined
        // });
        const marker = new kakao.maps.Marker({
            map: map,
            position: position
        });

        // const infoWindow = new naver.maps.InfoWindow({
        //     content: `
        //         <div style="padding:10px;">
        //             ${index === 0 ? "<b>🏆 가장 가까운 대피소</b><br>" : ""}
        //             <b>${shelter.name}</b><br>
        //             ${shelter.address}<br>
        //             거리: ${shelter.distance.toFixed(2)}km<br>
        //             수용인원: ${shelter.capacity.toLocaleString()}명
        //         </div>
        //     `
        // });
        const infoWindow = new kakao.maps.InfoWindow({
            content: `
                <div style="padding:10px; font-size:12px; width:200px;">
                    <b>${shelter.name}</b><br>
                    ${shelter.address.substring(0, 20)}...<br>
                    거리: ${shelter.distance.toFixed(2)}km
                </div>
            `,
            removable: true
        });

        // naver.maps.Event.addListener(marker, "click", () => {
        //     closeAllInfoWindows();
        //     infoWindow.open(map, marker);
        //     infoWindows.push(infoWindow);

        //     if (panorama) {
        //         showPanorama();
        //         panorama.setPosition(position);
        //         panorama.setVisible(true);
        //     }
        // });
        kakao.maps.event.addListener(marker, 'click', function () {
            closeAllInfoWindows();
            infoWindow.open(map, marker);
            infoWindows.push(infoWindow);

            if (panorama) {
                const roadviewClient = new kakao.maps.RoadviewClient();
                roadviewClient.getNearestPanoId(position, 50, function (panoId) {
                    if (panoId) {
                        showPanorama();
                        panorama.setPanoId(panoId, position);
                    }
                });
            }
        });

        markers.push(marker);
    });

    // map.fitBounds(bounds, { padding: 60 });
    map.setBounds(bounds);
}


/* ═══════════════════════════════════════════════════════════════════
 * 이벤트 핸들러
 * ═══════════════════════════════════════════════════════════════════ */

/**
 * GPS 현위치 검색
 */
function handleGeolocation() {
    addMessage("user", "📍 현위치로 대피소 검색");
    addMessage("bot", "GPS 위치를 가져오는 중입니다...");

    setControlsDisabled(true);

    if (!navigator.geolocation) {
        addMessage("bot", "❌ 브라우저에서 위치 정보가 지원되지 않습니다.");
        setControlsDisabled(false);
        return;
    }

    hidePanorama();
    navigator.geolocation.getCurrentPosition(
        onSuccessGeolocation,
        onErrorGeolocation
    );
}

/**
 * GPS 성공 콜백
 */
async function onSuccessGeolocation(position) {
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;

    addMessage("bot", `위치확인 완료! (lat ${lat.toFixed(4)}, lon ${lon.toFixed(4)})`);
    addMessage("bot", "🔍 주변 대피소 탐색 중...");

    const shelters = await searchSheltersByCoordinates(lat, lon);

    if (!shelters || shelters.length === 0) {
        addMessage("bot", "❌ 주변에 대피소가 없습니다.");
        setControlsDisabled(false);
        return;
    }

    shelters.forEach(shelter => {
        shelter.distance = haversine(lat, lon, shelter.lat, shelter.lon);
    });
    shelters.sort((a, b) => a.distance - b.distance);

    displayShelterResultsCurrent("현재 위치", [lat, lon], shelters);
}

/**
 * GPS 실패 콜백
 */
function onErrorGeolocation(error) {
    addMessage("bot", `❌ 위치정보 불러오기 실패 (코드 ${error.code})`);
    setControlsDisabled(false);
}

/**
 * 채팅 입력 처리
 */
async function handleChatInput() {
    const query = chatInput.value.trim();
    chatInput.value = "";
    if (!query) return;

    hidePanorama();
    addMessage("user", query);
    setControlsDisabled(true);

    if (query.includes("현위치") || query.includes("내 위치") || query.includes("현재 위치")) {
        handleGeolocation();
        return;
    }

    if (!API_AVAILABLE) {
        addMessage("bot", "❌ API 서버에 연결되지 않았습니다.");
        setControlsDisabled(false);
        return;
    }

    addMessage("bot", "🤖 입력 내용을 분석 중...");
    const result = await extractLocationWithLLM(query);

    console.log("result ---", result);

    if (!result || !result.success) {
        addMessage("bot", result?.message || "❌ 지명을 인식할 수 없습니다.");
        setControlsDisabled(false);
        return;
    }

    if (result.message) {
        console.log("result.message", result.message);
        addMessage("bot", result.message.replace(/\n/g, "<br>"));
    }

    if (result.shelters && result.shelters.length > 0 && result.coordinates) {
        displayShelterResults(result.location, result.coordinates, result.shelters);
    } else {
        resetMapToCurrentLocation();
    }

    setControlsDisabled(false);
}


/* ═══════════════════════════════════════════════════════════════════
 * 결과 표시 함수
 * ═══════════════════════════════════════════════════════════════════ */

/**
 * 현위치 기반 대피소 결과 표시
 */
/**
 * 인앱 길찾기 경로 그리기
 * [2026-01-06 추가] 외부 앱 연동 대신 현재 지도 위에 Polyline으로 대피소까지의 이동 경로를 시각화함
 */
async function drawRoute(originLat, originLon, destLat, destLon) {
    if (!API_AVAILABLE) {
        console.warn("API 서버에 연결되지 않아 경로를 가져올 수 없습니다.");
        return;
    }

    // 기존 경로 및 마커 제거
    if (currentPath) {
        currentPath.setMap(null);
    }
    routeMarkers.forEach(marker => marker.setMap(null));
    routeMarkers = [];

    // [2026-01-06 수정] 탭 초기화 (팝업 대신 탭 영역 사용)
    const navSummaryEl = document.getElementById('nav-summary');
    const navListEl = document.getElementById('nav-list');
    if (navSummaryEl) navSummaryEl.innerHTML = '<p class="text-gray-500 italic">경로 데이터를 불러오는 중...</p>';
    if (navListEl) navListEl.innerHTML = '<div class="text-center py-20"><p class="text-gray-400">잠시만 기다려 주세요...</p></div>';

    try {
        // 카카오 모빌리티 API는 lon,lat 순서를 사용함
        const origin = `${originLon},${originLat}`;
        const destination = `${destLon},${destLat}`;

        const response = await fetch(`${window.FASTAPI_URL}/api/directions?origin=${origin}&destination=${destination}`);
        const data = await response.json();

        if (!data.routes || data.routes.length === 0) {
            console.log("경로를 찾을 수 없습니다.");
            return;
        }

        const route = data.routes[0];
        const linePath = [];
        data.routes[0].sections.forEach(section => {
            section.roads.forEach(road => {
                const vertexes = road.vertexes;
                for (let i = 0; i < vertexes.length; i += 2) {
                    linePath.push(new kakao.maps.LatLng(vertexes[i + 1], vertexes[i]));
                }
            });
        });

        // 폴리라인 생성
        currentPath = new kakao.maps.Polyline({
            path: linePath,
            strokeWeight: 6,
            strokeColor: '#3B82F6', // Blue-500
            strokeOpacity: 0.8,
            strokeStyle: 'solid'
        });

        currentPath.setMap(map);

        // [2026-01-06 추가] 출발/도착 마커 표시
        const startMarker = new kakao.maps.CustomOverlay({
            position: linePath[0],
            content: '<div style="background:#10B981;color:white;padding:5px 12px;border-radius:15px;font-weight:bold;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,0.3); z-index:1001;">S</div>',
            yAnchor: 1.2,
            zIndex: 1001
        });
        const endMarker = new kakao.maps.CustomOverlay({
            position: linePath[linePath.length - 1],
            content: '<div style="background:#EF4444;color:white;padding:5px 12px;border-radius:15px;font-weight:bold;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,0.3); z-index:1001;">E</div>',
            yAnchor: 1.2,
            zIndex: 1001
        });

        startMarker.setMap(map);
        endMarker.setMap(map);
        routeMarkers.push(startMarker, endMarker);

        // [2026-01-06 수정] 슬라이딩 패널 업데이트
        if (navSummary && navList) {
            const summary = route.summary;
            const distanceKm = (summary.distance / 1000).toFixed(1);
            const durationMin = Math.ceil(summary.duration / 60);

            navSummary.innerHTML = `
                <div class="flex-1 border-r border-emerald-200">거리: <b class="text-emerald-700">${distanceKm}km</b></div>
                <div class="flex-1">소요시간: <b class="text-emerald-700">${durationMin}분</b></div>
            `;

            let listHtml = "";
            route.sections[0].guides.forEach((guide, index) => {
                if (guide.name || guide.guidance) {
                    listHtml += `
                        <div class="flex items-start gap-3 p-3 rounded-xl bg-gray-50 border border-gray-100 hover:border-emerald-200 transition-colors shadow-sm">
                            <span class="flex-shrink-0 w-6 h-6 bg-emerald-500 text-white rounded-full flex items-center justify-center font-bold text-xs mt-0.5 shadow-sm">${index + 1}</span>
                            <div class="flex-1">
                                <div class="text-gray-800 font-bold leading-tight mb-1 text-[13px]">${guide.name || guide.guidance}</div>
                                ${guide.distance > 0 ? `<div class="text-blue-500 font-semibold text-[10px]">${guide.distance}m 이동</div>` : ''}
                            </div>
                        </div>
                    `;
                }
            });
            navList.innerHTML = listHtml;

            // 토글 버튼 표시 및 서랍 열기
            if (navToggleBtn) navToggleBtn.classList.remove('hidden');
            openNavDrawer();
        }

        // 경로가 모두 보이도록 지도 범위 조정
        const bounds = new kakao.maps.LatLngBounds();
        linePath.forEach(point => bounds.extend(point));
        map.setBounds(bounds);

        console.log("🛣️ 경로 및 내비 상세 안내 완료 (2026-01-06)");

    } catch (error) {
        console.error("경로 안내 자동 실행 오류:", error);
    }
}

function displayShelterResultsCurrent(locationName, coords, shelters) {
    const nearest = shelters[0];
    const userLat = coords[0];
    const userLon = coords[1];

    let shelterList = "";
    shelters.forEach((shelter, index) => {
        shelterList += `
            <div class="mt-1 text-sm ${index === 0 ? 'font-bold text-emerald-100' : 'opacity-80'}">
                ${index === 0 ? '🏆 ' : `${index + 1}. `}${shelter.name} (${shelter.distance.toFixed(2)}km)
            </div>
        `;
    });

    addMessage("bot",
        `
        <div class="mb-2">
            <p class="text-xl font-bold text-emerald-600">${nearest.name}</p>
            <p class="text-sm text-gray-600">${nearest.address}</p>
        </div>
        <div class="space-y-1 mb-3">
            <p>📍 거리: <b>${nearest.distance.toFixed(2)}km</b></p>
            <p>👥 수용인원: <b>${nearest.capacity.toLocaleString()}명</b></p>
        </div>
        
        <button onclick="drawRoute(${userLat}, ${userLon}, ${nearest.lat}, ${nearest.lon})" 
           class="w-full text-center bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-lg transition-colors mb-3 shadow-md focus:outline-none focus:ring-2 focus:ring-blue-300">
           🏃 지도에서 길찾기 (경로 표시)
        </button>

        <details class="mt-3">
            <summary class="cursor-pointer font-semibold text-blue-600">📋 전체 대피소 목록 보기</summary>
            <div class="mt-2 ml-2 max-h-40 overflow-y-auto border-t pt-2">${shelterList}</div>
        </details>
        `,
        true
    );

    showMapWithMultipleShelters(userLat, userLon, shelters, locationName);

    // [2026-01-06 추가] 조회 결과에 따라 최단 거리 대피소 경로 자동 안내
    console.log("🏃 최단 거리 대피소로 자동 경로 탐색 시작 (2026-01-06)");
    drawRoute(userLat, userLon, nearest.lat, nearest.lon);

    setControlsDisabled(false);
}

function displayShelterResults(locationName, coords, shelters) {
    const nearest = shelters[0];
    const userLat = coords[0];
    const userLon = coords[1];

    // 2026-01-06: 장소명 검색 시에도 최단 거리 대피소 정보와 길찾기 기능 제공
    addMessage("bot",
        `
        <div class="mb-2">
            <p class="text-lg font-bold text-emerald-600">📍 ${locationName} 근처 대피소</p>
            <p class="text-sm">가장 가까운 곳: <b>${nearest.name}</b></p>
        </div>
        <div class="mb-3 text-sm">
            가까운 대피소 <b>${shelters.length}곳</b>을 찾았습니다. 지도를 확인해 주세요.
        </div>
        <button onclick="drawRoute(${userLat}, ${userLon}, ${nearest.lat}, ${nearest.lon})" 
           class="w-full text-center bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-lg transition-colors shadow-md focus:outline-none focus:ring-2 focus:ring-blue-300">
           🏃 지도에서 길찾기 (경로 표시)
        </button>
        `,
        true
    );

    showMapWithMultipleShelters(userLat, userLon, shelters, locationName);

    // [2026-01-06 추가] 조회 결과에 따라 가장 가까운 대피소까지 경로를 자동으로 그려줌
    console.log("🏃 최단 거리 대피소로 자동 보행 경로 안내 시작 (2026-01-06)");
    drawRoute(userLat, userLon, nearest.lat, nearest.lon);

    setControlsDisabled(false);
}


/* ═══════════════════════════════════════════════════════════════════
 * 초기화
 * ═══════════════════════════════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", async () => {
    await checkApiStatus();
    initializeMap();

    if (API_AVAILABLE) {
        initialMessageEl.innerHTML = `
            <span class="text-black-600 font-normal">저는 </span>
            <span class="text-red-600 font-bold text-lg">재난안전 챗봇</span>
            <span class="text-black-600 font-normal">입니다 🤖</span><br>
            <span class="text-blue-700 font-bold">주소 / 장소명</span>
            <span class="text-black-700 font-normal">을 입력하거나</span>
            <span class="text-blue-700 font-bold">"현위치"</span>
            <span class="text-black-700 font-normal">로 검색해 보세요.</span>
        `;
        setControlsDisabled(false);
    } else {
        initialMessageEl.innerHTML = `
            <span class="text-red-600 font-bold">⚠️ 서버 연결 실패. FastAPI 서버를 실행해주세요.</span>
        `;
    }
});