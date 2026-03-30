"""
认证路由
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.services.registration_service import RegistrationService
from app.services.user_service import UserService
from app.schemas.auth import EmailCodeRequest, EmailCodeResponse, RegisterRequest, RegisterResponse
from app.schemas.user import UserCreate, UserResponse, UserLoginResponse

router = APIRouter(prefix="/auth", tags=["认证"])
settings = get_settings()


@router.post("/login", response_model=UserLoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """用户登录获取 Token"""
    # 查找用户
    user = await UserService.get_user_by_username(db, form_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证密码
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账号已被禁用"
        )
    
    # 生成 Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "is_admin": user.is_admin
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)
    }


@router.post("/send-email-code", response_model=EmailCodeResponse)
async def send_email_code(
    payload: EmailCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    existing_user = await UserService.get_user_by_email(db, payload.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    _, code = await RegistrationService.create_email_code(db, str(payload.email))

    debug_code = None
    host = request.headers.get("host", "")
    if host.startswith("127.0.0.1") or host.startswith("localhost"):
        debug_code = code

    return {
        "message": "验证码已发送",
        "expires_in_seconds": RegistrationService.EMAIL_CODE_TTL_MINUTES * 60,
        "debug_code": debug_code,
    }


@router.post("/register", response_model=RegisterResponse)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""

    existing_user = await UserService.get_user_by_username(db, payload.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被注册")

    existing_email = await UserService.get_user_by_email(db, str(payload.email))
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

    existing_phone = await UserService.get_user_by_phone(db, payload.phone)
    if existing_phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号已被注册")

    try:
        invite_code = await RegistrationService.validate_invite_code(db, payload.invite_code)
        email_code = await RegistrationService.verify_email_code(db, str(payload.email), payload.email_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = await UserService.create_user(
        db,
        UserCreate(
            username=payload.username,
            password=payload.password,
            email=str(payload.email),
            phone=payload.phone,
            total_quota=0.0,
            is_admin=False,
        )
    )
    user.email_verified = True

    await RegistrationService.consume_email_code(db, email_code)
    await RegistrationService.consume_invite_code(db, invite_code, user)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "is_admin": user.is_admin
        },
        expires_delta=access_token_expires
    )
    await db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)
    }
