import frappe

from frappe_ai.agent import tools

DEFAULT_PROMPT = (
	"You are an assistant operating inside a Frappe site for user {user}.\n"
	"You help with records, reports, and tasks across any DocType the user can access.\n"
	"Always use the provided tools to read or change data. Never invent record names, "
	"field values, or counts. Inspect a DocType with get_doctype_fields before writing to it.\n"
	"Never execute arbitrary code or SQL, and never attempt to bypass Frappe permissions.\n"
	"When a tool returns a permission error, tell the user they are not allowed to perform "
	"that action instead of retrying."
)


def build_system_prompt(agent_doc, user: str, context: dict | None = None, summary: str | None = None, allowed_tools: list[str] | None = None) -> str:
	base = DEFAULT_PROMPT
	if agent_doc.agent_prompt:
		stored = frappe.db.get_value("Agent Prompt", agent_doc.agent_prompt, "prompt")
		if stored and stored.strip():
			base = stored

	company = frappe.defaults.get_user_default("Company", user) or ""
	rendered = render(
		base,
		{
			"user": user,
			"company": company,
			"date": frappe.utils.today(),
			"context": frappe.as_json(context) if context else "",
		},
	)

	parts = [rendered.strip(), tool_catalog(allowed_tools)]
	if company:
		parts.append(f"User's default company: {company}.")
	if summary and summary.strip():
		parts.append(f"Summary of earlier conversation:\n{summary.strip()}")
	return "\n\n".join(p for p in parts if p)


def render(template: str, values: dict) -> str:
	out = template
	for key, value in values.items():
		out = out.replace("{" + key + "}", str(value))
	return out


def tool_catalog(allowed_tools: list[str] | None) -> str:
	schemas = tools.TOOL_SCHEMAS
	if allowed_tools:
		allowed_set = set(allowed_tools)
		schemas = [s for s in schemas if s["name"] in allowed_set]
	lines = [f"- {s['name']}: {s['description']}" for s in schemas]
	return "Available tools:\n" + "\n".join(lines)
