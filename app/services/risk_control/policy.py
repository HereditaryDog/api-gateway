from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskPolicy:
    global_qps: float = 30.0
    global_burst: int = 30
    ip_requests_per_minute: int = 120
    auth_ip_requests_per_minute: int = 20
    default_user_requests_per_minute: int = 60
    exempt_paths: tuple[str, ...] = (
        "/health",
        "/v1/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
        "/admin.html",
    )
    exempt_prefixes: tuple[str, ...] = ("/static/",)
    sensitive_paths: tuple[str, ...] = (
        "/v1/chat/completions",
        "/v1/completions",
    )

    def is_exempt(self, path: str) -> bool:
        if path in self.exempt_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.exempt_prefixes)

    def is_auth_path(self, path: str) -> bool:
        return path in {"/api/auth/login", "/api/auth/register"}

    def should_check_sensitive(self, path: str, method: str) -> bool:
        return method.upper() == "POST" and path in self.sensitive_paths
