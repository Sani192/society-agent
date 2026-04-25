-- Baseline PostgreSQL schema for the current application model state.
-- Apply this file directly to provision a fresh database without legacy transition steps.


CREATE TABLE societies (
	id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	city VARCHAR(100) NOT NULL, 
	state VARCHAR(100) NOT NULL, 
	timezone VARCHAR(50) NOT NULL, 
	config_json JSONB NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);


CREATE TABLE channel_conversations (
	id UUID NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	external_user_id VARCHAR(255) NOT NULL, 
	chat_id_or_phone VARCHAR(255), 
	first_occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	last_occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_channel_conversation_user UNIQUE (channel, external_user_id), 
	CONSTRAINT ck_channel_conversations_channel CHECK (channel IN ('whatsapp', 'telegram'))
);

CREATE INDEX ix_channel_conversations_channel_external_user ON channel_conversations (channel, external_user_id);


CREATE TABLE channel_message_events (
	id UUID NOT NULL, 
	trace_id VARCHAR(255), 
	correlation_id VARCHAR(255), 
	channel VARCHAR(20) NOT NULL, 
	direction VARCHAR(20) NOT NULL, 
	event_type VARCHAR(50) NOT NULL, 
	provider_message_id VARCHAR(255), 
	provider_update_id VARCHAR(255), 
	chat_id_or_phone VARCHAR(255), 
	external_user_id VARCHAR(255), 
	message_text_raw TEXT, 
	message_text_raw_encrypted TEXT, 
	message_text_redacted TEXT, 
	payload_json JSONB, 
	payload_json_encrypted TEXT, 
	prev_event_hash VARCHAR(64), 
	event_hash VARCHAR(64), 
	http_status INTEGER, 
	provider_error_code VARCHAR(100), 
	provider_error_message TEXT, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_channel_message_events_channel CHECK (channel IN ('whatsapp', 'telegram')), 
	CONSTRAINT ck_channel_message_events_direction CHECK (direction IN ('inbound', 'outbound', 'status', 'system')), 
	CONSTRAINT ck_channel_message_events_event_type CHECK (event_type IN ('webhook_received', 'message_parsed', 'reply_generated', 'send_attempt', 'send_result', 'delivery_status', 'processing_completed', 'exception'))
);

CREATE INDEX ix_channel_message_events_provider_message_id ON channel_message_events (provider_message_id);

CREATE INDEX ix_channel_message_events_correlation_id ON channel_message_events (correlation_id);

CREATE INDEX ix_channel_message_events_event_hash ON channel_message_events (event_hash);

CREATE INDEX ix_channel_message_events_channel_external_user_occurred ON channel_message_events (channel, external_user_id, occurred_at);

CREATE INDEX ix_channel_message_events_trace_id ON channel_message_events (trace_id);


CREATE TABLE channel_dead_letters (
	id UUID NOT NULL, 
	trace_id VARCHAR(255) NOT NULL, 
	correlation_id VARCHAR(255), 
	channel VARCHAR(20) NOT NULL, 
	recipient VARCHAR(255) NOT NULL, 
	payload_json JSONB, 
	error_class VARCHAR(255) NOT NULL, 
	error_message TEXT NOT NULL, 
	stack_summary JSONB, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_channel_dead_letters_channel CHECK (channel IN ('whatsapp', 'telegram'))
);

CREATE INDEX ix_channel_dead_letters_trace_id ON channel_dead_letters (trace_id);

CREATE INDEX ix_channel_dead_letters_correlation_id ON channel_dead_letters (correlation_id);


CREATE TABLE inbound_webhook_envelopes (
	id UUID NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	payload_json JSONB NOT NULL, 
	payload_hash VARCHAR(64) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	enqueued_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_inbound_webhook_envelopes_channel CHECK (channel IN ('whatsapp', 'telegram'))
);

CREATE INDEX ix_inbound_webhook_envelopes_status ON inbound_webhook_envelopes (status);

CREATE INDEX ix_inbound_webhook_envelopes_payload_hash ON inbound_webhook_envelopes (payload_hash);

CREATE INDEX ix_inbound_webhook_envelopes_channel ON inbound_webhook_envelopes (channel);


CREATE TABLE webhook_idempotency_keys (
	id UUID NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	provider_message_id VARCHAR(255), 
	provider_update_id VARCHAR(255), 
	idempotency_key VARCHAR(255) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_webhook_idempotency_keys_channel CHECK (channel IN ('whatsapp', 'telegram')), 
	CONSTRAINT uq_webhook_idempotency_keys_channel_key UNIQUE (channel, idempotency_key)
);

CREATE INDEX ix_webhook_idempotency_keys_lookup ON webhook_idempotency_keys (channel, provider_message_id, provider_update_id);


CREATE TABLE member_identities (
	id UUID NOT NULL, 
	normalized_identifier VARCHAR NOT NULL, 
	normalized_phone VARCHAR, 
	whatsapp_user_id VARCHAR, 
	telegram_user_id VARCHAR, 
	preferred_language VARCHAR(8) DEFAULT 'en' NOT NULL, 
	metadata_json JSONB, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_member_identities_normalized_identifier ON member_identities (normalized_identifier);

CREATE UNIQUE INDEX ix_member_identities_telegram_user_id ON member_identities (telegram_user_id);

CREATE UNIQUE INDEX ix_member_identities_whatsapp_user_id ON member_identities (whatsapp_user_id);

CREATE INDEX ix_member_identities_normalized_phone ON member_identities (normalized_phone);


CREATE TABLE bootstrap_seed_guard (
	seed_key TEXT NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (seed_key)
);


CREATE TABLE committee_members (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	phone_number VARCHAR(20) NOT NULL, 
	role VARCHAR(50) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id) ON DELETE CASCADE, 
	UNIQUE (phone_number)
);


CREATE TABLE flats (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	flat_number VARCHAR(50) NOT NULL, 
	block VARCHAR(50) NOT NULL, 
	owner_name VARCHAR(255), 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_flats_society_flat_number UNIQUE (society_id, flat_number), 
	FOREIGN KEY(society_id) REFERENCES societies (id) ON DELETE CASCADE
);


CREATE TABLE reminder_configs (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	enabled BOOLEAN, 
	run_hour INTEGER NOT NULL, 
	run_minute INTEGER NOT NULL, 
	frequency VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (society_id), 
	FOREIGN KEY(society_id) REFERENCES societies (id)
);


CREATE TABLE committee_member_channel_identities (
	id UUID NOT NULL, 
	committee_member_id UUID NOT NULL, 
	channel_type VARCHAR(50) NOT NULL, 
	external_user_id VARCHAR(255), 
	username VARCHAR(255), 
	is_verified BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_channel_external_user UNIQUE (channel_type, external_user_id), 
	FOREIGN KEY(committee_member_id) REFERENCES committee_members (id) ON DELETE CASCADE
);

CREATE INDEX ix_committee_member_channel_identities_username ON committee_member_channel_identities (username);

CREATE INDEX ix_committee_member_channel_identities_channel_type ON committee_member_channel_identities (channel_type);

CREATE INDEX ix_committee_member_channel_identities_external_user_id ON committee_member_channel_identities (external_user_id);


CREATE TABLE committee_member_link_codes (
	id UUID NOT NULL, 
	committee_member_id UUID NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	consumed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(committee_member_id) REFERENCES committee_members (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_committee_member_link_codes_code ON committee_member_link_codes (code);


CREATE TABLE events (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	event_date TIMESTAMP WITH TIME ZONE NOT NULL, 
	charge_per_adult INTEGER, 
	charge_per_child INTEGER, 
	food_types JSONB NOT NULL, 
	payment_deadline TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(50) NOT NULL, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(created_by) REFERENCES committee_members (id)
);

CREATE INDEX ix_events_society_event_date ON events (society_id, event_date);


CREATE TABLE audit_logs (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_id UUID NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	reason VARCHAR(255), 
	performed_by UUID, 
	performed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(performed_by) REFERENCES committee_members (id)
);


CREATE TABLE user_flat_mappings (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	member_identity_id UUID NOT NULL, 
	role VARCHAR, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id), 
	FOREIGN KEY(member_identity_id) REFERENCES member_identities (id)
);

CREATE INDEX ix_user_flat_mappings_member_identity_id ON user_flat_mappings (member_identity_id);


CREATE TABLE pending_users (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	request_code VARCHAR NOT NULL, 
	member_identity_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	status VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(member_identity_id) REFERENCES member_identities (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id)
);

CREATE INDEX ix_pending_users_request_code ON pending_users (request_code);

CREATE INDEX ix_pending_users_member_identity_id ON pending_users (member_identity_id);


CREATE TABLE event_food_passes (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	veg_count INTEGER NOT NULL, 
	jain_count INTEGER NOT NULL, 
	kids_count INTEGER NOT NULL, 
	total_amount INTEGER NOT NULL, 
	is_participating BOOLEAN NOT NULL, 
	is_locked BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_event_food_passes_event_flat UNIQUE (event_id, flat_id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id)
);


CREATE TABLE event_food_tokens (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	food_type VARCHAR(20) NOT NULL, 
	token_code VARCHAR(20) NOT NULL, 
	qr_payload VARCHAR(255) NOT NULL, 
	served_at TIMESTAMP WITH TIME ZONE, 
	served_method VARCHAR(20), 
	served_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_event_food_tokens_event_token UNIQUE (event_id, token_code), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id), 
	FOREIGN KEY(served_by) REFERENCES committee_members (id)
);

CREATE INDEX ix_event_food_tokens_event_id ON event_food_tokens (event_id);

CREATE INDEX ix_event_food_tokens_token_code ON event_food_tokens (token_code);

CREATE INDEX ix_event_food_tokens_flat_id ON event_food_tokens (flat_id);


CREATE TABLE event_food_counters (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	is_open BOOLEAN NOT NULL, 
	opened_at TIMESTAMP WITH TIME ZONE, 
	closes_at TIMESTAMP WITH TIME ZONE, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	opened_by UUID, 
	closed_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(opened_by) REFERENCES committee_members (id), 
	FOREIGN KEY(closed_by) REFERENCES committee_members (id)
);

CREATE UNIQUE INDEX ix_event_food_counters_event_id ON event_food_counters (event_id);


CREATE TABLE payments (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	expected_amount INTEGER NOT NULL, 
	paid_amount INTEGER NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	payment_mode VARCHAR(50), 
	paid_at TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id)
);

CREATE INDEX ix_payments_event_flat ON payments (event_id, flat_id);

CREATE INDEX ix_payments_event_paid_at ON payments (event_id, paid_at);


CREATE TABLE refunds (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	amount INTEGER NOT NULL, 
	reason VARCHAR(255) NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id), 
	FOREIGN KEY(created_by) REFERENCES committee_members (id)
);

CREATE INDEX ix_refunds_event_flat ON refunds (event_id, flat_id);

CREATE INDEX ix_refunds_event_status ON refunds (event_id, status);

CREATE INDEX ix_refunds_event_created_at ON refunds (event_id, created_at);


CREATE TABLE payment_requests (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	request_code VARCHAR(50) NOT NULL, 
	amount INTEGER NOT NULL, 
	payment_mode VARCHAR(50), 
	status VARCHAR(50) NOT NULL, 
	requested_by_mapping_id UUID NOT NULL, 
	member_identity_id UUID NOT NULL, 
	requested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id), 
	FOREIGN KEY(requested_by_mapping_id) REFERENCES user_flat_mappings (id), 
	FOREIGN KEY(member_identity_id) REFERENCES member_identities (id), 
	FOREIGN KEY(approved_by) REFERENCES committee_members (id)
);

CREATE INDEX ix_payment_requests_member_identity_id ON payment_requests (member_identity_id);

CREATE INDEX ix_payment_requests_requested_by_mapping_id ON payment_requests (requested_by_mapping_id);

CREATE INDEX ix_payment_requests_request_code ON payment_requests (request_code);


CREATE TABLE refund_requests (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	request_code VARCHAR(50) NOT NULL, 
	amount INTEGER NOT NULL, 
	reason VARCHAR(255) NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	requested_by_mapping_id UUID NOT NULL, 
	member_identity_id UUID NOT NULL, 
	requested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id), 
	FOREIGN KEY(requested_by_mapping_id) REFERENCES user_flat_mappings (id), 
	FOREIGN KEY(member_identity_id) REFERENCES member_identities (id), 
	FOREIGN KEY(approved_by) REFERENCES committee_members (id)
);

CREATE INDEX ix_refund_requests_member_identity_id ON refund_requests (member_identity_id);

CREATE INDEX ix_refund_requests_request_code ON refund_requests (request_code);

CREATE INDEX ix_refund_requests_requested_by_mapping_id ON refund_requests (requested_by_mapping_id);


CREATE TABLE event_contributions (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	contribution_code VARCHAR(20) NOT NULL, 
	contribution_type VARCHAR(50) NOT NULL, 
	source_name VARCHAR(255) NOT NULL, 
	flat_id UUID, 
	amount INTEGER, 
	in_kind_details JSONB, 
	notes VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id)
);

CREATE INDEX ix_event_contributions_contribution_code ON event_contributions (contribution_code);

CREATE INDEX ix_event_contributions_event_created_at ON event_contributions (event_id, created_at);

CREATE INDEX ix_event_contributions_event_flat ON event_contributions (event_id, flat_id);


CREATE TABLE event_expenses (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	amount INTEGER NOT NULL, 
	is_override BOOLEAN NOT NULL, 
	override_reason VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id)
);

CREATE INDEX ix_event_expenses_event_created_at ON event_expenses (event_id, created_at);


CREATE TABLE society_balance (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	opening_balance INTEGER NOT NULL, 
	closing_balance INTEGER NOT NULL, 
	calculated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(event_id) REFERENCES events (id)
);


CREATE TABLE workflow_state (
	id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	current_state VARCHAR(50) NOT NULL, 
	allowed_next_states JSONB NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id)
);


CREATE TABLE payment_reminders (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	event_id UUID NOT NULL, 
	flat_id UUID NOT NULL, 
	pending_amount INTEGER NOT NULL, 
	reminder_date DATE NOT NULL, 
	status VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_payment_reminders_event_flat_date UNIQUE (event_id, flat_id, reminder_date), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(flat_id) REFERENCES flats (id)
);


CREATE TABLE announcements (
	id UUID NOT NULL, 
	society_id UUID NOT NULL, 
	event_id UUID, 
	type VARCHAR(50) NOT NULL, 
	message_text TEXT NOT NULL, 
	created_by UUID NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	total_targets INTEGER NOT NULL, 
	sent_count INTEGER NOT NULL, 
	failed_count INTEGER NOT NULL, 
	skipped_count INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(society_id) REFERENCES societies (id), 
	FOREIGN KEY(event_id) REFERENCES events (id), 
	FOREIGN KEY(created_by) REFERENCES committee_members (id)
);


CREATE TABLE contribution_refunds (
	id UUID NOT NULL, 
	contribution_id UUID NOT NULL, 
	amount INTEGER NOT NULL, 
	reason VARCHAR(255) NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(contribution_id) REFERENCES event_contributions (id)
);

CREATE INDEX ix_contribution_refunds_contribution_processed_at ON contribution_refunds (contribution_id, processed_at);


CREATE TABLE announcement_deliveries (
	announcement_id UUID NOT NULL, 
	member_identity_id UUID NOT NULL, 
	channel VARCHAR(50) NOT NULL, 
	recipient_id VARCHAR(255) NOT NULL, 
	rendered_payload JSONB, 
	status VARCHAR(50) NOT NULL, 
	attempts INTEGER NOT NULL, 
	last_error TEXT, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	processing_started_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (announcement_id, member_identity_id, channel), 
	FOREIGN KEY(announcement_id) REFERENCES announcements (id) ON DELETE CASCADE, 
	FOREIGN KEY(member_identity_id) REFERENCES member_identities (id) ON DELETE CASCADE
);

CREATE INDEX idx_announcement_deliveries_claim_pending ON announcement_deliveries (status, processing_started_at, sent_at, announcement_id);
