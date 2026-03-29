"""
数据库迁移脚本 - 添加 Coding Plan 支持

运行方式:
    cd api-gateway && python migrate_coding_plan.py
"""
import asyncio
import sqlite3
from pathlib import Path


def migrate_database(db_path: str = "./data/app.db"):
    """执行数据库迁移"""
    
    print(f"Migrating database: {db_path}")
    
    # 确保目录存在
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 创建 provider_billing_configs 表
        print("Creating provider_billing_configs table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS provider_billing_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                billing_mode VARCHAR(20) NOT NULL DEFAULT 'token',
                cost_per_request DECIMAL(10, 6) DEFAULT 0,
                price_per_request DECIMAL(10, 6) DEFAULT 0,
                subscription_type VARCHAR(50),
                quota_window_type VARCHAR(20),
                quota_requests INTEGER DEFAULT 0,
                quota_reset_cron VARCHAR(50),
                enable_risk_control BOOLEAN DEFAULT FALSE,
                min_qps_limit DECIMAL(5, 2) DEFAULT 0.5,
                max_qps_limit DECIMAL(5, 2) DEFAULT 2.0,
                jitter_ms_min INTEGER DEFAULT 100,
                jitter_ms_max INTEGER DEFAULT 500,
                remark TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        
        # 添加索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_billing_config_provider 
            ON provider_billing_configs(provider_id)
        """)
        
        # 2. 创建 upstream_key_quotas 表
        print("Creating upstream_key_quotas table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS upstream_key_quotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id INTEGER NOT NULL,
                window_5h_used INTEGER DEFAULT 0,
                window_5h_limit INTEGER DEFAULT 6000,
                window_5h_reset_at TIMESTAMP,
                window_week_used INTEGER DEFAULT 0,
                window_week_limit INTEGER DEFAULT 45000,
                window_week_reset_at TIMESTAMP,
                window_month_used INTEGER DEFAULT 0,
                window_month_limit INTEGER DEFAULT 90000,
                window_month_reset_at TIMESTAMP,
                is_throttled BOOLEAN DEFAULT FALSE,
                throttle_until TIMESTAMP,
                consecutive_errors INTEGER DEFAULT 0,
                last_error_at TIMESTAMP,
                avg_response_time_ms REAL DEFAULT 0.0,
                success_rate REAL DEFAULT 1.0,
                updated_at TIMESTAMP
            )
        """)
        
        # 添加索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_key_quota_key 
            ON upstream_key_quotas(key_id)
        """)
        
        # 3. 创建 request_logs 表
        print("Creating request_logs table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                upstream_key_id INTEGER,
                request_id VARCHAR(64),
                model VARCHAR(100),
                provider_type VARCHAR(50),
                billing_mode VARCHAR(20),
                cost_amount DECIMAL(10, 6) DEFAULT 0,
                charge_amount DECIMAL(10, 6) DEFAULT 0,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                error_code VARCHAR(50),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 添加索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_request_logs_user 
            ON request_logs(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_request_logs_created 
            ON request_logs(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_request_logs_model 
            ON request_logs(model)
        """)
        
        # 4. 修改 upstream_providers 表
        print("Modifying upstream_providers table...")
        
        # 检查列是否存在
        cursor.execute("PRAGMA table_info(upstream_providers)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'adapter_type' not in columns:
            cursor.execute("""
                ALTER TABLE upstream_providers 
                ADD COLUMN adapter_type VARCHAR(50) DEFAULT 'standard'
            """)
            print("  - Added adapter_type column")
        
        if 'risk_pool_size' not in columns:
            cursor.execute("""
                ALTER TABLE upstream_providers 
                ADD COLUMN risk_pool_size INTEGER DEFAULT 1
            """)
            print("  - Added risk_pool_size column")
        
        conn.commit()
        print("\nMigration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def rollback_migration(db_path: str = "./data/app.db"):
    """回滚迁移（危险操作，仅用于测试）"""
    
    print(f"Rolling back migration: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 删除新创建的表
        cursor.execute("DROP TABLE IF EXISTS provider_billing_configs")
        cursor.execute("DROP TABLE IF EXISTS upstream_key_quotas")
        cursor.execute("DROP TABLE IF EXISTS request_logs")
        
        # SQLite 不支持删除列，需要重建表
        # 这里简化处理，实际生产环境需要更复杂的回滚逻辑
        
        conn.commit()
        print("Rollback completed!")
        
    except Exception as e:
        conn.rollback()
        print(f"Rollback failed: {e}")
        raise
    finally:
        conn.close()


def verify_migration(db_path: str = "./data/app.db"):
    """验证迁移结果"""
    
    print(f"Verifying migration: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    tables = [
        'provider_billing_configs',
        'upstream_key_quotas',
        'request_logs'
    ]
    
    print("Checking new tables:")
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        exists = cursor.fetchone() is not None
        print(f"  - {table}: {'✓' if exists else '✗'}")
    
    # 检查上游 providers 表的新列
    print("\nChecking upstream_providers columns:")
    cursor.execute("PRAGMA table_info(upstream_providers)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_columns = ['adapter_type', 'risk_pool_size']
    for col in new_columns:
        exists = col in columns
        print(f"  - {col}: {'✓' if exists else '✗'}")
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    elif len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_migration()
    else:
        migrate_database()
        print()
        verify_migration()
