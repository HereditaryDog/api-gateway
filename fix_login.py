#!/usr/bin/env python3
"""
修复登录问题 - 直接操作数据库创建用户
"""
import sqlite3
import os
from passlib.context import CryptContext

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_db():
    """初始化数据库表"""
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect('data/app.db')
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            hashed_password TEXT NOT NULL,
            api_key TEXT UNIQUE,
            points_balance REAL DEFAULT 0,
            total_quota REAL DEFAULT 1000,
            used_quota REAL DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            is_admin BOOLEAN DEFAULT 0,
            rate_limit INTEGER DEFAULT 60,
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            last_used_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn, cursor

def create_admin():
    """创建管理员账号"""
    conn, cursor = init_db()
    
    # 检查是否已有admin用户
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    existing = cursor.fetchone()
    
    if existing:
        print("[INFO] 管理员已存在，更新密码...")
        # 更新密码
        hashed = pwd_context.hash("admin123")
        cursor.execute(
            "UPDATE users SET hashed_password = ?, is_active = 1 WHERE username = 'admin'",
            (hashed,)
        )
    else:
        print("[INFO] 创建新管理员...")
        # 生成API Key
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        api_key = "sk-" + "".join(secrets.choice(alphabet) for _ in range(48))
        
        # 创建用户
        hashed = pwd_context.hash("admin123")
        cursor.execute('''
            INSERT INTO users (username, email, hashed_password, api_key, points_balance, is_active, is_admin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("admin", "admin@example.com", hashed, api_key, 10000, 1, 1))
    
    conn.commit()
    conn.close()
    print("[OK] 管理员账号修复完成！")
    print("   用户名: admin")
    print("   密码: admin123")

if __name__ == "__main__":
    create_admin()
