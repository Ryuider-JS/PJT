# -*- coding: utf-8 -*-
"""
LangGraph 구조 시각화 스크립트
모든 노드의 그래프 구조를 이미지로 생성
"""
import os
import sys
from graphviz import Digraph

def create_router_graph():
    """router_node.py의 그래프 구조"""
    dot = Digraph(comment='Router Node Graph', format='png')
    dot.attr(rankdir='TB', size='8,6')
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
    
    # 시작 노드
    dot.node('START', 'START', shape='ellipse', fillcolor='lightgreen')
    dot.node('END', 'END', shape='ellipse', fillcolor='lightcoral')
    
    # 노드들
    dot.node('check_file_type', 'check_file_type\n파일 타입 확인\n• CSV → business_plan\n• PDF/DOCX → 내용 추출\n• 이메일 감지 → email\n• 없음 → no_file_no_email')
    dot.node('extract_content', 'extract_content\n파일 내용 추출\n(PDF/DOCX)')
    dot.node('llm_router', 'llm_router\nLLM 기반 라우팅\n(노드 선택)')
    
    # 엣지
    dot.edge('START', 'check_file_type')
    dot.edge('check_file_type', 'END', label='CSV/이메일/없음')
    dot.edge('check_file_type', 'extract_content', label='PDF/DOCX')
    dot.edge('extract_content', 'llm_router')
    dot.edge('llm_router', 'END')
    
    return dot

def create_email_graph():
    """email_node.py의 그래프 구조"""
    dot = Digraph(comment='Email Node Graph', format='png')
    dot.attr(rankdir='TB', size='8,6')
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightyellow')
    
    # 시작/종료
    dot.node('START', 'START', shape='ellipse', fillcolor='lightgreen')
    dot.node('END', 'END', shape='ellipse', fillcolor='lightcoral')
    
    # 노드들
    dot.node('web_search', 'web_search\n웹 검색 수행\n• Tavily 검색\n• 이메일 본문 생성')
    dot.node('tool_node', 'tool_node\n이메일 전송\n• LLM이 툴 호출\n• send_email_smtp 실행')
    
    # 엣지
    dot.edge('START', 'web_search')
    dot.edge('web_search', 'tool_node')
    dot.edge('tool_node', 'END')
    
    return dot

def create_market_research_graph():
    """market_research_node.py의 그래프 구조"""
    dot = Digraph(comment='Market Research Node Graph', format='png')
    dot.attr(rankdir='TB', size='10,8')
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightcyan')
    
    # 시작/종료
    dot.node('START', 'START', shape='ellipse', fillcolor='lightgreen')
    dot.node('END', 'END', shape='ellipse', fillcolor='lightcoral')
    
    # 노드들
    dot.node('supervisor', 'supervisor_node\nSupervisor\n• 검색 결과 평가\n• 다음 작업 결정\n• 반복 제한 (max 4)')
    dot.node('websearch', 'websearch\n웹 검색 노드\n• Tavily 검색\n• 내화물 제조사 동향 분석')
    dot.node('dbsearch', 'dbsearch\n벡터DB 검색\n• FAISS 검색\n• PDF 문서 분석')
    dot.node('integrator', 'integrator\n결과 통합\n• 웹검색 + DB검색\n• 최종 보고서 생성')
    dot.node('word_file', 'word_file\n(선택적)\nWord 파일 저장')
    
    # 엣지
    dot.edge('START', 'supervisor')
    dot.edge('supervisor', 'websearch', label='websearch')
    dot.edge('supervisor', 'dbsearch', label='dbsearch')
    dot.edge('supervisor', 'integrator', label='finish')
    dot.edge('websearch', 'supervisor', label='재평가')
    dot.edge('dbsearch', 'supervisor', label='재평가')
    dot.edge('integrator', 'word_file')
    dot.edge('word_file', 'END')
    
    return dot

def create_strategy_plan_graph():
    """strategy_plan_node.py의 그래프 구조"""
    dot = Digraph(comment='Strategy Plan Node Graph', format='png')
    dot.attr(rankdir='TB', size='12,10')
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lavender')
    
    # 시작/종료
    dot.node('START', 'START', shape='ellipse', fillcolor='lightgreen')
    dot.node('END', 'END', shape='ellipse', fillcolor='lightcoral')
    
    # 노드들
    dot.node('plan', 'manager_planner\n작업 배분 계획\n• 세부전략 분석\n• 검색 담당자별 작업 할당')
    dot.node('web_Industry', 'web_Industry\n산업 동향 검색\n• Tavily 검색\n• 산업 트렌드 분석')
    dot.node('web_Technology', 'web_Technology\n기술 동향 검색\n• 기술 트렌드 검색\n• 기술 시사점 도출')
    dot.node('web_Policy', 'web_Policy\n정책 동향 검색\n• 정부 정책 검색\n• 정책 동향 분석')
    dot.node('web_Regulation', 'web_Regulation\n규제/법령 검색\n• 규제 동향 검색\n• 법령 분석')
    dot.node('integrator', 'integrator\n결과 통합\n• 4개 검색 결과 통합\n• 3개년 로드맵 생성')
    dot.node('word_file', 'word_file\n(선택적)\nWord 파일 저장')
    
    # 엣지
    dot.edge('START', 'plan')
    dot.edge('plan', 'web_Industry')
    dot.edge('plan', 'web_Technology')
    dot.edge('plan', 'web_Policy')
    dot.edge('plan', 'web_Regulation')
    dot.edge('web_Industry', 'integrator')
    dot.edge('web_Technology', 'integrator')
    dot.edge('web_Policy', 'integrator')
    dot.edge('web_Regulation', 'integrator')
    dot.edge('integrator', 'word_file')
    dot.edge('word_file', 'END')
    
    return dot

def create_overall_system_graph():
    """전체 시스템 구조 그래프"""
    dot = Digraph(comment='Overall System Graph', format='png')
    dot.attr(rankdir='TB', size='14,10')
    dot.attr('node', shape='box', style='rounded,filled')
    
    # 시작/종료
    dot.node('START', 'START\n사용자 입력', shape='ellipse', fillcolor='lightgreen')
    dot.node('END', 'END\n결과 반환', shape='ellipse', fillcolor='lightcoral')
    
    # 라우터
    dot.node('router', 'Router Node\n(LLM 기반 라우팅)', fillcolor='lightblue')
    
    # 각 노드들
    dot.node('business_plan', 'Business Plan Node\nCSV → SQLite\nSQL Agent 분석', fillcolor='lightyellow')
    dot.node('email', 'Email Node\n웹 검색 + 이메일 전송', fillcolor='lightyellow')
    dot.node('market_research', 'Market Research Node\nPDF 벡터DB + 웹 검색\nSupervisor 패턴', fillcolor='lightcyan')
    dot.node('meeting_docx', 'Meeting DOCX Node\nHybrid Retrieval\nBM25 + Vector + Rerank', fillcolor='lightgreen')
    dot.node('strategy_plan', 'Strategy Plan Node\nPDF 전략 추출 + 4개 웹 검색\n3개년 로드맵 생성', fillcolor='lavender')
    
    # 엣지
    dot.edge('START', 'router')
    dot.edge('router', 'business_plan', label='CSV 파일')
    dot.edge('router', 'email', label='이메일 감지')
    dot.edge('router', 'market_research', label='PDF (시장조사)')
    dot.edge('router', 'meeting_docx', label='DOCX (회의록)')
    dot.edge('router', 'strategy_plan', label='PDF (로드맵)')
    dot.edge('business_plan', 'END')
    dot.edge('email', 'END')
    dot.edge('market_research', 'END')
    dot.edge('meeting_docx', 'END')
    dot.edge('strategy_plan', 'END')
    
    return dot

def create_business_plan_diagram():
    """business_plan_node.py의 처리 흐름"""
    dot = Digraph(comment='Business Plan Flow', format='png')
    dot.attr(rankdir='LR', size='10,6')
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightyellow')
    
    dot.node('csv', 'CSV 파일', shape='cylinder', fillcolor='lightgray')
    dot.node('sqlite', 'SQLite DB\n변환', fillcolor='lightyellow')
    dot.node('agent', 'SQL Agent\n(LangChain)', fillcolor='lightblue')
    dot.node('result', '분석 결과', fillcolor='lightgreen')
    
    dot.edge('csv', 'sqlite')
    dot.edge('sqlite', 'agent')
    dot.edge('agent', 'result')
    
    return dot

def create_meeting_docx_diagram():
    """meeting_docx_node.py의 처리 흐름"""
    dot = Digraph(comment='Meeting DOCX Flow', format='png')
    dot.attr(rankdir='LR', size='12,6')
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightgreen')
    
    dot.node('docx', 'DOCX 파일', shape='cylinder', fillcolor='lightgray')
    dot.node('split', '텍스트 분할\n(Chunk)', fillcolor='lightgreen')
    dot.node('hybrid', 'Hybrid Retrieval\nBM25 + Vector', fillcolor='lightblue')
    dot.node('rerank', 'Cross-Encoder\nReranker', fillcolor='lightcyan')
    dot.node('rag', 'RAG Chain\n답변 생성', fillcolor='lightyellow')
    dot.node('result', '검색 결과', fillcolor='lightcoral')
    
    dot.edge('docx', 'split')
    dot.edge('split', 'hybrid')
    dot.edge('hybrid', 'rerank')
    dot.edge('rerank', 'rag')
    dot.edge('rag', 'result')
    
    return dot

def main():
    """모든 그래프 생성"""
    print("🔄 LangGraph 구조 시각화 시작...")
    
    output_dir = "graph_visualizations"
    os.makedirs(output_dir, exist_ok=True)
    
    graphs = {
        '01_router_graph': create_router_graph(),
        '02_email_graph': create_email_graph(),
        '03_market_research_graph': create_market_research_graph(),
        '04_strategy_plan_graph': create_strategy_plan_graph(),
        '05_overall_system': create_overall_system_graph(),
        '06_business_plan_flow': create_business_plan_diagram(),
        '07_meeting_docx_flow': create_meeting_docx_diagram(),
    }
    
    for name, graph in graphs.items():
        try:
            filepath = os.path.join(output_dir, name)
            graph.render(filepath, cleanup=True)
            print(f"✅ 생성 완료: {filepath}.png")
        except Exception as e:
            print(f"❌ 오류 발생 ({name}): {str(e)}")
            print("   Graphviz가 설치되어 있는지 확인하세요: pip install graphviz")
            print("   시스템에 Graphviz가 설치되어 있어야 합니다: https://graphviz.org/download/")
    
    print(f"\n📁 모든 그래프가 '{output_dir}' 폴더에 저장되었습니다.")
    print("\n생성된 그래프:")
    for name in graphs.keys():
        print(f"  - {name}.png")

if __name__ == "__main__":
    main()

