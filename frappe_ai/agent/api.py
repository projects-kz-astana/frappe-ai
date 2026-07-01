import frappe


@frappe.whitelist()
def chat(agent: str, message: str, session: str = "new") -> dict:
	user = frappe.session.user

	if session == "new":
		agent_doc = frappe.get_doc("Agent", agent)
		model = frappe.db.get_value("AI Client", agent_doc.ai_client, "model")
		doc = frappe.get_doc(
			{
				"doctype": "Agent Session",
				"agent": agent,
				"user": user,
				"status": "Active",
				"model": model,
				"session_title": message[:120],
			}
		)
		doc.insert(ignore_permissions=True)
		session = doc.name
	else:
		owner = frappe.db.get_value("Agent Session", session, "user")
		if owner != user and "System Manager" not in frappe.get_roles(user):
			frappe.throw("Not permitted to use this session.", frappe.PermissionError)
		frappe.db.set_value("Agent Session", session, "status", "Active")

	frappe.db.commit()

	frappe.enqueue(
		"frappe_ai.agent.jobs.run_agent",
		session_name=session,
		message=message,
		user=user,
		queue="long",
		timeout=300,
	)

	return {"session": session, "status": "queued"}


@frappe.whitelist()
def list_available_agents() -> list[dict]:
	return frappe.get_all("Agent", filters={"enabled": 1}, fields=["name", "agent_name", "description"], order_by="agent_name asc")


@frappe.whitelist()
def get_messages(session: str) -> list[dict]:
	owner = frappe.db.get_value("Agent Session", session, "user")
	if owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw("Not permitted to read this session.", frappe.PermissionError)
	return frappe.get_all(
		"Agent Message",
		filters={"session": session, "role": ["in", ["user", "assistant"]]},
		fields=["role", "content", "creation"],
		order_by="creation asc",
	)
