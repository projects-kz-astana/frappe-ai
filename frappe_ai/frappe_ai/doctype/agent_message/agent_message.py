import frappe
from frappe.model.document import Document


class AgentMessage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		content: DF.LongText | None
		latency_ms: DF.Int
		role: DF.Literal["user", "assistant", "tool"]
		session: DF.Link
		tokens_used: DF.Int
		tool_calls: DF.JSON | None
	# end: auto-generated types

	pass
