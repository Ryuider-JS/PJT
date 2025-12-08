from langchain_core.tools import tool
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
from typing import TypedDict, List
from langgraph.graph import StateGraph, END, START

# LangChain의 메시지, LLM, 파서 등
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

# Web Search
from langchain_tavily import TavilySearch
import os

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL") 
APP_PASSWORD = os.getenv("APP_PASSWORD") 
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587 

@tool
def send_email_smtp(to: str, subject: str, body: str, is_html: bool = False) -> str:
    """
    Gmail SMTP를 사용하여 이메일을 전송하는 Tool.

    Parameters
    ----------
    to : str
        수신자 이메일 주소
    subject : str
        메일 제목
    body : str
        메일 본문 (텍스트 또는 HTML)
    is_html : bool
        True → HTML 이메일로 전송
        False → 일반 텍스트로 전송
    Returns
    -------
    str : 전송 상태 메시지
    """

    try:
        # ---------------------------
        # 이메일 구성
        # ---------------------------
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to
        msg["Subject"] = subject

        if is_html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        # ---------------------------
        # SMTP 연결
        # ---------------------------
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # TLS 보안 연결
        server.login(SENDER_EMAIL, APP_PASSWORD)

        # ---------------------------
        # 메일 전송
        # ---------------------------
        server.sendmail(SENDER_EMAIL, to, msg.as_string())
        server.quit()

        return f"메일 전송 완료: {to}"

    except Exception as e:
        return f"메일 전송 실패: {str(e)}"

# Tool 리스트
tools = [send_email_smtp]


# ---------------------------------------------------------
# State는 LangGraph에서 노드 간 데이터를 전달하는 구조입니다.
# 아래 구조는 모든 노드가 공통으로 접근할 수 있는 형태입니다.
# ---------------------------------------------------------

class Web_Mail_State(TypedDict):
    subject: str          # 사용자 질문
    messages: List[BaseMessage]
    emailbody: str
    answer: str           # 최종 생성 답변

# ---------------------------------------------------------
# 📌 기본 LLM 설정
# ---------------------------------------------------------
# 자주 쓰는 gpt-4o-mini 모델로 설정

llm = ChatOpenAI(model="gpt-5-mini")

# ---------------------------------------------------------
# 🔍 Web Search Tool
# ---------------------------------------------------------
tavily_tool = TavilySearch(
    max_results=10,
    days=30
    )

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter

def web_search(state:Web_Mail_State):
  """
  웹 검색 노드: 사용자 질의에서 검색 키워드를 추출하고 웹 검색 후 이메일 본문 생성
  """
  import re
  
  # 사용자 메시지에서 검색 키워드 추출
  user_message = state["messages"][-1].content if state.get("messages") else ""
  
  # 이메일 주소 패턴
  email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
  
  # 이메일 주소 제거 및 검색 키워드 추출
  # "rjs8833@gmail.com으로 000회사 관련 정보를 이메일로 보내줘라" 
  # -> "000회사 관련 정보"
  search_query = re.sub(email_pattern, '', user_message)
  search_query = re.sub(r'이메일로\s*보내|메일로\s*보내|메일\s*보내|이메일\s*보내|에\s*메일|으로\s*메일|에게\s*메일', '', search_query, flags=re.IGNORECASE)
  search_query = search_query.strip()
  
  # 검색 키워드가 비어있으면 기본 subject 사용
  if not search_query or len(search_query) < 2:
      search_query = state["subject"]
  
  # LLM을 사용하여 검색 키워드 추출 (더 정확하게)
  if user_message and user_message != search_query:
      keyword_extraction_prompt = f"""
다음 사용자 메시지에서 이메일 전송과 관련된 실제 검색할 키워드나 주제를 추출해주세요.
이메일 주소나 "보내줘", "전송" 같은 동사는 제외하고, 실제로 검색해야 할 내용만 추출하세요.

사용자 메시지: {user_message}

검색 키워드만 추출해서 출력하세요. 다른 설명 없이 키워드만:
"""
      try:
          extracted_keyword = llm.invoke(keyword_extraction_prompt).content.strip()
          if extracted_keyword and len(extracted_keyword) > 2:
              search_query = extracted_keyword
      except:
          pass  # 추출 실패 시 기존 search_query 사용

  system_message = """
  웹검색 정보 : {context}

  검색한 정보 기반으로 이메일 본문 만들어줘
  이메일 본문에 대해 참고할 수 있는 내용을 제목, 링크로 표 만들어서 같이 보내줘
  다른 텍스트 말고 메일 본문만 출력해줘

  """

  # ✅ 프롬프트 템플릿
  prompt = ChatPromptTemplate.from_messages([
      ("system", system_message),
      ("user", "{question}")
  ])

  # ✅ LCEL 체인 구성
  rag_chain1 = (
      {"context": itemgetter("question") | tavily_tool, "question": itemgetter("question")}
      | prompt
      | llm
      | StrOutputParser()
  )

  generation = rag_chain1.invoke({"question": search_query})
  print("웹서치 기반 답변을 진행합니다.")
  print(f"검색 키워드: {search_query}")
  print(f"웹서치 기반 메일 본문 : {generation}")
  return {"emailbody": generation}

def tool_node(state: Web_Mail_State):
    """
    사용자 메시지를 분석하여 필요한 툴을 호출하는 노드입니다.
    LLM에 툴을 바인딩하고, 사용자 메시지를 기반으로 툴 호출을 생성합니다.

    Args:
        state: 현재 State 객체 (messages 필드를 포함)

    Returns:
        dict: 업데이트된 State (tool_calls 필드 추가)
    """
    messages = state["messages"][-1].content
    subject = state["subject"]
    emailbody = state["emailbody"]


    user_query = f"""
    {messages}

    제목 : {subject}
    본문 : {emailbody}
    """

    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(user_query)

    print(f"툴 호출 메세지 : {response}")
    tool_node = ToolNode(tools)
    result = tool_node.invoke({"messages": [response]})
    print(f"user_query : {user_query}")
    return {"answer": [result]}  # 새로운 AI 메시지를 리스트로 반환

# 그래프를 구성합니다.
workflow = StateGraph(Web_Mail_State)

# 정의한 함수들을 노드로 추가합니다.
workflow.add_node("send_mail", tool_node)
workflow.add_node("web_search", web_search)

# 각 답변 생성 노드는 작업 완료 후 종료(END)됩니다.
workflow.add_edge(START, "web_search")
workflow.add_edge("web_search","send_mail")
workflow.add_edge("send_mail", END)

# 그래프를 실행 가능한 애플리케이션으로 컴파일합니다.
# app = workflow.compile()

def create_email_chain(api_key: str = None, tavily_api_key: str = None, verbose: bool = False):
    """
    이메일 전송 체인 생성 함수 (Streamlit 호환)
    
    Args:
        api_key: OpenAI API 키
        tavily_api_key: Tavily API 키 (웹 검색용)
        verbose: 상세 로그 출력 여부
        
    Returns:
        이메일 체인 객체 (invoke 메서드 제공)
    """
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    if tavily_api_key:
        os.environ["TAVILY_API_KEY"] = tavily_api_key
    
    # 그래프 컴파일
    app = workflow.compile()
    
    class EmailChain:
        """이메일 체인 래퍼 클래스"""
        
        def __init__(self, app, verbose_flag=False):
            self.app = app
            self.verbose = verbose_flag
        
        def invoke(self, inputs: dict) -> str:
            """
            streamlit_app.py에서 호출하는 형태: {"question": "질문 내용"}
            
            Args:
                inputs: {"question": str} 형태의 딕셔너리
                
            Returns:
                str: 최종 결과 메시지
            """
            import re
            question = inputs.get("question", "")
            
            # 사용자 질의에서 이메일 주소 추출 (한글과 영문이 섞인 경우도 고려)
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            email_matches = re.findall(email_pattern, question)
            email_address = email_matches[0] if email_matches else None
            
            if self.verbose:
                print(f"이메일 전송 요청: {question}")
                print(f"추출된 이메일: {email_address}")
            
            # 기본 제목 (사용자 질의에서 추출하거나 기본값 사용)
            subject = "이메일 전송 요청"
            
            # 질의에서 제목 추출 시도 (예: "제목: ..." 또는 "subject: ...")
            subject_match = re.search(r'(?:제목|subject)[\s:]+(.+?)(?:,|$)', question, re.IGNORECASE)
            if subject_match:
                subject = subject_match.group(1).strip()
            else:
                # 제목이 명시되지 않은 경우, 이메일 주소와 "보내줘" 같은 단어를 제외한 나머지를 제목으로 사용
                temp_subject = question
                # 이메일 주소 제거
                temp_subject = re.sub(email_pattern, '', temp_subject)
                # "보내줘", "전송" 같은 동사 제거
                temp_subject = re.sub(r'이메일로\s*보내|메일로\s*보내|메일\s*보내|이메일\s*보내|에\s*메일|으로\s*메일|에게\s*메일|보내줘|전송', '', temp_subject, flags=re.IGNORECASE)
                temp_subject = temp_subject.strip()
                if temp_subject and len(temp_subject) > 2:
                    subject = temp_subject
            
            # 그래프 실행
            result = self.app.invoke({
                "messages": [HumanMessage(content=question)],
                "subject": subject,
                "emailbody": "",
                "answer": ""
            })
            
            # 결과에서 이메일 전송 결과 추출
            answer = result.get("answer", "")
            
            # tool_calls 결과에서 이메일 전송 상태 확인
            success = False
            final_email = email_address  # 기본값은 추출한 이메일 주소
            
            if isinstance(answer, list) and len(answer) > 0:
                if isinstance(answer[0], dict) and "messages" in answer[0]:
                    messages = answer[0]["messages"]
                    for msg in messages:
                        if hasattr(msg, 'content'):
                            content = msg.content
                            if "메일 전송 완료" in content or "전송 완료" in content:
                                success = True
                                # 메시지에서 이메일 주소 다시 추출 (정확성을 위해)
                                email_match = re.search(email_pattern, content)
                                if email_match:
                                    final_email = email_match.group(0)
                                break
                            elif "메일 전송 실패" in content or "실패" in content:
                                success = False
                                # 실패 시에도 이메일 주소 추출
                                email_match = re.search(email_pattern, content)
                                if email_match:
                                    final_email = email_match.group(0)
                                break
            
            # 성공 메시지 생성
            if success and final_email:
                return f"{final_email}에 성공적으로 전송이 완료되었습니다."
            elif final_email:
                # 실패한 경우
                return str(answer) if answer else f"{final_email}로의 이메일 전송이 실패했습니다."
            else:
                return str(answer) if answer else "이메일 주소를 찾을 수 없거나 전송 결과를 가져올 수 없습니다."
    
    return EmailChain(app, verbose)


# 직접 실행 시 (테스트용)
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    chain = create_email_chain(verbose=True)
    result = chain.invoke({"question": "scv0317@gmail.com에 메일보내줘"})
    print("\n" + "="*60)
    print("📧 이메일 전송 결과")
    print("="*60)
    print(result)
    print("="*60)
