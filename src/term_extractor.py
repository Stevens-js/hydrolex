from dataclasses import dataclass
import re
from pathlib import Path
from llm_factory import _load_config,get_llm
from pdf_parser import ParsedPage, parse_pdf
import json

@dataclass
class Term:
    term_ZH: str              # 中文术语名，如"机组台数"
    term_EN: str              # 英文术语名，如有，如"number of units"
    definition: str           # 释义
    page_num: int             # 来源页码
    confidence: float         # 置信度 0-1
    source_type: str          # "regex" / "llm" / "seed"
    standard_name: str = ""   # 来源规范名称
    definition_type: str = "" # 释义来源 "原文" / "llm生成" / "人工补充" / ""

pattern = re.compile(r'^\s*(\d+(?:\.\d+)*)\s+(.+?)(?:\s{2,}(.*))?$')

def _is_top_level_heading(line: str) -> bool:
    """判断是否是一级标题（如 '4 规划'），用来检测术语章节结束"""
    parts = line.split()
    if len(parts) < 2:
        return False
    first = parts[0]
    if first.isdigit() and len(first) <= 2:
        return True
    return False

def splitCnEn(s):
    pat = re.compile(r'^([\u4e00-\u9fa5\s]+?)\s+(.*)$')
    m = pat.match(s.strip())
    if m:
        cn = m.group(1).strip()
        en = m.group(2).strip()
        return cn, en
    else:
        return s.strip(), ""

def extract_terms(pages: list[ParsedPage], use_llm: bool = False, standard_name: str = "") -> list[Term]:
    """从已解析的页面中提取术语

    Args:
        pages: parse_pdf 的输出
        use_llm: 是否启用 LLM 补充提取（默认关闭，先跑正则）

    Returns:
        提取到的术语列表
    """
    config = _load_config()
    keyword = config["extraction"]["term_chapter_keyword"]

    terms: list[Term] = []
    in_term_chapter = False          # 是否在术语章节内
    current_term: str | None = None  # 当前正在收集的术语名
    current_definition_lines: list[str] = []  # 当前释义的行（可能多行）
    current_page_num = 1             # 当前术语所在的页码

    def save_current():
        """把当前累积的术语打包存入 terms 列表"""
        nonlocal current_term, current_definition_lines
        if current_term is not None and current_definition_lines:
            definition = " ".join(current_definition_lines).strip()
            cn,en = splitCnEn(current_term)
            terms.append(Term(
                term_ZH=cn,
                term_EN=en,
                definition=definition,
                page_num=current_page_num,
                confidence=0.9,
                source_type="regex",
                standard_name=standard_name
            ))
        current_term = None
        current_definition_lines = []

    for page in pages:
        lines = page.text.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 1. 检测术语章节起点（含关键词的行）
            if keyword in line:
                in_term_chapter = True
                continue

            # 2. 不在术语章节，跳过
            if not in_term_chapter:
                continue

            # 3. 检测是否离开术语章节（遇到一级标题如 "4 规划"）
            if _is_top_level_heading(line):
                save_current()
                in_term_chapter = False
                continue

            # 4. 用正则匹配条款号行
            match = pattern.match(line)
            if match:
                save_current()
                current_term = match.group(2).strip()
                current_page_num = page.page_num
                inline_definition = match.group(3)
                if inline_definition:
                    current_definition_lines.append(inline_definition.strip())
            else:
                if current_term is not None:
                    current_definition_lines.append(line)

    save_current()

    # 策略 2：LLM 补充提取（待实现，见任务）
    if use_llm:

        lines = []
        for page in pages:
            lines.append(f"[第{page.page_num}页]\n{page.text}\n")
        joint_text= "\n".join(lines)                
        chunk_size = 4000
        chunks = []
        for num in range(0,len(joint_text),chunk_size):
            chunks.append(joint_text[num:num + chunk_size])
        prompt_template = """你是一位抽水蓄能行业的规范审查专家。请从下面的规范正文中提取行业术语及其释义。

        要求：
        1. 只提取真正的行业专有名词（如装机容量、机组台数、水头、库容等）
        2. 释义用规范原文中的表述，如果原文没有明确释义，则根据上下文给出简短解释
        3. 输出严格的 JSON 数组格式，不要包含任何其他文字
        4. JSON 格式：[{{"term_ZH": "中文术语", "term_EN": "英文术语(没有则空字符串)", "definition": "释义"}}]

        规范正文：
        {content}"""
        llm = get_llm()
        for chunk in chunks:
            prompt = prompt_template.format(content=chunk)
            try:
                response = llm.invoke(prompt)
                content = response.content.strip()
                content = content.strip("`").strip()
                if content.startswith("json"):
                    content = content[4:].strip()
                data = json.loads(content)
                existing = {t.term_ZH for t in terms}
                for item in data:
                    zh = item.get("term_ZH", "").strip()
                    if zh and zh not in existing:
                        terms.append(Term(
                            term_ZH=item.get("term_ZH","").strip(),
                            term_EN=item.get("term_EN","").strip(),
                            definition=item.get("definition","").strip(),
                            page_num=0,
                            confidence=0.6,
                            source_type="llm",
                            standard_name=standard_name
                        ))
                        existing.add(zh)
            except Exception as e:
                print(f"LLM 提取失败：{e}")
                continue

    return terms


if __name__ == "__main__":
    from pdf_parser import get_standard_name

    # === 测试 1：假数据（验证正则逻辑）===
#     test_pages = [ParsedPage(
#         page_num=1,
#         text="""3 术语和定义
# 3.1 机组台数 number of units
# 单座电站安装的机组总台数。
# 含备用机组。
# 3.2 装机容量  电站各台机组铭牌容量的总和。
# 3.3 水头  电站上游与下游水位的高程差。
# 4 规划
# """
#     )]
#     terms = extract_terms(test_pages, standard_name="测试规范")
#     print("=== 假数据测试（混合格式）===")
#     for t in terms:
#         print(f"[{t.source_type}] {t.term_ZH} ({t.term_EN}): {t.definition} | 来源:{t.standard_name} (p{t.page_num}, conf={t.confidence})")

    # === 测试 2：真实 PDF（需要 data/pdfs/练习.pdf 存在）===
    pdf_path = Path(__file__).parent.parent / "data" / "pdfs" / "练习.pdf"
    if pdf_path.exists():
        print(f"\n=== 真实 PDF 测试: {pdf_path.name} ===")
        std_name = get_standard_name(str(pdf_path))
        real_pages = parse_pdf(str(pdf_path))
        real_terms = extract_terms(real_pages, use_llm=True, standard_name=std_name)
        print(f"共提取 {len(real_terms)} 条术语:")
        for t in real_terms:
            print(f"[{t.source_type}] {t.term_ZH}: {t.definition[:50]}... | 来源:{t.standard_name} (p{t.page_num})")
    else:
        print(f"\n真实 PDF 不存在: {pdf_path}，跳过")
