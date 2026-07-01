import frappe
from frappe.model.document import Document


class AgentPrompt(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		enabled: DF.Check
		prompt: DF.Code
		title: DF.Data
	# end: auto-generated types

	pass
