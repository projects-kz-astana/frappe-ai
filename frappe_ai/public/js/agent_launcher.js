frappe.provide("frappe.ui");

$(document).on("app_ready", () => {
	if (frappe.session.user === "Guest") return;
	frappe.ui.AgentLauncher.init();
});

frappe.ui.AgentLauncher = {
	init() {
		if (this.button) return;
		this.button = $(`
			<div id="agent-chat-launcher" title="${__("Chat with an Agent")}" style="
				position: fixed; right: 24px; bottom: 24px; width: 48px; height: 48px;
				border-radius: 50%; background: var(--primary); color: var(--primary-inverse, #fff);
				display: flex; align-items: center; justify-content: center; cursor: pointer;
				box-shadow: var(--shadow-lg, 0 2px 8px rgba(0,0,0,.25)); z-index: 1071;">
				${frappe.utils.icon("small-message", "md")}
			</div>
		`).appendTo("body");
		this.button.on("click", () => this.open());
	},

	open() {
		frappe.call({
			method: "frappe_ai.agent.api.list_available_agents",
			callback: (r) => {
				const agents = r.message || [];
				if (!agents.length) {
					frappe.msgprint(__("No agents are available to chat with."));
					return;
				}
				if (agents.length === 1) {
					this.launch(agents[0].name);
					return;
				}
				this.pick(agents);
			},
		});
	},

	pick(agents) {
		const dialog = new frappe.ui.Dialog({
			title: __("Choose an Agent"),
			fields: [
				{
					fieldname: "agent",
					fieldtype: "Select",
					label: __("Agent"),
					options: agents.map((a) => ({ label: a.agent_name || a.name, value: a.name })),
					reqd: 1,
				},
			],
			primary_action_label: __("Chat"),
			primary_action: (values) => {
				dialog.hide();
				this.launch(values.agent);
			},
		});
		dialog.show();
	},

	launch(agent) {
		const chat = new frappe.ui.AgentChat(agent);
		chat.show();
	},
};
