from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.core.config import get_settings
from app.core.bootstrap import ensure_admin_user
from app.core.database import init_db
from app.routers import auth_router, users_router, upstream_router, usage_router, proxy_router, risk_admin_router, invite_admin_router
from app.middleware.gateway_risk import GatewayRiskMiddleware
from app.__version__ import __version__, __title__, __description__

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    await init_db()
    created_admin = await ensure_admin_user()
    if created_admin:
        print(f"[START] Admin user '{settings.ADMIN_USERNAME}' created.")
    print(f"[START] {settings.PLATFORM_NAME} started!")
    yield
    # 关闭时执行
    print("[STOP] Server shutting down...")


app = FastAPI(
    title=__title__,
    description=__description__,
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全站风控中间件
app.add_middleware(GatewayRiskMiddleware)

# 注册路由
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(upstream_router, prefix="/api")
app.include_router(usage_router, prefix="/api")
app.include_router(risk_admin_router, prefix="/api")
app.include_router(invite_admin_router, prefix="/api")
app.include_router(proxy_router)  # OpenAI 兼容接口，不需要 /api 前缀

# 挂载静态文件
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def serve_frontend():
    """服务前端页面"""
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "API Gateway is running", "docs": "/docs"}


@app.get("/admin.html")
async def serve_admin():
    """服务管理端页面"""
    admin_path = os.path.join(frontend_path, "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    raise HTTPException(status_code=404, detail="Admin page not found")


@app.get("/api")
async def api_root():
    """API 根路径"""
    return {
        "name": __title__,
        "version": __version__,
        "description": __description__,
        "docs": "/docs",
        "health": "/health",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.get("/v1/health")
async def openai_health_check():
    """OpenAI 格式的健康检查"""
    return {"status": "ok"}
