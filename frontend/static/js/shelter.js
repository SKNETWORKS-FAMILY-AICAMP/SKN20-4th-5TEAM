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
let currentPathBg = null; // 2026-01-08: 경로 외곽선(그림자) 효과
let routeMarkers = [];  // 2026-01-06: 길찾기 출발/도착 지점 마커 관리
let routeArrows = [];   // 2026-01-08: 경로 위 정적 화살표
let movingArrow = null; // 2026-01-08: 이동 애니메이션 화살표
let arrowAnimId = null; // 2026-01-08: 애니메이션 타이머/ID
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
    if (toggleBtn) toggleBtn.classList.add('hidden'); // 패널이 열리면 버튼 숨김
}

function closeNavDrawer() {
    const drawer = document.getElementById('nav-drawer');
    const toggleBtn = document.getElementById('nav-toggle-btn');
    if (drawer) drawer.classList.add('-translate-x-full');

    // 경로 데이터가 있는 경우에만 버튼을 다시 보여줌
    if (toggleBtn && navSummary && navSummary.innerHTML.includes('km')) {
        toggleBtn.classList.remove('hidden');
    }
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
        // [2026-01-07 최종수정] 지도의 height를 직접 건드리지 않고, 하단 컨테이너 크기만 조절합니다.
        // mapDiv.style.height = '50%'; (삭제)
        panoContainer.style.height = '50%';

        if (placeholder) placeholder.style.display = 'none';
        if (closeBtn) closeBtn.classList.remove('hidden');

        // [2026-01-07 수정] 애니메이션(0.3s)이 완료된 후 레이아웃 재계산
        setTimeout(() => {
            if (map) map.relayout();
            if (panorama) panorama.relayout();
            console.log('📷 로드뷰 표시 (relayout 완료)');
        }, 350);
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
        // [2026-01-07 최종수정] 지도의 height를 100%로 다시 돌릴 필요 없이 컨테이너만 0으로 만듭니다.
        // mapDiv.style.height = '100%'; (삭제)
        panoContainer.style.height = '0%';

        // 2026-01-06: 카카오 로드뷰는 setVisible을 지원하지 않으므로 주석 처리
        // if (panorama) panorama.setVisible(false); 

        if (placeholder) placeholder.style.display = 'flex';
        if (closeBtn) closeBtn.classList.add('hidden');

        // [2026-01-07 수정] 애니메이션 완료 후 지도 레이아웃 재계산
        setTimeout(() => {
            if (map) map.relayout();
            console.log('🗺️ 로드뷰 숨김 (relayout 완료)');
        }, 350);
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
        badge.className = "px-6 py-2 rounded-full text-xl font-black shadow-lg bg-emerald-500 text-white animate-pulse";
        badge.textContent = "🤖 LLM ON";
    } else if (API_AVAILABLE) {
        badge.className = "px-6 py-2 rounded-full text-xl font-black shadow-lg bg-orange-500 text-white";
        badge.textContent = "📍 규칙 기반";
    } else {
        badge.className = "px-6 py-2 rounded-full text-xl font-black shadow-lg bg-gray-500 text-white";
        badge.textContent = "📂 로컬 모드";
    }
}

/**
 * 채팅 메시지 추가
 */
function addMessage(sender, text, isResult = false) {
    const chatWindow = document.getElementById('chat-window');
    const wrap = document.createElement('div');
    const avatar = document.createElement('div');
    const box = document.createElement('div');

    // [2026-01-08 추가] 이전의 모든 봇 아바타를 정지 이미지로 변경
    if (sender !== "user") {
        const allBotImages = chatWindow.querySelectorAll('img[alt="Bot Avatar"]');
        allBotImages.forEach(img => {
            img.src = "/static/images/bot2.png";
        });
    }

    if (sender === "user") {
        wrap.className = "flex justify-end mb-4 px-2 hover:opacity-95 transition-all";
        box.className = "bg-red-50 text-gray-900 p-4 rounded-3xl rounded-tr-none max-w-[85%] shadow-md border border-red-100";
        box.innerHTML = text;
        wrap.appendChild(box);
    } else {
        wrap.className = "flex justify-start mb-6 px-2 hover:opacity-95 transition-all group items-start gap-3";

        // 캐릭터 아바타 추가
        avatar.className = "flex-shrink-0 w-12 h-12 rounded-2xl overflow-hidden shadow-lg bg-white transform group-hover:scale-105 transition-transform duration-300";
        // 최신 메시지는 GIF 사용
        avatar.innerHTML = `<img src="/static/images/bot2_talking_v2.gif" class="w-full h-full object-cover" alt="Bot Avatar">`;

        if (isResult) {
            box.style.background = "#FFFFFF";
            box.style.color = "#111827"; // gray-900
            box.className = "p-6 rounded-3xl rounded-tl-none max-w-[85%] shadow-xl border-l-[6px] border-emerald-500 border-t border-r border-b border-gray-100 transition-all";
            box.innerHTML = `<p class="font-black text-2xl mb-3 text-emerald-700 flex items-center gap-2 border-b border-emerald-50 pb-2">📍 대피소 검색 결과 <span class="animate-bounce">✨</span></p><div class="leading-relaxed">${text}</div>`;
        } else {
            box.className = "bg-white text-gray-800 p-4 rounded-3xl rounded-tl-none max-w-[80%] shadow-lg border border-gray-100";
            box.innerHTML = `<p class="font-bold text-emerald-600 mb-1 flex items-center gap-2">🛡️ 대피소 도우미</p><div>${text}</div>`;
        }

        wrap.appendChild(avatar);
        wrap.appendChild(box);
    }

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
        <div style="background:#3182CE;color:white;padding:10px 18px;border-radius:20px;font-weight:bold;box-shadow:0 4px 10px rgba(0,0,0,0.4); font-size:18px; border: 2px solid white;">
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
        <div style="background:#3182CE;color:white;padding:10px 18px;border-radius:20px;font-weight:bold;box-shadow:0 4px 10px rgba(0,0,0,0.4); font-size:18px; border: 2px solid white;">
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
    closeNavDrawer(); // 새 검색 시작 시 패널 닫기 (버튼 표시 여부는 로직에 따름)
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
        displayShelterResults(result.location, result.coordinates, result.shelters, result.intent); // intent 추가 전달
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
    if (currentPath) currentPath.setMap(null);
    if (currentPathBg) currentPathBg.setMap(null);
    if (movingArrow) movingArrow.setMap(null);
    if (arrowAnimId) {
        clearInterval(arrowAnimId);
        arrowAnimId = null;
    }

    routeMarkers.forEach(marker => marker.setMap(null));
    routeMarkers = [];
    routeArrows.forEach(arrow => arrow.setMap(null));
    routeArrows = [];

    // [2026-01-06 수정] 탭 초기화 (팝업 대신 탭 영역 사용)
    const navSummaryEl = document.getElementById('nav-summary');
    const navListEl = document.getElementById('nav-list');
    if (navSummaryEl) navSummaryEl.innerHTML = '<p class="text-gray-500 italic">경로 데이터를 불러오는 중...</p>';
    if (navListEl) navListEl.innerHTML = '<div class="text-center py-20"><p class="text-gray-400">잠시만 기다려 주세요...</p></div>';

    try {
        const origin = `${originLon},${originLat}`;
        const destination = `${destLon},${destLat}`;

        // [2026-01-07 수정] T Map API 프록시 호출
        const response = await fetch(`${window.FASTAPI_URL}/api/directions?origin=${origin}&destination=${destination}`);
        const data = await response.json();

        // [2026-01-07 수정] T Map (GeoJSON) 데이터 처리
        if (!data.features || data.features.length === 0) {
            console.log("경로를 찾을 수 없습니다.");
            if (navSummaryEl) navSummaryEl.innerHTML = '<p class="text-red-500">경로를 찾을 수 없습니다.</p>';
            return;
        }

        const linePath = [];
        let listHtml = "";
        let totalDistance = 0;
        let totalTime = 0;
        let guideIndex = 1;

        // T Map GeoJSON 파싱
        data.features.forEach((feature) => {
            const geometry = feature.geometry;
            const properties = feature.properties;

            if (geometry.type === "LineString") {
                // 경로 좌표 모으기
                geometry.coordinates.forEach(coord => {
                    linePath.push(new kakao.maps.LatLng(coord[1], coord[0]));
                });
            } else if (geometry.type === "Point") {
                // 안내 지점 처리
                if (properties.description) {
                    const segmentDist = properties.distance ? `<div class="text-blue-600 font-bold text-lg mt-2">${properties.distance}m 이동</div>` : "";
                    listHtml += `
                        <div class="flex items-start gap-4 p-5 rounded-2xl bg-gray-50 border border-gray-200 hover:border-emerald-300 transition-all shadow-sm">
                            <span class="flex-shrink-0 w-10 h-10 bg-emerald-500 text-white rounded-full flex items-center justify-center font-bold text-lg shadow-md">${guideIndex++}</span>
                            <div class="flex-1 pt-1">
                                <div class="text-gray-800 font-bold leading-relaxed text-xl">${properties.description}</div>
                                ${segmentDist}
                            </div>
                        </div>
                    `;
                }
            }

            // 첫 번째 feature(일반적으로 전체 요약 정보 포함)에서 메타데이터 추출
            if (properties.totalDistance && totalDistance === 0) {
                totalDistance = properties.totalDistance;
                totalTime = properties.totalTime;
            }
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


        // 출발/도착 마커 표시 - [2026-01-07 크기 대폭 확대]
        const startMarker = new kakao.maps.CustomOverlay({
            position: linePath[0],
            content: '<div style="background:#10B981;color:white;padding:8px 11px;border-radius:25px;font-weight:900;font-size:28px;box-shadow:0 4px 12px rgba(0,0,0,0.4); z-index:1001; border:3px solid white; opacity: 0.45;">S</div>',
            yAnchor: 1.2,
            zIndex: 1001
        });
        const endMarker = new kakao.maps.CustomOverlay({
            position: linePath[linePath.length - 1],
            content: '<div style="background:#EF4444;color:white;padding:8px 11px;border-radius:25px;font-weight:900;font-size:28px;box-shadow:0 4px 12px rgba(0,0,0,0.4); z-index:1001; border:3px solid white; opacity: 0.45;">E</div>',
            yAnchor: 1.2,
            zIndex: 1001
        });

        startMarker.setMap(map);
        endMarker.setMap(map);
        routeMarkers.push(startMarker, endMarker);

        // 슬라이딩 패널 업데이트
        if (navSummary && navList) {
            const distanceKm = (totalDistance / 1000).toFixed(1);
            const durationMin = Math.ceil(totalTime / 60);

            navSummary.innerHTML = `
                <div class="flex-1 border-r border-emerald-100 py-0.5 text-center">
                    <span class="text-sm text-emerald-600 font-medium block">총 거리</span>
                    <b class="text-2xl text-emerald-800">${distanceKm}km</b>
                </div>
                <div class="flex-1 py-0.5 text-center">
                    <span class="text-sm text-emerald-600 font-medium block">소요 시간</span>
                    <b class="text-2xl text-emerald-800">${durationMin}분</b>
                </div>
            `;
            navList.innerHTML = listHtml;

            // 토글 버튼 표시 및 서랍 열기
            if (navToggleBtn) navToggleBtn.classList.remove('hidden');
            openNavDrawer();
        }

        // 경로가 모두 보이도록 지도 범위 조정
        const bounds = new kakao.maps.LatLngBounds();
        linePath.forEach(point => bounds.extend(point));
        map.setBounds(bounds);

        // [2026-01-08 추가] 이동하는 화살표 애니메이션 시작
        animateMovingArrow(linePath);

        console.log("🛣️ T Map 기반 경로 안내 완료 (2026-01-07)");

    } catch (error) {
        console.error("경로 안내 자동 실행 오류:", error);
    }
}

/* [2026-01-07 주석 처리] 기존 카카오 기반 drawRoute 로직
async function drawRoute(originLat, originLon, destLat, destLon) {
    if (!API_AVAILABLE) {
        console.warn("API 서버에 연결되지 않아 경로를 가져올 수 없습니다.");
        return;
    }

    if (currentPath) {
        currentPath.setMap(null);
    }
    routeMarkers.forEach(marker => marker.setMap(null));
    routeMarkers = [];

    const navSummaryEl = document.getElementById('nav-summary');
    const navListEl = document.getElementById('nav-list');
    if (navSummaryEl) navSummaryEl.innerHTML = '<p class="text-gray-500 italic">경로 데이터를 불러오는 중...</p>';
    if (navListEl) navListEl.innerHTML = '<div class="text-center py-20"><p class="text-gray-400">잠시만 기다려 주세요...</p></div>';

    try {
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

        currentPath = new kakao.maps.Polyline({
            path: linePath,
            strokeWeight: 6,
            strokeColor: '#3B82F6', 
            strokeOpacity: 0.8,
            strokeStyle: 'solid'
        });

        currentPath.setMap(map);

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
                                ${guide.distance > 0 ? \`<div class="text-blue-500 font-semibold text-[10px]">\${guide.distance}m 이동</div>\` : ''}
                            </div>
                        </div>
                    `;
                }
            });
            navList.innerHTML = listHtml;

            if (navToggleBtn) navToggleBtn.classList.remove('hidden');
            openNavDrawer();
        }

        const bounds = new kakao.maps.LatLngBounds();
        linePath.forEach(point => bounds.extend(point));
        map.setBounds(bounds);
    } catch (error) {
        console.error("경로 안내 자동 실행 오류:", error);
    }
}
*/

function displayShelterResultsCurrent(locationName, coords, shelters, intent = null) {
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

    // [2026-01-07 수정] 길찾기가 불필요한 의도 목록 확장
    const NO_DIRECTIONS_INTENTS = ['shelter_info', 'shelter_count', 'shelter_capacity', 'disaster_guideline', 'general_knowledge', 'general_chat'];
    const hideDirections = NO_DIRECTIONS_INTENTS.includes(intent);

    const directionsBtn = hideDirections ? '' : `
        <button onclick="drawRoute(${userLat}, ${userLon}, ${nearest.lat}, ${nearest.lon})" 
           class="w-full text-center bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-lg transition-colors mb-3 shadow-md focus:outline-none focus:ring-2 focus:ring-blue-300">
           🏃 지도에서 길찾기 (경로 표시)
        </button>
    `;

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
        
        ${directionsBtn}

        <details class="mt-3">
            <summary class="cursor-pointer font-semibold text-blue-600">📋 전체 대피소 목록 보기</summary>
            <div class="mt-2 ml-2 max-h-40 overflow-y-auto border-t pt-2">${shelterList}</div>
        </details>
        `,
        true
    );

    showMapWithMultipleShelters(userLat, userLon, shelters, locationName);

    // [2026-01-07 수정] shelter_info가 아닐 때만 자동 경로 안내
    if (!hideDirections) {
        console.log("🏃 최단 거리 대피소로 자동 경로 탐색 시작 (2026-01-07)");
        drawRoute(userLat, userLon, nearest.lat, nearest.lon);
    } else {
        console.log("ℹ️ 시설 정보 조회 의도이므로 길찾기를 건너뜁니다.");
        if (typeof closeNavDrawer === 'function') closeNavDrawer(); // 내비 드로워 닫기
    }

    setControlsDisabled(false);
}

function displayShelterResults(locationName, coords, shelters, intent = null) {
    const nearest = shelters[0];
    const userLat = coords[0];
    const userLon = coords[1];

    // [2026-01-07 수정] 길찾기가 불필요한 의도 목록 확장
    const NO_DIRECTIONS_INTENTS = ['shelter_info', 'shelter_count', 'shelter_capacity', 'disaster_guideline', 'general_knowledge', 'general_chat'];
    const hideDirections = NO_DIRECTIONS_INTENTS.includes(intent);

    const directionsBtn = hideDirections ? '' : `
        <button onclick="drawRoute(${userLat}, ${userLon}, ${nearest.lat}, ${nearest.lon})" 
           class="w-full text-center bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-lg transition-colors shadow-md focus:outline-none focus:ring-2 focus:ring-blue-300">
           🏃 지도에서 길찾기 (경로 표시)
        </button>
    `;

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
        ${directionsBtn}
        `,
        true
    );

    showMapWithMultipleShelters(userLat, userLon, shelters, locationName);

    // [2026-01-07 수정] shelter_info가 아닐 때만 자동 경로 안내
    if (!hideDirections) {
        console.log("🏃 최단 거리 대피소로 자동 보행 경로 안내 시작 (2026-01-07)");
        drawRoute(userLat, userLon, nearest.lat, nearest.lon);
    } else {
        console.log("ℹ️ 시설 정보 조회 의도이므로 길찾기를 건너뜁니다.");
        if (typeof closeNavDrawer === 'function') closeNavDrawer(); // 내비 드로워 닫기
    }

    setControlsDisabled(false);
}


/**
 * 경로를 따라 이동하는 화살표 애니메이션 (2026-01-08 추가)
 */
function animateMovingArrow(path) {
    if (!path || path.length < 2) return;

    let step = 0;
    const totalSteps = path.length;

    // 만약 이미 있다면 제거
    if (movingArrow) movingArrow.setMap(null);

    // 움직이는 화살표 생성 (커스텀 오버레이)
    movingArrow = new kakao.maps.CustomOverlay({
        position: path[0],
        content: `<div style="color: #FFD700; font-size: 28px; text-shadow: 0 0 8px rgba(0,0,0,0.6); font-weight: 900; filter: drop-shadow(0 0 4px red); pointer-events: none;">➤</div>`,
        zIndex: 1005
    });
    movingArrow.setMap(map);

    // 일정 시간마다 화살표 위치 업데이트
    arrowAnimId = setInterval(() => {
        if (step >= totalSteps - 1) {
            step = 0; // 도착하면 다시 출발지로 (무한 반복)
        }

        const start = path[step];
        const end = path[step + 1];

        // 각도 계산 및 회전 적용
        const angle = Math.atan2(end.getLat() - start.getLat(), end.getLng() - start.getLng()) * 180 / Math.PI;
        const rotation = -angle;

        movingArrow.setPosition(start);
        movingArrow.setContent(`<div style="transform: rotate(${rotation}deg); color: #FFD700; font-size: 28px; text-shadow: 0 0 8px rgba(0,0,0,0.6); font-weight: 900; filter: drop-shadow(0 0 4px red); pointer-events: none;">➤</div>`);

        step++;
    }, 150); // 0.15초 간격으로 이동
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