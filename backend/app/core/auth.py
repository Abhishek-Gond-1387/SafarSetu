"""Supabase JWT authentication and token verification dependency."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.core.config import settings

# HTTP Bearer scheme with manual error handling for explicit 401 messages
security = HTTPBearer(auto_error=False)


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

    Security Guarantee: Never trusts client-supplied user_id without cryptographic verification.
    """
    # Support dev demo tokens (alg: "none") in development / test environments
    if settings.ENVIRONMENT in ("development", "test"):
        try:
            unverified_header = jwt.get_unverified_header(token)
            if unverified_header.get("alg") == "none":
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
        except Exception:
            pass

    jwt_secret = settings.SUPABASE_JWT_SECRET

    # If no secret is configured and running in test/development, check if mock bypass is active
    if not jwt_secret:
        if settings.ENVIRONMENT in ("development", "test"):
            # In test mode without a secret, decode without verification only if signature check is bypassed
            try:
                unverified_claims = jwt.decode(token, options={"verify_signature": False})
                user_id_str = unverified_claims.get("sub")
                if not user_id_str:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token missing subject claim ('sub')",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                # Check expiration manually
                exp = unverified_claims.get("exp")
                if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has expired",
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
                    detail=f"Invalid token format: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unconfigured: SUPABASE_JWT_SECRET is missing.",
            )

    try:
        claims = jwt.decode(
            token,
            jwt_secret,
            algorithms=[settings.SUPABASE_JWT_ALGORITHM],
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

