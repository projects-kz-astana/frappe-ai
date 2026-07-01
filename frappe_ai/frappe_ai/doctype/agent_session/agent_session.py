import frappe
from frappe.model.document import Document


class AgentSession(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent: DF.Link
		context_json: DF.JSON | None
		model: DF.Data | None
		session_title: DF.Data | None
		status: DF.Literal["Active", "Completed", "Error"]
		summary: DF.LongText | None
		user: DF.Link | None
	# end: auto-generated types

	def before_insert(self):
		if not self.user:
			self.user = frappe.session.user

	def on_trash(self):
		for name in frappe.get_all(
			"Agent Message", filters={"session": self.name}, pluck="name"
		):
			frappe.delete_doc("Agent Message", name, ignore_permissions=True, force=True)
