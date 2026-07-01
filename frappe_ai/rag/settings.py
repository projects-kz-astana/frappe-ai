import frappe


def get_settings():
    return frappe.get_single("RAG Settings")


def embedding_api_key(settings) -> str:
    key = (settings.get("embedding_api_key") or "").strip()
    if key:
        return key
    client_name = settings.get("llm_client") or ""
    if client_name:
        return str(frappe.db.get_value("AI Client", client_name, "api_key") or "")
    return ""
