"""
회의록 검색 노드 모듈
주간회의록, 임원회의 자료 Word 파일 검색
"""
import os
from langchain_community.document_loaders import Docx2txtLoader
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_classic.retrievers import EnsembleRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from operator import itemgetter


def create_meeting_docx_chain(docx_file_paths: list, api_key: str = None, verbose: bool = False):
    """
    회의록 검색 체인 생성 함수
    
    Args:
        docx_file_paths (list): Word 파일 경로 리스트
        api_key (str, optional): OpenAI API 키. None이면 환경 변수에서 가져옴
        verbose (bool): 상세 로그 출력 여부
        
    Returns:
        rag_chain: RAG 체인 객체
    """
    try:
        # API 키 설정
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        
        if not docx_file_paths:
            raise ValueError("Word 파일 경로 리스트가 비어있습니다.")
        
        # 문서 로드
        all_documents = []
        for file_path in docx_file_paths:
            try:
                loader = Docx2txtLoader(file_path)
                docs = loader.load()
                if verbose:
                    print(f"📄 {os.path.basename(file_path)}: {len(docs)}개 페이지 로드")
                all_documents.extend(docs)
            except Exception as e:
                if verbose:
                    print(f"⚠️ 파일 로드 실패 ({os.path.basename(file_path)}): {str(e)}")
                continue
        
        if not all_documents:
            raise ValueError("로드된 문서가 없습니다.")
        
        # 텍스트 분할
        rec_splitter = RecursiveCharacterTextSplitter(
            chunk_size=100,
            chunk_overlap=10,
        )
        rec_docs = rec_splitter.split_documents(all_documents)
        if verbose:
            print(f"✅ {len(rec_docs)}개 청크로 분할 완료")
        
        # 벡터 스토어 및 리트리버 구성
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vectorstore = FAISS.from_documents(rec_docs, embeddings)
        vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        
        bm25_retriever = BM25Retriever.from_documents(rec_docs)
        bm25_retriever.k = 3
        
        hybrid_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, vector_retriever],
            weights=[0.4, 0.6],
        )
        
        # Cross-Encoder 기반 reranker
        model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-large")
        reranker = CrossEncoderReranker(model=model, top_n=2)
        
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=reranker,
            base_retriever=hybrid_retriever,
        )
        
        # LLM 프롬프트 및 체인
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{context} 기반으로 답변하는 챗봇이야"),
            ("user", "{question}"),
        ])
        
        llm = ChatOpenAI(model="gpt-5-mini", api_key=api_key)
        
        rag_chain = (
            {"context": itemgetter("question") | compression_retriever, "question": itemgetter("question")}
            | prompt
            | llm
            | StrOutputParser()
        )
        
        if verbose:
            print("✅ 회의록 검색 체인 구성 완료")
        
        return rag_chain
        
    except Exception as e:
        raise Exception(f"회의록 노드 초기화 실패: {str(e)}")


# 직접 실행 시 (기존 코드 호환성 유지)
if __name__ == "__main__":
    from glob import glob
    
    MEETING_DIR = r"C:\Users\user\Desktop\PJT1\주간회의록"
    docx_pattern = os.path.join(MEETING_DIR, "2511*.docx")
    docx_files = sorted(glob(docx_pattern))
    
    if not docx_files:
        raise FileNotFoundError(f"주간회의록 폴더에서 '{docx_pattern}' 패턴에 맞는 파일을 찾을 수 없습니다.")
    
    chain = create_meeting_docx_chain(docx_files, verbose=True)
    
    user_question = input("질문을 입력하세요 (예: 이번주 안전이슈는 어떤게 있어?): ").strip()
    if not user_question:
        raise ValueError("질문이 입력되지 않았습니다.")
    
    print("\n🤖 챗봇 답변:")
    print(chain.invoke({"question": user_question}))
