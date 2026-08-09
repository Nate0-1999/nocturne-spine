# Law coverage

Generated deterministically by `scripts/check_test_motivations.py`.

- Tests discovered: 161
- Motivated tests: 161
- Grandfathered baseline debt: 0
- Stale baseline entries: 0

## SPEC and ADR defenders

### 0 — ZERO DEFENDERS

- _None._

### 1 — ZERO DEFENDERS

- _None._

### 1.0 — ZERO DEFENDERS

- _None._

### 1.1 — ZERO DEFENDERS

- _None._

### 1.2 — ZERO DEFENDERS

- _None._

### 1.3 — ZERO DEFENDERS

- _None._

### 1.4 — ZERO DEFENDERS

- _None._

### 2 — ZERO DEFENDERS

- _None._

### 2.1 — ZERO DEFENDERS

- _None._

### ADR-001 — ZERO DEFENDERS

- _None._

### ADR-010 — ZERO DEFENDERS

- _None._

### ADR-002 — ZERO DEFENDERS

- _None._

### ADR-003 — ZERO DEFENDERS

- _None._

### ADR-004 — ZERO DEFENDERS

- _None._

### ADR-005 — 1 defender(s)

- `tests/test_commit_feedback_api.py::test_autonomous_entry_accepts_one_citation_transition`

### ADR-011 — ZERO DEFENDERS

- _None._

### ADR-007 — ZERO DEFENDERS

- _None._

### ADR-008 — ZERO DEFENDERS

- _None._

### ADR-012 — ZERO DEFENDERS

- _None._

### ADR-013 — ZERO DEFENDERS

- _None._

### ADR-014 — ZERO DEFENDERS

- _None._

### ADR-015 — ZERO DEFENDERS

- _None._

### ADR-016 — ZERO DEFENDERS

- _None._

### ADR-017 — ZERO DEFENDERS

- _None._

### ADR-018 — ZERO DEFENDERS

- _None._

### ADR-019 — ZERO DEFENDERS

- _None._

### ADR-020 — ZERO DEFENDERS

- _None._

### ADR-021 — ZERO DEFENDERS

- _None._

### ADR-022 — 3 defender(s)

- `tests/test_memory_api.py::test_memory_split_preserves_exact_source_and_writes_one_linked_active_family`
- `tests/test_memory_api.py::test_memory_split_rejects_invalid_or_lossy_families_before_embedding`
- `tests/test_memory_api.py::test_memory_split_rolls_back_heads_revisions_and_edges_on_late_insert_failure`

### ADR-023 — ZERO DEFENDERS

- _None._

### ADR-024 — 9 defender(s)

- `tests/test_embeddings.py::test_embed_one_normalizes_and_validates_an_injected_provider`
- `tests/test_embeddings.py::test_embedding_receipt_failure_does_not_release_vectors`
- `tests/test_embeddings.py::test_empty_batch_is_local_but_still_requires_provider_configuration`
- `tests/test_embeddings.py::test_malformed_success_responses_raise_typed_errors`
- `tests/test_embeddings.py::test_missing_api_key_fails_at_call_time_without_an_http_request`
- `tests/test_embeddings.py::test_non_sequence_and_mixed_inputs_raise_typed_errors`
- `tests/test_embeddings.py::test_openai_request_and_response_order_follow_the_provider_contract`
- `tests/test_embeddings.py::test_production_embedding_is_receipted_before_vector_return`
- `tests/test_embeddings.py::test_transport_and_api_failures_remain_distinct`

### ADR-006 — ZERO DEFENDERS

- _None._

### ADR-009 — ZERO DEFENDERS

- _None._

### B.1 — ZERO DEFENDERS

- _None._

### B.2 — ZERO DEFENDERS

- _None._

### B.3 — ZERO DEFENDERS

- _None._

### B.4 — ZERO DEFENDERS

- _None._

### B.5 — ZERO DEFENDERS

- _None._

### B.6 — 6 defender(s)

- `tests/test_memory_api.py::test_memory_split_preserves_exact_source_and_writes_one_linked_active_family`
- `tests/test_memory_api.py::test_memory_split_preserves_existing_label_and_duplicate_conflict_bodies`
- `tests/test_memory_api.py::test_memory_split_rejects_invalid_or_lossy_families_before_embedding`
- `tests/test_memory_api.py::test_memory_split_returns_first_near_similar_child_without_any_write`
- `tests/test_memory_api.py::test_memory_split_rolls_back_heads_revisions_and_edges_on_late_insert_failure`
- `tests/test_test_motivations.py::test_report_indexes_citations_and_marks_uncovered_law`

### C.1 — ZERO DEFENDERS

- _None._

### C.2 — 15 defender(s)

- `tests/test_db.py::test_cas_command_requires_a_canonical_ulid`
- `tests/test_db.py::test_cas_requires_a_caller_owned_transaction`
- `tests/test_db.py::test_cas_updates_form_cloud_head_lineage`
- `tests/test_db.py::test_competing_cas_has_one_winner_and_current_409`
- `tests/test_db.py::test_lineage_error_rolls_back_when_caught_inside_outer_transaction`
- `tests/test_db.py::test_models_match_authoritative_c2_schema`
- `tests/test_db.py::test_revision_append_failure_rolls_back_head_update`
- `tests/test_db.py::test_search_tsv_trigger_tracks_sources_and_overwrites_tampering`
- `tests/test_db.py::test_tombstone_is_revisioned_and_releases_active_label`
- `tests/test_ids.py::test_mint_ulid_returns_distinct_canonical_values`
- `tests/test_m2n_migrations.py::test_every_supported_revision_upgrades_to_head`
- `tests/test_migration.py::test_0004_backfills_legacy_rows_and_downgrades_cleanly`
- `tests/test_migration.py::test_active_label_is_unique_while_unit_is_active`
- `tests/test_migration.py::test_c2_migration_and_v0_seed`
- `tests/test_migration.py::test_packaged_migration_tree_has_one_expected_head`

### C.3 — ZERO DEFENDERS

- _None._

### C.4 — 26 defender(s)

- `tests/test_api.py::test_exact_c4_bodies_reject_extra_fields`
- `tests/test_api.py::test_exactly_the_lawful_spine_routes_are_registered`
- `tests/test_api.py::test_health_endpoints_and_auth_are_live`
- `tests/test_api.py::test_http_errors_are_rfc7807`
- `tests/test_api.py::test_retrain_is_bearer_protected_before_any_training_work`
- `tests/test_api.py::test_unexpected_service_errors_are_sanitized_rfc7807`
- `tests/test_api.py::test_v15_list_paging_contract_is_validated`
- `tests/test_api.py::test_v15_machine_id_is_required_on_create_and_patch`
- `tests/test_api.py::test_validation_errors_are_rfc7807`
- `tests/test_memory_api.py::test_concurrent_same_principal_dedup_creates_only_one_root`
- `tests/test_memory_api.py::test_create_hard_duplicate_is_forced_but_scoped_to_principal`
- `tests/test_memory_api.py::test_create_similar_band_requires_force_retry`
- `tests/test_memory_api.py::test_create_writes_root_attribution_and_checks_label_before_embedding`
- `tests/test_memory_api.py::test_list_filters_total_paging_and_stable_order`
- `tests/test_memory_api.py::test_memory_limits_and_zero_vectors_fail_before_any_write`
- `tests/test_memory_api.py::test_origin_path_patch_is_cas_metadata_and_null_is_omitted`
- `tests/test_memory_api.py::test_patch_cas_reembeds_and_returns_exact_stale_conflict`
- `tests/test_memory_api.py::test_patch_label_conflict_covers_reactivation_and_stale_precedence`
- `tests/test_memory_api.py::test_patch_not_found_and_noop_are_problem_json`
- `tests/test_memory_api.py::test_similar_equal_scores_break_ties_by_memory_id`
- `tests/test_memory_service.py::test_dedup_boundaries_are_inclusive_exactly_where_enacted`
- `tests/test_search_api.py::test_search_default_k_has_uuid_cutoff_and_invalid_k_does_not_embed`
- `tests/test_search_api.py::test_search_empty_and_invalid_provider_vector_have_exact_responses`
- `tests/test_search_api.py::test_search_omitted_and_null_project_are_principal_wide`
- `tests/test_search_api.py::test_search_uses_raw_cosine_and_exact_principal_status_project_filters`
- `tests/test_tokens.py::test_cl100k_count_is_stable_and_treats_special_text_literally`

### C.5 — 4 defender(s)

- `tests/test_config.py::test_c5_dedup_and_embedding_defaults_are_exact`
- `tests/test_config.py::test_config_rejects_overlapping_bands_and_wrong_storage_dimension`
- `tests/test_config.py::test_embedding_runtime_wires_default_and_direct_provider_without_network`
- `tests/test_config.py::test_runtime_environment_cannot_override_artifact_version`

### C.6 — ZERO DEFENDERS

- _None._

### C.7 — ZERO DEFENDERS

- _None._

### C.8 — ZERO DEFENDERS

- _None._

### C.9 — ZERO DEFENDERS

- _None._

### C.10 — ZERO DEFENDERS

- _None._

### D.1 — ZERO DEFENDERS

- _None._

### D.2 — 2 defender(s)

- `tests/test_packaging.py::test_editable_checkout_materializes_the_same_deploy_context`
- `tests/test_packaging.py::test_materialized_source_modes_are_independent_of_the_callers_umask`

### D.3 — ZERO DEFENDERS

- _None._

### D.4 — ZERO DEFENDERS

- _None._

## Other referenced statutes

### A-007

- `tests/test_inject_scorer.py::test_active_learner_version_adds_immutable_offset_to_online_head_bias`
- `tests/test_inject_scorer.py::test_config_json_boundary_uses_only_the_scoring_fields`
- `tests/test_inject_scorer.py::test_confirmed_lock_bypasses_threshold_top_k_and_reduces_regular_budget`
- `tests/test_inject_scorer.py::test_confirmed_pin_is_already_forced_and_does_not_require_regular_membership`
- `tests/test_inject_scorer.py::test_every_supplied_pool_candidate_is_scored_before_threshold_and_budget_selection`
- `tests/test_inject_scorer.py::test_golden_pins_can_exceed_budget_and_bypass_a_below_tau_score`
- `tests/test_inject_scorer.py::test_golden_selection_preserves_pin_score_order_ranks_and_greedy_skips`
- `tests/test_inject_scorer.py::test_golden_six_feature_score_uses_enacted_tokenizer_and_snapshot_clock`
- `tests/test_inject_scorer.py::test_golden_tau_is_inclusive_and_negative_cosine_clamps_to_zero`
- `tests/test_inject_scorer.py::test_percentage_budget_saturates_for_an_arbitrarily_large_context_integer`
- `tests/test_inject_scorer.py::test_postgres_real_quantization_precedes_score_tie_breaking`

### A-027

- `tests/test_spend.py::test_canonical_views_are_double_run_deterministic_and_sentence_readable`
- `tests/test_spend.py::test_receipt_language_is_shipped_as_database_comments`
- `tests/test_spend.py::test_spend_contract_rejects_zero_lines_bad_enums_and_duplicate_ids`
- `tests/test_spend.py::test_spend_event_database_is_append_only`
- `tests/test_spend.py::test_spend_route_is_atomic_idempotent_and_conflict_safe`

### A-028

- `tests/test_vitals.py::test_spend_snapshot_escapes_reserved_and_tilde_model_keys_without_merging`
- `tests/test_vitals.py::test_thread_vitals_reads_only_authoritative_receipts_for_that_thread`
- `tests/test_vitals.py::test_vitals_has_an_empty_total_lane_and_rejects_query_parameters`
- `tests/test_vitals.py::test_vitals_requires_the_service_bearer`
- `tests/test_vitals.py::test_vitals_snapshot_is_canonical_conserving_and_honest`

### A-030

- `tests/test_inject_api.py::test_autonomous_prepare_preserves_locks_and_logs_entry_keep_exit`
- `tests/test_inject_api.py::test_budget_skip_continues_to_lower_scoring_candidate`
- `tests/test_inject_api.py::test_concurrent_prepare_is_one_shot_per_thread`
- `tests/test_inject_api.py::test_concurrent_threads_do_not_lose_injection_cas_updates`
- `tests/test_inject_api.py::test_exact_keyword_with_weak_embedding_reaches_the_gate_via_fts`
- `tests/test_inject_api.py::test_hybrid_pool_uses_or_terms_and_exact_uuid_tie_boundaries`
- `tests/test_inject_api.py::test_pins_bypass_threshold_and_budget_and_regular_ties_use_memory_id`
- `tests/test_inject_api.py::test_prepare_commit_replays_gate_and_prepare_updates_only_injected`
- `tests/test_inject_api.py::test_prepare_provider_failure_and_request_validation_are_write_free`
- `tests/test_inject_api.py::test_prepare_reads_one_frozen_database_snapshot`
- `tests/test_inject_api.py::test_unstamped_thread_requires_exact_identity_before_stamping`

### A-031

- `tests/test_learner_api.py::test_retrain_hygiene_excludes_whole_verification_gate`
- `tests/test_learner_api.py::test_retrain_proposes_inactive_content_addressed_winner_idempotently`
- `tests/test_learner_model.py::test_binary_replay_counts_each_override_and_applies_passive_discount`
- `tests/test_learner_model.py::test_disposition_and_hygiene_are_actor_classed_without_self_training`
- `tests/test_learner_model.py::test_replay_winner_requires_margin_except_for_exact_cheaper_tie`
- `tests/test_learner_model.py::test_time_split_keeps_whole_gates_and_uses_newest_for_holdout`
- `tests/test_learner_model.py::test_whole_log_fit_is_deterministic_simplex_constrained_and_shrunk`
- `tests/test_learner_scheduler.py::test_opt_in_scheduler_runs_after_interval_and_stops`

### A-032

- `tests/test_queue_api.py::test_candidate_is_queue_only_and_denial_is_revisioned_signal`
- `tests/test_queue_api.py::test_contradiction_cannot_passively_approve`
- `tests/test_queue_api.py::test_merge_approval_activates_candidate_tombstones_target_and_is_idempotent`
- `tests/test_queue_api.py::test_seed_batch_preserves_split_lineage_and_decides_atomically`

### A-035

- `tests/test_m2k_api.py::test_console_contributions_sum_exactly_and_control_inserts_a_version`
- `tests/test_m2k_api.py::test_memory_graph_uses_exact_encodings_and_current_membership`
- `tests/test_m2k_api.py::test_only_learner_proposals_can_be_activated_and_accuracy_is_measured`

### A-036

- `tests/test_commit_feedback_api.py::test_all_near_miss_empty_commit_is_repeatable_no_op`
- `tests/test_commit_feedback_api.py::test_autonomous_entry_accepts_one_citation_transition`
- `tests/test_commit_feedback_api.py::test_commit_mixed_gate_decisions_render_frozen_and_return_current_wrong`
- `tests/test_commit_feedback_api.py::test_commit_validation_and_concurrent_retry_are_atomic`
- `tests/test_commit_feedback_api.py::test_cross_injection_addbacks_serialize_counter_and_last_timestamp`
- `tests/test_commit_feedback_api.py::test_feedback_is_exactly_once_and_cited_increments_frequency`
- `tests/test_commit_feedback_api.py::test_lineage_failures_roll_back_commit_and_feedback`
- `tests/test_commit_feedback_api.py::test_mid_thread_removed_can_be_human_readded_and_removed_again`
- `tests/test_commit_feedback_api.py::test_never_uses_event_scorer_version_and_preserves_terminal_status`
- `tests/test_commit_feedback_api.py::test_renderer_encodes_control_attributes_and_breaks_rank_ties_by_memory_id`
- `tests/test_commit_feedback_api.py::test_third_never_from_near_miss_quarantines_and_zero_card_commit_is_canonical`

### A-037

- `tests/test_reconciliation.py::test_baseline_balanced_drift_and_vitals_projection`
- `tests/test_reconciliation.py::test_openrouter_client_reads_only_current_key_usage`
- `tests/test_reconciliation.py::test_scheduler_runs_immediately_and_stops_cleanly`
- `tests/test_reconciliation.py::test_unavailable_is_safe_and_reconciliation_rows_are_append_only`

### A-040

- `tests/test_test_motivations.py::test_syntax_digest_turns_a_modified_grandfathered_test_into_a_failure`

### A-041

- `tests/test_m2n_migrations.py::test_migration_lock_releases_after_success_and_failure`

### A-044

- `tests/test_api.py::test_committed_openapi_is_current`
- `tests/test_vitals.py::test_vitals_measures_database_size_without_guessing_harness_resources`

### A-047

- `tests/test_api.py::test_exactly_the_lawful_spine_routes_are_registered`
- `tests/test_m2k_api.py::test_console_contributions_sum_exactly_and_control_inserts_a_version`
- `tests/test_m2k_api.py::test_only_learner_proposals_can_be_activated_and_accuracy_is_measured`

### F027

- `tests/test_memory_api.py::test_memory_split_preserves_exact_source_and_writes_one_linked_active_family`
- `tests/test_memory_api.py::test_memory_split_preserves_existing_label_and_duplicate_conflict_bodies`
- `tests/test_memory_api.py::test_memory_split_rejects_invalid_or_lossy_families_before_embedding`
- `tests/test_memory_api.py::test_memory_split_returns_first_near_similar_child_without_any_write`
- `tests/test_memory_api.py::test_memory_split_rolls_back_heads_revisions_and_edges_on_late_insert_failure`

### P4

- `tests/test_billing_breaker.py::test_below_budget_fixture_never_constructs_gateway`
- `tests/test_billing_breaker.py::test_billing_api_failure_is_logged_and_propagated`
- `tests/test_billing_breaker.py::test_cloud_event_entrypoint_builds_the_exact_sdk_detach_request`
- `tests/test_billing_breaker.py::test_cloud_event_entrypoint_rejects_an_unconfirmed_postcondition`
- `tests/test_billing_breaker.py::test_deploy_billing_account_control_is_human_only`
- `tests/test_billing_breaker.py::test_deploy_billing_role_and_public_members_are_exact`
- `tests/test_billing_breaker.py::test_deploy_budget_validator_accepts_only_disconnected_or_exact_armed_phase`
- `tests/test_billing_breaker.py::test_deploy_budget_validator_rejects_extra_project_and_wrong_topic`
- `tests/test_billing_breaker.py::test_deploy_budget_validator_rejects_narrowing_filters`
- `tests/test_billing_breaker.py::test_deploy_budget_validator_requires_billing_account_ownership`
- `tests/test_billing_breaker.py::test_deploy_function_and_run_policy_pin_all_identities`
- `tests/test_billing_breaker.py::test_deploy_function_rejects_wrong_runtime_or_identity_configuration`
- `tests/test_billing_breaker.py::test_deploy_message_path_resources_forbid_single_message_transforms`
- `tests/test_billing_breaker.py::test_deploy_project_bindings_and_billing_manager_membership_are_exact`
- `tests/test_billing_breaker.py::test_deploy_rejects_old_eventarc_paths_to_fresh_d2_names`
- `tests/test_billing_breaker.py::test_deploy_resource_absence_uses_successful_exact_list_results`
- `tests/test_billing_breaker.py::test_deploy_role_permissions_allow_only_current_project_service_agents`
- `tests/test_billing_breaker.py::test_deploy_role_permissions_reject_untrusted_destructive_access`
- `tests/test_billing_breaker.py::test_deploy_run_policy_rejects_public_or_extra_invokers`
- `tests/test_billing_breaker.py::test_deploy_script_is_default_inert_and_least_privileged`
- `tests/test_billing_breaker.py::test_deploy_service_account_policy_must_be_empty`
- `tests/test_billing_breaker.py::test_deploy_topic_policy_allows_only_the_budget_publisher`
- `tests/test_billing_breaker.py::test_deploy_topic_subscription_list_includes_cross_project_names`
- `tests/test_billing_breaker.py::test_duplicate_delivery_repeats_the_same_idempotent_desired_state`
- `tests/test_billing_breaker.py::test_equality_and_overage_detach_the_fixed_project`
- `tests/test_billing_breaker.py::test_invalid_or_foreign_notifications_are_logged_and_acknowledged`
- `tests/test_billing_breaker.py::test_malformed_base64_and_json_never_reach_the_gateway`
- `tests/test_billing_breaker.py::test_runbook_proves_subscription_and_resource_absence_from_lists`
- `tests/test_packaging.py::test_container_base_is_an_exact_multiarch_python_release`
- `tests/test_packaging.py::test_distribution_metadata_uses_the_package_version`
- `tests/test_packaging.py::test_materialize_app_source_is_an_allowlisted_rebuildable_context`
- `tests/test_packaging.py::test_materialize_billing_breaker_preserves_human_deploy_path`
- `tests/test_packaging.py::test_materializers_refuse_nonempty_destinations`

## Baseline debt

_None._

## Stale baseline entries

_None._
