import enum
from sqlalchemy import Enum as SQLEnum


class FileType(str, enum.Enum):
    text = "text"
    audio = "audio"
    pdf = "pdf"
    docx = "docx"
    pptx = "pptx"
    excel = "excel"
    csv = "csv"


class OwnerType(str, enum.Enum):
    organisation = "organisation"
    private = "private"


class Visibility(str, enum.Enum):
    public = "public"
    private = "private"


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class OTPPurpose(str, enum.Enum):
    registration = "registration"
    forgot_password = "forgot_password"


class GrantedVia(str, enum.Enum):
    direct = "direct"
    inherited = "inherited"
    department = "department"


class NotificationType(str, enum.Enum):
    role_assigned = "role_assigned"
    document_access_direct = "document_access_direct"
    document_access_inherited_hierarchy = "document_access_inherited_hierarchy"
    document_access_inherited_department = "document_access_inherited_department"
    department_added = "department_added"
    evaluation_completed = "evaluation_completed"
    budget_exceeded = "budget_exceeded"
    database_access_direct = "database_access_direct"
    database_access_inherited_hierarchy = "database_access_inherited_hierarchy"
    database_access_inherited_department = "database_access_inherited_department"


class ModelProvider(str, enum.Enum):
    anthropic = "anthropic"
    openrouter = "openrouter"


class EvaluationStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class DatabaseEngine(str, enum.Enum):
    postgresql = "postgresql"
    mysql = "mysql"


# SQLAlchemy Enum Types
file_type_enum = SQLEnum(FileType, name="filetype")
owner_type_enum = SQLEnum(OwnerType, name="ownertype")
visibility_enum = SQLEnum(Visibility, name="visibility")
document_status_enum = SQLEnum(DocumentStatus, name="documentstatus")
message_role_enum = SQLEnum(MessageRole, name="messagerole")
otp_purpose_enum = SQLEnum(OTPPurpose, name="otppurpose")
granted_via_enum = SQLEnum(GrantedVia, name="grantedvia")
notification_type_enum = SQLEnum(NotificationType, name="notificationtype")
model_provider_enum = SQLEnum(ModelProvider, name="modelprovider")
evaluation_status_enum = SQLEnum(EvaluationStatus, name="evaluationstatus")
database_engine_enum = SQLEnum(DatabaseEngine, name="databaseengine")
