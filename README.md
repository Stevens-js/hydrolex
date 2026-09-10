# HydroLex

> 抽水蓄能行业规范术语提取与向量库管理 Agent

从 GB/T、NB/T 等行业规范 PDF 中自动提取术语及释义，经人工确认后存入向量库，支持多规范汇聚，供后续 RAG 问答 agent 调用。

## 功能特性

- **PDF 解析**：自动判断文本型/扫描件，文本型用 pdfplumber 直读，扫描件走 PaddleOCR（待实现）
- **术语提取**：正则提取规范"术语和定义"章节 + LLM 补充正文术语，支持多行释义、行内释义、带英文术语三种格式
- **释义处理**：原文释义优先，缺失则 LLM 生成，标注来源（原文/llm生成/人工补充）
- **向量库**：Chroma 持久化存储，同名术语多规范汇聚，保留多来源释义
- **LangGraph 编排**：状态机串联提取→确认→入库，支持 human-in-the-loop 暂停/恢复
- **Gradio 界面**：上传 PDF → 提取术语 → 表格勾选/编辑 → 确认入库 → 查看所有术语

## 技术栈

| 环节 | 技术 |
|---|---|
| 编排 | LangGraph（状态机 + human-in-the-loop） |
| LLM | LangChain + OpenAI 兼容协议（通义千问/GLM/DeepSeek 均可） |
| PDF 解析 | pdfplumber（文本型） |
| 向量库 | ChromaDB |
| Embedding | 云端 API（text-embedding-v2） |
| Web 界面 | Gradio |
| 语言 | Python 3.10+ |

## 项目结构

```
hydrolex/
├── src/
│   ├── __init__.py
│   ├── llm_factory.py            # LLM + Embedding 工厂函数
│   ├── pdf_parser.py             # PDF 解析（文本型 + OCR 占位）
│   ├── term_extractor.py         # 术语提取（正则 + LLM）
│   ├── definition_processor.py  # 释义补全
│   ├── vector_store.py           # Chroma 向量库 + 多规范汇聚
│   ├── graph.py                  # LangGraph 状态机编排
│   └── ui.py                     # Gradio Web 界面
├── data/
│   ├── pdfs/                     # 输入 PDF
│   ├── parsed/                  # 解析缓存（待实现）
│   └── chroma/                  # 向量库持久化
├── config.yaml                  # 配置文件
├── .env.example                 # 环境变量示例
├── .gitignore
└── requirements.txt
```

## 快速开始

### 1. 安装依赖

```bash
cd Practice/hydrolex
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` 为 `.env`，填入你的 API key：

```
LLM_API_KEY=your-api-key-here
```

修改 `config.yaml` 中的 `llm.provider`、`llm.model`、`llm.base_url` 为你使用的云 LLM 配置。

### 3. 运行

#### 方式一：Web 界面（推荐）

```bash
python -m src.ui
```

浏览器打开 `http://127.0.0.1:7860`，上传 PDF → 提取术语 → 确认入库。

#### 方式二：命令行（测试用）

```bash
python -m src.graph
```

会用 `data/pdfs/` 下的 PDF 跑完整流程，在控制台输出提取结果。

### 4. 查询术语

```python
from src.vector_store import query_term

result = query_term("机组台数")
print(result)
# {
#     'term_ZH': '机组台数',
#     'standard_names': ['GB/T 规范A', 'NB/T 规范B'],
#     'definitions': [
#         {'standard': 'GB/T 规范A', 'definition': '...', 'definition_type': '原文'},
#         {'standard': 'NB/T 规范B', 'definition': '...', 'definition_type': '原文'}
#     ]
# }
```

## 数据流

```
PDF 文件
    │
    ▼ parse_pdf()
list[ParsedPage]                    # 带页码的文本
    │
    ▼ extract_terms()
list[Term]                          # 术语 + 释义 + 来源
    │
    ▼ process_definitions()
list[Term]                          # 补全释义 + 标注来源类型
    │
    ▼ [interrupt: 等待用户确认]
    │
    ▼ upsert_terms()
Chroma 向量库                       # 多规范汇聚存储
```

## LangGraph 状态机

```
[START] → parse_pdf → extract_terms → process_definitions → [INTERRUPT] → upsert → [END]
```

在 `upsert` 节点前暂停，等待用户在 Gradio 界面确认后恢复执行。

## 数据结构

### Term（术语记录）

```python
@dataclass
class Term:
    term_ZH: str               # 中文术语名
    term_EN: str               # 英文术语名
    definition: str            # 释义
    page_num: int              # 来源页码
    confidence: float         # 置信度（正则 0.9，LLM 0.6）
    source_type: str           # "regex" / "llm" / "seed"
    standard_name: str = ""    # 规范名称
    definition_type: str = ""  # "原文" / "llm生成" / "人工补充"
```

### Chroma 元数据

```python
{
    "term_ZH": "机组台数",
    "term_EN": "number of units",
    "standard_names": ["GB/T XXX", "NB/T YYY"],   # 多规范来源
    "definitions": [                                # 多来源释义
        {"standard": "GB/T XXX", "definition": "...", "definition_type": "原文"},
        {"standard": "NB/T YYY", "definition": "...", "definition_type": "原文"}
    ],
    "page_num": 5,
    "confidence": 0.9,
    "source_type": "regex",
    "definition_type": "原文"
}
```

## 后续规划

- [ ] PaddleOCR 接入扫描件 PDF 解析
- [ ] 种子词表（Excel）正文匹配
- [ ] 带重叠切块优化 LLM 提取召回率
- [ ] RAG 问答 agent（基于向量库回答术语查询）
- [ ] 飞书卡片审批流确认

## 设计要点

### 模块解耦

每个模块只做单一职责，通过函数签名传递数据，不直接互相调用：

- `parse_pdf(path) -> list[ParsedPage]`
- `extract_terms(pages) -> list[Term]`
- `process_definitions(terms) -> list[Term]`
- `upsert_terms(terms) -> None`

编排逻辑集中在 `graph.py`，业务模块可独立测试。

### LLM 抽象层

所有 LLM 调用通过 `llm_factory.get_llm()` 获取实例，配置集中在 `config.yaml` + `.env`。切换 provider（通义/GLM/DeepSeek）只需改配置，业务代码不动。

### 多规范汇聚

同一术语在不同规范中的释义可能不同。入库时按 `term_ZH` 作为唯一 ID，合并 `standard_names` 和 `definitions` 列表，保留所有来源释义。查询时返回多来源，方便 RAG 问答引用具体规范条款。

## License

MIT
