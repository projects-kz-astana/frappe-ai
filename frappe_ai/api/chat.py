import frappe
from frappe_ai.clients import get_client


def ask(
    docname: str,
    user_message: str,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
) -> str:
    """Return only the text response string.

    Importable from anywhere:
        from frappe_ai.api.chat import ask
        text = ask("My Anthropic Client", "What is 2+2?")

    All generation parameters are optional and fall back to the values
    configured on the AI Client document when omitted.
    """
    return chat(
        docname=docname,
        user_message=user_message,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )["text"]


@frappe.whitelist()
def chat(
    docname: str,
    user_message: str,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
) -> dict:
    """Send a message to the configured AI client and return the response.

    Parameters fall back to the doctype's configured values when omitted.
    Returns {"text": str, "model": str, "usage": {"input": int, "output": int}}.

    Whitelisted. Callable from the Frappe desk via frappe.call():
        method: "frappe_ai.api.chat.chat"
    """
    doc = frappe.get_doc("AI Client", docname)
    if not doc.get("model"):
        frappe.throw("No model selected on AI Client '{0}'.".format(docname))

    client = get_client(docname)
    org = doc.get("organization") or ""

    sys_prompt = _pick_str(system_prompt, doc.get("system_prompt"))
    temp = _pick_float(temperature, doc.get("temperature"))
    tokens = _pick_int(max_tokens, doc.get("max_tokens"))
    p = _pick_float(top_p, doc.get("top_p"))

    if org == "Anthropic":
        return _anthropic_chat(client, doc, user_message, sys_prompt, temp, tokens, p)
    elif org == "OpenAI":
        return _openai_chat(client, doc, user_message, sys_prompt, tokens)
    elif org == "Google":
        return _google_chat(client, doc, user_message, sys_prompt, temp, tokens)
    else:
        frappe.throw("Unsupported organization: '{0}'".format(org))
        return {"text": "", "model": "", "usage": {"input": 0, "output": 0}}


def _anthropic_chat(
    client, doc, message, system_prompt, temperature, max_tokens, top_p
) -> dict:
    kwargs: dict = {
        "model": doc.model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": max_tokens or 4096,
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    if temperature is not None:
        kwargs["temperature"] = temperature
    if top_p is not None:
        kwargs["top_p"] = top_p
    if doc.top_k:
        kwargs["top_k"] = int(doc.top_k)

    if doc.enable_thinking:
        budget = int(doc.thinking_budget or 1024)
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
        response = client.beta.messages.create(
            betas=["interleaved-thinking-2025-05-14"], **kwargs
        )
    else:
        response = client.messages.create(**kwargs)

    text = "".join(
        getattr(block, "text", "") for block in response.content if block.type == "text"
    )
    return {
        "text": text,
        "model": response.model,
        "usage": _usage(response.usage, "input_tokens", "output_tokens"),
    }


def _openai_chat(client, doc, message, system_prompt, max_tokens) -> dict:
    kwargs: dict = {
        "model": doc.model,
        "input": message,
    }
    if system_prompt:
        kwargs["instructions"] = system_prompt
    if max_tokens:
        kwargs["max_output_tokens"] = int(max_tokens)

    effort = doc.reasoning_effort or ""
    if effort and effort != "none":
        kwargs["reasoning"] = {"effort": effort}

    response = client.responses.create(**kwargs)
    return {
        "text": response.output_text or "",
        "model": getattr(response, "model", doc.model),
        "usage": _usage(
            getattr(response, "usage", None), "input_tokens", "output_tokens"
        ),
    }


def _google_chat(client, doc, message, system_prompt, temperature, max_tokens) -> dict:
    kwargs: dict = {
        "model": doc.model,
        "input": message,
    }
    if system_prompt:
        kwargs["system_instruction"] = system_prompt

    gen_config: dict = {}
    if temperature is not None:
        gen_config["temperature"] = temperature
    level = doc.thinking_level or ""
    if level and level != "none":
        gen_config["thinking_level"] = level
    if max_tokens:
        gen_config["max_output_tokens"] = int(max_tokens)
    if gen_config:
        kwargs["generation_config"] = gen_config

    response = client.interactions.create(**kwargs)
    return {
        "text": response.output_text or "",
        "model": doc.model,
        "usage": {},
    }


def _pick_str(override, doc_val) -> str | None:
    if override is not None and str(override).strip():
        return str(override).strip()
    if doc_val and str(doc_val).strip():
        return str(doc_val).strip()
    return None


def _pick_float(override, doc_val) -> float | None:
    if override is not None and override != "":
        try:
            return float(override)
        except (ValueError, TypeError):
            pass
    if doc_val:
        try:
            return float(doc_val)
        except (ValueError, TypeError):
            pass
    return None


def _pick_int(override, doc_val) -> int | None:
    if override is not None and override != "":
        try:
            return int(float(override))
        except (ValueError, TypeError):
            pass
    if doc_val:
        try:
            return int(doc_val)
        except (ValueError, TypeError):
            pass
    return None


def _usage(usage_obj, in_key: str, out_key: str) -> dict:
    if not usage_obj:
        return {}
    return {
        "input": int(getattr(usage_obj, in_key, 0) or 0),
        "output": int(getattr(usage_obj, out_key, 0) or 0),
    }
