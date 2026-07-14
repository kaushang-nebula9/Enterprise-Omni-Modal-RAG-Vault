import re


def route_model(
    query: str,
    context_chunks: list[str],
    has_attachments: bool,
    available_models: list[dict],
) -> dict:
    """
    Selects the most appropriate tenant model configuration based on query signals,
    with zero additional LLM calls.

    Signals score:
      - has_attachments is True                                    | +3
      - estimated context tokens > 6000                            | +3
      - estimated context tokens > 2000                            | +1
      - query length > 300 characters                              | +2
      - query length > 100 characters                              | +1
      - query contains 2+ sentences                                | +1
      - contains " and ", "also", "additionally", "furthermore", "as well as" | +2
      - reasoning keywords                                         | +2
      - coding keywords                                            | +2
      - structured output keywords                                 | +1
      - simple lookup (what is, etc) with length < 80              | -2

    Tier mapping:
      - score <= 2  -> 'fast'
      - score 3-5   -> 'balanced'
      - score >= 6  -> 'powerful'
    """
    if not available_models:
        raise ValueError("No available models to route to.")

    score = 0

    # 1. Attachment detection
    if has_attachments:
        score += 3

    # 2. Token estimation
    context_tokens = sum(len(chunk.split()) * 1.3 for chunk in context_chunks)
    if context_tokens > 6000:
        score += 3
    if context_tokens > 2000:
        score += 1

    # 3. Query length detection
    q_len = len(query)
    if q_len > 300:
        score += 2
    if q_len > 100:
        score += 1

    # 4. Sentence detection
    sentences = re.split(r"[.!?](?:\s+|$)", query)
    sentences = [s for s in sentences if s.strip()]
    if len(sentences) >= 2:
        score += 1

    # 5. Multi-part detection
    query_lower = query.lower()
    multi_part_keywords = [" and ", "also", "additionally", "furthermore", "as well as"]
    if any(kw in query_lower for kw in multi_part_keywords):
        score += 2

    # 6. Task keywords - reasoning
    reasoning_keywords = [
        "why",
        "explain",
        "analyse",
        "analyze",
        "evaluate",
        "elaborate",
        "justify",
        "compare",
        "contrast",
        "pros and cons",
        "difference between",
        "implications",
    ]
    if any(kw in query_lower for kw in reasoning_keywords):
        score += 2

    # 7. Task keywords - coding
    coding_keywords = [
        "code",
        "implement",
        "function",
        "script",
        "debug",
        "error",
        "fix",
        "refactor",
        "class",
        "algorithm",
    ]
    if any(kw in query_lower for kw in coding_keywords):
        score += 2

    # 8. Task keywords - structured output
    structured_keywords = [
        "table",
        "list all",
        "enumerate",
        "summarise",
        "summarize",
        "breakdown",
        "break down",
    ]
    if any(kw in query_lower for kw in structured_keywords):
        score += 1

    # 9. Task keywords - simple lookup
    simple_lookup_keywords = ["what is", "who is", "when did", "define", "what does"]
    if q_len < 80 and any(kw in query_lower for kw in simple_lookup_keywords):
        score -= 2

    # Tier mapping
    if score <= 2:
        target_tier = "fast"
    elif score <= 5:
        target_tier = "balanced"
    else:
        target_tier = "powerful"

    # Fallbacks mapping
    tier_fallbacks = {
        "powerful": ["powerful", "balanced", "fast"],
        "fast": ["fast", "balanced", "powerful"],
        "balanced": ["balanced", "powerful", "fast"],
    }

    # Selection logic
    for tier in tier_fallbacks[target_tier]:
        matching_models = [m for m in available_models if m.get("tier") == tier]
        if matching_models:
            # Try to return the one marked default if it exists
            for m in matching_models:
                if m.get("is_default"):
                    return m
            return matching_models[0]

    # Available models list is not empty, so fallback to any first model
    for m in available_models:
        if m.get("is_default"):
            return m
    return available_models[0]


def get_default_model_config(db: any, tenant_id: any) -> any:
    """
    Queries for the model configuration where is_default = True for the tenant.
    If no default model is set, cascades to find any active model for the tenant.
    """
    from app.models.available_model import AvailableModel

    if not tenant_id:
        return None

    # 1. Try tenant-specific default model
    model = (
        db.query(AvailableModel)
        .filter(
            AvailableModel.tenant_id == tenant_id,
            AvailableModel.is_default.is_(True),
            AvailableModel.is_active.is_(True),
        )
        .first()
    )
    if model:
        return model

    # 2. Try any tenant-specific active model
    model = (
        db.query(AvailableModel)
        .filter(
            AvailableModel.tenant_id == tenant_id,
            AvailableModel.is_active.is_(True),
        )
        .first()
    )
    if model:
        return model

    # 3. Try global default model
    model = (
        db.query(AvailableModel)
        .filter(
            AvailableModel.tenant_id.is_(None),
            AvailableModel.is_default.is_(True),
            AvailableModel.is_active.is_(True),
        )
        .first()
    )
    if model:
        return model

    # 4. Try any global active model
    model = (
        db.query(AvailableModel)
        .filter(
            AvailableModel.tenant_id.is_(None),
            AvailableModel.is_active.is_(True),
        )
        .first()
    )
    if model:
        return model

    return None
