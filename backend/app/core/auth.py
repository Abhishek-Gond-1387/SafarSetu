"""Supabase JWT authentication and token verification dependency."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)

# HTTP Bearer scheme with manual error handling for explicit 401 messages
security = HTTPBearer(auto_error=False)

_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> Optional[PyJWKClient]:
    """Lazy initialize and cache PyJWKClient for Supabase asymmetric key verification."""
    global _jwks_client
    if _jwks_client is None and settings.SUPABASE_URL:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        try:
            _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
        except Exception as e:
            logger.warning(f"Could not initialize PyJWKClient for {jwks_url}: {e}")
            _jwks_client = None
    return _jwks_client


def reset_jwks_client() -> None:
    """Reset the cached JWKS client (primarily for testing)."""
    global _jwks_client
    _jwks_client = None


@dataclass
class AuthenticatedUser:
    """Authenticated Supabase user context extracted from verified JWT."""
    id: UUID
    email: Optional[str] = None
    role: str = "authenticated"
    app_metadata: Dict[str, Any] = field(default_factory=dict)
    user_metadata: Dict[str, Any] = field(default_factory=dict)


def verify_supabase_token(token: str) -> AuthenticatedUser:
    """Verify Supabase JWT signature, expiry, audience, and extract authenticated identity.

    Supports:
    - Asymmetric tokens (ES256, RS256) via Supabase JWKS endpoint.
    - Symmetric tokens (HS256, HS384, HS512) via SUPABASE_JWT_SECRET.
    - Development / test unsigned tokens (alg: "none").
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    alg = unverified_header.get("alg", "HS256")

    # 1. Dev demo tokens (alg: "none") in development / test environments
    if alg == "none":
        if settings.ENVIRONMENT in ("development", "test"):
            try:
                unverified_claims = jwt.decode(token, options={"verify_signature": False})
                user_id_str = unverified_claims.get("sub")
                if not user_id_str:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token missing subject claim ('sub')",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return AuthenticatedUser(
                    id=UUID(user_id_str),
                    email=unverified_claims.get("email"),
                    role=unverified_claims.get("role", "authenticated"),
                    app_metadata=unverified_claims.get("app_metadata", {}),
                    user_metadata=unverified_claims.get("user_metadata", {}),
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid demo token: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsigned tokens are not allowed in production",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims: Optional[Dict[str, Any]] = None

    # 2. Asymmetric Supabase tokens (ES256, RS256)
    if alg in ("ES256", "RS256"):
        jwks = get_jwks_client()
        if jwks:
            try:
                signing_key = jwks.get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["ES256", "RS256"],
                    audience=settings.SUPABASE_JWT_AUDIENCE,
                    options={
                        "verify_signature": True,
                        "verify_exp": True,
                        "verify_aud": True,
                    },
                )
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidAudienceError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token audience",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token signature",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.DecodeError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Malformed token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except Exception:
                # Network or key resolution fallback in dev
                pass

        if claims is None:
            if settings.ENVIRONMENT in ("development", "test"):
                try:
                    claims = jwt.decode(token, options={"verify_signature": False})
                    exp = claims.get("exp")
                    if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token has expired",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Token verification failed: {str(e)}",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Asymmetric token verification failed for alg '{alg}'",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    # 3. Symmetric Supabase tokens (HS256, HS384, HS512)
    else:
        jwt_secret = settings.SUPABASE_JWT_SECRET
        if not jwt_secret:
            if settings.ENVIRONMENT in ("development", "test"):
                try:
                    claims = jwt.decode(token, options={"verify_signature": False})
                    exp = claims.get("exp")
                    if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token has expired",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid token format: {str(e)}",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service unconfigured: SUPABASE_JWT_SECRET is missing.",
                )
        else:
            try:
                allowed_algs = list({settings.SUPABASE_JWT_ALGORITHM, "HS256", "HS384", "HS512"})
                claims = jwt.decode(
                    token,
                    jwt_secret,
                    algorithms=allowed_algs,
                    audience=settings.SUPABASE_JWT_AUDIENCE,
                    options={
                        "verify_signature": True,
                        "verify_exp": True,
                        "verify_aud": True,
                    },
                )
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidAudienceError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token audience",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token signature",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.DecodeError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Malformed token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token verification failed: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    user_id_str = claims.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim ('sub')",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject ('sub') is not a valid UUID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        id=user_uuid,
        email=claims.get("email"),
        role=claims.get("role", "authenticated"),
        app_metadata=claims.get("app_metadata", {}),
        user_metadata=claims.get("user_metadata", {}),
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthenticatedUser:
    """FastAPI dependency: Enforces that the request carries a valid Supabase bearer token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_supabase_token(credentials.credentials)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[AuthenticatedUser]:
    """FastAPI dependency: Extracts user if token is provided, returns None if omitted."""
    if not credentials or not credentials.credentials:
        return None
    return verify_supabase_token(credentials.credentials)
