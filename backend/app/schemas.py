from datetime import date
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ---- auth ------------------------------------------------------------------
class LoginIn(BaseModel):
    school_code: str | None = None  # omitted only for superadmin
    role: str
    login_id: str
    password: str


class OtpRequestIn(BaseModel):
    school_code: str
    mobile: str


class OtpVerifyIn(OtpRequestIn):
    code: str


class RefreshIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)


class SchoolBrief(ORM):
    id: int
    name: str
    code: str
    default_language: str
    logo_url: str


class UserOut(ORM):
    id: int
    role: str
    login_id: str
    full_name: str
    phone: str
    email: str
    language: str
    school_id: int | None
    must_change_password: bool
    school: SchoolBrief | None = None
    student_id: int | None = None
    teacher_id: int | None = None
    parent_id: int | None = None


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool
    user: UserOut


class ProfilePatch(BaseModel):
    phone: str | None = None
    email: str | None = None
    language: str | None = Field(default=None, pattern="^(en|te|hi|ml|ta)$")
    alert_channels: list[str] | None = None  # parents
    emergency_contact: str | None = None  # parents


# ---- school ----------------------------------------------------------------
class SchoolIn(BaseModel):
    name: str
    code: str = Field(min_length=2, max_length=32, pattern="^[A-Za-z0-9_-]+$")
    address: str = ""
    district: str = ""
    mandal: str = ""
    default_language: str = Field(default="en", pattern="^(en|te|hi|ml|ta)$")
    headmaster_name: str = ""
    headmaster_phone: str = ""
    admin_login: str = "admin"
    admin_password: str = Field(min_length=8, max_length=72)
    admin_name: str = "School Admin"


class SchoolOut(ORM):
    id: int
    name: str
    code: str
    address: str
    district: str
    mandal: str
    logo_url: str
    default_language: str
    headmaster_name: str
    headmaster_phone: str


class SchoolPatch(BaseModel):
    name: str | None = None
    address: str | None = None
    district: str | None = None
    mandal: str | None = None
    logo_url: str | None = None
    default_language: str | None = Field(default=None, pattern="^(en|te|hi|ml|ta)$")
    headmaster_name: str | None = None
    headmaster_phone: str | None = None


class AcademicYearIn(BaseModel):
    label: str
    start_date: date
    end_date: date
    is_current: bool = False


class AcademicYearOut(ORM, AcademicYearIn):
    id: int


# ---- structure -------------------------------------------------------------
class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    sort_order: int = 0


class ClassOut(ORM, ClassIn):
    id: int


class SectionIn(BaseModel):
    class_id: int
    name: str = Field(min_length=1, max_length=10)
    class_teacher_id: int | None = None


class SectionPatch(BaseModel):
    name: str | None = None
    class_teacher_id: int | None = None


class SectionOut(ORM, SectionIn):
    id: int


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = ""


class SubjectOut(ORM, SubjectIn):
    id: int


class AssignmentIn(BaseModel):
    teacher_id: int
    section_id: int
    subject_id: int


class AssignmentOut(ORM, AssignmentIn):
    id: int


# ---- people ----------------------------------------------------------------
class TeacherIn(BaseModel):
    employee_id: str = Field(min_length=1, max_length=32)
    full_name: str
    phone: str = ""
    email: str = ""
    qualification: str = ""
    joining_date: date | None = None
    photo_url: str = ""
    password: str | None = Field(default=None, min_length=8, max_length=72)  # else a temp one is generated


class TeacherPatch(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    qualification: str | None = None
    joining_date: date | None = None
    photo_url: str | None = None
    is_active: bool | None = None


class TeacherOut(ORM):
    id: int
    user_id: int = 0
    employee_id: str
    full_name: str
    phone: str
    email: str
    qualification: str
    joining_date: date | None
    photo_url: str
    is_active: bool
    temp_password: str | None = None  # only set in the create response


class StudentIn(BaseModel):
    admission_no: str = Field(min_length=1, max_length=32)
    full_name: str
    class_id: int
    section_id: int
    roll_no: int | None = None
    dob: date
    gender: str = ""
    parent_mobile: str = Field(min_length=6, max_length=20)
    parent_name: str = ""
    parent_relation: str = ""
    address: str = ""
    language: str = Field(default="en", pattern="^(en|te|hi|ml|ta)$")
    category: str = ""
    medical_notes: str = ""
    photo_url: str = ""

    @field_validator("parent_mobile")
    @classmethod
    def digits(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not v.lstrip("+").isdigit():
            raise ValueError("mobile must be digits")
        return v


class StudentPatch(BaseModel):
    full_name: str | None = None
    class_id: int | None = None
    section_id: int | None = None
    roll_no: int | None = None
    dob: date | None = None
    gender: str | None = None
    parent_mobile: str | None = None
    parent_name: str | None = None
    address: str | None = None
    language: str | None = Field(default=None, pattern="^(en|te|hi|ml|ta)$")
    category: str | None = None
    medical_notes: str | None = None
    photo_url: str | None = None


class StudentOut(ORM):
    id: int
    admission_no: str
    full_name: str
    class_id: int
    section_id: int
    roll_no: int | None
    dob: date
    gender: str
    photo_url: str
    parent_mobile: str
    address: str
    language: str
    category: str
    medical_notes: str
    temp_password: str | None = None  # only in the create response


class ParentOut(ORM):
    id: int
    full_name: str
    mobile: str
    relation: str
    language: str
    alert_channels: list
    emergency_contact: str
    children: list[StudentOut] = []
