import json
import time

import frappe

from frappe_ai.agent import memory, prompts, tools
from frappe_ai.clients import get_client


class AgentRunner:
	def __init__(self, session_name: str):
		self.session = frappe.get_doc("Agent Session", session_name)
		self.config = frappe.get_doc("Agent", self.session.agent)
		if not self.config.enabled:
			frappe.throw(f"Agent '{self.config.name}' is disabled.")

		self.client_doc = frappe.get_doc("AI Client", self.config.ai_client)
		self.organization = self.client_doc.organization
		self.model = self.client_doc.model
		if not self.model:
			frappe.throw(f"AI Client '{self.config.ai_client}' has no model selected.")

		self.client = get_client(self.config.ai_client)
		self.max_iterations = int(self.config.max_iterations or 10)
		self.max_tokens = int(self.config.max_tokens or 4096)
		self.allowed_tools = self.resolve_allowed_tools()

	def resolve_allowed_tools(self) -> list[str] | None:
		if self.config.all_tools:
			return None
		names = [row.tool for row in self.config.tools if row.tool]
		return names or None

	def run(self, user_message: str) -> str:
		context = json.loads(self.session.context_json) if self.session.context_json else None
		system = prompts.build_system_prompt(
			self.config,
			self.session.user,
			context=context,
			summary=self.session.summary,
			allowed_tools=self.allowed_tools,
		)
		window = memory.get_conversation_window(self.session.name)
		self.persist("user", user_message)

		if not self.session.model:
			self.session.db_set("model", self.model)

		if self.organization == "Anthropic":
			return self.run_anthropic(system, window, user_message)
		if self.organization == "OpenAI":
			return self.run_openai(system, window, user_message)
		frappe.throw(f"Agents do not support organization '{self.organization}'.")
		return ""

	def run_anthropic(self, system: str, window: list[dict], user_message: str) -> str:
		schemas = tools.get_tool_schemas(self.allowed_tools, "Anthropic")
		messages = [*window, {"role": "user", "content": user_message}]
		final_text = ""

		for _iteration in range(self.max_iterations):
			start = time.monotonic()
			kwargs = {
				"model": self.model,
				"max_tokens": self.max_tokens,
				"system": system,
				"tools": schemas,
				"messages": messages,
			}
			if self.config.temperature:
				kwargs["temperature"] = float(self.config.temperature)

			response = self.client.messages.create(**kwargs)
			latency = round((time.monotonic() - start) * 1000)
			tokens = anthropic_tokens(response)

			assistant_content = serialize_anthropic_content(response.content)
			messages.append({"role": "assistant", "content": assistant_content})
			text = extract_anthropic_text(response.content)
			tool_uses = [b for b in response.content if b.type == "tool_use"]

			if response.stop_reason != "tool_use" or not tool_uses:
				final_text = text
				self.persist("assistant", text, latency=latency, tokens=tokens)
				return final_text

			calls = [{"name": b.name, "input": b.input} for b in tool_uses]
			self.persist("assistant", text, tool_calls=calls, latency=latency, tokens=tokens)

			result_blocks = []
			records = []
			for block in tool_uses:
				output, is_error = self.call_tool(block.name, block.input)
				result_blocks.append(
					{
						"type": "tool_result",
						"tool_use_id": block.id,
						"content": stringify(output),
						"is_error": is_error,
					}
				)
				records.append({"name": block.name, "input": block.input, "output": output})

			messages.append({"role": "user", "content": result_blocks})
			self.persist("tool", "", tool_calls=records)

		final_text = final_text or "Reached the maximum number of tool iterations."
		self.persist("assistant", final_text)
		return final_text

	def run_openai(self, system: str, window: list[dict], user_message: str) -> str:
		schemas = tools.get_tool_schemas(self.allowed_tools, "OpenAI")
		messages = [
			{"role": "system", "content": system},
			*window,
			{"role": "user", "content": user_message},
		]
		final_text = ""

		for _iteration in range(self.max_iterations):
			start = time.monotonic()
			kwargs = {"model": self.model, "messages": messages, "tools": schemas}
			if self.config.temperature:
				kwargs["temperature"] = float(self.config.temperature)

			response = self.client.chat.completions.create(**kwargs)
			latency = round((time.monotonic() - start) * 1000)
			tokens = openai_tokens(response)
			message = response.choices[0].message
			tool_calls = message.tool_calls or []

			if not tool_calls:
				final_text = message.content or ""
				self.persist("assistant", final_text, latency=latency, tokens=tokens)
				return final_text

			messages.append(
				{
					"role": "assistant",
					"content": message.content or "",
					"tool_calls": [serialize_openai_call(c) for c in tool_calls],
				}
			)
			records = []
			for call in tool_calls:
				args = parse_openai_arguments(call.function.arguments)
				output, _is_error = self.call_tool(call.function.name, args)
				messages.append(
					{
						"role": "tool",
						"tool_call_id": call.id,
						"content": stringify(output),
					}
				)
				records.append(
					{"name": call.function.name, "input": args, "output": output}
				)
			self.persist(
				"assistant", message.content or "", tool_calls=records, latency=latency, tokens=tokens
			)

		final_text = final_text or "Reached the maximum number of tool iterations."
		self.persist("assistant", final_text)
		return final_text

	def call_tool(self, name: str, tool_input):
		if self.allowed_tools is not None and name not in self.allowed_tools:
			return {"error": f"Tool '{name}' is not enabled for this agent."}, True
		fn = tools.REGISTRY.get(name)
		if not fn:
			return {"error": f"Unknown tool: {name}"}, True
		try:
			return fn(**(tool_input or {})), False
		except frappe.PermissionError as exc:
			frappe.clear_last_message()
			return {"error": str(exc) or "Permission denied."}, True
		except Exception as exc:
			frappe.clear_last_message()
			return {"error": str(exc)}, True

	def persist(self, role: str, content: str, tool_calls=None, latency: int = 0, tokens: int = 0):
		doc = frappe.get_doc(
			{
				"doctype": "Agent Message",
				"session": self.session.name,
				"role": role,
				"content": content,
				"tool_calls": frappe.as_json(tool_calls) if tool_calls else None,
				"latency_ms": latency,
				"tokens_used": tokens,
			}
		)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()


def serialize_anthropic_content(blocks) -> list[dict]:
	out = []
	for block in blocks:
		if block.type == "text":
			out.append({"type": "text", "text": block.text})
		elif block.type == "tool_use":
			out.append(
				{"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
			)
	return out


def extract_anthropic_text(blocks) -> str:
	return "".join(b.text for b in blocks if b.type == "text").strip()


def anthropic_tokens(response) -> int:
	usage = getattr(response, "usage", None)
	if not usage:
		return 0
	return int(getattr(usage, "input_tokens", 0) or 0) + int(
		getattr(usage, "output_tokens", 0) or 0
	)


def openai_tokens(response) -> int:
	usage = getattr(response, "usage", None)
	return int(getattr(usage, "total_tokens", 0) or 0) if usage else 0


def serialize_openai_call(call) -> dict:
	return {
		"id": call.id,
		"type": "function",
		"function": {"name": call.function.name, "arguments": call.function.arguments},
	}


def parse_openai_arguments(arguments: str) -> dict:
	if not arguments:
		return {}
	try:
		return json.loads(arguments)
	except (ValueError, TypeError):
		return {}


def stringify(output) -> str:
	if isinstance(output, str):
		return output
	try:
		return frappe.as_json(output)
	except (TypeError, ValueError):
		return str(output)
