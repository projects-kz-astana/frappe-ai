import frappe

CLIENT_REGISTRY: dict[str, object] = {}


def get_client(docname: str) -> object:
	if docname not in CLIENT_REGISTRY:
		initialize_ai_client(docname)
	return CLIENT_REGISTRY[docname]


def initialize_all_ai_clients() -> None:
	try:
		docnames = frappe.get_all("AI Client", pluck="name")
	except Exception:
		# DB may not be available yet (during migrations).
		return

	for docname in docnames:
		if docname in CLIENT_REGISTRY:
			continue
		try:
			initialize_ai_client(docname)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"frappe_ai: failed to initialize client '{docname}'",
			)


def refresh_ai_client(doc, method: str | None = None) -> None:
	docname: str = doc if isinstance(doc, str) else doc.name
	CLIENT_REGISTRY.pop(docname, None)
	try:
		initialize_ai_client(docname)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			f"frappe_ai: failed to refresh client '{docname}'",
		)


def initialize_ai_client(docname: str) -> None:
	doc = frappe.get_doc("AI Client", docname)
	api_key = doc.get("api_key") or ""
	if not api_key:
		raise ValueError(f"AI Client '{docname}' has no API key set.")

	org = doc.get("organization") or ""

	if org == "Anthropic":
		from anthropic import Anthropic

		client = Anthropic(api_key=str(api_key))

	elif org == "OpenAI":
		from openai import OpenAI

		base_url = str(doc.get("base_url") or "").strip()
		kwargs = {"api_key": str(api_key)}
		if base_url:
			kwargs["base_url"] = base_url
		client = OpenAI(**kwargs)

	elif org == "Google":
		from google import genai

		client = genai.Client(api_key=str(api_key))

	else:
		raise ValueError(f"Unsupported organization: '{org}'")

	CLIENT_REGISTRY[docname] = client
