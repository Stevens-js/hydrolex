import gradio as gr
from pathlib import Path
from graph import build_graph
from pdf_parser import get_standard_name
from term_extractor import Term
from vector_store import upsert_terms, query_term, show_allterms

# 全局状态：保存当前提取到的术语
current_terms: list[Term] = []

def on_upload(pdf_file):
    global current_terms

    app = build_graph()
    config = {"configurable": {"thread_id": "1"}}

    pdf_path = str(pdf_file)
    
    std_name = get_standard_name(pdf_path)
    
    initial = {
        "pdf_path": pdf_path,
        "standard_name": std_name,
        "pages": [],
        "terms": [],
        "confirmed": False
    }
    
    result = app.invoke(initial, config=config)
    current_terms = result["terms"]

    table_data = []
    # 2. 转成表格数据
    for idx,term in enumerate(current_terms,1):
        table_data.append([idx,term.term_ZH, term.definition, term.source_type, term.definition_type, True])
    
    return table_data, f"提取到 {len(current_terms)} 条术语，请确认"

def on_confirm(table_data):
    global current_terms

    selected_terms = []
    for row in table_data.itertuples(index=False):
        # row 是 namedtuple，字段名对应 headers
        # row._0=术语, row._1=释义, row._2=来源, row._3=释义类型, row._4=保留
        term_zh = row[0]
        definition = row[1]
        source_type = row[2]
        definition_type = row[3]
        checked = row[4]

        if checked:
            for t in current_terms:
                if t.term_ZH == term_zh:
                    t.definition = definition
                    if definition_type:
                        t.definition_type = definition_type
                    selected_terms.append(t)
                    break

    upsert_terms(selected_terms)
    return f"已入库 {len(selected_terms)} 条术语"

def on_show_all():
    terms: list[Term] = show_allterms()
    table_data = [
        [idx, t["term_ZH"], t["definition"], t["source_type"], t["definition_type"]]
        for idx, t in enumerate(terms, 1)
    ]
    return table_data, f"共 {len(terms)} 条术语"
    
        
def create_ui():
    with gr.Blocks() as demo:
        gr.Markdown("# 抽水蓄能规范术语提取")
        
        pdf_input = gr.File(label="上传规范 PDF", file_types=[".pdf"])
        extract_btn = gr.Button("提取术语")
        
        term_table = gr.Dataframe(
            headers=["术语", "释义", "来源", "释义类型", "保留"],
            datatype=["str", "str", "str", "str", "bool"],
            interactive=True,
            label="术语列表"
        )

        
        confirm_btn = gr.Button("确认入库")
        status_text = gr.Textbox(label="状态", interactive=False)
        showallterm_btn = gr.Button("显示所有术语")
        allterm_table = gr.Dataframe(
                            headers=["序号","术语", "释义", "来源", "释义类型"],
                            datatype=["int","str", "str", "str", "str"],
                            interactive=True,
                            label="术语列表"
                        )
        txt_out = gr.Textbox(label="汇总信息")

        
        # 绑定事件
        extract_btn.click(
            fn=on_upload,
            inputs=pdf_input,
            outputs=[term_table, status_text]
        )
        confirm_btn.click(
            fn=on_confirm,
            inputs=term_table,
            outputs=status_text
        )
        showallterm_btn.click(
            fn=on_show_all,
            inputs=None,
            outputs=[allterm_table, txt_out]
        )

    
    return demo

if __name__ == "__main__":
    demo = create_ui()
    demo.launch()