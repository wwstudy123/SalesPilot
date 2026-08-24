"""命令行灌入 M5 知识库种子，供 make seed 和冷启动演示使用。"""

from sale_agent.ai.gateway import LLMGateway
from sale_agent.kb.seed_data import load_seed
from sale_agent.kb.store import KnowledgeStore
from sale_agent.kb.vector_store import build_vector_backend


def main() -> None:
    gateway = LLMGateway()
    vector_backend = build_vector_backend(embed_fn=gateway.embed)
    result = load_seed(KnowledgeStore(vector_backend=vector_backend))
    print(f"Knowledge base seeded: {result['stats']['ready_chunks']} ready chunks")


if __name__ == "__main__":
    main()
