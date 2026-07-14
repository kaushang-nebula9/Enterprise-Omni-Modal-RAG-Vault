import pytest
from app.services.model_router import route_model


def test_route_model_empty_models():
    with pytest.raises(ValueError):
        route_model("test", [], False, [])


def test_route_model_fast_simple():
    models = [
        {"id": "1", "display_name": "Fast Model", "tier": "fast"},
        {"id": "2", "display_name": "Balanced Model", "tier": "balanced"},
        {"id": "3", "display_name": "Powerful Model", "tier": "powerful"},
    ]
    # Simple lookup keyword: "what is" (-2), query len < 80 (-2), score should be -2 -> fast
    chosen = route_model("what is a cat?", [], False, models)
    assert chosen["id"] == "1"


def test_route_model_balanced_simple():
    models = [
        {"id": "1", "display_name": "Fast Model", "tier": "fast"},
        {"id": "2", "display_name": "Balanced Model", "tier": "balanced"},
        {"id": "3", "display_name": "Powerful Model", "tier": "powerful"},
    ]
    # query length <= 100 (+0), coding keywords (+2), sentence count >= 2 (+1) -> score = 3 -> balanced
    query = (
        "Here is some context. Can you implement a function to handle model routing?"
    )
    chosen = route_model(query, [], False, models)
    assert chosen["id"] == "2"


def test_route_model_powerful_complex():
    models = [
        {"id": "1", "display_name": "Fast Model", "tier": "fast"},
        {"id": "2", "display_name": "Balanced Model", "tier": "balanced"},
        {"id": "3", "display_name": "Powerful Model", "tier": "powerful"},
    ]
    # attachment (+3), context > 6000 tokens (+3), query length > 300 (+2), coding (+2), reasoning (+2) -> score = 12 -> powerful
    query = "I have uploaded the document. Please write a detailed python script to parse the files. Additionally, compare the differences between the two formats and justify why you chose this design pattern. The code must handle all edge cases. This is extremely important."
    context = ["chunk" * 1500] * 5  # ~ 7500 tokens
    chosen = route_model(query, context, True, models)
    assert chosen["id"] == "3"


def test_route_model_fallback_up():
    # Target is fast, but only powerful exists
    models = [
        {"id": "3", "display_name": "Powerful Model", "tier": "powerful"},
    ]
    chosen = route_model("what is a dog", [], False, models)
    assert chosen["id"] == "3"


def test_route_model_fallback_down():
    # Target is powerful, but only fast exists
    models = [
        {"id": "1", "display_name": "Fast Model", "tier": "fast"},
    ]
    query = "I have uploaded the document. Please write a detailed python script to parse the files. Additionally, compare the differences between the two formats and justify why you chose this design pattern. The code must handle all edge cases. This is extremely important."
    context = ["chunk" * 1500] * 5
    chosen = route_model(query, context, True, models)
    assert chosen["id"] == "1"


def test_route_model_is_default():
    models = [
        {"id": "1", "display_name": "Fast Model 1", "tier": "fast"},
        {"id": "2", "display_name": "Fast Model 2", "tier": "fast", "is_default": True},
    ]
    chosen = route_model("what is a cat?", [], False, models)
    assert chosen["id"] == "2"


@pytest.fixture(name="db")
def db_fixture():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.dialects.postgresql import JSONB

    @compiles(JSONB, "sqlite")
    def compile_jsonb_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_get_default_model_config_cascade(db):
    from app.services.model_router import get_default_model_config
    from app.models.available_model import AvailableModel
    import uuid

    tenant_id = uuid.uuid4()

    # 0. Empty DB
    assert get_default_model_config(db, tenant_id) is None

    # 1. Add active global model (non-default)
    global_model = AvailableModel(
        id=uuid.uuid4(),
        display_name="Global Model",
        provider_id="openai",
        model_name="gpt-4o",
        is_active=True,
        is_default=False,
        tenant_id=None,
    )
    db.add(global_model)
    db.commit()

    # Cascades to global active model
    res = get_default_model_config(db, tenant_id)
    assert res is not None and res.id == global_model.id

    # 2. Add tenant model (active, non-default)
    tenant_model = AvailableModel(
        id=uuid.uuid4(),
        display_name="Tenant Model",
        provider_id="anthropic",
        model_name="claude-3-5",
        is_active=True,
        is_default=False,
        tenant_id=tenant_id,
    )
    db.add(tenant_model)
    db.commit()

    # Cascades to tenant active model
    res = get_default_model_config(db, tenant_id)
    assert res is not None and res.id == tenant_model.id

    # 3. Add tenant default model
    tenant_default = AvailableModel(
        id=uuid.uuid4(),
        display_name="Tenant Default Model",
        provider_id="google",
        model_name="gemini-1.5",
        is_active=True,
        is_default=True,
        tenant_id=tenant_id,
    )
    db.add(tenant_default)
    db.commit()

    # Selects tenant default model
    res = get_default_model_config(db, tenant_id)
    assert res is not None and res.id == tenant_default.id
