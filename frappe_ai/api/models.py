import frappe


@frappe.whitelist()
def get_models_for_org(organization: str, docname: str) -> list[str]:
	if not docname:
		frappe.throw("Document name is required to fetch the API key.")

	doc = frappe.get_doc("AI Client", docname)

	if doc.get("organization") != organization:
		frappe.throw("Organization mismatch.")

	api_key = doc.get("api_key")
	if not api_key:
		frappe.throw("API Key is not set. Please save the document with a valid API key first.")

    try:
        if organization == "Anthropic":
            return _get_anthropic_models(str(api_key))
        elif organization == "OpenAI":
            base_url = str(doc.get("base_url") or "").strip()
            return _get_openai_models(str(api_key), base_url)
        elif organization == "Google":
			return _get_google_models(str(api_key))
		else:
			frappe.throw(f"Unsupported organization: {organization}")
			return []
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "AI Client – model fetch failed")
		frappe.throw(str(e))
		return []


def _get_anthropic_models(api_key: str) -> list:
	from anthropic import Anthropic

	client = Anthropic(api_key=api_key)
	page = client.models.list()
	return [m.id for m in page.data]


def _get_openai_models(api_key: str, base_url: str = "") -> list:
	from openai import OpenAI

	kwargs = {"api_key": api_key}
	if base_url:
		kwargs["base_url"] = base_url
	client = OpenAI(**kwargs)
	models = client.models.list()
	allowed_prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt-")
	return sorted([m.id for m in models.data if any(m.id.startswith(p) for p in allowed_prefixes)])


def _get_google_models(api_key: str) -> list:
	from google import genai

	client = genai.Client(api_key=api_key)
	return [
		m.name.split("/")[-1]
		for m in client.models.list()
		if "generateContent" in (m.supported_actions or [])
	]
