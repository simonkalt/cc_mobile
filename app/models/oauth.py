"""
OAuth login/link request and response models.
See documentation/OAUTH_LOGIN_API.md.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserLoginResponse, UserResponse

OAuthProvider = Literal["google", "linkedin"]
OAuthIntent = Literal["login", "register"]


class OAuthTokenExchangeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    redirect_uri: str
    code_verifier: str
    intent: Optional[OAuthIntent] = "login"
    data_use_sharing_notice_accepted: Optional[bool] = Field(
        default=None,
        alias="dataUseSharingNoticeAccepted",
    )


class OAuthLoginResponse(UserLoginResponse):
    linkedProvider: Optional[str] = None


class OAuthLinkResponse(BaseModel):
    success: bool = True
    user: UserResponse
    linkedProvider: str
