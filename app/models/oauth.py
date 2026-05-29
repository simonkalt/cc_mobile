"""
OAuth login/link request and response models.
See documentation/OAUTH_LOGIN_API.md.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserLoginResponse, UserResponse

OAuthProvider = Literal["google", "linkedin", "apple"]
OAuthIntent = Literal["login", "register", "replace_provider"]


class OAuthTokenExchangeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    redirect_uri: str
    # LinkedIn OIDC: omit on mobile (usePKCE false); server does not forward to LinkedIn.
    code_verifier: str = ""
    intent: Optional[OAuthIntent] = "login"
    data_use_sharing_notice_accepted: Optional[bool] = Field(
        default=None,
        alias="dataUseSharingNoticeAccepted",
    )
    replace_existing_provider: Optional[bool] = Field(
        default=None,
        alias="replaceExisting",
    )


class AppleFullName(BaseModel):
    """Apple returns the user's name only on the first authorization for the app."""

    givenName: Optional[str] = None
    familyName: Optional[str] = None


class AppleOAuthLoginRequest(BaseModel):
    """Sign in with Apple is native: the client posts the identity token directly."""

    model_config = ConfigDict(populate_by_name=True)

    identity_token: str
    authorization_code: Optional[str] = None
    # Apple's stable user id (credential.user). Informational only; the token's `sub` is authoritative.
    apple_user: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[AppleFullName] = None
    intent: Optional[OAuthIntent] = "login"
    data_use_sharing_notice_accepted: Optional[bool] = Field(
        default=None,
        alias="dataUseSharingNoticeAccepted",
    )


class AppleOAuthLinkRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    identity_token: str
    authorization_code: Optional[str] = None
    apple_user: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[AppleFullName] = None
    replace_existing_provider: Optional[bool] = Field(
        default=None,
        alias="replaceExisting",
    )


class OAuthLoginResponse(UserLoginResponse):
    linkedProvider: Optional[str] = None
    replacedProvider: Optional[str] = None


class OAuthLinkResponse(BaseModel):
    success: bool = True
    user: UserResponse
    linkedProvider: Optional[str] = None
    replacedProvider: Optional[str] = None
