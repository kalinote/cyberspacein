from datetime import datetime

from pydantic import BaseModel

from app.models.auth.session import LoginSessionModel


class LoginSessionResponse(BaseModel):
    session_id: str
    user_id: str
    status: str
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    login_ip: str | None
    user_agent: str | None
    terminated_at: datetime | None
    terminated_reason: str | None

    @classmethod
    def from_doc(cls, doc: LoginSessionModel) -> "LoginSessionResponse":
        return cls(
            session_id=doc.id,
            user_id=doc.user_id,
            status=doc.status,
            created_at=doc.created_at,
            last_activity_at=doc.last_activity_at,
            expires_at=doc.expires_at,
            login_ip=doc.login_ip,
            user_agent=doc.user_agent,
            terminated_at=doc.terminated_at,
            terminated_reason=doc.terminated_reason,
        )
