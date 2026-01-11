# -*- coding: utf-8 -*-
"""
행동요령 평가 (LLM 평가자 기반)
- GPT-4를 평가자로 사용
- 의미적 품질 평가
- 구조화된 피드백 제공
"""
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

from backend.app.services.langgraph_agent import create_langgraph_app
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import HumanMessage

# 재난별 참조 가이드라인 (평가 기준)
REFERENCE_GUIDELINES = {
    "earthquake": """
    지진 발생 시 행동요령:
    1. 실내: 책상이나 테이블 아래로 들어가 몸을 보호하세요
    2. 흔들림이 멈추면 가스와 전기를 차단하세요
    3. 문을 열어 출구를 확보하세요
    4. 실외: 건물과 떨어진 안전한 곳으로 대피하세요
    5. 엘리베이터 사용 금지, 계단 이용
    """,
    "fire": """
    화재 발생 시 행동요령:
    1. "불이야!" 크게 외치며 주변에 알리세요
    2. 낮은 자세로 코와 입을 막고 이동하세요
    3. 연기가 많으면 바닥으로 기어서 이동
    4. 소화기가 있으면 초기 진화 시도
    5. 119에 신고하고 안전한 곳으로 대피
    """,
    "flood": """
    홍수 발생 시 행동요령:
    1. 높은 곳으로 신속히 대피하세요
    2. 침수된 도로나 지하공간 진입 금지
    3. 전기/가스 차단 후 대피
    4. 물이 빠질 때까지 안전한 곳에 대기
    5. 교량이나 하천 근처 접근 금지
    """,
    "landslide": """
    산사태 발생 시 행동요령:
    1. 산에서 즉시 하산하세요
    2. 경사면과 수직 방향으로 대피
    3. 계곡이나 경사 아래 위치 피하기
    4. 안전한 고지대나 건물로 이동
    """,
    "tsunami": """
    쓰나미 발생 시 행동요령:
    1. 해안에서 최대한 멀리, 높은 곳으로 대피
    2. 지진 후 해안가에서 즉시 대피
    3. 쓰나미 경보 발령 시 즉각 대피
    4. 첫 파도가 지나가도 안심 금지 (여러 파도 올 수 있음)
    """,
    "storm": """
    폭풍 발생 시 행동요령:
    1. 실내로 대피하세요
    2. 창문에서 멀리 떨어지세요
    3. 야외 활동 중단
    4. 날아갈 수 있는 물건 고정
    """,
    "typhoon": """
    태풍 발생 시 행동요령:
    1. 외출 자제, 실내에 머무르세요
    2. 창문과 출입문을 잠그고 테이프로 보강
    3. 강풍에 날아갈 물건 실내로 이동
    4. 저지대, 해안가 접근 금지
    5. 태풍 눈이 지나가는 중에도 외출 금지
    """,
    "volcanic_ash": """
    화산재 발생 시 행동요령:
    1. 실내에 머무르고 창문을 닫으세요
    2. 외출 시 마스크 착용 필수
    3. 눈과 피부 보호
    4. 화산재가 가라앉을 때까지 대기
    """,
    "volcanic_eruption": """
    화산 폭발 시 행동요령:
    1. 화산에서 최대한 멀리 대피
    2. 용암 흐름 방향 반대로 이동
    3. 화산재로부터 호흡기 보호
    4. 낮은 지대 피하기 (가스 축적 위험)
    """,
    "wildfire": """
    산불 발생 시 행동요령:
    1. 바람을 등지고 대피
    2. 불길 반대 방향으로 신속히 이동
    3. 젖은 수건으로 코와 입 보호
    4. 119 신고
    """,
    "gas": """
    가스 누출 시 행동요령:
    1. 환기: 창문과 문을 즉시 열으세요
    2. 불꽃/전기 스위치 절대 금지
    3. 가스 밸브 잠그기
    4. 대피 후 119 신고
    """,
    "dam": """
    댐 붕괴 시 행동요령:
    1. 높은 곳으로 즉시 대피
    2. 하류 지역 신속히 벗어나기
    3. 라디오로 상황 확인
    """,
    "radiation": """
    방사능 누출 시 행동요령:
    1. 실내로 대피, 창문과 문 닫기
    2. 외부 공기 차단
    3. 요오드 복용 (당국 지시 시)
    4. 대피 지시 따르기
    """
}

class LLMEvaluator:
    """LLM 기반 응답 품질 평가자"""
    
    def __init__(self, model_name: str = "gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
    
    def evaluate_response(
        self, 
        query: str, 
        response: str, 
        expected_disaster: str
    ) -> Dict:
        """
        응답을 평가하고 구조화된 결과 반환
        
        Returns:
            {
                "total_score": 85,
                "relevance_score": 55,  # 관련성 (60점 만점)
                "quality_score": 18,     # 품질 (20점 만점)
                "purity_score": 12,      # 순수도 (20점 만점)
                "feedback": "상세 피드백...",
                "strengths": ["강점1", "강점2"],
                "weaknesses": ["약점1", "약점2"]
            }
        """
        reference = REFERENCE_GUIDELINES.get(
            expected_disaster.lower().replace(" ", "_"), 
            "해당 재난에 대한 참조 가이드라인이 없습니다."
        )
        
        evaluation_prompt = f"""당신은 재난 안전 교육 전문가입니다. 다음 응답을 평가해주세요.

**사용자 질문:**
{query}

**기대 재난 유형:**
{expected_disaster}

**참조 가이드라인 (정답 기준):**
{reference}

**실제 응답:**
{response}

---

다음 3가지 기준으로 평가하세요:

1. **관련성 (60점)**: 기대 재난의 행동요령이 얼마나 포함되었는가?
   - 핵심 행동요령 포함: 40-60점
   - 일부 관련 정보: 20-39점
   - 거의 무관: 0-19점

2. **품질 (20점)**: 내용이 얼마나 구체적이고 실용적인가?
   - 매우 구체적이고 실행 가능: 16-20점
   - 적절한 수준: 11-15점
   - 모호하거나 불충분: 0-10점

3. **순수도 (20점)**: 다른 재난 정보가 섞이지 않았는가?
   - 오염 없음: 16-20점
   - 약간의 관련 없는 내용: 11-15점
   - 심각한 오염 (다른 재난 가이드 혼입): 0-10점

**JSON 형식으로만 답변하세요:**
{{
  "relevance_score": 55,
  "quality_score": 18,
  "purity_score": 12,
  "total_score": 85,
  "feedback": "전체적인 평가 요약 (2-3문장)",
  "strengths": ["강점1", "강점2"],
  "weaknesses": ["약점1", "약점2"],
  "key_missing": ["누락된 핵심 정보1", "누락된 핵심 정보2"]
}}

추가 설명 없이 JSON만 출력하세요."""

        try:
            result = self.llm.invoke(evaluation_prompt)
            content = result.content.strip()
            
            # JSON 파싱 (마크다운 코드 블록 제거)
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            evaluation = json.loads(content)
            
            # 점수 검증
            evaluation["relevance_score"] = max(0, min(60, evaluation.get("relevance_score", 0)))
            evaluation["quality_score"] = max(0, min(20, evaluation.get("quality_score", 0)))
            evaluation["purity_score"] = max(0, min(20, evaluation.get("purity_score", 0)))
            evaluation["total_score"] = (
                evaluation["relevance_score"] + 
                evaluation["quality_score"] + 
                evaluation["purity_score"]
            )
            
            return evaluation
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 파싱 실패: {e}")
            print(f"응답 내용: {content[:200]}...")
            return {
                "total_score": 0,
                "relevance_score": 0,
                "quality_score": 0,
                "purity_score": 0,
                "feedback": "평가 실패 - JSON 파싱 오류",
                "strengths": [],
                "weaknesses": ["평가 시스템 오류"],
                "key_missing": [],
                "error": str(e)
            }
        except Exception as e:
            print(f"⚠️  평가 오류: {e}")
            return {
                "total_score": 0,
                "relevance_score": 0,
                "quality_score": 0,
                "purity_score": 0,
                "feedback": f"평가 실패: {str(e)}",
                "strengths": [],
                "weaknesses": ["평가 시스템 오류"],
                "key_missing": [],
                "error": str(e)
            }


def evaluate_with_llm(test_path: str, langgraph_app):
    """LLM 기반 행동요령 평가"""
    
    evaluator = LLMEvaluator()
    
    with open(test_path, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)
    
    results = {
        "total": len(test_cases),
        "excellent": 0,      # 90점 이상
        "good": 0,           # 70-89점
        "acceptable": 0,     # 50-69점
        "poor": 0,           # 50점 미만
        "avg_total_score": 0,
        "avg_relevance_score": 0,
        "avg_quality_score": 0,
        "avg_purity_score": 0,
        "details": []
    }
    
    total_scores = []
    relevance_scores = []
    quality_scores = []
    purity_scores = []
    
    for idx, case in enumerate(test_cases):
        query = case["query"]
        expected_disaster = case["expected_disaster_type"]
        
        print(f"\n{'='*70}")
        print(f"[테스트 {idx+1}/{len(test_cases)}] {query}")
        print(f"기대 재난: {expected_disaster}")
        print('='*70)
        
        try:
            # LangGraph 실행
            response = langgraph_app.invoke(
                {"messages": [HumanMessage(content=query)]},
                config={"configurable": {"thread_id": f"test_{idx}"}}
            )
            
            # 응답 추출
            response_text = ""
            if "messages" in response and response["messages"]:
                last_msg = response["messages"][-1]
                if hasattr(last_msg, 'content'):
                    response_text = last_msg.content
            
            print(f"\n📝 응답 길이: {len(response_text)} 자")
            print(f"📝 응답 미리보기: {response_text[:150]}...")
            
            # LLM 평가
            print("\n🤖 LLM 평가 중...")
            evaluation = evaluator.evaluate_response(
                query, 
                response_text, 
                expected_disaster
            )
            
            # 점수 집계
            total_score = evaluation["total_score"]
            total_scores.append(total_score)
            relevance_scores.append(evaluation["relevance_score"])
            quality_scores.append(evaluation["quality_score"])
            purity_scores.append(evaluation["purity_score"])
            
            # 등급 분류
            if total_score >= 90:
                results["excellent"] += 1
                grade = "🏆 우수"
            elif total_score >= 70:
                results["good"] += 1
                grade = "✅ 양호"
            elif total_score >= 50:
                results["acceptable"] += 1
                grade = "⚠️  보통"
            else:
                results["poor"] += 1
                grade = "❌ 미흡"
            
            # 결과 출력
            print(f"\n📊 평가 결과: {grade}")
            print(f"   총점: {total_score}/100")
            print(f"   - 관련성: {evaluation['relevance_score']}/60")
            print(f"   - 품질: {evaluation['quality_score']}/20")
            print(f"   - 순수도: {evaluation['purity_score']}/20")
            print(f"\n💬 피드백: {evaluation['feedback']}")
            
            if evaluation.get('strengths'):
                print(f"\n✨ 강점:")
                for strength in evaluation['strengths']:
                    print(f"   • {strength}")
            
            if evaluation.get('weaknesses'):
                print(f"\n⚠️  약점:")
                for weakness in evaluation['weaknesses']:
                    print(f"   • {weakness}")
            
            if evaluation.get('key_missing'):
                print(f"\n📌 누락된 핵심 정보:")
                for missing in evaluation['key_missing']:
                    print(f"   • {missing}")
            
            # 상세 결과 저장
            results["details"].append({
                "query": query,
                "expected_disaster": expected_disaster,
                "response": response_text,
                "response_preview": response_text[:300],
                "evaluation": evaluation,
                "grade": grade
            })
            
        except Exception as e:
            print(f"\n❌ 에러 발생: {e}")
            import traceback
            traceback.print_exc()
            
            results["poor"] += 1
            results["details"].append({
                "query": query,
                "expected_disaster": expected_disaster,
                "error": str(e),
                "evaluation": {
                    "total_score": 0,
                    "relevance_score": 0,
                    "quality_score": 0,
                    "purity_score": 0,
                    "feedback": f"시스템 오류: {str(e)}"
                },
                "grade": "❌ 오류"
            })
    
    # 평균 계산
    if total_scores:
        results["avg_total_score"] = round(sum(total_scores) / len(total_scores), 2)
        results["avg_relevance_score"] = round(sum(relevance_scores) / len(relevance_scores), 2)
        results["avg_quality_score"] = round(sum(quality_scores) / len(quality_scores), 2)
        results["avg_purity_score"] = round(sum(purity_scores) / len(purity_scores), 2)
    
    return results


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 LLM 기반 행동요령 평가 시스템")
    print("="*70)
    
    print("\n[1/3] 벡터스토어 로드 중...")
    vectorstore = Chroma(
        persist_directory=str(project_root / "chroma_db"),
        embedding_function=OpenAIEmbeddings()
    )
    print("✅ 벡터스토어 로드 완료")
    
    print("\n[2/3] LangGraph 앱 생성 중...")
    langgraph_app = create_langgraph_app(vectorstore)
    print("✅ LangGraph 앱 생성 완료")
    
    print("\n[3/3] 평가 시작...")
    test_path = project_root / "eval" / "guideline_test.json"
    results = evaluate_with_llm(str(test_path), langgraph_app)
    
    # 최종 결과 출력
    print("\n" + "="*70)
    print("📊 최종 평가 결과")
    print("="*70)
    print(f"총 테스트: {results['total']}개")
    print(f"\n등급별 분포:")
    print(f"  🏆 우수 (90-100점): {results['excellent']}개 ({results['excellent']/results['total']*100:.1f}%)")
    print(f"  ✅ 양호 (70-89점):  {results['good']}개 ({results['good']/results['total']*100:.1f}%)")
    print(f"  ⚠️  보통 (50-69점):  {results['acceptable']}개 ({results['acceptable']/results['total']*100:.1f}%)")
    print(f"  ❌ 미흡 (0-49점):   {results['poor']}개 ({results['poor']/results['total']*100:.1f}%)")
    print(f"\n평균 점수:")
    print(f"  총점:   {results['avg_total_score']:.2f}/100")
    print(f"  관련성: {results['avg_relevance_score']:.2f}/60")
    print(f"  품질:   {results['avg_quality_score']:.2f}/20")
    print(f"  순수도: {results['avg_purity_score']:.2f}/20")
    print("="*70)
    
    # 결과 저장
    output_path = project_root / "eval" / "guideline_results_llm.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 결과 저장 완료: {output_path}")
    print("\n💡 각 테스트 케이스의 상세 피드백이 JSON 파일에 저장되었습니다.")