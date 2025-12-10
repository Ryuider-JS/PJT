"""
시장조사 노드 모듈
Refractory Window PDF, 경쟁사 IR PDF 파일 및 Tavily 웹 검색 데이터 분석
"""
import os
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from operator import itemgetter


class MarketResearchChain:
    """시장조사 체인 래퍼 클래스 - streamlit_app.py와 호환되도록 invoke 메서드 제공"""
    
    def __init__(self, app, default_subject: str = "시장조사"):
        self.app = app
        self.default_subject = default_subject
    
    def invoke(self, inputs: dict) -> str:
        """
        streamlit_app.py에서 호출하는 형태: {"question": "질문 내용"}
        
        Args:
            inputs: {"question": str} 형태의 딕셔너리
            
        Returns:
            str: 최종 답변 문자열
        """
        question = inputs.get("question", "")
        
        # 질문에서 주제와 검색 키워드 추출 (간단한 추출 로직)
        # 실제로는 LLM을 사용하여 더 정교하게 추출할 수 있음
        subject = self._extract_subject(question)
        search_keyword = subject  # 기본적으로 주제와 동일하게 설정
        
        # LangGraph 앱 실행
        result = self.app.invoke({
            "messages": [HumanMessage(content=question)],
            "subject": subject,
            "search": search_keyword,
            "count": 0,
            "websearch": "",
            "dbsearch": "",
            "answer": "",
            "task": ""
        })
        
        # 최종 답변 반환
        return result.get("answer", "답변을 생성할 수 없습니다.")
    
    def _extract_subject(self, question: str) -> str:
        """질문에서 주제를 추출하는 간단한 로직"""
        # 기본 주제 사용 또는 질문의 일부를 사용
        if len(question) > 50:
            return question[:50] + "..."
        return question if question else self.default_subject


def create_market_research_chain(pdf_file_paths: list = None, api_key: str = None, verbose: bool = False):
    """
    시장조사 체인 생성 함수
    
    Args:
        pdf_file_paths (list, optional): PDF 파일 경로 리스트 (Streamlit file_uploader 객체 또는 경로 문자열)
        api_key (str, optional): OpenAI API 키
        verbose (bool): 상세 로그 출력 여부
        
    Returns:
        MarketResearchChain: 시장조사 체인 객체 (invoke 메서드 제공)
    """
    if not pdf_file_paths:
        raise ValueError("PDF 파일 경로가 제공되지 않았습니다.")
    
    # API 키 설정
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    
    # Tavily API 키 확인 (환경변수에서 가져오거나 설정 필요)
    if not os.environ.get("TAVILY_API_KEY"):
        if verbose:
            print("⚠️ TAVILY_API_KEY가 설정되지 않았습니다. 웹 검색 기능이 작동하지 않을 수 있습니다.")
    
    # PDF 파일들을 로드하고 병합
    all_docs = []
    temp_files_to_cleanup = []
    
    for pdf_file in pdf_file_paths:
        try:
            # Streamlit file_uploader 객체인 경우 임시 파일로 저장
            if hasattr(pdf_file, 'read') or hasattr(pdf_file, 'getvalue'):
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    # 파일 포인터를 처음으로 이동
                    if hasattr(pdf_file, 'seek'):
                        pdf_file.seek(0)
                    # 파일 데이터 읽기
                    if hasattr(pdf_file, 'read'):
                        file_data = pdf_file.read()
                    elif hasattr(pdf_file, 'getvalue'):
                        file_data = pdf_file.getvalue()
                    else:
                        continue
                    tmp_file.write(file_data)
                    pdf_path = tmp_file.name
                    temp_files_to_cleanup.append(pdf_path)
            else:
                # 문자열 경로인 경우
                pdf_path = pdf_file
            
            if verbose:
                print(f"📄 PDF 파일 로드 중: {pdf_path}")
            
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            all_docs.extend(docs)
                    
        except Exception as e:
            if verbose:
                print(f"❌ PDF 파일 로드 실패 ({pdf_file}): {str(e)}")
            continue
    
    # 모든 임시 파일 정리
    for temp_file in temp_files_to_cleanup:
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        except:
            pass
    
    if not all_docs:
        raise ValueError("로드된 PDF 문서가 없습니다.")
    
    if verbose:
        print(f"✅ 총 {len(all_docs)}개 페이지 로드 완료")
    
    # 문서를 의미 있는 단위(chunk)로 분할
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
    rec_docs = text_splitter.split_documents(all_docs)
    
    if verbose:
        print(f"✅ {len(rec_docs)}개 청크로 분할 완료")
    
    # 임베딩 및 벡터스토어 생성
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small"
    )
    vectorstore = FAISS.from_documents(rec_docs, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    
    if verbose:
        print("✅ 벡터스토어 생성 완료")
    
    # LLM 설정
    llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
    route_llm = ChatOpenAI(model="gpt-5-mini", temperature=0)  
    
    # Tavily 웹 검색 도구
    tavily_tool = TavilySearch(max_results=5)
    
    # State 정의
    class web_db_State(TypedDict):
        subject: str                # 벡터db 검색 키워드
        messages: List[BaseMessage] # 질문
        search: str                 # 웹 검색 키워드
        count: int                  # 진행 횟수
        websearch: str              # 웹 검색 데이터
        dbsearch: str               # db 검색 데이터
        answer: str                 # 최종 생성 답변
        task: str                   # 에이전트에서 판단한 다음 작업
    
    # Supervisor Node
    def supervisor_node(state: web_db_State):
        messages = state.get("messages", [])
        websearch = state.get("websearch", "")
        dbsearch = state.get("dbsearch", "")
        count = state.get("count", 0)
        search = state.get("search", "")
        subject = state.get("subject", "")
        
        # 반복 횟수 제한
        if count >= 4:
            if verbose:
                print("→ Supervisor: count 4 이상 → finish로 강제 종료")
            return {
                "task": "finish",
                "websearch": websearch,
                "count": count,
                "dbsearch": dbsearch
            }
        
        # Supervisor LLM 판단
        context_prompt = f"""
        당신은 Multi-Agent Supervisor입니다.
        "최근 Search 결과"와 웹 검색 키워드를 비교하여, 내용이 부족하다면 "websearch"를 출력하고
        "최근 db Search 결과"와 벡터DB 검색 키워드를 비교하여, 내용이 부족하다면 "dbsearch"를 출력하고
        내용이 부족하지 않다면 "finish"를 출력하세요.

        --- 벡터DB 검색 키워드 ---
        {subject}

        --- 웹 검색 키워드 ---
        {search}

        --- 최근 Web Search 결과 ---
        {websearch}

        --- 최근 db Search 결과 ---
        {dbsearch}

        위 정보를 토대로 다음 작업 중 하나를 선택해 출력하세요:
        출력 형식: {{ "task": "websearch" 또는 "dbsearch" 또는 "finish"}}
        절대 다른 텍스트를 출력하지 마세요.
        """
        chain = route_llm | JsonOutputParser()
        decision = chain.invoke(context_prompt)
        
        task = decision.get("task", "finish")
        
        return {
            "task": task,
            "websearch": websearch,
            "count": count,
            "dbsearch": dbsearch
        }
    
    # VectorDB 검색 노드
    def vectordb(state: web_db_State):
        system_message = """
        db검색 정보 : {context}

        검색된 정보들 기반으로
        내화물 제조사별로 동향을 조사하고
        보고서 생성을 위한 내용 만들어줘
        
        주로 들어가야할 내용은 다음과 같아. 
        1. 손익
        2. 원료조달
        3. 판매처
        4. 기술개발
        5. M&A 등 투자
        6. 기타 주요 이슈
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", "{question}")
        ])
        
        rag_chain1 = (
            {"context": itemgetter("question") | retriever, "question": itemgetter("question")}
            | prompt
            | llm
            | StrOutputParser()
        )
        
        generation = rag_chain1.invoke({"question": state["subject"]})
        if verbose:
            print("벡터db 기반 답변을 진행합니다.")
        
        return {
            "dbsearch": generation,
            "count": state["count"] + 1,
        }
    
    # 웹 검색 노드
    def websearch(state: web_db_State):
        search = state["search"]
        system_message = """
        웹검색 정보 : {context}
        
        검색된 정보들 기반으로
        내화물 제조사별로 동향을 조사하고
        보고서 생성을 위한 내용 만들어줘
        
        주로 들어가야할 내용은 다음과 같아. 
        1. 손익
        2. 원료조달
        3. 판매처
        4. 기술개발
        5. M&A 등 투자
        6. 기타 주요 이슈
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", "{question}")
        ])
        
        rag_chain1 = (
            {"context": itemgetter("question") | tavily_tool, "question": itemgetter("question")}
            | prompt
            | llm
            | StrOutputParser()
        )
        
        generation = rag_chain1.invoke({"question": search})
        if verbose:
            print("웹서치 기반 답변을 진행합니다.")
        
        return {
            "websearch": generation,
            "count": state["count"] + 1,
        }
    
    # Integrator 노드 (결과 취합)
    def integrator(state: web_db_State):
        subject = state["subject"]
        websearch = state["websearch"]
        dbsearch = state["dbsearch"]
        
        if verbose:
            print(f"=== Manager (Integrator) 실행 ===")
        
        prompt = f"""
        주제:
        {subject}

        웹서치 결과:
        {websearch}

        db서치 결과:
        {dbsearch}

        위 내용들을 통합하여
        질의에 대한 보고서 만들어줘

        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        final_design = response.content
        
        if verbose:
            print(f"결과 생성 완료")
        
        return {"answer": final_design, "messages": [response]}
    
    # Tool Node (Word 파일 저장 - 선택적)
    def tool_node(state: web_db_State):
        answer = state["answer"]
        # Word 파일 저장은 선택적으로 구현 (필요시 활성화)
        # 현재는 답변만 반환
        return {"answer": answer}
    
    # 라우팅 조건
    def route_condition(state: web_db_State):
        return state["task"]
    
    # 그래프 구성
    workflow = StateGraph(web_db_State)
    
    workflow.add_node("supervisor_node", supervisor_node)
    workflow.add_node("word_file", tool_node)
    workflow.add_node("websearch", websearch)
    workflow.add_node("dbsearch", vectordb)
    workflow.add_node("integrator", integrator)
    
    workflow.add_conditional_edges(
        "supervisor_node",
        route_condition,
        {
            "websearch": "websearch",
            "dbsearch": "dbsearch",
            "finish": "integrator",
        }
    )
    
    workflow.add_edge(START, "supervisor_node")
    workflow.add_edge("websearch", "supervisor_node")
    workflow.add_edge("dbsearch", "supervisor_node")
    workflow.add_edge("integrator", "word_file")
    workflow.add_edge("word_file", END)
    
    # 그래프 컴파일
    app = workflow.compile()
    
    # 래퍼 클래스로 반환
    return MarketResearchChain(app, default_subject="시장조사")


if __name__ == "__main__":
    print("시장조사 노드 모듈입니다. streamlit_app.py에서 사용하세요.")
