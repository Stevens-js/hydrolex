import os,yaml
from pathlib import Path
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

def _load_config():
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")
    with open(project_root / "config.yaml",encoding="utf-8") as f:
        return yaml.safe_load(f)
    
def get_llm():
    config = _load_config()
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_base_url = config["llm"]["base_url"]
    llm_model = config["llm"]["model"]
    llm_temperature = config["llm"]["temperature"]
    if not llm_api_key:
        raise ValueError("请在 .env 文件中设置 LLM_API_KEY")
    return ChatOpenAI(api_key=llm_api_key,base_url=llm_base_url,model=llm_model,temperature=llm_temperature)

def get_embeddings():
    config = _load_config()
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_base_url = config["llm"]["base_url"]
    embedding_model = config["embedding"]["model_name"]
    if not llm_api_key:
        raise ValueError("请在 .env 文件中设置 LLM_API_KEY")
    return embedding_functions.OpenAIEmbeddingFunction(api_key=llm_api_key,api_base=llm_base_url,model_name=embedding_model)


if __name__ == "__main__":
    llm = get_llm()
    em = get_embeddings()
    print(type(llm))
    print(type(em))