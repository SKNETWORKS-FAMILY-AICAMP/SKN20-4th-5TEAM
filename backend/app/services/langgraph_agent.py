# -*- coding: utf-8 -*-
"""
LangGraph Agent 및 Tools 정의
대피소 검색, 재난 행동요령, 통계 기능을 담당하는 AI Agent
"""

import os
import requests
import json
import re
from math import radians, sin, cos, sqrt, atan2
from typing import TypedDict, Annotated, Optional
import time

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트 기준)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

class EnsembleRetriever:
    """간단한 앙상블 리트리버 구현"""

    def __init__(self, retrievers, weights=None):
        self.retrievers = retrievers
        self.weights = weights or [1.0 / len(retrievers)] * len(retrievers)

    def invoke(self, query):
        all_docs = []
        for retriever, weight in zip(self.retrievers, self.weights):
            try:
                docs = retriever.invoke(query)
                for doc in docs:
                    doc.metadata["retriever_weight"] = weight
                    all_docs.append(doc)
            except:
                continue
        # 중복 제거 및 가중치 기반 정렬
        seen = set()
        unique_docs = []
        for doc in all_docs:
            doc_id = doc.page_content[:100]
            if doc_id not in seen:
                seen.add(doc_id)
                unique_docs.append(doc)
        return unique_docs[:10]


def create_hybrid_retrievers(vectorstore):
    """하이브리드 리트리버 생성 (Vector + BM25)"""
    if vectorstore is None:
        return None, None

    try:
        # 1. Vector Retriever
        shelter_vector_retriever = vectorstore.as_retriever(
            search_kwargs={"k": 5, "filter": {"type": "shelter"}}
        )
        guideline_vector_retriever = vectorstore.as_retriever(
            search_kwargs={"k": 3, "filter": {"type": "disaster_guideline"}}
        )

        # 2. BM25 Retriever 생성
        def create_bm25_retriever(doc_type: str):
            try:
                all_docs = vectorstore.get(where={"type": doc_type})
                if not all_docs or "documents" not in all_docs:
                    return None

                documents = []
                for i, text in enumerate(all_docs["documents"]):
                    metadata = (
                        all_docs["metadatas"][i] if "metadatas" in all_docs else {}
                    )
                    documents.append(Document(page_content=text, metadata=metadata))

                bm25_retriever = BM25Retriever.from_documents(documents)
                bm25_retriever.k = 5
                return bm25_retriever
            except Exception as e:
                print(f"⚠️ BM25 Retriever 생성 실패 ({doc_type}): {e}")
                return None

        shelter_bm25 = create_bm25_retriever("shelter")
        guideline_bm25 = create_bm25_retriever("disaster_guideline")

        # 3. Ensemble (Hybrid) Retriever
        shelter_hybrid = EnsembleRetriever(
            retrievers=(
                [shelter_vector_retriever, shelter_bm25]
                if shelter_bm25
                else [shelter_vector_retriever]
            ),
            weights=[0.6, 0.4] if shelter_bm25 else [1.0],
        )

        guideline_hybrid = EnsembleRetriever(
            retrievers=(
                [guideline_vector_retriever, guideline_bm25]
                if guideline_bm25
                else [guideline_vector_retriever]
            ),
            weights=[0.7, 0.3] if guideline_bm25 else [1.0],
        )

        return shelter_hybrid, guideline_hybrid

    except Exception as e:
        print(f"⚠️ 하이브리드 리트리버 생성 실패: {e}")
        return None, None


def create_langgraph_app(vectorstore):
    """LangGraph Agent 생성"""

    # 1. LLM 초기화
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_creative = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)  # 일반 지식용

    # 2. 의도 분류 체인
    # 2. 의도 분류 체인
    intent_classification_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """당신은 사용자 질문의 의도를 정확하게 분류하는 AI입니다.

    질문을 다음 카테고리 중 하나로 분류하세요:

    1. **hybrid_location_disaster**: 위치 + 재난 상황 복합 질문 ⭐ 우선순위 1
    - 예: "설악산 근처인데 산사태 발생 시", "강남역에서 지진 나면", "명동 화재"
    - 키워드: 지명 + (지진/화재/산사태/홍수 등)

    2. **shelter_info**: 특정 대피소의 상세 정보 조회 ⭐ 새로 추가
    - 예: "동대문맨션 수용인원", "서울역 대피소 정보", "롯데월드 최대 수용"
    - 키워드: 시설명 + (수용인원/정보/면적 등)

    3. **shelter_search**: 특정 위치의 대피소 찾기
    - 예: "한라산 근처 대피소", "강남역 대피소"
    - 키워드: 지명 + (근처/주변/대피소) WITHOUT 재난 키워드
    
    4. **shelter_count**: 특정 조건의 대피소 개수 세기
    - 예: "서울 대피소 개수", "지하 대피소 몇 개"
    
    5. **shelter_capacity**: 수용인원 기준 대피소 찾기
    - 예: "천 명 이상 수용 가능한 대피소"
    - 키워드: 숫자 + (이상/이하/수용)
    
    6. **disaster_guideline**: 재난 행동요령만 질문
    - 예: "지진 발생 시 행동요령" (위치 정보 없음)
    
    7. **general_knowledge**: 재난 관련 일반 지식
    - 예: "지진이 뭐야", "쓰나미란"
    
    8. **general_chat**: 일반 대화
    - 예: "안녕", "고마워"

    **중요 우선순위**: 
    - "위치 + 재난"이 함께 있으면 무조건 **hybrid_location_disaster**
    - "시설명 + 수용인원/정보"는 **shelter_info**
    - "위치 + 근처/주변"만 있고 재난 없으면 **shelter_search**

    **응답 형식**: JSON
    {{
        "intent": "카테고리명",
        "confidence": 0.95,
        "reason": "분류 근거"
    }}""",
            ),
            ("user", "{query}"),
        ]
    )

    intent_chain = intent_classification_prompt | llm | StrOutputParser()

    # 3. 질문 재정의 체인 (검색 정확도 향상)
    query_rewrite_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """당신은 검색 쿼리를 최적화하는 전문가입니다.

사용자의 질문을 **검색 시스템별로 최적화**된 형태로 재작성하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1️⃣ 카카오 API용 (위치 검색)**
- **목적**: 정확한 장소 좌표 찾기
- **원칙**: 
  ✅ 특정 위치(역, 건물, 매장): 그대로 유지
     예) "강남역", "롯데월드", "스타벅스 명동점"
  
  ✅ 지역명(시/구/동): 행정기관으로 변환
     예) "서울" → "서울시청"
     예) "동작구" → "동작구청"
     예) "송파" → "송파구청"
     예) "여의도동" → "여의도동 주민센터"
  
  ✅ "대피소", "근처", "주변" 등 제거
  
- **예시**:
  * "강남역 근처 대피소" → "강남역"
  * "서울 대피소" → "서울시청"
  * "동작구 주변" → "동작구청"
  * "송파 지하 대피소" → "송파구청"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**2️⃣ VectorDB용 (의미 검색)**
- **목적**: 유사한 문서 찾기 (BM25 + Vector)
- **원칙**:
  ✅ 핵심 키워드 + 동의어 추가
  ✅ 지역명 다양한 표현 (서울 → 서울 서울시 서울특별시)
  ✅ 위치 유형 명확화 (지하 → 지하 지하층)
  ✅ 최대 10단어 이내
  
- **예시**:
  * "강남역 근처 대피소" → "강남역 강남 대피소 피난처"
  * "서울 대피소" → "서울 서울시 서울특별시 대피소"
  * "동작구 지하" → "동작구 동작 지하 지하층 대피소"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**응답 형식** (JSON):
{{
    "kakao": "카카오 API용 쿼리",
    "vector": "VectorDB용 쿼리",
    "location_type": "specific" or "region"
}}

**location_type 판단 기준**:
- "specific": 역명, 건물명, 매장명 등 구체적 장소
- "region": 시/구/동 등 행정구역""",
            ),
            ("user", "{original_query}"),
        ]
    )

    query_rewrite_chain = query_rewrite_prompt | llm | StrOutputParser()

    # 4. 하이브리드 리트리버 생성
    shelter_hybrid, guideline_hybrid = create_hybrid_retrievers(vectorstore)

    # 5. Tools 정의
    @tool
    def search_shelter_by_location(query: str) -> dict:
        """
        특정 위치의 대피소를 검색합니다.
        - 특정 장소(역, 건물): 해당 위치 중심으로 검색
        - 지역명(시/구): 행정기관(시청/구청) 중심으로 검색
        """
        start_time = time.time()
        
        try:
            # ⭐ 질문 재정의로 location_type 판단
            vector_query = query_rewrite_chain.invoke({"original_query": query})
            
            try:
                import json
                parsed = json.loads(vector_query)
                kakao_query = parsed.get("kakao", query)
                vector_query = parsed.get("vector", query)
                location_type = parsed.get("location_type", "specific")
                
                print(f"[search_shelter_by_location] 위치 유형: {location_type}")
                print(f"[search_shelter_by_location] 카카오용: '{kakao_query}'")
                print(f"[search_shelter_by_location] Vector용: '{vector_query}'")
                
            except:
                # JSON 파싱 실패 시 기본값
                kakao_query = query
                location_type = "specific"
                
                # 기존 정제 로직
                remove_words = ["근처", "주변", "인근", "대피소", "피난소", "피난처", 
                              "알려줘", "찾아줘", "어디", "있어", "의", "를", "을"]
                for word in remove_words:
                    kakao_query = kakao_query.replace(word, "")
                
                kakao_query = " ".join(kakao_query.split()).strip()
        
            # 카카오 API 호출
            api_start = time.time()
            kakao_api_key = os.getenv("KAKAO_REST_API_KEY")
            if not kakao_api_key:
                return {"text": "카카오 API 키가 설정되지 않았습니다.", "structured_data": None}

            headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            params = {"query": kakao_query}

            try:
                response = requests.get(url, headers=headers, params=params)
                data = response.json()

                if not data.get("documents"):
                    return {
                        "text": f"'{kakao_query}' 위치를 찾을 수 없습니다.",
                        "structured_data": None,
                    }

                place = data["documents"][0]
                user_lat = float(place["y"])
                user_lon = float(place["x"])
                place_name = place["place_name"]
                
                location_desc = f"{place_name} ({location_type})"
                print(f"[카카오 API] 장소 확인: {location_desc} ({user_lat}, {user_lon})")

            except Exception as e:
                print(f"[카카오 API 오류] {e}")
                return {
                    "text": f"카카오 API 호출 중 오류가 발생했습니다: {str(e)}",
                    "structured_data": None,
                }
            
            api_time = time.time() - api_start
            print(f"⏱️ [카카오 API 호출 시간] {api_time:.3f}초")
            
            # VectorDB 검색 (기존 로직)
            vector_start = time.time()
            all_data = vectorstore.get(where={"type": "shelter"})
            vector_time = time.time() - vector_start
            print(f"⏱️ [ChromaDB 검색 시간] {vector_time:.3f}초")
            
            # 거리 계산
            calc_start = time.time()
            def haversine(lat1, lon1, lat2, lon2):
                R = 6371
                dlat = radians(lat2 - lat1)
                dlon = radians(lon2 - lon1)
                a = (
                    sin(dlat / 2) ** 2
                    + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
                )
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                return R * c

            shelters = []

            for metadata in all_data["metadatas"]:
                try:
                    lat = float(metadata.get("lat", 0))
                    lon = float(metadata.get("lon", 0))
                    if lat == 0 or lon == 0:
                        continue

                    distance = haversine(user_lat, user_lon, lat, lon)
                    shelters.append(
                        {
                            "name": metadata.get("facility_name", "N/A"),
                            "address": metadata.get("address", "N/A"),
                            "lat": lat,
                            "lon": lon,
                            "distance": distance,
                            "capacity": int(metadata.get("capacity", 0)),
                            "shelter_type": metadata.get("shelter_type", "N/A"),
                            "facility_type": metadata.get("facility_type", "N/A"),
                        }
                    )
                except Exception:
                    continue

            # 거리순 정렬
            shelters.sort(key=lambda x: x["distance"])
            top_5 = shelters[:5]

            if not top_5:
                return {
                    "text": f"'{place_name}' 근처에 대피소를 찾을 수 없습니다.",
                    "structured_data": None,
                }

            # 텍스트 결과 포맷팅
            location_text = "지역" if location_type == "region" else "위치"
            result_text = f"📍 **{place_name}** {location_text} 기준 대피소 {len(top_5)}곳\n\n"
            for i, s in enumerate(top_5, 1):
                result_text += f"{i}. **{s['name']}**\n"
                result_text += f"   📍 거리: {s['distance']:.2f}km\n"
                result_text += f"   📍 주소: {s['address']}\n"
                result_text += f"   📍 위치: {s['shelter_type']}\n"
                result_text += f"   📍 수용인원: {s['capacity']:,}명\n\n"

            # 구조화된 데이터 (지도 표시용)
            structured_data = {
                "location": place_name,
                "location_type": location_type,  # NEW
                "user_coordinates": [user_lat, user_lon],
                "coordinates": [user_lat, user_lon],
                "shelters": top_5,
                "total_count": len(all_data["metadatas"]),
            }

            total_time = time.time() - start_time
            print(f"⏱️ [search_shelter_by_location 총 시간] {total_time:.3f}초")
            
            return {"text": result_text.strip(), "structured_data": structured_data}

        except Exception as e:
            print(f"[ERROR] search_shelter_by_location: {e}")
            import traceback
            traceback.print_exc()
            return {"text": f"검색 중 오류 발생: {str(e)}", "structured_data": None}

    @tool
    def count_shelters(query: str) -> dict:
        """
        특정 조건(지역, 위치유형 등)에 맞는 대피소 개수를 셉니다.
        지도 표시용 구조화된 데이터를 포함합니다.

        Args:
            query: 검색 조건 (예: "서울 지하", "부산 민방위")

        Returns:
            dict: {"text": str, "structured_data": dict} 형식
        """
        try:
            # 쿼리 재정의
            rewritten = query_rewrite_chain.invoke({"original_query": query})
            print(f"[count_shelters] 재정의: {query} → {rewritten}")

            if shelter_hybrid is None:
                return {
                    "text": "검색 시스템이 초기화되지 않았습니다.",
                    "structured_data": None,
                }

            # 1단계: VectorDB 전체에서 매칭되는 대피소 찾기 (전체 개수 카운트용)
            all_data = vectorstore.get(where={"type": "shelter"})
            all_shelters = []

            # 검색 키워드 추출 (공백으로 분리)
            search_keywords = rewritten.lower().split()

            for metadata in all_data["metadatas"]:
                # 시설명, 주소, 위치유형에서 키워드 검색
                facility_name = metadata.get("facility_name", "").lower()
                address = metadata.get("address", "").lower()
                shelter_type = metadata.get("shelter_type", "").lower()

                # 검색 대상 텍스트 결합
                search_text = f"{facility_name} {address} {shelter_type}"

                # 모든 키워드 중 하나라도 포함되면 매칭
                if any(keyword in search_text for keyword in search_keywords):
                    all_shelters.append(
                        {
                            "name": metadata.get("facility_name", "N/A"),
                            "address": metadata.get("address", "N/A"),
                            "lat": float(metadata.get("lat", 0)),
                            "lon": float(metadata.get("lon", 0)),
                            "distance": 0,
                            "capacity": int(metadata.get("capacity", 0)),
                            "shelter_type": metadata.get("shelter_type", "N/A"),
                            "facility_type": metadata.get("facility_type", "N/A"),
                        }
                    )

            total_count = len(all_shelters)

            # 2단계: 하이브리드 검색으로 상위 결과 추출 (지도 표시용)
            results = shelter_hybrid.invoke(rewritten)

            # 중복 제거 및 대피소 정보 수집
            seen = set()
            top_shelters = []
            for doc in results:
                name = doc.metadata.get("facility_name", "")
                if name and name not in seen:
                    seen.add(name)
                    top_shelters.append(
                        {
                            "name": name,
                            "address": doc.metadata.get("address", "N/A"),
                            "lat": float(doc.metadata.get("lat", 0)),
                            "lon": float(doc.metadata.get("lon", 0)),
                            "distance": 0,
                            "capacity": int(doc.metadata.get("capacity", 0)),
                            "shelter_type": doc.metadata.get("shelter_type", "N/A"),
                            "facility_type": doc.metadata.get("facility_type", "N/A"),
                        }
                    )
                    if len(top_shelters) >= 10:  # 최대 10개
                        break

            if total_count == 0:
                return {
                    "text": f"'{query}' 조건에 맞는 대피소를 찾을 수 없습니다.",
                    "structured_data": None,
                }

            # 중심 좌표 계산 (평균)
            display_shelters = top_shelters if top_shelters else all_shelters[:10]
            avg_lat = (
                sum(s["lat"] for s in display_shelters if s["lat"] != 0)
                / len([s for s in display_shelters if s["lat"] != 0])
                if any(s["lat"] != 0 for s in display_shelters)
                else 0
            )
            avg_lon = (
                sum(s["lon"] for s in display_shelters if s["lon"] != 0)
                / len([s for s in display_shelters if s["lon"] != 0])
                if any(s["lon"] != 0 for s in display_shelters)
                else 0
            )

            structured_data = {
                "location": query,
                "coordinates": (avg_lat, avg_lon) if avg_lat != 0 else None,
                "shelters": display_shelters,  # 지도에 표시할 10개
                "total_count": total_count,  # VectorDB 전체 매칭 개수
            }

            return {
                "text": f"**'{query}'** 조건에 맞는 대피소는 총 **{total_count}개**입니다. 📊",
                "structured_data": structured_data,
            }

        except Exception as e:
            print(f"[ERROR] count_shelters: {e}")
            import traceback

            traceback.print_exc()
            return {"text": f"검색 중 오류 발생: {str(e)}", "structured_data": None}

    @tool
    def search_shelter_by_capacity(query: str) -> dict:
        """
        수용인원 기준으로 대피소를 검색합니다.
        위치 조건이 있으면 해당 지역 내에서만 검색합니다.
        "이상"과 "이하"를 구분하여 필터링합니다.

        Args:
            query: 수용인원 조건 (예: "천 명 이상", "300명 이하", "서울 동작구 천명 이상")

        Returns:
            dict: {"text": str, "structured_data": dict} 형식
        """
        try:
            # 1단계: "이상" vs "이하" 판단
            is_minimum = True  # 기본값: 이상
            if "이하" in query:
                is_minimum = False

            # 2단계: 숫자 단위 먼저 처리 (천, 만)
            capacity_value = 0

            # "천명", "천 명", "1천명" 등 처리
            if "천" in query or "1000" in query:
                # 천 앞의 숫자 찾기
                thousand_pattern = re.search(r"(\d+)\s*천", query)
                if thousand_pattern:
                    capacity_value = int(thousand_pattern.group(1)) * 1000
                else:
                    capacity_value = 1000  # 숫자 없이 "천명"만 있는 경우
            elif "만" in query or "10000" in query:
                # 만 앞의 숫자 찾기
                ten_thousand_pattern = re.search(r"(\d+)\s*만", query)
                if ten_thousand_pattern:
                    capacity_value = int(ten_thousand_pattern.group(1)) * 10000
                else:
                    capacity_value = 10000  # 숫자 없이 "만명"만 있는 경우
            else:
                # 일반 숫자 추출
                numbers = re.findall(r"\d+", query)
                if numbers:
                    capacity_value = int(numbers[0])

            if capacity_value == 0:
                return {
                    "text": "수용인원을 명확히 입력해주세요. (예: 1000명 이상, 천명 이상)",
                    "structured_data": None,
                }

            # 2단계: 위치 키워드 추출
            location_query = query

            # 수용인원 관련 부분 완전 제거
            remove_patterns = [
                r"\d+\s*천\s*명?\s*(이상|이하)?",  # "1천명 이상", "천명"
                r"\d+\s*만\s*명?\s*(이상|이하)?",  # "1만명 이상", "만명"
                r"\d+\s*명\s*(이상|이하)?",  # "53600명 이상", "1000명"
                r"천\s*명?\s*(이상|이하)?",  # "천명 이상"
                r"만\s*명?\s*(이상|이하)?",  # "만명 이상"
                r"수용\s*인원\s*(이|가)?",  # "수용인원이", "수용인원"
                r"수용\s*할?\s*수\s*있는",  # "수용할 수 있는"
                r"수용\s*가능한?",  # "수용가능한"
                r"최대\s*수용",  # "최대수용"
                r"인원\s*(이|가|을|를)?",  # "인원이", "인원을"
                r"대피소\s*(를|을|이|가)?",  # "대피소를", "대피소"
                r"찾아\s*줘?",
                r"알려\s*줘?",
                r"있어\??",
                r"있니\??",
                r"있나요\??",
            ]

            for pattern in remove_patterns:
                location_query = re.sub(
                    pattern, " ", location_query, flags=re.IGNORECASE
                )

            # "에서", "의" 등 조사 제거
            location_query = re.sub(r"\s*(에서|에|의|에서의)\s*", " ", location_query)

            # 공백 정리
            location_query = " ".join(location_query.split()).strip()

            condition_text = "이상" if is_minimum else "이하"
            print(
                f"[search_shelter_by_capacity] 수용인원: {capacity_value}명 {condition_text}"
            )
            print(f"[search_shelter_by_capacity] 위치 필터: '{location_query}'")

            # 모든 대피소 가져오기
            all_data = vectorstore.get(where={"type": "shelter"})
            shelters = []

            for metadata in all_data["metadatas"]:
                capacity = int(metadata.get("capacity", 0))

                # 수용인원 조건 체크 (이상 vs 이하)
                if is_minimum:
                    if capacity < capacity_value:
                        continue
                else:
                    if capacity > capacity_value:
                        continue

                # 위치 조건 체크 (위치 키워드가 있으면)
                if location_query:
                    facility_name = metadata.get("facility_name", "").lower()
                    address = metadata.get("address", "").lower()
                    shelter_type = metadata.get("shelter_type", "").lower()

                    # 시설명, 주소, 위치유형에서 위치 키워드 검색
                    search_text = f"{facility_name} {address} {shelter_type}"

                    # 위치 키워드의 모든 부분이 포함되어야 매칭
                    location_keywords = location_query.split()
                    if not all(
                        keyword in search_text
                        for keyword in location_keywords
                        if keyword
                    ):
                        continue

                shelters.append(
                    {
                        "name": metadata.get("facility_name", "N/A"),
                        "address": metadata.get("address", "N/A"),
                        "lat": float(metadata.get("lat", 0)),
                        "lon": float(metadata.get("lon", 0)),
                        "capacity": capacity,
                        "shelter_type": metadata.get("shelter_type", "N/A"),
                        "distance": 0,  # 수용인원 검색은 거리 정보 없음
                    }
                )

            # 수용인원 내림차순 정렬
            shelters.sort(key=lambda x: x["capacity"], reverse=True)
            top_10 = shelters[:10]

            if not top_10:
                location_text = (
                    f"'{location_query}' 지역에서 " if location_query else ""
                )
                condition_text = "이상" if is_minimum else "이하"
                return {
                    "text": f"{location_text}{capacity_value:,}명 {condition_text} 수용 가능한 대피소를 찾을 수 없습니다.",
                    "structured_data": None,
                }

            location_text = f"**{location_query}** 지역 " if location_query else ""
            condition_text = "이상" if is_minimum else "이하"
            result = f"📊 {location_text}**{capacity_value:,}명 {condition_text}** 수용 가능한 대피소 **{len(shelters)}곳** 중 상위 10곳\n\n"
            for i, s in enumerate(top_10, 1):
                result += f"{i}. **{s['name']}** ({s['capacity']:,}명)\n"
                result += f"   📍 {s['address']}\n"
                result += f"   📍 위치: {s['shelter_type']}\n\n"

            # 중심 좌표 계산 (평균)
            avg_lat = (
                sum(s["lat"] for s in top_10 if s["lat"] != 0)
                / len([s for s in top_10 if s["lat"] != 0])
                if any(s["lat"] != 0 for s in top_10)
                else 0
            )
            avg_lon = (
                sum(s["lon"] for s in top_10 if s["lon"] != 0)
                / len([s for s in top_10 if s["lon"] != 0])
                if any(s["lon"] != 0 for s in top_10)
                else 0
            )

            structured_data = {
                "location": (
                    f"{location_query} {capacity_value:,}명 {condition_text}"
                    if location_query
                    else f"{capacity_value:,}명 {condition_text} 수용 가능"
                ),
                "coordinates": (avg_lat, avg_lon) if avg_lat != 0 else None,
                "shelters": top_10,
                "total_count": len(shelters),
            }

            return {"text": result.strip(), "structured_data": structured_data}

        except Exception as e:
            print(f"[ERROR] search_shelter_by_capacity: {e}")
            import traceback

            traceback.print_exc()
            return {"text": f"검색 중 오류 발생: {str(e)}", "structured_data": None}

    @tool
    def search_disaster_guideline(query: str) -> dict:
        """
        재난 행동요령을 검색합니다.

        Args:
            query: 재난 유형 (예: "지진", "화재", "산사태")

        Returns:
            dict: {"text": str, "structured_data": None} 형식
        """
        try:
            # 쿼리 재정의
            rewritten = query_rewrite_chain.invoke({"original_query": query})
            print(f"[search_disaster_guideline] 재정의: {query} → {rewritten}")

            # ⭐ 재난 키워드 매핑 (사용자 입력 → VectorDB 저장명)
            disaster_keyword_mapping = {
            # 기상 재난 - 비 관련 (단계별 구분)
            "비": "호우",
            "폭우": "호우",
            "집중호우": "호우",
            "장마": "호우",
            "게릴라성 호우": "호우",
            "많은 비": "호우",
            "강한 비": "호우",
            
            # 기상 재난 - 물 관련
            "홍수": "홍수",
            "침수": "홍수",
            "범람": "홍수",
            "강물이 넘쳤": "홍수",
            "물이 넘쳤": "홍수",
            "물난리": "홍수",
            "수해": "홍수",
            
            # 기상 재난 - 바람/태풍
            "태풍": "태풍",
            "강풍": "태풍",
            "돌풍": "태풍",
            "폭풍": "태풍",
            
            # 지질 재난 - 지진 관련
            "지진": "지진",
            "진동": "지진",
            "땅이 흔들": "지진",
            "여진": "지진",
            
            # 지질 재난 - 해양
            "쓰나미": "지진해일",
            "해일": "지진해일",
            "지진해일": "지진해일",
            "해안 침수": "지진해일",
            
            # 지질 재난 - 산사태
            "산사태": "산사태",
            "토석류": "산사태",
            "산 무너짐": "산사태",
            "산 붕괴": "산사태",
            "낙석": "산사태",
            "사면 붕괴": "산사태",
            
            # 화재 재난
            "화재": "화재",
            "불": "화재",
            "화염": "화재",
            "연기": "화재",
            "산불": "산불",
            "산에 불": "산불",
            "산림 화재": "산불",
            "들불": "산불",
            
            # 폭발/가스
            "폭발": "폭발",
            "가스": "가스",
            "가스 누출": "가스",
            "가스 폭발": "폭발",
            
            # 화산 재난
            "화산": "화산폭발",
            "화산 폭발": "화산폭발",
            "화산재": "화산재",
            "분화": "화산폭발",
            
            # 방사능
            "방사능": "방사능",
            "방사선": "방사능",
            "핵": "방사능",
            "원전": "방사능",
            
            # 붕괴 재난
            "붕괴": "댐붕괴",
            "댐 붕괴": "댐붕괴",
            "댐 터짐": "댐붕괴",
            }

            # 사용자 입력에서 재난 키워드 추출
            detected_keyword = None
            detected_disaster = None

            for keyword, mapped_name in disaster_keyword_mapping.items():
                if keyword in query.lower():
                    detected_keyword = keyword  # 사용자 입력 원본
                    detected_disaster = mapped_name  # VectorDB 검색용
                    break

            if not detected_disaster:
                # 매핑 실패 시 재정의된 쿼리 그대로 사용
                detected_disaster = rewritten
                detected_keyword = query

            print(f"[search_disaster_guideline] 검색 키워드: '{detected_disaster}' (입력: '{detected_keyword}')")

            # ⭐ VectorDB에서 keyword 필드로 정확히 필터링 ($and 연산자 사용)
            all_data = vectorstore.get(
                where={
                    "$and": [  # 논리 연산자로 감싸기
                        {"type": "disaster_guideline"},
                        {"keyword": detected_disaster}
                    ]
                }
            )

            if not all_data or not all_data.get("documents"):
                return {
                    "text": f"'{detected_keyword}' 관련 행동요령을 찾을 수 없습니다.",
                    "structured_data": None,
                }

            # 상위 3개 결과 통합
            combined = "\n\n".join(all_data["documents"][:3])

            return {
                "text": f"🚨 **{detected_keyword} 행동요령**\n\n{combined}",
                "structured_data": None,
            }

        except Exception as e:
            print(f"[ERROR] search_disaster_guideline: {e}")
            import traceback
            traceback.print_exc()
            return {"text": f"검색 중 오류 발생: {str(e)}", "structured_data": None}

    @tool
    def answer_general_knowledge(query: str) -> dict:
        """
        재난 관련 일반 지식 질문에 답변합니다. (정의, 원인, 특징 등)
        VectorDB에 없는 정보는 LLM의 사전 학습 지식을 활용합니다.

        Args:
            query: 일반 지식 질문 (예: "지진이 뭐야", "쓰나미란")

        Returns:
            dict: {"text": str, "structured_data": None} 형식
        """
        try:
            print(f"[answer_general_knowledge] 질문: {query}")

            # LLM에게 직접 질문 (사전 학습 지식 활용)
            prompt = f"""당신은 재난 안전 전문가입니다.
다음 질문에 정확하고 간결하게 답변하세요.

질문: {query}

답변 형식:
- 핵심 정의를 2-3문장으로 설명
- 주요 특징이나 원인을 불릿 포인트로 정리
- 전문 용어는 쉽게 풀어서 설명
- 최대 200자 이내로 간결하게"""

            response = llm_creative.invoke([HumanMessage(content=prompt)])

            return {
                "text": f"💡 **{query}**\n\n{response.content}",
                "structured_data": None,  # 일반 지식은 위치 정보 없음
            }

        except Exception as e:
            print(f"[ERROR] answer_general_knowledge: {e}")
            return {
                "text": "죄송합니다. 답변 생성 중 오류가 발생했습니다.",
                "structured_data": None,
            }

    @tool
    def search_shelter_by_name(query: str) -> dict:
        """
        특정 대피소의 상세 정보를 시설명으로 검색합니다.
        위치 조건이 있으면 해당 지역 내에서만 검색합니다.
        수용인원, 주소, 위치 등 해당 시설의 모든 정보를 반환합니다.
        지도 표시용 구조화된 데이터를 포함합니다.

        Args:
            query: 대피소 시설명 (예: "동대문맨션", "제주도 동아아파트", "서울 롯데월드")

        Returns:
            dict: {"text": str, "structured_data": dict} 형식

        Examples:
            - "동대문맨션 수용인원" → search_shelter_by_name("동대문맨션")
            - "제주도 동아아파트 정보" → search_shelter_by_name("제주도 동아아파트")
        """
        try:
            print(f"[search_shelter_by_name] 검색 시작: '{query}'")

            # 1단계: 위치와 시설명 분리
            original_query = query.strip().lower()

            # 지역 키워드 리스트 (시/도/구 단위)
            location_keywords = [
                # 제주 관련 (길이순 정렬 - 긴 것부터)
                "제주특별자치도",
                "제주도",
                "제주시",
                "서귀포시",
                "제주",
                # 광역시/도
                "서울특별시",
                "서울",
                "부산광역시",
                "부산",
                "대구광역시",
                "대구",
                "인천광역시",
                "인천",
                "광주광역시",
                "광주",
                "대전광역시",
                "대전",
                "울산광역시",
                "울산",
                "세종특별자치시",
                "세종",
                "경기도",
                "경기",
                "강원도",
                "강원특별자치도",
                "강원",
                "충청북도",
                "충북",
                "충청남도",
                "충남",
                "전라북도",
                "전북",
                "전라남도",
                "전남",
                "경상북도",
                "경북",
                "경상남도",
                "경남",
                # 서울 구
                "강남구",
                "강동구",
                "강북구",
                "강서구",
                "관악구",
                "광진구",
                "구로구",
                "금천구",
                "노원구",
                "도봉구",
                "동대문구",
                "동작구",
                "마포구",
                "서대문구",
                "서초구",
                "성동구",
                "성북구",
                "송파구",
                "양천구",
                "영등포구",
                "용산구",
                "은평구",
                "종로구",
                "중구",
                "중랑구",
            ]

            # 위치 키워드 추출 (긴 것부터 매칭 - 이미 정렬됨)
            location_filter = None
            for loc in location_keywords:
                if loc in original_query:
                    location_filter = loc
                    print(f"[DEBUG] 위치 키워드 '{loc}' 매칭됨")
                    break

            print(f"[DEBUG] 최종 location_filter: '{location_filter}'")

            # 2단계: 검색어 정제 (불필요한 단어 제거)
            search_term = original_query

            # 위치 키워드 먼저 제거 (시설명만 남김)
            if location_filter:
                search_term = search_term.replace(location_filter, " ")

            # 불필요한 단어 제거
            remove_words = [
                "대피소",
                "수용인원",
                "최대수용인원",
                "몇명",
                "정보",
                "알려줘",
                "알려",
                "의",
                "이",
                "가",
                "은",
                "는",
                "?",
                "!",
                "를",
                "을",
                "도",
                "시",
                "군",
                "구",
            ]  # 행정구역 단위도 제거

            for word in remove_words:
                search_term = search_term.replace(word, " ")

            search_term = (
                " ".join(search_term.split()).strip().lower()
            )  # 소문자 변환 추가

            print(f"[search_shelter_by_name] 정제된 검색어: '{search_term}'")
            print(f"[search_shelter_by_name] 위치 필터: '{location_filter}'")

            # VectorStore에서 shelter 타입 문서 가져오기
            all_data = vectorstore.get(where={"type": "shelter"})

            # 3단계: 시설명 매칭 (부분 일치)
            matches = []
            match_attempt = 0
            for metadata in all_data["metadatas"]:
                facility_name = metadata.get("facility_name", "")
                facility_lower = facility_name.lower()
                address = metadata.get("address", "").lower()

                # 시설명 매칭 (양방향 부분 일치)
                if search_term in facility_lower or facility_lower in search_term:
                    match_attempt += 1

                    # 위치 필터가 있으면 주소도 체크
                    if location_filter:
                        filter_lower = location_filter.lower()

                        # 유연한 위치 매칭 - 행정구역 단위 제거 (긴 것부터 순서대로)
                        filter_core = (
                            filter_lower.replace(
                                "특별자치도", ""
                            )  # '제주특별자치도' → '제주'
                            .replace("특별자치시", "")  # '세종특별자치시' → '세종'
                            .replace("특별시", "")  # '서울특별시' → '서울'
                            .replace("광역시", "")  # '부산광역시' → '부산'
                            .replace("도", "")  # '경기도' → '경기', '제주도' → '제주'
                            .replace("시", "")
                            .replace("군", "")
                            .replace("구", "")
                            .strip()
                        )

                        if match_attempt <= 3:
                            print(
                                f"[DEBUG] 시설명 매칭: '{facility_name}', 주소: '{address[:30]}...', filter_lower: '{filter_lower}', filter_core: '{filter_core}', 포함여부: {filter_core in address}"
                            )

                        if filter_core not in address:
                            continue

                    matches.append(
                        {
                            "name": facility_name,
                            "address": metadata.get("address", "N/A"),
                            "lat": float(metadata.get("lat", 0)),
                            "lon": float(metadata.get("lon", 0)),
                            "capacity": int(metadata.get("capacity", 0)),
                            "shelter_type": metadata.get("shelter_type", "N/A"),
                            "facility_type": metadata.get("facility_type", "N/A"),
                            "operating_status": metadata.get("operating_status", "N/A"),
                            "distance": 0,  # 시설명 검색은 거리 정보 없음
                        }
                    )
                    print(
                        f"[search_shelter_by_name] 매칭됨: {facility_name} ({metadata.get('address', 'N/A')})"
                    )

            print(f"[DEBUG] 총 매칭된 대피소 개수: {len(matches)}")

            if not matches:
                location_text = f"{location_filter} " if location_filter else ""
                return {
                    "text": f"❌ '{location_text}{search_term}' 시설을 찾을 수 없습니다.\n시설명을 정확히 입력해주세요.",
                    "structured_data": None,
                }

            # 결과 반환
            if len(matches) == 1:
                m = matches[0]
                text = f"""📍 **{m['name']}**

    ✅ **최대 수용인원: {m['capacity']:,}명**
    📍 주소: {m['address']}
    📍 위치: {m['shelter_type']}
    📍 시설 유형: {m['facility_type']}
    📍 운영 상태: {m['operating_status']}"""

                # 구조화된 데이터 (지도 표시용)
                structured_data = {
                    "location": m["name"],
                    "coordinates": (m["lat"], m["lon"]) if m["lat"] != 0 else None,
                    "shelters": [m],
                    "total_count": 1,
                }

                return {"text": text, "structured_data": structured_data}

            else:
                # 여러 개 발견 시
                print(f"[DEBUG] 여러 개 발견 분기 진입: {len(matches)}개")
                text = (
                    f"📍 **'{search_term}'** 관련 대피소 **{len(matches)}곳** 발견\n\n"
                )
                for i, m in enumerate(matches[:5], 1):  # 상위 5개만
                    text += f"{i}. **{m['name']}**\n"
                    text += f"   ✅ 수용인원: **{m['capacity']:,}명**\n"
                    text += f"   📍 주소: {m['address']}\n"
                    text += f"   📍 위치: {m['shelter_type']}\n\n"

                if len(matches) > 5:
                    text += f"💡 외 {len(matches) - 5}곳 더 있습니다."

                # 중심 좌표 계산 (평균)
                avg_lat = (
                    sum(s["lat"] for s in matches if s["lat"] != 0)
                    / len([s for s in matches if s["lat"] != 0])
                    if any(s["lat"] != 0 for s in matches)
                    else 0
                )
                avg_lon = (
                    sum(s["lon"] for s in matches if s["lon"] != 0)
                    / len([s for s in matches if s["lon"] != 0])
                    if any(s["lon"] != 0 for s in matches)
                    else 0
                )

                structured_data = {
                    "location": search_term,
                    "coordinates": (avg_lat, avg_lon) if avg_lat != 0 else None,
                    "shelters": matches[:5],
                    "total_count": len(matches),
                }

                return {"text": text.strip(), "structured_data": structured_data}

        except Exception as e:
            print(f"[ERROR] search_shelter_by_name: {e}")
            import traceback

            traceback.print_exc()
            return {"text": f"❌ 검색 중 오류 발생: {str(e)}", "structured_data": None}

    @tool
    def search_location_with_disaster(query: str) -> dict:
        """
        특정 위치에서 재난 발생 시 대피소와 행동요령을 함께 제공합니다.
        위치 기반 대피소 검색 + 재난 행동요령을 통합하여 반환합니다.
        지도 표시용 구조화된 데이터를 포함합니다.

        Args:
            query: 위치 + 재난 상황 (예: "설악산 근처 산사태", "강남역에서 지진")

        Returns:
            dict: {"text": str, "structured_data": dict} 형식

        Examples:
            - "설악산 근처인데 산사태 발생 시" → 설악산 대피소 + 산사태 행동요령
            - "명동에서 지진 나면" → 명동 대피소 + 지진 행동요령
        """
        try:
            print(f"[search_location_with_disaster] 복합 질문 처리: {query}")

           # 1단계: 재난 유형 감지
            # 키워드 매핑: 사용자 입력 → VectorDB 저장명
            disaster_keyword_mapping = {
            # 기상 재난 - 비 관련 (단계별 구분)
            "비": "호우",
            "폭우": "호우",
            "집중호우": "호우",
            "장마": "호우",
            "게릴라성 호우": "호우",
            "많은 비": "호우",
            "강한 비": "호우",
            
            # 기상 재난 - 물 관련
            "홍수": "홍수",
            "침수": "홍수",
            "범람": "홍수",
            "강물이 넘쳤": "홍수",
            "물이 넘쳤": "홍수",
            "물난리": "홍수",
            "수해": "홍수",
            
            # 기상 재난 - 바람/태풍
            "태풍": "태풍",
            "강풍": "태풍",
            "돌풍": "태풍",
            "폭풍": "태풍",
            
            # 지질 재난 - 지진 관련
            "지진": "지진",
            "진동": "지진",
            "땅이 흔들": "지진",
            "여진": "지진",
            
            # 지질 재난 - 해양
            "쓰나미": "지진해일",
            "해일": "지진해일",
            "지진해일": "지진해일",
            "해안 침수": "지진해일",
            
            # 지질 재난 - 산사태
            "산사태": "산사태",
            "토석류": "산사태",
            "산 무너짐": "산사태",
            "산 붕괴": "산사태",
            "낙석": "산사태",
            "사면 붕괴": "산사태",
            
            # 화재 재난
            "화재": "화재",
            "불": "화재",
            "화염": "화재",
            "연기": "화재",
            "산불": "산불",
            "산에 불": "산불",
            "산림 화재": "산불",
            "들불": "산불",
            
            # 폭발/가스
            "폭발": "폭발",
            "가스": "가스",
            "가스 누출": "가스",
            "가스 폭발": "폭발",
            
            # 화산 재난
            "화산": "화산폭발",
            "화산 폭발": "화산폭발",
            "화산재": "화산재",
            "분화": "화산폭발",
            
            # 방사능
            "방사능": "방사능",
            "방사선": "방사능",
            "핵": "방사능",
            "원전": "방사능",
            
            # 붕괴 재난
            "붕괴": "댐붕괴",
            "댐 붕괴": "댐붕괴",
            "댐 터짐": "댐붕괴",
            }

            detected_disaster = None
            detected_keyword = None  # 사용자가 입력한 키워드
            location_query = query

            for keyword, mapped_name in disaster_keyword_mapping.items():
                if keyword in query:
                    detected_keyword = keyword  # 원본 키워드
                    detected_disaster = mapped_name  # VectorDB 검색용
                    location_query = location_query.replace(keyword, "")
                    break

            # "발생", "나면", "났을 때" 등 제거
            for word in ["발생", "발생하면", "발생 시", "났을 때", "나면", "때", "근처인데", "에서", "어떻게", "대처", "행동요령"]:
                location_query = location_query.replace(word, "")

            location_query = location_query.strip()
            
            if not detected_disaster:
                return {
                    "text": "재난 유형을 파악할 수 없습니다. 예: '설악산 산사태', '강남역 지진', '양양 쓰나미'",
                    "structured_data": None,
                }

            print(f"[search_location_with_disaster] 위치: '{location_query}', 재난: '{detected_disaster}' (입력: '{detected_keyword}')")


            # 2단계: 질문 재정의로 위치 유형 판단 (search_shelter_by_location과 동일)
            rewritten = query_rewrite_chain.invoke({"original_query": location_query})
            
            kakao_query = location_query
            location_type = "specific"
            
            try:
                import json
                parsed = json.loads(rewritten)
                kakao_query = parsed.get("kakao", location_query)
                vector_query = parsed.get("vector", location_query)
                location_type = parsed.get("location_type", "specific")
                
                print(f"[search_location_with_disaster] 위치 유형: {location_type}")
                print(f"[search_location_with_disaster] 카카오용: '{kakao_query}'")
                print(f"[search_location_with_disaster] Vector용: '{vector_query}'")
                
            except:
                # JSON 파싱 실패 시 기존 정제 로직
                remove_words = ["근처", "주변", "인근", "대피소", "피난소", "피난처"]
                for word in remove_words:
                    kakao_query = kakao_query.replace(word, "")
                kakao_query = " ".join(kakao_query.split()).strip()

            print(f"[search_location_with_disaster] 최종 카카오 검색어: '{kakao_query}' ({location_type})")

            # 3단계: 카카오 API로 좌표 검색 (search_shelter_by_location과 동일)
            kakao_api_key = os.getenv("KAKAO_REST_API_KEY")
            if not kakao_api_key:
                return {"text": "카카오 API 키가 설정되지 않았습니다.", "structured_data": None}

            headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            params = {"query": kakao_query}

            try:
                response = requests.get(url, headers=headers, params=params)
                data = response.json()

                if not data.get("documents"):
                    return {
                        "text": f"'{kakao_query}' 위치를 찾을 수 없습니다.",
                        "structured_data": None,
                    }

                place = data["documents"][0]
                user_lat = float(place["y"])
                user_lon = float(place["x"])
                place_name = place["place_name"]
                
                location_desc = f"{place_name} ({location_type})"
                print(f"[search_location_with_disaster] 장소 확인: {location_desc} ({user_lat}, {user_lon})")

            except Exception as e:
                print(f"[search_location_with_disaster] 카카오 API 오류: {e}")
                return {
                    "text": f"카카오 API 호출 중 오류가 발생했습니다: {str(e)}",
                    "structured_data": None,
                }

            # 4단계: 근처 대피소 검색 (거리 계산)
            def haversine(lat1, lon1, lat2, lon2):
                from math import radians, sin, cos, sqrt, atan2
                R = 6371
                dlat = radians(lat2 - lat1)
                dlon = radians(lon2 - lon1)
                a = (
                    sin(dlat / 2) ** 2
                    + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
                )
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                return R * c

            all_data = vectorstore.get(where={"type": "shelter"})
            shelters = []

            for metadata in all_data["metadatas"]:
                try:
                    lat = float(metadata.get("lat", 0))
                    lon = float(metadata.get("lon", 0))
                    if lat == 0 or lon == 0:
                        continue

                    distance = haversine(user_lat, user_lon, lat, lon)
                    shelters.append(
                        {
                            "name": metadata.get("facility_name", "N/A"),
                            "address": metadata.get("address", "N/A"),
                            "lat": lat,
                            "lon": lon,
                            "distance": distance,
                            "capacity": int(metadata.get("capacity", 0)),
                            "shelter_type": metadata.get("shelter_type", "N/A"),
                            "facility_type": metadata.get("facility_type", "N/A"),
                        }
                    )
                except Exception:
                    continue

            shelters.sort(key=lambda x: x["distance"])
            top_3 = shelters[:3]  # 가장 가까운 3곳만

            if not top_3:
                return {
                    "text": f"'{place_name}' 근처에 대피소를 찾을 수 없습니다.",
                    "structured_data": None,
                }

            # 5단계: 재난 행동요령 검색
            guideline_text = ""
            if guideline_hybrid:
                try:
                    guideline_results = guideline_hybrid.invoke(detected_disaster)
                    if guideline_results:
                        # 상위 2개 결과만 사용 (간결하게)
                        guideline_text = "\n\n".join(
                            [doc.page_content for doc in guideline_results[:2]]
                        )
                except Exception as e:
                    print(f"[search_location_with_disaster] 가이드라인 검색 실패: {e}")
                    guideline_text = f"{detected_disaster} 관련 행동요령을 찾을 수 없습니다."

            ## 6단계: 통합 결과 생성
            location_text = "지역" if location_type == "region" else "위치"
            # 사용자가 입력한 키워드를 표시 (더 자연스러운 응답)
            display_disaster = detected_keyword if detected_keyword else detected_disaster
            result = f"""🚨 **{place_name} {location_text} 기준 {display_disaster} 발생 시 대응 가이드**

    📍 **가장 가까운 대피소 {len(top_3)}곳**

    """

            for i, s in enumerate(top_3, 1):
                result += f"{i}. **{s['name']}** ({s['distance']:.2f}km)\n"
                result += f"   📍 {s['address']}\n"
                result += f"   📍 위치: {s['shelter_type']} | 수용: {s['capacity']:,}명\n\n"

            result += f"""

    🚨 **{display_disaster} 행동요령**


    {guideline_text}

    💡 **즉시 행동 체크리스트**
    ✅ 가장 가까운 대피소로 이동
    ✅ 위 행동요령을 숙지하고 침착하게 대응
    ✅ 119 신고 (필요 시)
    """

            # 구조화된 데이터 (지도 표시용)
            structured_data = {
                "location": place_name,
                "location_type": location_type,  # NEW
                "user_coordinates": [user_lat, user_lon],  # 사용자 위치 (길찾기용)
                "coordinates": [user_lat, user_lon],
                "shelters": top_3,
                "total_count": len(all_data["metadatas"]),
            }

            return {"text": result.strip(), "structured_data": structured_data}

        except Exception as e:
            print(f"[ERROR] search_location_with_disaster: {e}")
            import traceback
            traceback.print_exc()
            return {
                "text": f"복합 검색 중 오류 발생: {str(e)}",
                "structured_data": None,
            }

    # 6. Tools 리스트
    tools = [
        search_shelter_by_location,
        count_shelters,
        search_shelter_by_capacity,
        search_disaster_guideline,
        answer_general_knowledge,
        search_shelter_by_name,
        search_location_with_disaster,
    ]

    # 7. LLM에 Tools 바인딩
    llm_with_tools = llm.bind_tools(tools)

    # 8. State 정의
    class AgentState(TypedDict):
        messages: Annotated[list[BaseMessage], add_messages]
        intent: str
        rewritten_query: str
        structured_data: Optional[dict]  # 지도 표시용 구조화된 데이터

    # 9. 시스템 프롬프트
    SYSTEM_PROMPT = """당신은 대한민국의 재난 안전 전문 AI 도우미입니다.

**핵심 원칙**:
1. **정확성 우선**: 제공된 도구 결과만 사용하고, 없는 정보는 지어내지 마세요
2. **의도 파악**: 사용자 질문의 의도를 정확히 분류하고 적절한 도구를 선택하세요
3. **복합 질문 처리**: 여러 의도가 섞인 질문은 순차적으로 처리하세요

**도구 선택 가이드**:
- 위치 + 재난 복합 질문 → search_location_with_disaster
   - "설악산 근처인데 산사태 발생 시" → search_location_with_disaster("설악산 산사태")
   - "강남역에서 지진 나면" → search_location_with_disaster("강남역 지진")
   - "명동 화재 났을 때" → search_location_with_disaster("명동 화재")
   
- 특정 시설명이 포함된 질문 → search_shelter_by_name
   - "동대문맨션 수용인원" → search_shelter_by_name("동대문맨션")
   - "서울역 대피소 정보" → search_shelter_by_name("서울역")
   
- "근처", "주변" 키워드만 → search_shelter_by_location
   - "강남역 근처 대피소" → search_shelter_by_location("강남역")
   - "명동 주변 피난소" → search_shelter_by_location("명동")

- "X명 이상/이하" 조건 → search_shelter_by_capacity
   - "1000명 이상 수용 가능한 대피소" → search_shelter_by_capacity("1000명 이상")

- "개수", "몇 개" → count_shelters
   - "서울 지하 대피소 몇 개?" → count_shelters("서울 지하")

- 재난 행동요령만 → search_disaster_guideline
   - "지진 발생 시 행동요령" → search_disaster_guideline("지진")
   - (위치 정보 없이 행동요령만 필요한 경우)

- 재난 일반 지식 → answer_general_knowledge
   - "지진이 뭐야?" → answer_general_knowledge("지진이 뭐야")

**중요 판단 기준**:
- 질문에 "위치 + 재난"이 함께 있으면 → search_location_with_disaster
- 질문에 "시설명 + 정보 요청"이 있으면 → search_shelter_by_name
- 질문에 "위치 + 근처/주변"만 있으면 → search_shelter_by_location

**응답 형식**:
- 구체적이고 실용적인 정보 제공
- 중요 정보는 **볼드체** 강조
- 숫자는 쉼표 구분 (1,000명)
- 이모지 적절히 활용 (📍🚨💡📊)
"""

    # 10. 노드 함수들
    def intent_classifier_node(state: AgentState):
        """의도 분류 노드 (LLM만 사용)"""
        start_time = time.time()
        messages = state["messages"]
        last_message = messages[-1].content

        print(f"\n[의도분류 노드] 입력: {last_message}")

        try:
            # LLM 기반 의도 분류
            intent_result = intent_chain.invoke({"query": last_message})
            intent_data = json.loads(intent_result)
            intent = intent_data["intent"]

            elapsed = time.time() - start_time
            print(f"⏱️ [의도분류 시간] {elapsed:.3f}초")
            print(f"[의도분류 노드] 결과: {intent} (신뢰도: {intent_data.get('confidence', 0)})")

            return {"intent": intent}

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"⏱️ [의도분류 시간 (실패)] {elapsed:.3f}초")
            print(f"[의도분류 노드] 오류: {e}, 기본값 사용")
            return {"intent": "general_chat"}


    def query_rewrite_node(state: AgentState):
        """질문 재정의 노드 (시간 측정)"""
        start_time = time.time()
        messages = state["messages"]
        last_message = messages[-1].content
        intent = state.get("intent", "")

        if intent in ["general_chat", "general_knowledge"]:
            return {"rewritten_query": last_message}

        print(f"\n[질문재정의 노드] 입력: {last_message}")

        try:
            rewritten = query_rewrite_chain.invoke({"original_query": last_message})
            
            # JSON 파싱 시도
            try:
                import json
                parsed = json.loads(rewritten)
                kakao_query = parsed.get("kakao", last_message)
                vector_query = parsed.get("vector", last_message)
                
                print(f"[질문재정의] 카카오용: {kakao_query}")
                print(f"[질문재정의] Vector용: {vector_query}")
                
                # State에 두 쿼리 모두 저장
                return {
                    "rewritten_query": vector_query,  # 기본값 (기존 로직 유지)
                    "kakao_query": kakao_query,       # 카카오 전용 (NEW)
                }
            except (json.JSONDecodeError, KeyError):
                # JSON 파싱 실패 시 기존 방식 사용
                print(f"[질문재정의] 단일 쿼리: {rewritten}")
                return {"rewritten_query": rewritten}
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"⏱️ [질문재정의 시간 (실패)] {elapsed:.3f}초")
            print(f"[질문재정의 노드] 오류: {e}")
            return {"rewritten_query": last_message}


    def agent_node(state: AgentState):
        """에이전트 추론 노드 (시간 측정)"""
        start_time = time.time()
        messages = state["messages"]
        intent = state.get("intent", "")

        print(f"\n[에이전트 노드] 의도: {intent}")

        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        response = llm_with_tools.invoke(messages)
        
        elapsed = time.time() - start_time
        print(f"⏱️ [LLM 호출 시간] {elapsed:.3f}초")

        return {"messages": [response]}


    def tools_node_with_structured_data(state: AgentState):
        """도구 실행 노드 (시간 측정)"""
        start_time = time.time()
        from langgraph.prebuilt import ToolNode

        tool_node = ToolNode(tools)
        result = tool_node.invoke(state)

        # 도구 결과에서 structured_data 추출
        messages = result.get("messages", [])
        structured_data = None

        for message in messages:
            if hasattr(message, "content"):
                content = message.content

                # content가 문자열인 경우 JSON 파싱 시도
                if isinstance(content, str):
                    try:
                        import json

                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "structured_data" in parsed:
                            # None이 아닌 structured_data를 우선적으로 사용
                            if parsed["structured_data"] is not None:
                                structured_data = parsed["structured_data"]
                                print(
                                    f"[tools_node] structured_data 추출 완료 (JSON): True"
                                )
                            message.content = parsed.get("text", content)
                    except (json.JSONDecodeError, TypeError):
                        pass

                # content가 dict인 경우 직접 처리
                elif isinstance(content, dict) and "structured_data" in content:
                    # None이 아닌 structured_data를 우선적으로 사용
                    if content["structured_data"] is not None:
                        structured_data = content["structured_data"]
                        print(f"[tools_node] structured_data 추출 완료 (dict): True")
                    message.content = content.get("text", str(content))

        elapsed = time.time() - start_time
        print(f"⏱️ [도구 실행 시간] {elapsed:.3f}초")

        return {"messages": messages, "structured_data": structured_data}

    def should_continue(state: AgentState):
        """도구 실행 필요 여부 판단"""
        messages = state["messages"]
        last_message = messages[-1]

        # 도구 호출이 있으면 도구 실행
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # 없으면 종료
        return END

    def should_continue_after_tools(state: AgentState):
        """도구 실행 후 추가 처리 필요 여부 판단 (NEW)"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # 도구 실행 결과가 있고, structured_data가 있으면 바로 종료
        if state.get("structured_data") is not None:
            print("[최적화] structured_data 존재 → 즉시 종료")
            return END
        
        # 도구 실행 결과가 텍스트로만 있어도 종료
        if hasattr(last_message, "content") and len(str(last_message.content)) > 50:
            print("[최적화] 충분한 답변 존재 → 즉시 종료")
            return END
        
        # 추가 도구 호출이 필요한 경우만 agent로 복귀
        return "agent"

    # 11. 그래프 구성
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("intent_classifier", intent_classifier_node)
    workflow.add_node("query_rewrite", query_rewrite_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node_with_structured_data)

    # 엣지 연결
    workflow.add_edge(START, "intent_classifier")
    workflow.add_edge("intent_classifier", "query_rewrite")
    workflow.add_edge("query_rewrite", "agent")
    workflow.add_conditional_edges("agent", should_continue, ["tools", END])
    workflow.add_conditional_edges("tools", should_continue_after_tools, ["agent", END])  # 수정

    # 12. 메모리 체크포인트
    memory = MemorySaver()

    # 13. 컴파일
    app = workflow.compile(checkpointer=memory)

    print("[LangGraph] 앱 생성 완료")
    print(f"  - 노드: intent_classifier → query_rewrite → agent ⇄ tools")
    print(f"  - 도구: {len(tools)}개")

    return app
