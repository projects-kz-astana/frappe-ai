import frappe

MAX_RECENT_MESSAGES = 10
SUMMARY_THRESHOLD = 20
SUMMARY_KEEP = 6


def get_conversation_window(session_name: str) -> list[dict]:
	rows = frappe.get_all(
		"Agent Message",
		filters={"session": session_name, "role": ["in", ["user", "assistant"]]},
		fields=["role", "content"],
		order_by="creation asc",
	)
	clean = [
		{"role": r["role"], "content": r["content"]}
		for r in rows
		if (r.get("content") or "").strip()
	]
	window = clean[-MAX_RECENT_MESSAGES:]
	while window and window[0]["role"] != "user":
		window.pop(0)
	return window


def update_summary(session_name: str) -> None:
	rows = frappe.get_all(
		"Agent Message",
		filters={"session": session_name, "role": ["in", ["user", "assistant"]]},
		fields=["name", "role", "content"],
		order_by="creation asc",
	)
	if len(rows) <= SUMMARY_THRESHOLD:
		return

	older = rows[:-SUMMARY_KEEP]
	session = frappe.get_doc("Agent Session", session_name)
	transcript = "\n".join(
		f"{r['role']}: {(r['content'] or '').strip()}" for r in older
	)
	previous = (session.summary or "").strip()

	prompt = (
		"Summarize the following assistant conversation into a concise running memo "
		"that preserves user goals, decisions, record names, and unresolved items. "
		"Keep it under 200 words.\n\n"
	)
	if previous:
		prompt += f"[Existing summary]\n{previous}\n\n"
	prompt += f"[Conversation]\n{transcript}"

	agent_doc = frappe.get_doc("Agent", session.agent)
	from frappe_ai.api.chat import ask

	new_summary = ask(docname=agent_doc.ai_client, user_message=prompt)
	session.db_set("summary", new_summary)

	for r in older:
		frappe.delete_doc(
			"Agent Message", r["name"], ignore_permissions=True, force=True
		)
	frappe.db.commit()
