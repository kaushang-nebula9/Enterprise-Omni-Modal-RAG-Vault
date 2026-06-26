from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import models here so Alembic can detect them
from app.models.otp_verification import OTPVerification
from app.models.role import Role
from app.models.department import Department
from app.models.available_model import AvailableModel
from app.models.usage_log import UsageLog
from app.models.query_log import QueryLog
from app.models.evaluation import EvaluationRun, EvaluationResult
