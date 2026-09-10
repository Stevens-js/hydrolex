from term_extractor import Term
from llm_factory import get_llm
import json

def process_definitions(terms: list[Term]) -> list[Term]:
    """补全缺失的释义
    - 有释义的不动
    - 没释义的用 LLM 生成
    """
    need_full:list[Term] = []
    for term in terms:
        if not term.definition.strip():
            need_full.append(term)
    prompt_template = """你是抽水蓄能行业的专家。请为下面的行业术语生成简短准确的释义。

    要求：
    1. 释义每条 20-50 字
    2. 输出严格的 JSON 数组格式，不要包含任何其他文字
    3. JSON 格式：[{{"term_ZH": "死水位", "definition": "释义"}}]

    术语列表：
    {term_name}"""

    try:
        llm = get_llm()
        term_names = []
        for item in need_full:
            term_names.append(item.term_ZH)

        prompt = prompt_template.format(term_name = term_names)
        response = llm.invoke(prompt)
        content = response.content.strip()
        content = content.strip("`").strip()
        if content.startswith("json"):
            content = content[:4].strip()
        data = json.loads(content)
        fill_map = {}
        for item in data:
            term = item["term_ZH"]
            definition = item["definition"]
            fill_map[term] = definition
        for item in need_full:
            if item.term_ZH in fill_map:
                item.definition = fill_map[item.term_ZH]
                item.definition_type = "llm生成"

        for term in terms:
            for item in need_full:
                if item.term_ZH == term.term_ZH:
                    term.definition = item.definition
                    term.definition_type = item.definition_type
        
        for term in terms:
            if term.definition.strip():
                if term.source_type == "regex":
                    term.definition_type = "原文"
                if term.source_type == "llm":
                    term.definition_type = "llm生成"
    except Exception as e:
        print(f"LLM 提取失败：{e}")

    return terms

if __name__ == "__main__":
    test_terms = [
    Term(term_ZH="机组台数", term_EN="", definition="单座电站安装的机组总台数。",
         page_num=1, confidence=0.9, source_type="regex", standard_name="测试"),
    Term(term_ZH="死水位", term_EN="", definition="",  # ← 没释义，需要补
         page_num=0, confidence=0.5, source_type="seed", standard_name="测试"),
    ]
    result = process_definitions(test_terms)
    for t in result:
        print(f"[{t.definition_type}] {t.term_ZH}: {t.definition}")
