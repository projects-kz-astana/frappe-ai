import frappe

from frappe_ai.agent import memory
from frappe_ai.agent.runner import AgentRunner


def run_agent(session_name: str, message: str, user: str) -> None:
	frappe.set_user(user)
	try:
		result = AgentRunner(session_name).run(message)
		memory.update_summary(session_name)
		frappe.db.set_value("Agent Session", session_name, "status", "Completed")
		frappe.db.commit()
		frappe.publish_realtime(
			"agent_response",
			{"session": session_name, "content": result, "status": "done"},
			user=user,
		)
	except Exception as exc:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Frappe AI: Agent job failed")
		frappe.db.set_value("Agent Session", session_name, "status", "Error")
		frappe.db.commit()
		frappe.publish_realtime(
			"agent_response",
			{"session": session_name, "content": str(exc), "status": "error"},
			user=user,
		)
