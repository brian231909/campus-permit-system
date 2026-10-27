"""API 輸入驗證。"""
import re
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
SCHOOL_ID_RE = re.compile(r"[A-Za-z0-9]{6,12}")
PHONE_RE = re.compile(r"09\d{8}")
PLATE_RE = re.compile(r"[A-Za-z0-9\-]{2,12}")
COMMON_PASSWORDS = {"password1234", "password12345", "123456789012", "1234567890ab", "qwertyuiop12", "iloveyou1234", "administrator", "welcome12345", "letmein123456", "abcdefghijkl", "111111111111", "000000000000", "passw0rd1234", "changeme1234"}
class RegisterIn(BaseModel):
    school_id: str
    name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    phone: str | None = None
    user_type: Literal["student", "teacher"]
    password: str = Field(min_length=12, max_length=128)
    @field_validator("school_id")
    @classmethod
    def school_id_valid(cls, v):
        v=v.strip()
        if not SCHOOL_ID_RE.fullmatch(v): raise ValueError("學號／教職員編號須為 6 到 12 碼英數字")
        return v.upper()
    @field_validator("name")
    @classmethod
    def name_valid(cls,v):
        v=v.strip()
        if not v: raise ValueError("姓名不可空白")
        return v
    @field_validator("email")
    @classmethod
    def email_valid(cls,v):
        v=v.lower()
        if len(v)>254: raise ValueError("信箱過長")
        return v
    @field_validator("phone")
    @classmethod
    def phone_valid(cls,v):
        if v is None or not v.strip(): return None
        v=v.strip()
        if not PHONE_RE.fullmatch(v): raise ValueError("手機須為 09 開頭共 10 碼數字")
        return v
    @model_validator(mode="after")
    def password_rules(self):
        pw=self.password.lower()
        if pw in COMMON_PASSWORDS: raise ValueError("密碼太常見，請換一個")
        if self.school_id.lower() in pw: raise ValueError("密碼不可包含學號／教職員編號")
        local=self.email.split("@")[0]
        if len(local)>=3 and local in pw: raise ValueError("密碼不可包含信箱帳號")
        return self
class LoginIn(BaseModel):
    school_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
class VehicleIn(BaseModel):
    license_plate: str = Field(min_length=2, max_length=12)
    vehicle_type: Literal["motorcycle", "car", "other"]
    make_model: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=30)
    @field_validator("license_plate")
    @classmethod
    def plate_valid(cls, v):
        v=v.strip().upper().replace(" ", "")
        if not PLATE_RE.fullmatch(v): raise ValueError("車牌僅可包含英數字及連字號，長度 2 至 12 碼")
        return v
    @field_validator("make_model", "color")
    @classmethod
    def optional_trim(cls,v): return v.strip() if v and v.strip() else None
class VehicleUpdateIn(BaseModel):
    vehicle_type: Literal["motorcycle", "car", "other"] | None = None
    make_model: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=30)
    @field_validator("make_model", "color")
    @classmethod
    def optional_trim(cls,v): return v.strip() if v and v.strip() else None
class PermitApplyIn(BaseModel):
    vehicle_id: int = Field(gt=0)
    purpose: str = Field(min_length=3, max_length=300)
    @field_validator("purpose")
    @classmethod
    def purpose_valid(cls,v):
        v=v.strip()
        if len(v)<3: raise ValueError("申請用途至少 3 個字")
        return v
class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=500)
    @field_validator("comment")
    @classmethod
    def comment_trim(cls,v): return v.strip() if v and v.strip() else None
class UserStatusIn(BaseModel):
    status: Literal["active", "disabled", "pending"]
