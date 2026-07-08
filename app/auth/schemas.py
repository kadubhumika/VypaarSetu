from pydantic import BaseModel, EmailStr


# --- Merchant ---
class MerchantRegister(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str


class MerchantLogin(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    reset_token: str
    new_password: str


class UpdatePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class GoogleLoginRequest(BaseModel):
    id_token: str  # the credential returned by Google Identity Services on the frontend


# --- Customer (OTP) ---
class OTPRequest(BaseModel):
    email: EmailStr


class OTPVerify(BaseModel):
    email: EmailStr
    otp: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
