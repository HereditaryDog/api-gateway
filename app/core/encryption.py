"""
Fernet 加密工具
使用 Fernet 对称加密算法加密敏感数据（API Keys）
"""
import base64
from cryptography.fernet import Fernet
from app.core.config import get_settings

settings = get_settings()

# 生成/获取加密密钥
# 从环境变量或配置中获取，确保是 32 字节的 base64 编码
_encryption_key = settings.SECRET_KEY
if len(_encryption_key) < 32:
    _encryption_key = _encryption_key.ljust(32, '0')
elif len(_encryption_key) > 32:
    _encryption_key = _encryption_key[:32]

# 转换为 Fernet 需要的 base64 格式
ENCRYPTION_KEY = base64.urlsafe_b64encode(_encryption_key.encode())
fernet = Fernet(ENCRYPTION_KEY)


def encrypt_data(data: str) -> str:
    """加密数据"""
    if not data:
        return ""
    return fernet.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """解密数据"""
    if not encrypted_data:
        return ""
    try:
        return fernet.decrypt(encrypted_data.encode()).decode()
    except Exception:
        return ""
