from dataclasses import dataclass
from pathlib import Path
import pdfplumber


@dataclass
class ParsedPage:
    page_num: int
    text: str


def get_standard_name(pdf_path: str) -> str:
    """从 PDF 文件路径中提取规范名称（文件名不含后缀）"""
    return Path(pdf_path).stem


def parse_pdf(pdf_path: str) -> list[ParsedPage]:
    """自动判断 PDF 类型并解析，返回每页的文本"""
    pages = []
    with pdfplumber.open(pdf_path) as pdf :
        for page_num,page in enumerate(pdf.pages,1):
            text = page.extract_text() or ""
            parsed_page = ParsedPage(page_num=page_num,text=text)
            pages.append(parsed_page)
    total_chars = sum(len(page.text) for page in pages)
    if len(pages) > 0:
        avg_chars = total_chars / len(pages)
    else :
        raise ValueError("PDF 解析失败：未提取到任何页面")
    if avg_chars < 10:
        raise NotImplementedError("OCR 功能待实现")
    return pages

if __name__ == "__main__":
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    pdfs_path =  project_root / "data" / "pdfs" / "AIAgent入门.pdf"
    pages = parse_pdf(pdfs_path)
    for page in pages:
        print(page.text)
        print(page.page_num)
    

    
