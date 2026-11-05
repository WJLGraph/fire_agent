"""
全局配置 — 从环境变量 / .env 读取
"""
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 项目基本信息
    PROJECT_NAME: str = "焰哨多Agent与可视化平台"
    VERSION: str = "1.0.1"

    # 报告署名信息（自动追加到生成的每份分析报告末尾）
    REPORT_FOOTER: str = (
        "\n\n---\n\n"
        "> **系统与开发者信息**\n"
        "> - 系统名称：焰哨多Agent与可视化平台\n"
        "> - 开发者：wjl\n"
        "> - 联系邮箱：19136220923@163.com\n"
        "> - 后端源码：https://gitee.com/wjl2004/fire_agent_back\n"
        "> - 前端源码：https://gitee.com/wjl2004/fire_agent_front\n"
        "> - 在线演示：https://wjl2004.ffuf.cn/\n"
        "> - GitHub 仓库：https://github.com/wjl-cong/fire_agent (⭐ Star welcome!)\n"
    )

    # 运行环境：development（默认，保持向后兼容） / production
    # production 下强制校验 JWT_SECRET、关闭 API 文档路由
    ENV: str = "development"

    # JWT 认证（生产必须由 .env 提供强随机值；默认空 = 起不来，避免全网共享同一把签名密钥）
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    # 会话空闲上限：15 小时。滑动续期由 app.core.session 中间件负责——
    # 期间任意一次请求都会重新签发同 payload 的新 token（exp 再往后推 15h），
    # 因此「连续 15h 无任何请求」才会真正过期。
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15 * 60

    # 种子管理员初始口令（留空则生产环境不创建 admin，避免弱口令常驻）
    ADMIN_INIT_PASSWORD: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:4173"]

    # 数据库
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/fire_agent"

    # 高德地图 Key
    AMAP_KEY: str = ""

    # 活跃 LLM 提供商（aliyun | amd | ollama | longcat）
    ACTIVE_LLM_PROVIDER: str = "aliyun"

    # 模型 API — 阿里百炼（兼容 OpenAI 格式）
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = ""
    LLM_MODEL: str = "qwen-plus"
    EMBEDDING_MODEL: str = "qwen3.7-text-embedding-flash"
    # 视觉 / 语音模型（视觉、语音均可切换 aliyun/amd）
    VISION_PROVIDER: str = "aliyun"
    VISION_MODEL: str = "qwen-vl-plus"
    ASR_MODEL: str = "qwen3-asr-flash"
    TTS_PROVIDER: str = "aliyun"  # aliyun | amd
    TTS_MODEL: str = "qwen3-tts-flash"

    # 文档识别 OCR（PaddleOCR → MinerU2.5-Pro 云端增强（amd）→ RapidOCR 最后兜底）
    OCR_PROVIDER: str = "local"
    OCR_MODEL: str = "MinerU2.5-Pro"

    # 模型 API — AMD GPU Cloud（兼容 OpenAI 格式）
    AMD_API_KEY: str = ""
    AMD_API_BASE: str = "https://developer.amd.com.cn/radeon/v1"
    AMD_MODEL: str = "DeepSeek-V4-Flash"

    # 模型 API — 本地 Ollama（兼容 OpenAI 格式，无需 API Key）
    OLLAMA_API_BASE: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # 模型 API — LongCat（兼容 OpenAI 格式，仅 LLM）
    LONGCAT_API_KEY: str = ""
    LONGCAT_API_BASE: str = "https://api.longcat.chat/openai"
    LONGCAT_MODEL: str = "LongCat-2.5-Preview"

    # Qwen3.8-Flash-Next 可用时间窗口（空表示不限）
    QWEN3_8_FLASH_START: str = ""
    QWEN3_8_FLASH_END: str = ""

    # RAG 知识库
    KB_UPLOAD_DIR: str = "data/knowledge_base"
    KB_CHUNK_SIZE: int = 500
    KB_CHUNK_OVERLAP: int = 50
    KB_TOP_K: int = 5

    # Rerank 精排（阿里 DashScope text-rerank，使用 LLM_API_KEY；失败自动降级 RRF 融合原序）
    RERANK_ENABLED: bool = True
    RERANK_MODEL: str = "qwen3.7-text-rerank"

    # Agent 高级参数（P1）
    AGENT_REQUIRE_APPROVAL: bool = True  # 报告生成后需人工审批（HITL）才定稿

    # P2：全链路流式输出（报告/RAG 回答逐字推送；关闭后回退整段返回）
    LLM_STREAM_ENABLED: bool = True

    # P2：用户偏好长期记忆（PostgresStore，ReportAgent 注入；关闭后不读写偏好）
    PREFERENCES_ENABLED: bool = True

    # P2：Langfuse 私有化观测（需自建 Langfuse 服务；False 或未配密钥时降级纯日志）
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""

    # P2：MCP 工具化数据源（高德天气只读 server；未安装依赖或调用失败自动降级跳过）
    MCP_ENABLED: bool = True

    # AgentGauntlet 红队评测故障注入（W1；默认关闭零影响，仅评测时由评测进程以环境变量开启）
    GAUNTLET_CHAOS: bool = False
    GAUNTLET_FAULTS_PATH: str = ""
    GAUNTLET_SEED: int = 42
    # AgentGauntlet 攻击轮（W2）：system prompt 哨兵串——非空时注入报告生成提示词，
    # 供评测端 LEAKED_PROMPT 判定；评测完成后置空即恢复原状
    GAUNTLET_SYS_CANARY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()