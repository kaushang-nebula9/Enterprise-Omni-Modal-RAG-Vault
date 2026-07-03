import os
import uvicorn
from alembic.config import Config
from alembic import command

if __name__ == "__main__":
    app_env = os.environ.get("APP_ENV", "development")

    if app_env != "development":
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
    else:
        print("Skipping alembic upgrade in development mode")

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
