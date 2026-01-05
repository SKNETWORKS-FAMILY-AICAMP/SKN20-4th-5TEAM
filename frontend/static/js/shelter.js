/* ═══════════════════════════════════════════════════════════════════
 * 전역 변수 및 상수
 * ═══════════════════════════════════════════════════════════════════ */

// API 주소 (Django에서 주입)
const API_BASE_URL = window.FASTAPI_URL || 'http://127.0.0.1:8443';

let USE_LLM = false;
let API_AVAILABLE = false;

// 지도 관련 변수
let map = null;
let userMarker = null;
let shelterMarkers = [];
let openInfoWindows = [];
let currentUserPosition = null;
let panorama = null;

// DOM 요소
const chatWindow = document.getElementById('chat-window');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const geoBtn = document.getElementById('geo-btn');
const initialMessageEl = document.getElementById('initial-message');

// 상수
const EARTH_RADIUS = 6371;


/* ═══════════════════════════════════════════════════════════════════
 * 유틸리티 함수
 * ═══════════════════════════════════════════════════════════════════ */

function safeLatLng(lat, lon) {
    const a = Number(lat);
    const b = Number(lon);
    if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
    return new naver.maps.LatLng(a, b);
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
    const panoDiv = document.getElementById('pano');
    const placeholder = document.getElementById('pano-placeholder');
    const closeBtn = document.getElementById('pano-close-btn');
    
    if (mapDiv && panoDiv) {
        mapDiv.style.height = '50%';
        panoDiv.style.height = '50%';
        if (placeholder) placeholder.style.display = 'none';
        if (closeBtn) closeBtn.classList.remove('hidden');
        console.log('📷 파노라마 표시');
    }
}

/**
 * 파노라마 숨김 (지도 100%로 복귀)
 */
function hidePanorama() {
    const mapDiv = document.getElementById('map');
    const panoDiv = document.getElementById('pano');
    const placeholder = document.getElementById('pano-placeholder');
    const closeBtn = document.getElementById('pano-close-btn');
    
    if (mapDiv && panoDiv) {
        mapDiv.style.height = '100%';
        panoDiv.style.height = '0%';
        if (panorama) panorama.setVisible(false);
        if (placeholder) placeholder.style.display = 'flex';
        if (closeBtn) closeBtn.classList.add('hidden');
        console.log('🗺️ 파노라마 숨김');
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
    openInfoWindows.forEach(window => window.close());
    openInfoWindows = [];
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
 * 지도 관련 함수
 * ═══════════════════════════════════════════════════════════════════ */

/**
 * 지도 초기화
 */
function initializeMap() {
    if (typeof naver === 'undefined') {
        console.error('Naver Maps API가 로드되지 않았습니다.');
        return;
    }

    const defaultCenter = new naver.maps.LatLng(37.5665, 126.9780);
    
    map = new naver.maps.Map("map", {
        center: defaultCenter,
        zoom: 12,
        minZoom: 8,
        maxZoom: 18
    });

    // 파노라마 초기화
    try {
        panorama = new naver.maps.Panorama("pano", {
            position: defaultCenter,
            pov: { pan: 0, tilt: 0, fov: 100 },
            visible: false
        });
        console.log('파노라마 초기화 완료');
    } catch (error) {
        console.warn('파노라마 초기화 실패:', error);
    }

    // 지도 클릭 이벤트
    naver.maps.Event.addListener(map, "click", function(e) {
        closeAllInfoWindows();
        
        if (panorama) {
            const clickedPos = e.coord;
            showPanorama();
            panorama.setPosition(clickedPos);
            panorama.setVisible(true);
            console.log('파노라마 위치 업데이트:', clickedPos.toString());
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
            const userPosition = new naver.maps.LatLng(userLat, userLon);

            currentUserPosition = { 
                lat: userLat, 
                lon: userLon, 
                position: userPosition 
            };

            map.setCenter(userPosition);
            map.setZoom(14);

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
    userMarker = new naver.maps.Marker({
        map: map,
        position: userPosition,
        icon: {
            content: `<div style="background:#4299E1;color:white;padding:6px 10px;border-radius:12px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3);">📍 현재 위치</div>`,
            anchor: new naver.maps.Point(50, 60)
        }
    });

    const userInfoWindow = new naver.maps.InfoWindow({
        content: `
            <div style="padding:15px;min-width:200px;">
                <div style="font-weight:bold;color:#1f2937;margin-bottom:8px;">📍 현재 위치</div>
                <div style="color:#6b7280;font-size:13px;">
                    위도: ${userLat.toFixed(6)}<br>
                    경도: ${userLon.toFixed(6)}
                </div>
            </div>
        `
    });

    naver.maps.Event.addListener(userMarker, "click", () => {
        closeAllInfoWindows();
        userInfoWindow.open(map, userMarker);
        openInfoWindows.push(userInfoWindow);
        
        if (panorama) {
            showPanorama();
            panorama.setPosition(userPosition);
            panorama.setVisible(true);
        }
    });
}

/**
 * 지도를 현위치로 리셋
 */
function resetMapToCurrentLocation() {
    if (!map || !currentUserPosition) return;
    
    shelterMarkers.forEach(marker => marker.setMap(null));
    shelterMarkers = [];
    closeAllInfoWindows();
    
    map.setCenter(currentUserPosition.position);
    map.setZoom(14);
    
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
    if (typeof naver === 'undefined') return;

    const center = new naver.maps.LatLng(centerLat, centerLon);

    if (!map) {
        map = new naver.maps.Map("map", { center, zoom: 14 });
        naver.maps.Event.addListener(map, "click", closeAllInfoWindows);
    } else {
        map.setCenter(center);
        map.setZoom(14);
    }

    closeAllInfoWindows();
    if (userMarker) userMarker.setMap(null);
    shelterMarkers.forEach(marker => marker.setMap(null));
    shelterMarkers = [];

    // 검색 위치 마커
    userMarker = new naver.maps.Marker({
        map,
        position: center,
        icon: {
            content: `<div style="background:#4299E1;color:white;padding:6px 10px;border-radius:12px;font-weight:bold;">📍 ${locationName}</div>`,
            anchor: new naver.maps.Point(50, 60)
        }
    });

    const bounds = new naver.maps.LatLngBounds(center, center);

    // 대피소 마커 생성
    shelters.forEach((shelter, index) => {
        const position = safeLatLng(shelter.lat, shelter.lon);
        if (!position) return;
        bounds.extend(position);

        const marker = new naver.maps.Marker({
            map,
            position: position,
            icon: index === 0 ? {
                url: "https://maps.google.com/mapfiles/ms/icons/red-dot.png"
            } : undefined
        });

        const infoWindow = new naver.maps.InfoWindow({
            content: `
                <div style="padding:10px;">
                    ${index === 0 ? "<b>🏆 가장 가까운 대피소</b><br>" : ""}
                    <b>${shelter.name}</b><br>
                    ${shelter.address}<br>
                    거리: ${shelter.distance.toFixed(2)}km<br>
                    수용인원: ${shelter.capacity.toLocaleString()}명
                </div>
            `
        });

        naver.maps.Event.addListener(marker, "click", () => {
            closeAllInfoWindows();
            infoWindow.open(map, marker);
            openInfoWindows.push(infoWindow);
            
            if (panorama) {
                showPanorama();
                panorama.setPosition(position);
                panorama.setVisible(true);
            }
        });

        shelterMarkers.push(marker);
    });

    map.fitBounds(bounds, { padding: 60 });
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
function displayShelterResultsCurrent(locationName, coords, shelters) {
    const nearest = shelters[0];

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
        <p class="text-xl font-bold">${nearest.name}</p>
        <p>${nearest.address}</p>
        <p class="mt-2">📍 거리: <b>${nearest.distance.toFixed(2)}km</b></p>
        <p class="mt-2">수용인원: <b>${nearest.capacity.toLocaleString()}명</b></p>
        <details class="mt-3">
            <summary>📋 전체 대피소 목록 보기</summary>
            <div class="mt-2 ml-2 max-h-40 overflow-y-auto">${shelterList}</div>
        </details>
        `,
        true
    );

    showMapWithMultipleShelters(coords[0], coords[1], shelters, locationName);
    setControlsDisabled(false);
}

/**
 * 장소명 기반 대피소 결과 표시
 */
function displayShelterResults(locationName, coords, shelters) {
    showMapWithMultipleShelters(coords[0], coords[1], shelters, locationName);
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