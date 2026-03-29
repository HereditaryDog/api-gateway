from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.core.config import get_settings
from app.core.database import init_db
from app.routers import auth_router, users_router, upstream_router, usage_router, proxy_router
from app.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    await init_db()
    print(f"[START] {settings.PLATFORM_NAME} started!")
    yield
    # 关闭时执行
    print("[STOP] Server shutting down...")


app = FastAPI(
    title=settings.PLATFORM_NAME,
    description="API Gateway - 聚合多个 LLM 服务商的 API 转发平台",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 速率限制中间件
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# 注册路由
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(upstream_router, prefix="/api")
app.include_router(usage_router, prefix="/api")
app.include_router(proxy_router)  # OpenAI 兼容接口，不需要 /api 前缀

# 挂载静态文件
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def serve_frontend():
    """服务前端页面"""
    # 优先返回运维监控后台
    admin_path = os.path.join(frontend_path, "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    return {"message": "API Gateway is running", "docs": "/docs"}


@app.get("/api")
async def api_root():
    """API 根路径"""
    return {
        "name": settings.PLATFORM_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.get("/v1/health")
async def openai_health_check():
    """OpenAI 格式的健康检查"""
    return {"status": "ok"}
