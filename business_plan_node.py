# -*- coding: utf-8 -*-
"""
경영계획 분석 노드 모듈
CSV 파일 기반 재무/경영 데이터 분석 (SQL 기반)
"""
import os
import sys
import io
import tempfile
import sqlite3

# Windows 환경에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
            if hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except:
        pass

import pandas as pd
from dotenv import load_dotenv

# LangChain 관련 import
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import create_agent


def create_business_plan_chain(csv_file_path: str, api_key: str = None, verbose: bool = False):
    """
    경영계획 분석 체인 생성 함수 (SQL 기반)
    
    Args:
        csv_file_path (str): CSV 파일 경로
        api_key (str, optional): OpenAI API 키. None이면 환경 변수에서 가져옴
        verbose (bool): 상세 로그 출력 여부
        
    Returns:
        tuple: (agent_wrapper, df_data) - 에이전트 래퍼 객체와 데이터프레임
    """

    try:
        # API 키 설정
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        
        # CSV 읽기
        df_data = pd.read_csv(csv_file_path)
        
        if verbose:
            print(f"✅ CSV 파일 읽기 완료: {csv_file_path}")
            print(f"  - 크기: {df_data.shape}")
        
        # 임시 DB 파일 생성
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db_path = temp_db.name
        temp_db.close()
        
        # DB 연결
        conn = sqlite3.connect(temp_db_path)
        
        # 테이블 생성 (필요하면 replace)
        df_data.to_sql("bizplan", conn, if_exists="replace", index=False)
        
        conn.close()
        
        if verbose:
            print(f"✅ SQLite DB 생성 완료: {temp_db_path}")
        
        # SQLDatabase 초기화
        db = SQLDatabase.from_uri(f"sqlite:///{temp_db_path}")
        
        # LLM 초기화
        llm = ChatOpenAI(
            model="gpt-5-mini",  # gpt-5-mini는 존재하지 않으므로 gpt-4o-mini 사용
            temperature=0
        )
        
        if verbose:
            print("✅ GPT-5-mini 모델 초기화 성공")
        
        # SQLDatabaseToolkit 초기화
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        
        tools = toolkit.get_tools()
        
        if verbose:
            print(f"✅ SQL 도구 {len(tools)}개 로드 완료")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
        
        # 시스템 프롬프트 생성
        system_prompt = """
You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct {dialect} query to run,
then look at the results of the query and return the answer. Unless the user
specifies a specific number of examples they wish to obtain, always limit your
query to at most {top_k} results.

You can order the results by a relevant column to return the most interesting
examples in the database. Never query for all the columns from a specific table,
only ask for the relevant columns given the question.

You MUST double check your query before executing it. If you get an error while
executing a query, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the
database.

To start you should ALWAYS look at the tables in the database to see what you
can query. Do NOT skip this step.

Then you should query the schema of the most relevant tables.

----- 조건
매출액, 판매량은 비용에 포함되지 않는다.
""".format(
            dialect=db.dialect,
            top_k=5,
        )
        
        # 에이전트 생성
        agent = create_agent(
            llm,
            tools,
            system_prompt=system_prompt,
        )
        
        if verbose:
            print("✅ SQL 에이전트 생성 완료")
        
        # streamlit_app.py와의 호환성을 위한 래퍼 클래스
        class AgentWrapper:
            def __init__(self, agent, db_path, verbose_flag=False):
                self.agent = agent
                self.db_path = db_path
                self.verbose = verbose_flag
            
            def _extract_content(self, message):
                """메시지에서 내용 추출"""
                if hasattr(message, 'content'):
                    return message.content
                elif hasattr(message, 'text'):
                    return message.text
                elif isinstance(message, dict):
                    if 'content' in message:
                        return message['content']
                    elif 'text' in message:
                        return message['text']
                return str(message)
            
            def invoke(self, inputs):
                """streamlit_app.py에서 호출하는 형태로 변환"""
                question = inputs.get("question", "")
                if not question:
                    return "질문을 입력해주세요."
                
                # 에이전트 실행 (stream 방식 사용)
                try:
                    result_messages = []
                    # agent.stream() 방식 사용
                    for step in self.agent.stream(
                        {"messages": [{"role": "user", "content": question}]},
                        stream_mode="values",
                    ):
                        if "messages" in step and step["messages"]:
                            last_message = step["messages"][-1]
                            content = self._extract_content(last_message)
                            if content and content.strip():
                                result_messages.append(content)
                    
                    # 마지막 메시지 반환
                    if result_messages:
                        return result_messages[-1]
                    else:
                        # stream이 실패한 경우 invoke 시도
                        response = self.agent.invoke(
                            {"messages": [{"role": "user", "content": question}]}
                        )
                        if "messages" in response and response["messages"]:
                            for msg in reversed(response["messages"]):
                                content = self._extract_content(msg)
                                if content and content.strip():
                                    if isinstance(msg, dict) and msg.get("role") != "user":
                                        return content
                                    elif hasattr(msg, 'type') and msg.type != "human":
                                        return content
                                    elif hasattr(msg, 'role') and msg.role != "user":
                                        return content
                                    else:
                                        return content
                        return str(response)
                    
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    if self.verbose:
                        print(f"에이전트 실행 오류: {error_detail}")
                    return f"오류가 발생했습니다: {str(e)}"
            
            def __del__(self):
                # 임시 DB 파일 정리
                try:
                    if os.path.exists(self.db_path):
                        os.unlink(self.db_path)
                except:
                    pass
        
        agent_wrapper = AgentWrapper(agent, temp_db_path, verbose)
        
        if verbose:
            print("✅ 경영계획 분석 체인 구성 완료")
        
        return agent_wrapper, df_data
        
    except Exception as e:
        raise Exception(f"경영계획 노드 초기화 실패: {str(e)}")


# 직접 실행 시 (테스트용)
if __name__ == "__main__":
    from dotenv import load_dotenv
    env_path = r"C:\Users\user\Desktop\PJT1\.env"
    load_dotenv(dotenv_path=env_path)
    
    data_path = r"C:\Users\user\Desktop\PJT1\경영계획\Biz_plan_A_가.csv"
    chain, df = create_business_plan_chain(data_path, verbose=True)
    
    print("\n" + "="*60)
    print("📊 비즈니스 플랜 데이터 분석 시스템 (SQL 기반)")
    print("="*60)
    print("질문을 입력하세요. (종료하려면 'quit', 'exit', '종료' 중 하나를 입력하세요)")
    print("-"*60)
    
    while True:
        try:
            user_question = input("\n💬 질문: ").strip()
            if user_question.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n👋 분석을 종료합니다. 감사합니다!")
                break
            if not user_question:
                print("⚠️  질문을 입력해주세요.")
                continue
            
            print("\n" + "-"*60)
            print(f"🔍 질문: {user_question}")
            print("-"*60)
            print("⏳ 분석 중...")
            
            result = chain.invoke({"question": user_question})
            
            print("\n" + "="*60)
            print("📊 분석 결과:")
            print("="*60)
            print(result)
            print("="*60)
            
        except KeyboardInterrupt:
            print("\n\n👋 사용자에 의해 중단되었습니다. 감사합니다!")
            break
        except Exception as e:
            print(f"\n❌ 오류가 발생했습니다: {str(e)}")
            import traceback
            traceback.print_exc()
            print("다시 시도해주세요.")
