# Copyright (c) 2026, Sambhav Saxena and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class AIClient(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		api_key: DF.SmallText
		base_url: DF.Data | None
		enable_thinking: DF.Check
		max_tokens: DF.Int
		model: DF.Literal[None]
		name1: DF.Data
		organization: DF.Literal["Anthropic", "OpenAI", "Google"]
		reasoning_effort: DF.Literal[None, "none", "low", "medium", "high", "xhigh"]
		system_prompt: DF.SmallText
		temperature: DF.Float
		thinking_budget: DF.Int
		thinking_level: DF.Literal[None, "none", "low", "medium", "high"]
		top_k: DF.Int
		top_p: DF.Float
	# end: auto-generated types

	_DOCTYPE_NAME = "AI Client"
