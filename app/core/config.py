import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.yaml_config import load_yaml_config


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def from_yaml(cls):
        config = load_yaml_config()
        defaults = {
            # 数据库
            "DATABASE_URL": cls._get_database_url(config),

            # Redis
            "REDIS_URL": config.get('redis', {}).get('url', 'redis://localhost:6379/0'),

            # JWT
            "SECRET_KEY": config.get('security', {}).get('jwt_secret', 'your-secret'),
            "ALGORITHM": config.get('security', {}).get('algorithm', 'HS256'),
            "ACCESS_TOKEN_EXPIRE_MINUTES": config.get('security', {}).get('access_token_expire_minutes', 10080),

            # 管理员
            "ADMIN_USERNAME": config.get('admin', {}).get('username', 'admin'),
            "ADMIN_PASSWORD": config.get('admin', {}).get('password', 'admin123'),

            # 平台信息
            "PLATFORM_NAME": config.get('platform', {}).get('name', 'API Gateway'),
            "PLATFORM_URL": config.get('platform', {}).get('url', 'http://localhost:8000'),

            # 日志
            "LOG_LEVEL": config.get('logging', {}).get('level', 'INFO'),

            # 配额
            "DEFAULT_QUOTA_K": config.get('quota', {}).get('default_quota_k', 1000),

            # 上游配置
            "UPSTREAM_TIMEOUT": config.get('timeout', {}).get('request_timeout', 60),
            "MAX_RETRIES": config.get('key_management', {}).get('max_retry', 2),
        }

        # BaseSettings 无法覆盖显式传入的 init kwargs，这里手动让环境变量拥有更高优先级。
        for field_name in cls.model_fields:
            if field_name in os.environ:
                defaults[field_name] = os.environ[field_name]

        return cls.model_validate(defaults)
    
    @staticmethod
    def _get_database_url(config: dict) -> str:
        """根据配置生成数据库 URL"""
        driver = config.get('database', {}).get('driver', 'sqlite')
        
        if driver == 'postgresql':
            host = config.get('database', {}).get('host', 'localhost')
            port = config.get('database', {}).get('port', 5432)
            user = config.get('database', {}).get('user', 'postgres')
            password = config.get('database', {}).get('password', 'postgres')
            name = config.get('database', {}).get('name', 'apigateway')
            return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
        else:
            # SQLite - 使用绝对路径避免路径问题
            import os
            path = config.get('database', {}).get('sqlite_path', './data/app.db')
            # 确保目录存在
            db_dir = os.path.dirname(os.path.abspath(path))
            os.makedirs(db_dir, exist_ok=True)
            return f"sqlite+aiosqlite:///{os.path.abspath(path)}"
    
    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./apigateway.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    SECRET_KEY: str = "your-super-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7天
    
    # 管理员
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    
    # 平台信息
    PLATFORM_NAME: str = "API Gateway"
    PLATFORM_URL: str = "http://localhost:8000"
    
    # 日志
    LOG_LEVEL: str = "INFO"
    
    # 配额
    DEFAULT_QUOTA_K: int = 1000  # 默认1000千tokens
    
    # 上游配置
    UPSTREAM_TIMEOUT: int = 60
    MAX_RETRIES: int = 2
    
@lru_cache()
def get_settings() -> Settings:
    return Settings.from_yaml()
