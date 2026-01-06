# -*- coding: utf-8 -*-
"""
대피소 안내 챗봇 API 서버
FastAPI 기반 웹 API
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

# 프로젝트 루트 경로 설정
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# .env 파일 로드 (프로젝트 루트 기준)
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

# 백엔드 서비스 모듈 임포트
from backend.app.services.data_loaders import load_shelter_csv, load_all_disaster_jsons
from backend.app.services.documents import csv_to_documents, json_to_documents
from backend.app.services.embedding_and_vectordb import create_embeddings_and_vectordb
from backend.app.services.langgraph_agent import create_langgraph_app, create_hybrid_retrievers

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import HumanMessage
import pandas as pd


# -----------------------------------------------------------------------------
# 경로 설정
# -----------------------------------------------------------------------------
DATA_DIR = project_root / "data"
CHROMA_DB_DIR = project_root / "chroma_db"

print(f"[경로] 프로젝트 루트: {project_root}")
print(f"[경로] 데이터 디렉토리: {DATA_DIR}")
print(f"[경로] Chroma DB: {CHROMA_DB_DIR}")


# -----------------------------------------------------------------------------
# Pydantic 모델 정의
# -----------------------------------------------------------------------------

class LocationExtractRequest(BaseModel):
    query: str


class LocationExtractResponse(BaseModel):
    success: bool
    location: Optional[str] = None
    coordinates: Optional[tuple] = None
    shelters: List[Dict] = []
    total_count: int = 0
    message: str = ""


class ChatbotRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatbotResponse(BaseModel):
    response: str
    session_id: str


# -----------------------------------------------------------------------------
# FastAPI Lifespan
# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 실행되는 초기화 작업"""
    global vectorstore, shelter_df, embeddings
    global shelter_hybrid_retriever, guideline_hybrid_retriever, langgraph_app

    # OpenAI 임베딩 초기화
    try:
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", 
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        print("[lifespan] 임베딩 모델 초기화 성공")
    except Exception as e:
        embeddings = None
        print(f"[lifespan] 임베딩 모델 초기화 실패: {e}")

    # 벡터 DB 로드
    try:
        vectorstore = Chroma(
            collection_name="shelter_and_disaster_guidelines",
            embedding_function=embeddings,
            persist_directory=str(CHROMA_DB_DIR),
        )
        print("[lifespan] 벡터DB 로드 성공")
    except Exception as e:
        vectorstore = None
        print(f"[lifespan] 벡터DB 로드 실패: {e}")

    # 대피소 데이터 로드 (절대 경로 사용)
    try:
        shelter_csv_path = DATA_DIR / "shelter.csv"
        print(f"[lifespan] 대피소 CSV 경로: {shelter_csv_path}")
        
        shelter_data = load_shelter_csv("shelter.csv", data_dir=str(DATA_DIR))
        shelter_df = pd.DataFrame(shelter_data)
        print(f"[lifespan] 대피소 데이터 로드 성공: {len(shelter_df)}개")
    except Exception as e:
        shelter_df = None
        print(f"[lifespan] 대피소 데이터 로드 실패: {e}")
        import traceback
        traceback.print_exc()

    # LangGraph 초기화
    try:
        shelter_hybrid_retriever, guideline_hybrid_retriever = create_hybrid_retrievers(vectorstore)
        langgraph_app = create_langgraph_app(vectorstore)
        print("[lifespan] LangGraph Agent 초기화 완료")
    except Exception as e:
        shelter_hybrid_retriever = None
        guideline_hybrid_retriever = None
        langgraph_app = None
        print(f"[lifespan] LangGraph 초기화 실패: {e}")
        import traceback
        traceback.print_exc()

    yield  # 애플리케이션 실행 중

    # 종료 시 정리 작업


# FastAPI 앱 생성
app = FastAPI(
    title="재난 대피 챗봇 API",
    description="RAG 기반 재난 대피 정보 제공 시스템",
    version="1.0.0",
    lifespan=lifespan
)

# 전역 변수
vectorstore = None
shelter_df = None
embeddings = None
shelter_hybrid_retriever = None
guideline_hybrid_retriever = None
langgraph_app = None


# -----------------------------------------------------------------------------
# CORS 설정
# -----------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    # allow_origins=[
    #     "http://localhost:8000",
    #     "http://127.0.0.1:8000",
    # ],
    allow_origins=["*"],  # 2026-01-06: 외부 IP 접근 허용을 위해 모든 오리진 허용으로 변경
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# API 엔드포인트
# -----------------------------------------------------------------------------

@app.get("/")
async def read_root():
    """루트 엔드포인트"""
    return {
        "message": "재난 대피 챗봇 API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "ok",
        "vectorstore_ready": vectorstore is not None,
        "shelter_data_ready": shelter_df is not None,
    }


@app.get("/api/status")
async def get_api_status():
    """상세 상태 확인"""
    openai_available = bool(os.getenv("OPENAI_API_KEY"))

    return {
        "server_ready": True,
        "llm_available": openai_available,
        "vectorstore_ready": vectorstore is not None,
        "total_shelters": len(shelter_df) if shelter_df is not None else 0,
        "shelter_data_ready": shelter_df is not None,
    }


@app.post("/api/location/extract")
async def extract_location(request: LocationExtractRequest = Body(...)):
    """
    LangGraph Agent 기반 통합 검색
    기존 main.py의 로직 그대로 사용
    """
    if langgraph_app is None:
        return LocationExtractResponse(
            success=False, 
            message="서버 초기화가 완료되지 않았습니다."
        )

    query = request.query.strip()
    if not query:
        return LocationExtractResponse(
            success=False, 
            message="입력 문장이 비어 있습니다."
        )

    print(f"[API] 사용자 쿼리: '{query}'")

    try:
        session_id = f"session_{hash(query) % 100000}"
        config = {"configurable": {"thread_id": session_id}}

        result = langgraph_app.invoke(
            {"messages": [HumanMessage(content=query)]}, 
            config=config
        )

        final_message = result["messages"][-1]
        structured_data = result.get("structured_data", None)

        if structured_data:
            print(f"[INFO] 구조화된 응답 반환 (좌표 포함)")
            return LocationExtractResponse(
                success=True,
                location=structured_data.get("location"),
                coordinates=structured_data.get("coordinates"),
                shelters=structured_data.get("shelters", []),
                total_count=structured_data.get("total_count", 0),
                message=final_message.content,
            )
        else:
            print(f"[INFO] 텍스트 응답 반환")
            return LocationExtractResponse(
                success=True,
                location=None,
                coordinates=None,
                shelters=[],
                total_count=0,
                message=final_message.content,
            )

    except Exception as e:
        print(f"[ERROR] LangGraph Agent 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return LocationExtractResponse(
            success=False,
            message="처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )


@app.get("/api/shelters/nearest")
async def get_nearest_shelters(lat: float, lon: float, k: int = 5):
    """
    현위치 기준 가장 가까운 대피소 검색
    기존 main.py의 로직 그대로 사용
    """
    print(f"[API] get_nearest_shelters 호출: lat={lat}, lon={lon}, k={k}")
    
    import math

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    if vectorstore is None:
        if shelter_df is None:
            return {
                "user_location": {"lat": lat, "lon": lon},
                "shelters": [],
                "total_count": 0,
            }

        shelters = []
        for _, row in shelter_df.iterrows():
            s_lat = row.get("위도(EPSG4326)")
            s_lon = row.get("경도(EPSG4326)")

            if s_lat is not None and s_lon is not None:
                try:
                    s_lat = float(s_lat)
                    s_lon = float(s_lon)
                    distance = haversine(lat, lon, s_lat, s_lon)

                    shelters.append({
                        "name": row.get("시설명", "N/A"),
                        "address": row.get("도로명전체주소", "N/A"),
                        "lat": s_lat,
                        "lon": s_lon,
                        "capacity": int(row.get("최대수용인원", 0)) if pd.notna(row.get("최대수용인원")) else 0,
                        "distance": distance,
                    })
                except Exception:
                    continue

        shelters.sort(key=lambda x: x["distance"])
        top_shelters = shelters[:k]

        return {
            "user_location": {"lat": lat, "lon": lon},
            "shelters": top_shelters,
            "total_count": len(top_shelters),
        }

    try:
        all_data = vectorstore.get(where={"type": "shelter"})
        all_metadatas = all_data.get("metadatas", [])

        shelters = []
        for metadata in all_metadatas:
            if metadata.get("type") != "shelter":
                continue

            s_lat = metadata.get("lat")
            s_lon = metadata.get("lon")

            if s_lat is not None and s_lon is not None:
                try:
                    s_lat = float(s_lat)
                    s_lon = float(s_lon)
                    distance = haversine(lat, lon, s_lat, s_lon)

                    shelter_info = {
                        "name": metadata.get("facility_name", "N/A"),
                        "address": metadata.get("address", "N/A"),
                        "lat": s_lat,
                        "lon": s_lon,
                        "capacity": int(metadata.get("capacity", 0)),
                        "distance": distance,
                    }
                    shelters.append(shelter_info)

                except (ValueError, TypeError) as e:
                    continue

        shelters.sort(key=lambda x: x["distance"])
        top_shelters = shelters[:k]

        return {
            "user_location": {"lat": lat, "lon": lon},
            "shelters": top_shelters,
            "total_count": len(top_shelters),
        }

    except Exception as e:
        print(f"[ERROR] VectorStore 사용 중 오류: {e}")
        return {
            "user_location": {"lat": lat, "lon": lon},
            "shelters": [],
            "total_count": 0,
        }


@app.post("/api/chatbot", response_model=ChatbotResponse)
async def chatbot_endpoint(request: ChatbotRequest):
    """
    LangGraph Agent 기반 챗봇
    기존 main.py의 로직 그대로 사용
    """
    try:
        if langgraph_app is None:
            raise HTTPException(
                status_code=503,
                detail="챗봇 시스템이 초기화되지 않았습니다."
            )

        config = {"configurable": {"thread_id": request.session_id}}

        result = langgraph_app.invoke(
            {"messages": [HumanMessage(content=request.message)]}, 
            config=config
        )

        bot_response = result["messages"][-1].content

        return ChatbotResponse(
            response=bot_response, 
            session_id=request.session_id
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 챗봇 오류: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"챗봇 처리 중 오류가 발생했습니다: {str(e)}"
        )


# -----------------------------------------------------------------------------
# 서버 실행
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )