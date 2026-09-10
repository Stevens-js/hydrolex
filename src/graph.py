from langgraph.graph import StateGraph,START,END
from typing import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from term_extractor import Term,extract_terms
from pdf_parser import ParsedPage,parse_pdf,get_standard_name
from definition_processor import process_definitions
from vector_store import upsert_terms
from pathlib import Path

class GraphState(TypedDict):
    pdf_path: str
    standard_name: str
    pages: list[ParsedPage]
    terms: list[Term]
    confirmed: bool             #判断用户是否确定

# 输入：{"pdf_path": "data/pdfs/某规范.pdf", "standard_name": "某规范"}
# 输出：{"pages": [ParsedPage(...), ...]}
def parse_pdf_node(state: GraphState) -> dict:
    pages = parse_pdf(state["pdf_path"])
    return {"pages": pages}

# 输入：{"pages": [ParsedPage(...), ...], "standard_name": "某规范"}
# 输出：{"terms": [Term(...), ...]}
def extract_terms_node(state: GraphState) -> dict:
    terms = extract_terms(state["pages"],use_llm = True,standard_name=state["standard_name"])
    return {"terms": terms}

# 输入：{"terms": [Term(...), ...]}
# 输出：{"terms": [Term(...), ...]}
def process_definitions_node(state: GraphState) -> dict:
    terms = process_definitions(state["terms"])
    return {"terms": terms}

# 输入：{"terms": [Term(...), ...]}
# 输出：{"confirmed": bool}
def upsert_node(state: GraphState) -> dict:
    # confirmed=True 后才执行
    upsert_terms(state["terms"])
    return {"confirmed": True}

def build_graph():
    graph = StateGraph(GraphState)

    #添加节点
    graph.add_node("parse_pdf",parse_pdf_node)
    graph.add_node("extract_terms",extract_terms_node)
    graph.add_node("process_definitions",process_definitions_node)
    graph.add_node("upsert",upsert_node)

    #添加边
    graph.add_edge(START,"parse_pdf")
    graph.add_edge("parse_pdf","extract_terms")
    graph.add_edge("extract_terms","process_definitions")
    graph.add_edge("process_definitions","upsert")
    graph.add_edge("upsert",END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory, interrupt_before=["upsert"])

if __name__ == "__main__":
    app = build_graph()
    config = {"configurable": {"thread_id": "1"}}

    project_root = Path(__file__).parent.parent
    
    initial = {
        "pdf_path": str(project_root / "data" / "pdfs" / "练习.pdf"),
        "standard_name": get_standard_name(str(project_root / "data" / "pdfs" / "练习.pdf")),
        "pages": [],
        "terms": [],
        "confirmed": False
    }
    
    # 第一次调用：跑到 upsert 前暂停
    result = app.invoke(initial, config=config)
    print("=== 暂停，提取到的术语 ===")
    for t in result["terms"]:
        print(f"[{t.source_type}] {t.term_ZH}: {t.definition[:30]}...")
    
    # 第二次调用：恢复，执行 upsert
    print("\n=== 恢复，执行入库 ===")
    result = app.invoke(None, config=config)
    print(f"完成，confirmed={result['confirmed']}")
    
    # 验证入库结果
    from vector_store import query_term
    if result["terms"]:
        print(query_term(result["terms"][0].term_ZH))