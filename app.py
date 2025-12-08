# -*- coding: utf-8 -*-
"""
조건 분기 랭그래프 스트림릿 앱
사용자의 질의 내용, 입력 자료에 따라 1~4 노드로 분기하여 처리

실행 방법:
    streamlit run streamlit_app.py
"""
import os
import sys
import io
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from business_plan_node import create_business_plan_chain
from meeting_docx_node import create_meeting_docx_chain
from market_research_node import create_market_research_chain
from strategy_plan_node import create_strategy_plan_chain
from router_node import create_router_chain

if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

load_dotenv()

경영계획_path = Path(__file__).parent / "경영계획"
if str(경영계획_path) not in sys.path:
    sys.path.insert(0, str(경영계획_path))

# 페이지 설정
st.set_page_config(
    page_title="조건 분기 랭그래프 시스템",
    page_icon="🔄",
    layout="wide"
)

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "node_chain" not in st.session_state:
    st.session_state.node_chain = None
if "router" not in st.session_state:
    st.session_state.router = None

# 노드 타입 정의
NODE_TYPES = {
    "business_plan": {
        "name": "1. 경영계획 분석",
        "description": "경영계획 CSV 파일을 분석합니다",
        "input_type": ["csv"],
        "file_desc": "경영계획 CSV 파일",
        "example": "2025년 경비에서 가장 큰 항목은?"
    },
    "market_research": {
        "name": "2. 시장조사",
        "description": "Refractory Window PDF, 경쟁사 IR PDF 파일 및 Tavily 웹 검색 데이터를 분석합니다",
        "input_type": ["pdf"],
        "file_desc": "PDF 파일 (Refractory Window, 경쟁사 IR 등)",
        "example": "시장 동향을 분석해줘"
    },
    "meeting_docx": {
        "name": "3. 회의록 검색",
        "description": "주간회의록, 임원회의 자료 Word 파일을 검색합니다",
        "input_type": ["docx"],
        "file_desc": "회의록 Word 파일 (.docx)",
        "example": "이번주 안전이슈는 어떤게 있어?"
    },
    "strategy_plan": {
        "name": "5. 전략 로드맵 수립",
        "description": "PDF 파일에서 전략을 추출하고 웹 검색을 통해 3개년 로드맵을 수립합니다",
        "input_type": ["pdf"],
        "file_desc": "전략 PDF 파일",
        "example": "3개년 전략 로드맵 수립해줘"
    }
}

def route_query(user_query: str, uploaded_files: dict) -> str:
    """
    LLM 기반 라우팅 함수
    사용자 질의와 입력 자료를 분석하여 적절한 노드로 자동 라우팅
    
    Args:
        user_query: 사용자 질의 내용
        uploaded_files: 업로드된 파일 딕셔너리 (타입별로 분류된 파일 리스트)
        
    Returns:
        라우팅된 노드 타입 문자열
    """
    # 라우터가 초기화되어 있으면 사용
    if st.session_state.router:
        return st.session_state.router(user_query, uploaded_files)
    
    # 라우터가 없으면 기본값 반환
    return "market_research"

# 노드 초기화 함수들 (각 노드 모듈의 함수 호출)
def initialize_business_plan_node(csv_file_path: str, api_key: str):
    """경영계획 분석 노드 초기화"""
    try:
        chain, df_data = create_business_plan_chain(csv_file_path, api_key, verbose=False)
        return chain, df_data
    except Exception as e:
        st.error(f"❌ 경영계획 노드 초기화 실패: {str(e)}")
        return None, None


def initialize_meeting_docx_node(docx_files: list, api_key: str):
    """회의록 검색 노드 초기화"""
    try:
        chain = create_meeting_docx_chain(docx_files, api_key, verbose=False)
        return chain
    except Exception as e:
        st.error(f"❌ 회의록 노드 초기화 실패: {str(e)}")
        return None


def initialize_market_research_node(pdf_files: list, api_key: str):
    """시장조사 노드 초기화"""
    try:
        chain = create_market_research_chain(pdf_files, api_key, verbose=False)
        return chain
    except NotImplementedError:
        st.info("⚠️ 시장조사 노드는 아직 구현 중입니다.")
        return None
    except Exception as e:
        st.error(f"❌ 시장조사 노드 초기화 실패: {str(e)}")
        return None


def initialize_strategy_plan_node(pdf_file_path: str, api_key: str, tavily_api_key: str = None):
    """전략 로드맵 수립 노드 초기화"""
    try:
        chain = create_strategy_plan_chain(
            pdf_file_path=pdf_file_path,
            api_key=api_key,
            tavily_api_key=tavily_api_key,
            save_word_file=False,
            verbose=False
        )
        return chain
    except Exception as e:
        st.error(f"❌ 전략 로드맵 노드 초기화 실패: {str(e)}")
        return None


api_key = os.environ.get("OPENAI_API_KEY", "")
tavily_api_key = os.environ.get("TAVILY_API_KEY", "")

if api_key:
    os.environ["OPENAI_API_KEY"] = api_key
    # 라우터 초기화 (LLM 기반)
    if st.session_state.router is None:
        st.session_state.router = create_router_chain(api_key=api_key, verbose=True)
else:
    st.warning("⚠️ OpenAI API Key가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 설정해주세요.")

if tavily_api_key:
    os.environ["TAVILY_API_KEY"] = tavily_api_key
else:
    st.info("💡 Tavily API Key가 설정되지 않았습니다. 전략 로드맵 수립 기능을 사용하려면 .env 파일에 TAVILY_API_KEY를 설정해주세요.")

# 메인 UI
st.title("🔄 조건 분기 랭그래프 시스템")
st.markdown("**사용자의 질의 내용과 입력 자료에 따라 적절한 노드로 자동 분기하여 분석합니다**")

# 초기화 버튼
col1, col2 = st.columns([5, 1])
with col1:
    st.write("")  # 공간
with col2:
    if st.button("🔄 초기화", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.session_state.node_chain = None
        st.session_state.uploaded_files = {}
        st.session_state.router = None
        st.rerun()

st.markdown("---")

# 파일 업로드 섹션 (통합)
st.subheader("📁 입력 자료 업로드")
uploaded_files = st.file_uploader(
    "파일을 업로드하세요 (CSV, PDF, DOCX 모두 가능, 복수 파일 선택 가능)",
    type=["csv", "pdf", "docx"],
    accept_multiple_files=True,
    help="경영계획(CSV), 시장조사(PDF), 회의록/전략보고서(DOCX) 파일을 업로드할 수 있습니다"
)

# 업로드된 파일을 타입별로 분류하여 저장
if uploaded_files:
    st.session_state.uploaded_files = {}
    for file in uploaded_files:
        file_ext = file.name.split('.')[-1].lower()
        if file_ext == "csv":
            if "csv" not in st.session_state.uploaded_files:
                st.session_state.uploaded_files["csv"] = []
            st.session_state.uploaded_files["csv"].append(file)
        elif file_ext == "pdf":
            if "pdf" not in st.session_state.uploaded_files:
                st.session_state.uploaded_files["pdf"] = []
            st.session_state.uploaded_files["pdf"].append(file)
        elif file_ext == "docx":
            if "docx" not in st.session_state.uploaded_files:
                st.session_state.uploaded_files["docx"] = []
            st.session_state.uploaded_files["docx"].append(file)
else:
    st.session_state.uploaded_files = {}

# 업로드된 파일 정보 표시
if st.session_state.uploaded_files:
    st.markdown("---")
    with st.expander("📎 업로드된 파일 정보", expanded=False):
        for file_type, files in st.session_state.uploaded_files.items():
            if isinstance(files, list):
                for f in files:
                    file_size = len(f.getvalue() if hasattr(f, 'getvalue') else f.read()) / 1024  # KB
                    st.write(f"  • **{file_type.upper()}**: {f.name if hasattr(f, 'name') else str(f)} ({file_size:.2f} KB)")
                    if hasattr(f, 'seek'):
                        f.seek(0)  # 파일 포인터 리셋
            else:
                file_size = len(files.getvalue() if hasattr(files, 'getvalue') else files.read()) / 1024  # KB
                st.write(f"  • **{file_type.upper()}**: {files.name if hasattr(files, 'name') else str(files)} ({file_size:.2f} KB)")
                if hasattr(files, 'seek'):
                    files.seek(0)  # 파일 포인터 리셋

st.markdown("---")

# 질의 입력 및 처리
st.subheader("💬 질의 입력")

# 채팅 인터페이스
if st.session_state.messages:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("질문을 입력하세요..."):
    if not api_key:
        st.error("❌ API Key를 먼저 입력해주세요.")
        st.stop()
    
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 노드 라우팅 (자동 선택)
    routed_node = route_query(prompt, st.session_state.uploaded_files)
    
    with st.chat_message("assistant"):
        with st.spinner(f"⏳ {NODE_TYPES.get(routed_node, {}).get('name', '노드')} 처리 중..."):
            try:
                result = None
                temp_files = []
                graph_created = False
                
                # 노드별 처리
                if routed_node == "business_plan":
                    csv_files = st.session_state.uploaded_files.get("csv", [])
                    if not csv_files:
                        result = "❌ 경영계획 분석을 위해서는 CSV 파일이 필요합니다."
                    else:
                        # 첫 번째 CSV 파일 사용 (여러 파일이 있을 경우 첫 번째만)
                        csv_file = csv_files[0] if isinstance(csv_files, list) else csv_files
                        # 임시 파일로 저장
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
                            # 파일 포인터를 처음으로 이동
                            if hasattr(csv_file, 'seek'):
                                csv_file.seek(0)
                            file_data = csv_file.getvalue() if hasattr(csv_file, 'getvalue') else csv_file.read()
                            tmp_file.write(file_data)
                            tmp_csv_path = tmp_file.name
                            temp_files.append(tmp_csv_path)
                        
                        chain, df_data = initialize_business_plan_node(tmp_csv_path, api_key)
                        if chain:
                            result = chain.invoke({"question": prompt})
                            # 그래프 확인
                            if os.path.exists("temp_plot.png"):
                                graph_created = True
                                temp_files.append("temp_plot.png")
                        else:
                            result = "❌ 경영계획 노드 초기화에 실패했습니다."
                
                elif routed_node == "meeting_docx":
                    docx_files = st.session_state.uploaded_files.get("docx", [])
                    if not docx_files:
                        result = "❌ 회의록 검색을 위해서는 Word 파일이 필요합니다."
                    else:
                        # 여러 파일 지원 - 이미 리스트로 저장되어 있음
                        # 업로드된 파일을 임시 파일로 저장
                        temp_docx_paths = []
                        for docx_file in docx_files:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
                                # 파일 포인터를 처음으로 이동
                                if hasattr(docx_file, 'seek'):
                                    docx_file.seek(0)
                                file_data = docx_file.getvalue() if hasattr(docx_file, 'getvalue') else docx_file.read()
                                tmp_file.write(file_data)
                                temp_docx_paths.append(tmp_file.name)
                                temp_files.append(tmp_file.name)
                        
                        chain = initialize_meeting_docx_node(temp_docx_paths, api_key)
                        if chain:
                            result = chain.invoke({"question": prompt})
                        else:
                            result = "❌ 회의록 노드 초기화에 실패했습니다."
                
                elif routed_node == "market_research":
                    pdf_files = st.session_state.uploaded_files.get("pdf", [])
                    if not pdf_files:
                        result = "❌ 시장조사 분석을 위해서는 PDF 파일이 필요합니다."
                    else:
                        chain = initialize_market_research_node(pdf_files, api_key)
                        if chain:
                            result = chain.invoke({"question": prompt})
                        else:
                            result = "⚠️ 시장조사 노드는 아직 구현 중입니다."
                
                elif routed_node == "strategy_plan":
                    pdf_files = st.session_state.uploaded_files.get("pdf", [])
                    if not pdf_files:
                        result = "❌ 전략 로드맵 수립을 위해서는 PDF 파일이 필요합니다."
                    elif not tavily_api_key:
                        result = "❌ 전략 로드맵 수립을 위해서는 Tavily API Key가 필요합니다."
                    else:
                        # 첫 번째 PDF 파일 사용
                        pdf_file = pdf_files[0] if isinstance(pdf_files, list) else pdf_files
                        # 임시 파일로 저장
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            # 파일 포인터를 처음으로 이동
                            if hasattr(pdf_file, 'seek'):
                                pdf_file.seek(0)
                            file_data = pdf_file.getvalue() if hasattr(pdf_file, 'getvalue') else pdf_file.read()
                            tmp_file.write(file_data)
                            tmp_pdf_path = tmp_file.name
                            temp_files.append(tmp_pdf_path)
                        
                        chain = initialize_strategy_plan_node(tmp_pdf_path, api_key, tavily_api_key)
                        if chain:
                            result = chain.invoke({"question": prompt})
                        else:
                            result = "❌ 전략 로드맵 노드 초기화에 실패했습니다."
                
                else:
                    result = "❌ 적절한 노드를 찾을 수 없습니다. 질의 내용이나 파일 타입을 확인해주세요."
                
                # 결과 표시
                if result:
                    st.markdown(result)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": result,
                        "graph": graph_created
                    })
                    
                    # 사용된 노드 정보 표시
                    st.caption(f"📍 사용된 노드: {NODE_TYPES.get(routed_node, {}).get('name', '알 수 없음')}")
                
                # 그래프 표시
                if graph_created and os.path.exists("temp_plot.png"):
                    st.image("temp_plot.png", use_container_width=True)
                
                # 임시 파일 정리
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                    except:
                        pass
                        
            except Exception as e:
                import traceback
                error_msg = f"❌ 오류 발생: {str(e)}"
                st.error(error_msg)
                with st.expander("🔍 오류 상세 정보"):
                    st.code(traceback.format_exc())
                st.session_state.messages.append({"role": "assistant", "content": error_msg})


