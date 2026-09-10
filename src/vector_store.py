import chromadb
from llm_factory import get_embeddings,_load_config
from pathlib import Path
from term_extractor import Term
import json

_collection = None  # 全局缓存，避免重复创建

def _get_collection() :
    """读 config，返回 Chroma collection（单例缓存）"""
    global _collection
    if _collection is not None:
        return _collection

    config = _load_config()
    project_root = Path(__file__).parent.parent
    persist_path = str(project_root/config["vector_store"]["persist_directory"])
    client = chromadb.PersistentClient(path=persist_path)
    embeddings = get_embeddings()
    _collection = client.get_or_create_collection(name=config["vector_store"]["collection_name"],embedding_function=embeddings)
    return _collection

def upsert_term(term: Term):
    collection = _get_collection()
    term_id = f"term_{term.term_ZH}"
    existing = collection.get(ids=[term_id])
    if not existing["ids"]:
        #不存在就新建
        collection.add(ids=[term_id],
                       documents=[term.term_ZH],
                       metadatas=[{
                           "term_ZH":term.term_ZH,
                           "term_EN":term.term_EN,
                           "standard_names":json.dumps([term.standard_name], ensure_ascii=False),
                           "definitions":json.dumps([{
                                "standard": term.standard_name,
                                "definition": term.definition,
                                "definition_type": term.definition_type
                           }],ensure_ascii=False),
                           "page_num":term.page_num,
                           "confidence":term.confidence,
                           "source_type":term.source_type,
                           "definition_type":term.definition_type
                       }])
    else:
        #存在就更新
        meta = existing["metadatas"][0]
        names = set(json.loads(meta.get("standard_names", "[]")))
        names.add(term.standard_name)

        defs = json.loads(meta.get("definitions", "[]"))
        # 检查是否已存在该规范的释义
        existing_std = {d["standard"] for d in defs}
        if term.standard_name not in existing_std:
            defs.append({
                "standard": term.standard_name,
                "definition": term.definition,
                "definition_type": term.definition_type
            })

        collection.update(
            ids=[term_id],
            metadatas=[{
                **meta,
                "standard_names": json.dumps(list(names), ensure_ascii=False),
                "definitions": json.dumps(defs, ensure_ascii=False),
            }]
        )


def query_term(term_name: str) -> dict | None:
    """按术语名精确查询，返回该术语的所有来源释义"""
    collection = _get_collection()
    term_id = f"term_{term_name}"

    result = collection.get(ids=[term_id])
    if not result["ids"]:
        return None
    meta = result["metadatas"][0]
    meta["definitions"] = json.loads(meta.get("definitions","[]"))
    meta["standard_names"] = json.loads(meta.get("standard_names", "[]"))
    return meta

def upsert_terms(terms :list[Term]):
    for term in terms:
        try:
            upsert_term(term)
        except Exception as e:
            print(f"入库失败[{term.term_ZH}]：{e}")

def show_allterms() -> list[Term]:
    collection = _get_collection()
    result = collection.get()
    metas = result["metadatas"]
    terms :list[Term] = []
    for meta in metas:
        defs = json.loads(meta.get("definitions", "[]"))
        names = json.loads(meta.get("standard_names", "[]"))
        # 取第一条释义作为主展示
        primary_def = defs[0]["definition"] if defs else ""
        terms.append({
            "term_ZH": meta.get("term_ZH", ""),
            "term_EN": meta.get("term_EN", ""),
            "definition": primary_def,
            "all_definitions": defs,           # 所有来源释义
            "standard_names": names,           # 所有来源规范
            "source_type": meta.get("source_type", ""),
            "definition_type": meta.get("definition_type", ""),
            "page_num": meta.get("page_num", 0),
            "confidence": meta.get("confidence", 0)
        })
    return terms


if __name__ == "__main__":
    terms:list[Term] = show_allterms()
    for term in terms:
        print(term)
        print()

    # from term_extractor import Term
    
    # # 模拟两个规范的同一术语
    # t1 = Term(term_ZH="机组台数", term_EN="number of units",
    #           definition="单座电站安装的机组总台数。",
    #           page_num=1, confidence=0.9, source_type="regex",
    #           standard_name="GB/T 规范A", definition_type="原文")
    
    # t2 = Term(term_ZH="机组台数", term_EN="",
    #           definition="电站机组的总数量。",
    #           page_num=3, confidence=0.9, source_type="regex",
    #           standard_name="NB/T 规范B", definition_type="原文")
    
    # upsert_term(t1)
    # upsert_term(t2)  # 同名，应该合并
    
    # result = query_term("机组台数")
    # print(result)


# @dataclass
# class Term:
#     term_ZH: str              # 中文术语名，如"机组台数"
#     term_EN: str              # 英文术语名，如有，如"number of units"
#     definition: str           # 释义
#     page_num: int             # 来源页码
#     confidence: float         # 置信度 0-1
#     source_type: str          # "regex" / "llm" / "seed"
#     standard_name: str = ""   # 来源规范名称
#     definition_type: str = "" # 释义来源 "原文" / "llm生成" / "人工补充" / ""