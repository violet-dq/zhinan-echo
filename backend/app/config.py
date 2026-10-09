"""全局配置：读取 .env / 环境变量，所有外部依赖均可留空并自动降级。"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "知南·Echo"
    app_desc: str = "学习DDL与资料管理智能体"

    # LLM（OpenAI 兼容协议，DeepSeek 原生支持 function calling / tool_calls）
    llm_api_base: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_fast_model: str = "deepseek-chat"   # DeepSeek 无独立轻量模型，主模型即可
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048

    # Embedding（OpenAI 兼容协议，推荐 SiliconFlow BGE-M3）
    embedding_api_base: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # 数据库：默认 SQLite，生产可切 PostgreSQL（与报名表技术路线一致）
    database_url: str = "sqlite:///./data/zhinan.db"

    jwt_secret: str = "zhinan-echo-dev-secret-change-me"
    jwt_expire_hours: int = 72

    # 邮件提醒（可选）
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""

    data_dir: str = "./data"
    max_upload_mb: int = 50

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.strip())

    @property
    def embedding_enabled(self) -> bool:
        return bool(self.embedding_api_key.strip())

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_user.strip())

    def ensure_dirs(self) -> None:
        for sub in ("uploads", "vector_store", "exports"):
            os.makedirs(os.path.join(self.data_dir, sub), exist_ok=True)
        os.makedirs(os.path.dirname(self.database_url.split("///")[-1]) or ".", exist_ok=True)


settings = Settings()
