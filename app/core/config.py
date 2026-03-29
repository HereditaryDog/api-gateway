from pydantic_settings import BaseSettings
from functools import lru_cache
from app.core.yaml_config import yaml_settings


class Settings(BaseSettings):
    """应用配置"""
    
    # 从 YAML 加载配置
    @classmethod
    def from_yaml(cls):
        config = yaml_settings
        return cls(
            # 数据库
            DATABASE_URL=cls._get_database_url(config),
            
            # Redis
            REDIS_URL=config.get('redis', {}).get('url', 'redis://localhost:6379/0'),
            
            # JWT
            SECRET_KEY=config.get('security', {}).get('jwt_secret', 'your-secret'),
            
            # 管理员
            ADMIN_USERNAME=config.get('admin', {}).get('username', 'admin'),
            ADMIN_PASSWORD=config.get('admin', {}).get('password', 'admin123'),
            
            # 平台信息
            PLATFORM_NAME="API Gateway",
            PLATFORM_URL="http://localhost:8000",
            
            # 日志
            LOG_LEVEL=config.get('logging', {}).get('level', 'INFO'),
            
            # 上游配置
            UPSTREAM_TIMEOUT=config.get('timeout', {}).get('request_timeout', 60),
            MAX_RETRIES=config.get('key_management', {}).get('max_retry', 2),
        )
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings.from_yaml()
