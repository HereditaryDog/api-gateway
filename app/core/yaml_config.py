"""
YAML 配置加载
支持环境变量展开 ${ENV_VAR:-default}
"""
import os
import re
import yaml
from functools import lru_cache


def _load_dotenv():
    """加载 .env 文件"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    if not os.path.exists(env_path):
        return
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _expand_env(value):
    """展开环境变量 ${ENV_VAR:-default}"""
    if isinstance(value, str):
        def replacer(m):
            var = m.group(1)
            # 支持 ${VAR:-default} 语法
            if ':-' in var:
                var, default = var.split(':-', 1)
                return os.environ.get(var, default)
            return os.environ.get(var, m.group(0))
        return re.sub(r'\$\{([^}]+)\}', replacer, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(i) for i in value]
    return value


@lru_cache()
def load_yaml_config():
    """加载 YAML 配置文件"""
    # 先加载 .env
    _load_dotenv()
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config.yaml'
    )
    
    if not os.path.exists(config_path):
        # 返回默认配置
        return {
            'admin': {'username': 'admin', 'password': 'admin123'},
            'security': {'encryption_key': 'your-encryption-key-32-chars-long!', 'jwt_secret': 'your-secret'},
            'database': {'driver': 'sqlite', 'sqlite_path': './data/app.db'},
            'rate_limit': {'user_rpm': 60, 'provider_rpm': 30},
            'timeout': {'request_timeout': 60},
            'key_management': {'max_retry': 2},
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    
    return _expand_env(raw)


# 全局配置对象
yaml_settings = load_yaml_config()
