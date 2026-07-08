from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Postgres
    database_url: str

    # Redis
    redis_url: str

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # OTP
    otp_ttl_seconds: int = 300

    # SMTP (optional — falls back to console logging if unset)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None

    # Twilio WhatsApp (optional — falls back to console logging if unset)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None  # e.g. "whatsapp:+14155238886" (Twilio sandbox number)

    # Razorpay (optional — falls back to a stub order id if unset)
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None

    # Google Sign-In (optional — Google login button stays disabled until this is set)
    google_client_id: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
