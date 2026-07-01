frappe.provide("frappe.ui");

frappe.ui.AgentChat = class AgentChat {
	constructor(agent) {
		this.agent = agent;
		this.session = "new";
		this.subscribed = false;
		this.make_dialog();
	}

	show() {
		this.dialog.show();
		this.subscribe();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Chat {0}", [this.agent]),
			size: "large",
			fields: [
				{ fieldname: "messages_html", fieldtype: "HTML" },
				{ fieldname: "message", fieldtype: "Small Text", label: __("Message"), reqd: 1 },
			],
			primary_action_label: __("Send"),
			primary_action: () => {
				const text = this.dialog.get_value("message");
				if (text && text.trim()) this.send(text.trim());
			},
		});

		this.body = this.dialog.fields_dict.messages_html.$wrapper;
		this.body.css({ "max-height": "420px", "overflow-y": "auto", "margin-bottom": "12px" });
	}

	subscribe() {
		if (this.subscribed) return;
		this.subscribed = true;
		frappe.realtime.on("agent_response", (data) => {
			if (data.session !== this.session) return;
			this.set_pending(false);
			if (data.status === "error") {
				this.append("error", data.content);
			} else {
				this.append("assistant", data.content);
			}
		});
	}

	send(text) {
		this.append("user", text);
		this.dialog.set_value("message", "");
		this.set_pending(true);
		frappe.call({
			method: "frappe_ai.agent.api.chat",
			args: { agent: this.agent, message: text, session: this.session },
			callback: (r) => {
				if (r.message && r.message.session) this.session = r.message.session;
			},
			error: () => this.set_pending(false),
		});
	}

	set_pending(pending) {
		if (pending) {
			this.dialog.disable_primary_action();
			this.dialog.set_title(__("Thinking…"));
		} else {
			this.dialog.enable_primary_action();
			this.dialog.set_title(__("Chat {0}", [this.agent]));
		}
	}

	append(role, text) {
		const colors = { user: "#e7f3ff", assistant: "#f4f5f6", error: "#fbeae9" };
		const label = { user: __("You"), assistant: __("Agent"), error: __("Error") }[role];
		const bubble = $(`
			<div style="margin-bottom:10px;">
				<div style="font-size:11px;color:#8d99a6;margin-bottom:2px;">${label}</div>
				<div style="background:${colors[role]};padding:8px 10px;border-radius:8px;white-space:pre-wrap;"></div>
			</div>
		`);
		bubble.find("div").last().text(text);
		this.body.append(bubble);
		this.body.scrollTop(this.body[0].scrollHeight);
	}
};
