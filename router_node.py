# -*- coding: utf-8 -*-
"""
LLM 기반 라우터 노드 모듈
파일 타입과 내용을 분석하여 적절한 노드로 자동 라우팅
"""
import os
import sys
import tempfile
import re
from typing import TypedDict, List, Optional, Literal
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader

# Windows 환경에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass


class RouterState(TypedDict):
    """라우터 상태 정의"""
    user_query: str                    # 사용자 질의
    uploaded_files: dict               # 업로드된 파일 딕셔너리 (타입별)
    file_type: Optional[str]           # 파일 타입 (csv, pdf, docx)
    file_content: Optional[str]        # 추출된 파일 내용 (PDF/DOCX만)
    routed_node: Optional[str]         # 라우팅된 노드 타입
    messages: List[BaseMessage]        # 메시지 기록
    has_email: bool                    # 이메일 주소 존재 여부


def detect_email(text: str, verbose: bool = False) -> Optional[str]:
    """
    텍스트에서 이메일 주소 감지
    
    Args:
        text: 검색할 텍스트
        verbose: 상세 로그 출력 여부
        
    Returns:
        이메일 주소가 있으면 이메일 주소, 없으면 None
    """
    # 이메일 주소 정규식 패턴 (한글과 영문이 섞인 경우도 고려)
    # 단어 경계 대신 공백이나 특수문자, 한글 등을 경계로 사용
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    matches = re.findall(email_pattern, text)
    
    if matches:
        if verbose:
            print(f"🔍 이메일 감지됨: {matches}")
        return matches[0]  # 첫 번째 이메일 주소 반환
    return None


def extract_file_content(file_obj, file_type: str) -> str:
    """
    파일 객체에서 텍스트 내용 추출
    
    Args:
        file_obj: Streamlit file_uploader 객체 또는 파일 경로
        file_type: 파일 타입 ('pdf' 또는 'docx')
        
    Returns:
        추출된 텍스트 내용
    """
    temp_path = None
    try:
        # Streamlit file_uploader 객체인 경우 임시 파일로 저장
        if hasattr(file_obj, 'read') or hasattr(file_obj, 'getvalue'):
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as tmp_file:
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                file_data = file_obj.getvalue() if hasattr(file_obj, 'getvalue') else file_obj.read()
                tmp_file.write(file_data)
                temp_path = tmp_file.name
                file_path = temp_path
        else:
            # 문자열 경로인 경우
            file_path = file_obj
        
        # 파일 타입에 따라 로더 선택
        if file_type == "pdf":
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            # 첫 몇 페이지만 추출 (LLM 토큰 제한 고려)
            content = "\n".join([doc.page_content for doc in docs[:10]])  # 최대 10페이지
            if len(docs) > 10:
                content += f"\n\n... (총 {len(docs)}페이지 중 처음 10페이지만 표시)"
        
        elif file_type == "docx":
            loader = Docx2txtLoader(file_path)
            docs = loader.load()
            # 전체 내용 추출 (DOCX는 보통 크기가 작음)
            content = "\n".join([doc.page_content for doc in docs])
        
        else:
            content = ""
        
        return content
        
    except Exception as e:
        return f"파일 내용 추출 중 오류 발생: {str(e)}"
    
    finally:
        # 임시 파일 정리
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


def check_file_type_node(state: RouterState) -> RouterState:
    """
    파일 타입 확인 노드
    CSV 파일이 있으면 바로 business_plan으로 라우팅
    파일이 없고 이메일이 있으면 email로 라우팅
    """
    uploaded_files = state.get("uploaded_files", {})
    user_query = state.get("user_query", "")
    
    # 파일이 없는 경우 이메일 체크
    if not any([uploaded_files.get("csv"), uploaded_files.get("pdf"), uploaded_files.get("docx")]):
        email_address = detect_email(user_query, verbose=False)
        if email_address:
            return {
                **state,
                "file_type": None,
                "has_email": True,
                "routed_node": "email"
            }
        else:
            # 파일도 없고 이메일도 없으면 특수 노드로 라우팅 (파일 요청)
            return {
                **state,
                "file_type": None,
                "has_email": False,
                "routed_node": "no_file_no_email"
            }
    
    # CSV 파일이 있으면 바로 business_plan으로 라우팅
    if uploaded_files.get("csv"):
        return {
            **state,
            "file_type": "csv",
            "routed_node": "business_plan",
            "has_email": False
        }
    
    # PDF 또는 DOCX 파일이 있으면 내용 추출 필요
    if uploaded_files.get("pdf"):
        return {
            **state,
            "file_type": "pdf",
            "has_email": False
        }
    
    if uploaded_files.get("docx"):
        return {
            **state,
            "file_type": "docx",
            "has_email": False
        }
    
    # 파일이 없으면 LLM이 사용자 질의만으로 판단하도록 진행
    return {
        **state,
        "file_type": None,
        "has_email": False
    }


def extract_content_node(state: RouterState) -> RouterState:
    """
    PDF/DOCX 파일 내용 추출 노드
    """
    file_type = state.get("file_type")
    uploaded_files = state.get("uploaded_files", {})
    
    if file_type not in ["pdf", "docx"]:
        return state
    
    # 첫 번째 파일만 사용 (여러 파일이 있을 경우)
    files = uploaded_files.get(file_type, [])
    if not files:
        return {
            **state,
            "file_content": ""
        }
    
    file_obj = files[0] if isinstance(files, list) else files
    
    # 파일 포인터 리셋 (이미 읽었을 수 있음)
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
    
    # 파일 내용 추출
    file_content = extract_file_content(file_obj, file_type)
    
    return {
        **state,
        "file_content": file_content
    }


def llm_router_node(state: RouterState) -> RouterState:
    """
    LLM 기반 라우팅 노드
    파일 내용과 사용자 질의를 분석하여 적절한 노드로 라우팅
    """
    user_query = state.get("user_query", "")
    file_type = state.get("file_type")
    file_content = state.get("file_content", "")
    
    # LLM 초기화
    llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
    
    # 파일 내용 처리
    if not file_content or file_content.startswith("파일 내용 추출 중 오류"):
        # 파일 내용이 없거나 오류인 경우 사용자 질의만으로 판단
        content_section = "파일 내용을 추출할 수 없습니다. 사용자 질의만으로 판단하세요."
    else:
        # 파일 내용 길이 제한 (토큰 제한 고려)
        content_preview = file_content[:5000] if len(file_content) > 5000 else file_content
        content_truncated = len(file_content) > 5000
        content_section = f"""{content_preview}
{'... (내용이 길어 일부만 표시됨)' if content_truncated else ''}"""
    
    # 라우팅 프롬프트
    routing_prompt = f"""당신은 문서 분류 전문가입니다. 주어진 사용자 질의와 파일 내용을 분석하여 적절한 처리 노드를 선택해야 합니다.

사용 가능한 노드 타입:
1. "business_plan": 경영계획 분석 (재무/경영/예산/매출/원가 관련 데이터 분석)
2. "market_research": 시장조사 
   - 다음 키워드나 내용이 포함된 경우: 시장, 경쟁, IR, refractory, 조사, 시장동향, 경쟁사, 마케팅
   - 경쟁사 IR 자료, 시장 동향 분석, 경쟁 분석 등
3. "meeting_docx": 회의록 검색
   - 회의록, 주간회의, 임원회의, 안전이슈, 회의 안건 등
4. "strategy_plan": 전략 로드맵 수립
   - 로드맵, 3개년, 전략 로드맵, 중장기 전략 등

파일 타입: {file_type}

사용자 질의:
{user_query}

파일 내용:
{content_section}

중요: 파일 내용과 사용자 질의를 종합적으로 분석하여 가장 적절한 노드를 선택하세요.
- 시장, 경쟁사, IR, refractory, 마케팅 관련 내용이 주로 다뤄지면 "market_research"
- 회의록, 안전이슈, 회의 관련 내용이면 "meeting_docx"
- 전략, 로드맵, 3개년 계획 관련이면 "strategy_plan"
- 파일 내용이 없는 경우 사용자 질의만으로 판단하세요.

출력 형식 (JSON만): {{"routed_node": "노드타입"}}
절대 다른 텍스트나 설명을 출력하지 마세요. JSON 형식만 출력하세요."""

    # JSON 파서
    parser = JsonOutputParser()
    chain = llm | parser
    
    try:
        result = chain.invoke(routing_prompt)
        routed_node = result.get("routed_node", "market_research")
        
        return {
            **state,
            "routed_node": routed_node
        }
    except Exception as e:
        # 오류 발생 시 기본값 사용
        return {
            **state,
            "routed_node": "market_research"
        }


def create_router_chain(api_key: str = None, verbose: bool = False):
    """
    LLM 기반 라우터 체인 생성 (LangGraph 사용)
    
    Args:
        api_key: OpenAI API 키
        verbose: 상세 로그 출력 여부
        
    Returns:
        라우터 체인 객체 (함수)
    """
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    
    # LangGraph 워크플로우 구성
    workflow = StateGraph(RouterState)
    
    # 노드 추가
    workflow.add_node("check_file_type", check_file_type_node)
    workflow.add_node("extract_content", extract_content_node)
    workflow.add_node("llm_router", llm_router_node)
    
    # 시작 노드
    workflow.add_edge(START, "check_file_type")
    
    # 조건부 분기: CSV면 바로 종료, 이메일이면 바로 종료, 아니면 내용 추출 또는 LLM 라우팅
    def route_after_check(state: RouterState) -> str:
        routed_node = state.get("routed_node")
        file_type = state.get("file_type")
        
        # CSV 파일이면 바로 종료
        if routed_node == "business_plan" or file_type == "csv":
            return "end"
        
        # 이메일 노드로 라우팅
        if routed_node == "email":
            return "end"
        
        # 파일이 없고 이메일도 없으면 종료 (파일 요청 메시지)
        if routed_node == "no_file_no_email":
            return "end"
        
        # PDF/DOCX면 내용 추출 후 LLM 라우팅
        if file_type in ["pdf", "docx"]:
            return "extract"
        
        # 파일이 없으면 사용자 질의만으로 LLM 라우팅
        return "llm_route"
    
    workflow.add_conditional_edges(
        "check_file_type",
        route_after_check,
        {
            "end": END,
            "extract": "extract_content",
            "llm_route": "llm_router"
        }
    )
    
    # 내용 추출 후 LLM 라우팅
    workflow.add_edge("extract_content", "llm_router")
    workflow.add_edge("llm_router", END)
    
    # 그래프 컴파일
    app = workflow.compile()
    
    # 래퍼 함수
    def route_query_with_llm(user_query: str, uploaded_files: dict) -> str:
        """
        LLM 기반 라우팅 함수
        
        Args:
            user_query: 사용자 질의
            uploaded_files: 업로드된 파일 딕셔너리
            
        Returns:
            라우팅된 노드 타입
        """
        try:
            # CSV 파일 체크 (간단한 케이스)
            if uploaded_files.get("csv"):
                if verbose:
                    print("✅ CSV 파일 감지 -> business_plan 노드로 라우팅")
                return "business_plan"
            
            # 파일이 없는 경우 이메일 체크 (우선 처리)
            if not any([uploaded_files.get("csv"), uploaded_files.get("pdf"), uploaded_files.get("docx")]):
                email_address = detect_email(user_query, verbose=verbose)
                if email_address:
                    if verbose:
                        print(f"✅ 이메일 감지 ({email_address}) -> email 노드로 라우팅")
                    return "email"
                else:
                    if verbose:
                        print("⚠️ 파일도 없고 이메일도 없음 -> no_file_no_email 노드로 라우팅")
                    return "no_file_no_email"
            
            # PDF/DOCX 파일이 있는 경우 LangGraph 실행
            # 파일이 없어도 사용자 질의만으로 라우팅 가능
            result = app.invoke({
                "user_query": user_query,
                "uploaded_files": uploaded_files,
                "file_type": None,
                "file_content": None,
                "routed_node": None,
                "messages": [],
                "has_email": False
            })
            
            routed_node = result.get("routed_node", "market_research")
            
            if verbose:
                print(f"✅ LLM 라우팅 결과: {routed_node}")
            
            return routed_node
            
        except Exception as e:
            if verbose:
                print(f"❌ 라우팅 오류: {str(e)}")
                import traceback
                traceback.print_exc()
            # 오류 발생 시 기본값 반환
            return "market_research"
    
    return route_query_with_llm


# 직접 실행 시 (테스트용)
if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv()
    
    router = create_router_chain(verbose=True)
    
    # 테스트 케이스
    test_cases = [
        {
            "query": "시장 동향을 분석해줘",
            "files": {"pdf": ["test.pdf"]}  # 실제 파일 경로 필요
        },
        {
            "query": "이번주 안전이슈는?",
            "files": {"docx": ["test.docx"]}
        }
    ]
    
    print("라우터 테스트 시작...")
    for test in test_cases:
        result = router(test["query"], test["files"])
        print(f"질의: {test['query']} -> 노드: {result}")

