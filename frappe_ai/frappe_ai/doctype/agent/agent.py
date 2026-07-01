import frappe
from frappe.model.document import Document


class Agent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from frappe_ai.frappe_ai.doctype.agent_tool.agent_tool import AgentTool

		agent_name: DF.Data
		agent_prompt: DF.Link | None
		ai_client: DF.Link
		all_tools: DF.Check
		description: DF.SmallText | None
		enabled: DF.Check
		max_iterations: DF.Int
		max_tokens: DF.Int
		temperature: DF.Float
		tools: DF.Table[AgentTool]
	# end: auto-generated types

	def validate(self):
		organization = frappe.db.get_value("AI Client", self.ai_client, "organization")
		if organization not in ("Anthropic", "OpenAI"):
			frappe.throw(
				"Agents support Anthropic and OpenAI clients only. "
				f"'{self.ai_client}' is configured for '{organization}'."
			)
