# STREET_SEMANTIC_MATRIX

수정 전 기준. 모든 registry 행을 포함한다. `same`은 같은 poker question의 수식/데이터 producer 재사용이며 모든 street의 action 정책이 같다는 뜻이 아니다. `overloaded`는 다른 질문이 공용 함수/skill에 남음. `distinct` 뒤에는 실제 producer를 적었다. producer가 다른 행과 같으면 아직 inline 분기이며 추출 전이다. 실제 추출 후 이름/배선은 REFACTOR_AND_VERIFICATION에서 함께 추적한다. SHADOW/OPT-IN 여부는 registry 상태를 함께 본다.

| concept | preflop | flop | turn | river |
| --- | --- | --- | --- | --- |
| bluff | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| semibluff | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | not applicable |
| cbet_flop | not applicable | distinct — persona.make_player;persona.sk | not applicable | not applicable |
| barrel_turn | not applicable | not applicable | distinct — persona.make_player;persona.sk | not applicable |
| barrel_river | not applicable | not applicable | not applicable | distinct — persona.make_player;persona.sk |
| checkraise_flop | not applicable | overloaded — persona.make_player;persona.sk | not applicable | not applicable |
| checkraise_late | not applicable | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| bluffcatch_early | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | not applicable |
| bluffcatch_river | not applicable | not applicable | not applicable | overloaded — persona.make_player;persona.sk |
| thin_value_turn | not applicable | not applicable | distinct — persona.make_player;persona.sk | not applicable |
| thin_value_river | not applicable | not applicable | not applicable | distinct — persona.make_player;persona.sk |
| blockbet | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| potcontrol | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| trap | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| overbet | not applicable | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| probe | not applicable | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| delayed_cbet | not applicable | not applicable | distinct — persona.make_player;persona.sk | not applicable |
| equity_denial | not applicable | same — persona.make_player;persona.sk | same — persona.make_player;persona.sk | not applicable |
| stackoff | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| reraise | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| outs | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | not applicable |
| potodds | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| spr | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| range_read | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| blocker | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| icm | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| board_texture | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| sizing_tell | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| pf_range | overloaded — persona.make_player;persona.sk | not applicable | not applicable | not applicable |
| positional | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| stack_decay | same — persona.make_player;persona.sk | same — persona.make_player;persona.sk | same — persona.make_player;persona.sk | same — persona.make_player;persona.sk |
| open_size | distinct — persona.make_player;persona.sk | not applicable | not applicable | not applicable |
| pf_defend | overloaded — persona.make_player;persona.sk | not applicable | not applicable | not applicable |
| range_merge | not applicable | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| multiway | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| fold_equity | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk | overloaded — persona.make_player;persona.sk |
| money_jump | same — persona.make_player;persona.sk | same — persona.make_player;persona.sk | same — persona.make_player;persona.sk | same — persona.make_player;persona.sk |
| legal_call_price | same — runner.Round.to_call | same — runner.Round.to_call | same — runner.Round.to_call | same — runner.Round.to_call |
| raise_reopening_rights | same — runner.Round.can_raise;runner.Round._only_incomplete | same — runner.Round.can_raise;runner.Round._only_incomplete | same — runner.Round.can_raise;runner.Round._only_incomplete | same — runner.Round.can_raise;runner.Round._only_incomplete |
| legal_action_application | same — runner.Round.apply | same — runner.Round.apply | same — runner.Round.apply | same — runner.Round.apply |
| contestable_pot | same — runner.Round.contestable_contrib | same — runner.Round.contestable_contrib | same — runner.Round.contestable_contrib | same — runner.Round.contestable_contrib |
| uncalled_return | same — runner.Round.settle_uncalled | same — runner.Round.settle_uncalled | same — runner.Round.settle_uncalled | same — runner.Round.settle_uncalled |
| public_action_kind | not applicable | same — action_events.normalized_action | same — action_events.normalized_action | same — action_events.normalized_action |
| public_postflop_story | not applicable | same — action_events.postflop_events | same — action_events.postflop_events | same — action_events.postflop_events |
| facing_response_kind | not applicable | same — action_events.response_context;action_events.pending_response_context | same — action_events.response_context;action_events.pending_response_context | same — action_events.response_context;action_events.pending_response_context |
| facing_wager_geometry | not applicable | same — action_events.facing_wager_context | same — action_events.facing_wager_context | same — action_events.facing_wager_context |
| aggressive_street_count | not applicable | same — action_events.aggressive_street_count;session._barrel_count | same — action_events.aggressive_street_count;session._barrel_count | same — action_events.aggressive_street_count;session._barrel_count |
| street_line_outcome | not applicable | same — action_events.street_outcome | same — action_events.street_outcome | same — action_events.street_outcome |
| preflop_public_roles | overloaded — session._pf_observation_flags;session._preflop_public_action_context;session._cold_reraise_context | not applicable | not applicable | not applicable |
| preflop_role_memory | same — session._merge_pf_seed;session._update_pf_state_after_apply | same — session._merge_pf_seed;session._update_pf_state_after_apply | same — session._merge_pf_seed;session._update_pf_state_after_apply | same — session._merge_pf_seed;session._update_pf_state_after_apply |
| absolute_field_position | not applicable | same — session.oop_field | same — session.oop_field | same — session.oop_field |
| aggressor_relative_position | not applicable | same — session.oop_vs | same — session.oop_vs | same — session.oop_vs |
| initiative_owner | same — runner.has_initiative | same — runner.has_initiative | same — runner.has_initiative | same — runner.has_initiative |
| called_aggression_ownership | not applicable | not applicable | overloaded — plan._called_prior_street_aggression | overloaded — plan._called_prior_street_aggression |
| rfi_width_prior | distinct — gto.rfi;gto.depth_mult;gto.behind_of | not applicable | not applicable | not applicable |
| defend_width_prior | distinct — gto.defend_pct;gto.mdf | not applicable | not applicable | not applicable |
| threebet_width_prior | overloaded — gto.threebet_pct | not applicable | not applicable | not applicable |
| chart_memory_accuracy | overloaded — persona.gto_knowledge;persona.gto_memory_confidence | not applicable | not applicable | not applicable |
| studied_condition_match | distinct — persona.gto_condition_match;persona.gto_studied_anchor | not applicable | not applicable | not applicable |
| preflop_condition_reasoning | distinct — persona.preflop_reasoning_confidence;persona.preflop_reasoned_width | not applicable | not applicable | not applicable |
| legacy_preflop_ordering | overloaded — preflop.pct;preflop.cls | not applicable | not applicable | not applicable |
| fallback_preflop_ordering | same — bot._pf_score;bot.range_combos | same — bot._pf_score;bot.range_combos | same — bot._pf_score;bot.range_combos | same — bot._pf_score;bot.range_combos |
| rfi_personality_deviation | overloaded — persona.open_pct | not applicable | not applicable | not applicable |
| limp_entry_motive | overloaded — preflop.limp_p | not applicable | not applicable | not applicable |
| open_execution_form | distinct — preflop.open_form | not applicable | not applicable | not applicable |
| open_sizing | distinct — preflop.open_size_bb;preflop.round_unit_bb | not applicable | not applicable | not applicable |
| unopened_decision | overloaded — preflop.open_decision | not applicable | not applicable | not applicable |
| isolation_decision | overloaded — preflop.iso_decision | not applicable | not applicable | not applicable |
| defend_attack_continue_widths | overloaded — preflop.defend_thresholds;preflop._saturate | not applicable | not applicable | not applicable |
| mixed_preflop_action_likelihood | distinct — preflop.defend_action_likelihoods | not applicable | not applicable | not applicable |
| sample_defend_action | distinct — preflop.defend_decision | not applicable | not applicable | not applicable |
| reraise_sizing_form | overloaded — preflop.raise_form;preflop.reraise_mult | not applicable | not applicable | not applicable |
| reshove_opportunity | overloaded — preflop.in_hotzone;preflop.reshove_range;preflop.reshove_weight;preflop.hotzone_pressure | not applicable | not applicable | not applicable |
| behind_player_threat | distinct — preflop.table_pressure | not applicable | not applicable | not applicable |
| preflop_card_removal | overloaded — preflop.preflop_blocker_share | not applicable | not applicable | not applicable |
| multiway_reraise_reasoning | distinct — preflop.multiway_reraise_decision;preflop.cold_reraise_decision | not applicable | not applicable | not applicable |
| legacy_calloff_threshold | overloaded — preflop.calloff_cap;preflop.calloff_decision | not applicable | not applicable | not applicable |
| layer_calloff_judgment | overloaded — preflop.calloff_layer_judgment | not applicable | not applicable | not applicable |
| calloff_comparison_shadow | distinct — preflop.calloff_ev_comparison | not applicable | not applicable | not applicable |
| weighted_combo_measure | same — ranges.weighted_range;ranges.range_items;ranges.range_mass;ranges.range_weight | same — ranges.weighted_range;ranges.range_items;ranges.range_mass;ranges.range_weight | same — ranges.weighted_range;ranges.range_items;ranges.range_mass;ranges.range_weight | same — ranges.weighted_range;ranges.range_items;ranges.range_mass;ranges.range_weight |
| weighted_range_transform | same — ranges.range_filter;ranges.range_select;ranges.range_copy;ranges.range_union | same — ranges.range_filter;ranges.range_select;ranges.range_copy;ranges.range_union | same — ranges.range_filter;ranges.range_select;ranges.range_copy;ranges.range_union | same — ranges.range_filter;ranges.range_select;ranges.range_copy;ranges.range_union |
| range_identity_signature | overloaded — ranges.range_signature;plan._range_sig;plan._decision_range_sig;plan._opp_ranges_signature | overloaded — ranges.range_signature;plan._range_sig;plan._decision_range_sig;plan._opp_ranges_signature | overloaded — ranges.range_signature;plan._range_sig;plan._decision_range_sig;plan._opp_ranges_signature | overloaded — ranges.range_signature;plan._range_sig;plan._decision_range_sig;plan._opp_ranges_signature |
| preflop_posterior_order | overloaded — ranges.preflop_reraise_posterior | not applicable | not applicable | not applicable |
| inverse_defend_likelihood | distinct — ranges._defend_likelihood_range | not applicable | not applicable | not applicable |
| preflop_range_reconstruction | same — session._preflop_story_range;session.HandRun._preflop_perceived_range;ranges.preflop_range | same — session._preflop_story_range;session.HandRun._preflop_perceived_range;ranges.preflop_range | same — session._preflop_story_range;session.HandRun._preflop_perceived_range;ranges.preflop_range | same — session._preflop_story_range;session.HandRun._preflop_perceived_range;ranges.preflop_range |
| postflop_action_posterior | not applicable | same — ranges.narrow_by_actions;session.HandRun._acts_of | same — ranges.narrow_by_actions;session.HandRun._acts_of | same — ranges.narrow_by_actions;session.HandRun._acts_of |
| range_reconstruction_grasp | not applicable | same — ranges.perceived_range;ranges.perceived_continue_range;ranges.perceived_facing_bet_response | same — ranges.perceived_range;ranges.perceived_continue_range;ranges.perceived_facing_bet_response | same — ranges.perceived_range;ranges.perceived_continue_range;ranges.perceived_facing_bet_response |
| line_bluff_composition | not applicable | same — ranges.line_bluff_share;bot.bluff_share;plan.line_bluff_prior | same — ranges.line_bluff_share;bot.bluff_share;plan.line_bluff_prior | same — ranges.line_bluff_share;bot.bluff_share;plan.line_bluff_prior |
| bet_range_partition | not applicable | overloaded — ranges._bet_range;bot.pick_bluffs | overloaded — ranges._bet_range;bot.pick_bluffs | overloaded — ranges._bet_range;bot.pick_bluffs |
| continue_range_partition | not applicable | same — ranges._continue_range | same — ranges._continue_range | same — ranges._continue_range |
| call_range_partition | not applicable | same — ranges._call_range | same — ranges._call_range | same — ranges._call_range |
| check_range_posterior | not applicable | same — ranges._check_range | same — ranges._check_range | same — ranges._check_range |
| raise_range_posterior | not applicable | overloaded — ranges._raise_range | overloaded — ranges._raise_range | overloaded — ranges._raise_range |
| hand_category | not applicable | same — bot.eval5;bot.eval7;session.best5 | same — bot.eval5;bot.eval7;session.best5 | same — bot.eval5;bot.eval7;session.best5 |
| hero_made_contribution | not applicable | same — bot.made_strength | same — bot.made_strength | same — bot.made_strength |
| future_draw_outs | not applicable | same — bot.draw_strength | same — bot.draw_strength | not applicable |
| current_board_not_behind | not applicable | same — plan.relative_strength;plan.joint_relative_strength;plan._decision_relative_strength | same — plan.relative_strength;plan.joint_relative_strength;plan._decision_relative_strength | same — plan.relative_strength;plan.joint_relative_strength;plan._decision_relative_strength |
| showdown_equity_share | same — bot._showdown_share;bot.equity_vs_pools;bot.equity_vs_combos | same — bot._showdown_share;bot.equity_vs_pools;bot.equity_vs_combos | same — bot._showdown_share;bot.equity_vs_pools;bot.equity_vs_combos | same — bot._showdown_share;bot.equity_vs_pools;bot.equity_vs_combos |
| unconditioned_equity | same — bot.equity;bot.equity_vs_range | same — bot.equity;bot.equity_vs_range | same — bot.equity;bot.equity_vs_range | same — bot.equity;bot.equity_vs_range |
| weighted_joint_sampling | same — bot._filter_pool;bot._sample_pool_combo;bot.equity_vs_pools | same — bot._filter_pool;bot._sample_pool_combo;bot.equity_vs_pools | same — bot._filter_pool;bot._sample_pool_combo;bot.equity_vs_pools | same — bot._filter_pool;bot._sample_pool_combo;bot.equity_vs_pools |
| range_advantage | not applicable | same — ranges.range_advantage;ranges.joint_range_advantage;plan._decision_range_advantage | same — ranges.range_advantage;ranges.joint_range_advantage;plan._decision_range_advantage | same — ranges.range_advantage;ranges.joint_range_advantage;plan._decision_range_advantage |
| strong_region_advantage | not applicable | same — ranges._strong_share;ranges.nut_advantage;ranges.joint_nut_advantage;plan._decision_nut_advantage | same — ranges._strong_share;ranges.nut_advantage;ranges.joint_nut_advantage;plan._decision_nut_advantage | same — ranges._strong_share;ranges.nut_advantage;ranges.joint_nut_advantage;plan._decision_nut_advantage |
| strong_support_blocker | not applicable | overloaded — ranges.blocker_score | overloaded — ranges.blocker_score | overloaded — ranges.blocker_score |
| continue_fold_blocker | not applicable | same — ranges.blocker_effect;ranges.joint_blocker_effect;plan._decision_blocker_effect | same — ranges.blocker_effect;ranges.joint_blocker_effect;plan._decision_blocker_effect | same — ranges.blocker_effect;ranges.joint_blocker_effect;plan._decision_blocker_effect |
| relative_strength_perception | not applicable | overloaded — plan.perceived_rel | overloaded — plan.perceived_rel | overloaded — plan.perceived_rel |
| spr_ratio | same — plan.spr | same — plan.spr | same — plan.spr | same — plan.spr |
| depth_perception | overloaded — depth.depth_feel;depth.base_feel;depth.field_adjusted_bb;depth.eroded_bb;depth.lookahead_hands;preflop.feel_of | overloaded — depth.depth_feel;depth.base_feel;depth.field_adjusted_bb;depth.eroded_bb;depth.lookahead_hands;preflop.feel_of | overloaded — depth.depth_feel;depth.base_feel;depth.field_adjusted_bb;depth.eroded_bb;depth.lookahead_hands;preflop.feel_of | overloaded — depth.depth_feel;depth.base_feel;depth.field_adjusted_bb;depth.eroded_bb;depth.lookahead_hands;preflop.feel_of |
| board_structure_facts | not applicable | same — texture.classify;plan.board_paired | same — texture.classify;plan.board_paired | same — texture.classify;plan.board_paired |
| board_completion_danger | not applicable | overloaded — bot.board_danger | overloaded — bot.board_danger | overloaded — bot.board_danger |
| flop_texture_cbet_prior | not applicable | distinct — texture.cbet_multiplier | not applicable | not applicable |
| street_texture_sizing | not applicable | overloaded — texture.size_fraction;texture.perceived | overloaded — texture.size_fraction;texture.perceived | overloaded — texture.size_fraction;texture.perceived |
| turn_card_range_shift | not applicable | not applicable | overloaded — texture.turn_card_effect | not applicable |
| replan_board_change | not applicable | not applicable | same — runner.board_changed | same — runner.board_changed |
| calculation_error | overloaded — persona.calc_noise | overloaded — persona.calc_noise | overloaded — persona.calc_noise | overloaded — persona.calc_noise |
| value_line_selection | not applicable | overloaded — plan.make_plan | overloaded — plan.make_plan | overloaded — plan.make_plan |
| vulnerable_paired_flush | not applicable | overloaded — plan.make_plan;plan.decide_response | overloaded — plan.make_plan;plan.decide_response | overloaded — plan.make_plan;plan.decide_response |
| shallow_one_pair_value | not applicable | same — plan.make_plan | same — plan.make_plan | same — plan.make_plan |
| deep_one_pair_caution | not applicable | overloaded — plan.make_plan;plan.decide_response | overloaded — plan.make_plan;plan.decide_response | overloaded — plan.make_plan;plan.decide_response |
| continue_range_value | not applicable | overloaded — plan.make_plan;plan.decide_response;plan.river_fix;plan.refresh | overloaded — plan.make_plan;plan.decide_response;plan.river_fix;plan.refresh | overloaded — plan.make_plan;plan.decide_response;plan.river_fix;plan.refresh |
| semibluff_line_selection | not applicable | overloaded — plan.make_plan;plan.decide_response;plan.refresh | overloaded — plan.make_plan;plan.decide_response;plan.refresh | not applicable |
| pure_bluff_line_selection | not applicable | overloaded — plan.make_plan;plan.bluff_mode | overloaded — plan.make_plan;plan.bluff_mode | overloaded — plan.make_plan;plan.bluff_mode |
| potcontrol_motive | not applicable | overloaded — plan.make_plan;plan.refresh | overloaded — plan.make_plan;plan.refresh | overloaded — plan.make_plan;plan.refresh |
| potcontrol_bet_propensity | not applicable | overloaded — plan.decide_aggression | overloaded — plan.decide_aggression | overloaded — plan.decide_aggression |
| blockbet_motive | not applicable | overloaded — plan.make_plan | overloaded — plan.make_plan | overloaded — plan.make_plan |
| trap_induction | not applicable | overloaded — plan.trap_judgment;plan.opp_bet_prob | overloaded — plan.trap_judgment;plan.opp_bet_prob | overloaded — plan.trap_judgment;plan.opp_bet_prob |
| trap_release_no_bite | not applicable | not applicable | same — plan.mark_no_bite;plan.refresh | same — plan.mark_no_bite;plan.refresh |
| draw_completion_value_gate | not applicable | not applicable | same — plan.refresh;plan.river_fix | same — plan.refresh;plan.river_fix |
| strength_improvement_promotion | not applicable | not applicable | same — plan.refresh | same — plan.refresh |
| missed_draw_river_conversion | not applicable | not applicable | not applicable | overloaded — plan.river_fix |
| river_thin_value | not applicable | not applicable | not applicable | distinct — plan.river_fix |
| flop_cbet_plan | not applicable | overloaded — plan.cbet_freq;plan.decide_aggression | not applicable | not applicable |
| turn_barrel_plan | not applicable | not applicable | overloaded — plan.cbet_freq;plan.decide_aggression | not applicable |
| river_barrel_plan | not applicable | not applicable | not applicable | overloaded — plan.cbet_freq;plan.decide_aggression |
| probe_after_checkthrough | not applicable | not applicable | overloaded — plan.decide_aggression | overloaded — plan.decide_aggression |
| turn_delayed_cbet | not applicable | not applicable | distinct — plan.decide_aggression | not applicable |
| bet_budget | not applicable | same — plan.budget_left | same — plan.budget_left | same — plan.budget_left |
| aggression_intent_sampling | not applicable | same — plan.attach_intent;plan.mk_intent;plan.set_intent;plan.intent_of | same — plan.attach_intent;plan.mk_intent;plan.set_intent;plan.intent_of | same — plan.attach_intent;plan.mk_intent;plan.set_intent;plan.intent_of |
| planned_bet_sizing | not applicable | overloaded — plan.decide_size | overloaded — plan.decide_size | overloaded — plan.decide_size |
| turn_overbet | not applicable | not applicable | overloaded — plan.overbet_frac | not applicable |
| river_overbet | not applicable | not applicable | not applicable | overloaded — plan.overbet_frac |
| equity_denial_sizing | not applicable | same — plan.decide_size | same — plan.decide_size | not applicable |
| target_investment_fraction | not applicable | overloaded — plan.target_commit | overloaded — plan.target_commit | overloaded — plan.target_commit |
| stackoff_spread_horizon | not applicable | overloaded — plan.stackoff_plan;plan.spread_curve | overloaded — plan.stackoff_plan;plan.spread_curve | overloaded — plan.stackoff_plan;plan.spread_curve |
| bluff_sizing_camouflage | not applicable | same — plan.bluff_mode;plan.barrel_size;plan.breakeven_fold | same — plan.bluff_mode;plan.barrel_size;plan.breakeven_fold | same — plan.bluff_mode;plan.barrel_size;plan.breakeven_fold |
| calldown_required_share | not applicable | overloaded — plan.calldown_need | overloaded — plan.calldown_need | overloaded — plan.calldown_need |
| nonvalue_raise_ev_gate | not applicable | overloaded — plan._nonvalue_raise_ev_gate | overloaded — plan._nonvalue_raise_ev_gate | overloaded — plan._nonvalue_raise_ev_gate |
| response_plan | not applicable | overloaded — plan.decide_response;plan.record_response_plan | overloaded — plan.decide_response;plan.record_response_plan | overloaded — plan.decide_response;plan.record_response_plan |
| call_bias_reapplication | not applicable | same — persona.call_bias;persona.bias;plan.decide_response | same — persona.call_bias;persona.bias;plan.decide_response | same — persona.call_bias;persona.bias;plan.decide_response |
| checkraise_flop_decision | not applicable | overloaded — plan.checkraise_decision | not applicable | not applicable |
| checkraise_turn_decision | not applicable | not applicable | overloaded — plan.checkraise_decision | not applicable |
| checkraise_river_decision | not applicable | not applicable | not applicable | overloaded — plan.checkraise_decision |
| checkraise_sizing | not applicable | overloaded — plan.checkraise_size | overloaded — plan.checkraise_size | overloaded — plan.checkraise_size |
| action_adapter_with_reasoning | not applicable | overloaded — plan.act_with_plan | overloaded — plan.act_with_plan | overloaded — plan.act_with_plan |
| human_planned_size_shape | same — persona.shape_size;persona.sizing_signature;plan.shape_planned_target | same — persona.shape_size;persona.sizing_signature;plan.shape_planned_target | same — persona.shape_size;persona.sizing_signature;plan.shape_planned_target | same — persona.shape_size;persona.sizing_signature;plan.shape_planned_target |
| effective_allin_promotion | not applicable | same — runner.effective_allin_v1 | same — runner.effective_allin_v1 | same — runner.effective_allin_v1 |
| plan_revision_lifecycle | not applicable | overloaded — plan.update_plan;runner.revise_plan;plan.refresh | overloaded — plan.update_plan;runner.revise_plan;plan.refresh | overloaded — plan.update_plan;runner.revise_plan;plan.refresh |
| plan_concept_permission | not applicable | overloaded — plan._allowed | overloaded — plan._allowed | overloaded — plan._allowed |
| opponent_fold_constraint | not applicable | same — plan.select_field_opponent | same — plan.select_field_opponent | same — plan.select_field_opponent |
| opponent_trap_target | not applicable | same — plan.select_field_opponent;plan.opp_bet_prob | same — plan.select_field_opponent;plan.opp_bet_prob | same — plan.select_field_opponent;plan.opp_bet_prob |
| field_effective_depth | not applicable | same — plan.field_effective_stack_bb | same — plan.field_effective_stack_bb | same — plan.field_effective_stack_bb |
| opponent_behavior_memory | overloaded — reads.Book.rec;reads.Book.observe_preflop;reads.Book.observe_postflop;reads.Book.observe_size | overloaded — reads.Book.rec;reads.Book.observe_preflop;reads.Book.observe_postflop;reads.Book.observe_size | overloaded — reads.Book.rec;reads.Book.observe_preflop;reads.Book.observe_postflop;reads.Book.observe_size | overloaded — reads.Book.rec;reads.Book.observe_preflop;reads.Book.observe_postflop;reads.Book.observe_size |
| preflop_raise_observation | distinct — reads.Book.observe_3bet;reads.Book.observe_4bet;reads.Book.observe_backraise;reads.Book.observe_cold_reraise;reads.Book.observe_limp_raise | not applicable | not applicable | not applicable |
| showdown_strength_observation | overloaded — reads.Book.observe_showdown;session.HandRun._finish;dynamics.Tilt.note_showdown | overloaded — reads.Book.observe_showdown;session.HandRun._finish;dynamics.Tilt.note_showdown | overloaded — reads.Book.observe_showdown;session.HandRun._finish;dynamics.Tilt.note_showdown | overloaded — reads.Book.observe_showdown;session.HandRun._finish;dynamics.Tilt.note_showdown |
| opponent_estimation | overloaded — reads.estimate;reads._shrink;reads.obs_from_profile | overloaded — reads.estimate;reads._shrink;reads.obs_from_profile | overloaded — reads.estimate;reads._shrink;reads.obs_from_profile | overloaded — reads.estimate;reads._shrink;reads.obs_from_profile |
| opponent_concept_inference | same — reads.infer_latent;reads.estimate_concepts;reads.perceived_profile;reads.range_profile | same — reads.infer_latent;reads.estimate_concepts;reads.perceived_profile;reads.range_profile | same — reads.infer_latent;reads.estimate_concepts;reads.perceived_profile;reads.range_profile | same — reads.infer_latent;reads.estimate_concepts;reads.perceived_profile;reads.range_profile |
| style_belief_reference | same — reads.style_hypotheses;reads.concept_belief;reads.opponent_belief | same — reads.style_hypotheses;reads.concept_belief;reads.opponent_belief | same — reads.style_hypotheses;reads.concept_belief;reads.opponent_belief | same — reads.style_hypotheses;reads.concept_belief;reads.opponent_belief |
| recency_window | same — reads._append_hand_snapshot;reads._recent_record | same — reads._append_hand_snapshot;reads._recent_record | same — reads._append_hand_snapshot;reads._recent_record | same — reads._append_hand_snapshot;reads._recent_record |
| exploit_read_permission | overloaded — persona._exploit_base_weight;persona.exploit_weight;persona.read_opponent;persona.street_gap | overloaded — persona._exploit_base_weight;persona.exploit_weight;persona.read_opponent;persona.street_gap | overloaded — persona._exploit_base_weight;persona.exploit_weight;persona.read_opponent;persona.street_gap | overloaded — persona._exploit_base_weight;persona.exploit_weight;persona.read_opponent;persona.street_gap |
| opponent_sizing_normalization | not applicable | overloaded — persona.opp_size_norm;persona.size_read | overloaded — persona.opp_size_norm;persona.size_read | overloaded — persona.opp_size_norm;persona.size_read |
| shown_hand_range_adjustment | not applicable | overloaded — runner.adjust_range_by_history | overloaded — runner.adjust_range_by_history | overloaded — runner.adjust_range_by_history |
| perceived_player_edge | same — persona.perceived_edge;preflop.crude_edge | same — persona.perceived_edge;preflop.crude_edge | same — persona.perceived_edge;preflop.crude_edge | same — persona.perceived_edge;preflop.crude_edge |
| accumulation_variance_drive | overloaded — persona.accum_drive;persona.variance_seek | overloaded — persona.accum_drive;persona.variance_seek | overloaded — persona.accum_drive;persona.variance_seek | overloaded — persona.accum_drive;persona.variance_seek |
| icm_exact_share | same — icm.icm_equity;icm._icm_equity_subset;icm._icm_equity_reference;icm._subset_path_prune_safe | same — icm.icm_equity;icm._icm_equity_subset;icm._icm_equity_reference;icm._subset_path_prune_safe | same — icm.icm_equity;icm._icm_equity_subset;icm._icm_equity_reference;icm._subset_path_prune_safe | same — icm.icm_equity;icm._icm_equity_subset;icm._icm_equity_reference;icm._subset_path_prune_safe |
| icm_bubble_factor | overloaded — icm.bubble_factor;icm.table_bf;play.Hand.bf | overloaded — icm.bubble_factor;icm.table_bf;play.Hand.bf | overloaded — icm.bubble_factor;icm.table_bf;play.Hand.bf | overloaded — icm.bubble_factor;icm.table_bf;play.Hand.bf |
| field_icm_proxy | same — icm.stage_pressure;icm.stack_pressure;icm.field_bf | same — icm.stage_pressure;icm.stack_pressure;icm.field_bf | same — icm.stage_pressure;icm.stack_pressure;icm.field_bf | same — icm.stage_pressure;icm.stack_pressure;icm.field_bf |
| perceived_icm_pressure | same — persona.icm_signal;persona.icm_aware;persona.icm_bf;persona.icm_press | same — persona.icm_signal;persona.icm_aware;persona.icm_bf;persona.icm_press | same — persona.icm_signal;persona.icm_aware;persona.icm_bf;persona.icm_press | same — persona.icm_signal;persona.icm_aware;persona.icm_bf;persona.icm_press |
| icm_required_equity_reference | same — icm.required_equity | same — icm.required_equity | same — icm.required_equity | same — icm.required_equity |
| payout_jump_context | same — context.money_jump_context;context.progress_of;formats.payouts | same — context.money_jump_context;context.progress_of;formats.payouts | same — context.money_jump_context;context.progress_of;formats.payouts | same — context.money_jump_context;context.progress_of;formats.payouts |
| money_jump_seat_topology | same — session._money_jump_observe | same — session._money_jump_observe | same — session._money_jump_observe | same — session._money_jump_observe |
| payout_importance | same — money_pressure.payout_importance | same — money_pressure.payout_importance | same — money_pressure.payout_importance | same — money_pressure.payout_importance |
| ladder_wait_buffer | same — money_pressure.ladder_buffer;money_pressure.shorter_severity;money_pressure.waiting_feasibility | same — money_pressure.ladder_buffer;money_pressure.shorter_severity;money_pressure.waiting_feasibility | same — money_pressure.ladder_buffer;money_pressure.shorter_severity;money_pressure.waiting_feasibility | same — money_pressure.ladder_buffer;money_pressure.shorter_severity;money_pressure.waiting_feasibility |
| money_self_preservation | same — money_pressure.objective_self_preservation;money_pressure.perceived_self_preservation | same — money_pressure.objective_self_preservation;money_pressure.perceived_self_preservation | same — money_pressure.objective_self_preservation;money_pressure.perceived_self_preservation | same — money_pressure.objective_self_preservation;money_pressure.perceived_self_preservation |
| money_urgency | same — money_pressure.objective_urgency;money_pressure.perceived_urgency | same — money_pressure.objective_urgency;money_pressure.perceived_urgency | same — money_pressure.objective_urgency;money_pressure.perceived_urgency | same — money_pressure.objective_urgency;money_pressure.perceived_urgency |
| stack_cover_pressure | overloaded — money_pressure.cover_strength;money_pressure.topology_safety;money_pressure.structural_pressure;money_pressure.pressure_opportunity;money_pressure.exploit_realization;money_pressure.read_adjustment | overloaded — money_pressure.cover_strength;money_pressure.topology_safety;money_pressure.structural_pressure;money_pressure.pressure_opportunity;money_pressure.exploit_realization;money_pressure.read_adjustment | overloaded — money_pressure.cover_strength;money_pressure.topology_safety;money_pressure.structural_pressure;money_pressure.pressure_opportunity;money_pressure.exploit_realization;money_pressure.read_adjustment | overloaded — money_pressure.cover_strength;money_pressure.topology_safety;money_pressure.structural_pressure;money_pressure.pressure_opportunity;money_pressure.exploit_realization;money_pressure.read_adjustment |
| money_commitment_budget | same — money_pressure.commitment_budget;money_pressure.low_commit_pressure | same — money_pressure.commitment_budget;money_pressure.low_commit_pressure | same — money_pressure.commitment_budget;money_pressure.low_commit_pressure | same — money_pressure.commitment_budget;money_pressure.low_commit_pressure |
| money_open_range_modifier | distinct — money_pressure.unopened_modifiers | not applicable | not applicable | not applicable |
| money_open_form_shadow | distinct — money_pressure.unopened_modifiers | not applicable | not applicable | not applicable |
| sidepot_geometry | same — session._decision_pot_layers;session._project_call_layers;session._project_bet_outcome_layers | same — session._decision_pot_layers;session._project_call_layers;session._project_bet_outcome_layers | same — session._decision_pot_layers;session._project_call_layers;session._project_bet_outcome_layers | same — session._decision_pot_layers;session._project_call_layers;session._project_bet_outcome_layers |
| layer_expected_share | same — session._diagnostic_layer_equities | same — session._diagnostic_layer_equities | same — session._diagnostic_layer_equities | same — session._diagnostic_layer_equities |
| layer_investment_ev | same — session._layer_investment_summary;session._layer_call_summary | same — session._layer_investment_summary;session._layer_call_summary | same — session._layer_investment_summary;session._layer_call_summary | same — session._layer_investment_summary;session._layer_call_summary |
| fold_call_bet_ev | not applicable | not applicable | not applicable | distinct — session._perceived_fold_to_bet_probability;session._combine_fold_call_ev |
| river_layer_bet_veto | not applicable | not applicable | not applicable | distinct — plan.apply_layer_bet_ev_judgment |
| pot_award_settlement | same — session.award_pots | same — session.award_pots | same — session.award_pots | same — session.award_pots |
| showdown_visibility | not applicable | not applicable | not applicable | overloaded — session.HandRun._finish |
| emotion_loss_shock | same — dynamics.Tilt.on_pot;dynamics.Tilt.on_fold_after_investing | same — dynamics.Tilt.on_pot;dynamics.Tilt.on_fold_after_investing | same — dynamics.Tilt.on_pot;dynamics.Tilt.on_fold_after_investing | same — dynamics.Tilt.on_pot;dynamics.Tilt.on_fold_after_investing |
| emotion_streak_and_dry | same — dynamics.Tilt.on_result | same — dynamics.Tilt.on_result | same — dynamics.Tilt.on_result | same — dynamics.Tilt.on_result |
| emotion_recovery | same — dynamics.Tilt.on_hand_end;dynamics.Tilt.decay_all | same — dynamics.Tilt.on_hand_end;dynamics.Tilt.decay_all | same — dynamics.Tilt.on_hand_end;dynamics.Tilt.decay_all | same — dynamics.Tilt.on_hand_end;dynamics.Tilt.decay_all |
| emotion_profile_view | overloaded — persona.tilted_view;persona.tilt_decay;persona.tilt_direction;play.Hand.axes;play.Hand.profile_views | overloaded — persona.tilted_view;persona.tilt_decay;persona.tilt_direction;play.Hand.axes;play.Hand.profile_views | overloaded — persona.tilted_view;persona.tilt_decay;persona.tilt_direction;play.Hand.axes;play.Hand.profile_views | overloaded — persona.tilted_view;persona.tilt_decay;persona.tilt_direction;play.Hand.axes;play.Hand.profile_views |
| persona_population_generation | overloaded — persona.make_player;persona._money_jump_skill;persona.skill_bounds;persona.derive | overloaded — persona.make_player;persona._money_jump_skill;persona.skill_bounds;persona.derive | overloaded — persona.make_player;persona._money_jump_skill;persona.skill_bounds;persona.derive | overloaded — persona.make_player;persona._money_jump_skill;persona.skill_bounds;persona.derive |
| display_skill_summary | same — persona.overall_skill;persona.skill_pct;persona.tier;persona.profile_card;persona.label | same — persona.overall_skill;persona.skill_pct;persona.tier;persona.profile_card;persona.label | same — persona.overall_skill;persona.skill_pct;persona.tier;persona.profile_card;persona.label | same — persona.overall_skill;persona.skill_pct;persona.tier;persona.profile_card;persona.label |
| physical_button_rotation | same — fieldsim.Table.advance_button;fieldsim.Table.restore_positions;fieldsim.Table.hand_layout;fieldsim.Table.reconcile_next_hand | same — fieldsim.Table.advance_button;fieldsim.Table.restore_positions;fieldsim.Table.hand_layout;fieldsim.Table.reconcile_next_hand | same — fieldsim.Table.advance_button;fieldsim.Table.restore_positions;fieldsim.Table.hand_layout;fieldsim.Table.reconcile_next_hand | same — fieldsim.Table.advance_button;fieldsim.Table.restore_positions;fieldsim.Table.hand_layout;fieldsim.Table.reconcile_next_hand |
| field_table_balance | same — fieldsim.Field._balance;fieldsim.Table.worst_open_seat;fieldsim.Table.broken_open_seats | same — fieldsim.Field._balance;fieldsim.Table.worst_open_seat;fieldsim.Table.broken_open_seats | same — fieldsim.Field._balance;fieldsim.Table.worst_open_seat;fieldsim.Table.broken_open_seats | same — fieldsim.Field._balance;fieldsim.Table.worst_open_seat;fieldsim.Table.broken_open_seats |
| field_context_producer | same — fieldsim.Field.stamp;context.Context.apply;context.erosion | same — fieldsim.Field.stamp;context.Context.apply;context.erosion | same — fieldsim.Field.stamp;context.Context.apply;context.erosion | same — fieldsim.Field.stamp;context.Context.apply;context.erosion |
| parallel_round_isolation | same — live2.compute_others_parallel;live2._overlay_parallel_dump;live2._merge_parallel_field | same — live2.compute_others_parallel;live2._overlay_parallel_dump;live2._merge_parallel_field | same — live2.compute_others_parallel;live2._overlay_parallel_dump;live2._merge_parallel_field | same — live2.compute_others_parallel;live2._overlay_parallel_dump;live2._merge_parallel_field |
| replay_decision_cache | same — live2.build_hand;live2.step;session.HandRun._run | same — live2.build_hand;live2.step;session.HandRun._run | same — live2.build_hand;live2.step;session.HandRun._run | same — live2.build_hand;live2.step;session.HandRun._run |
| legacy_tournament_progress | same — field.Field.step;field.Tables.reconcile;tourney.Tournament.next_hand | same — field.Field.step;field.Tables.reconcile;tourney.Tournament.next_hand | same — field.Field.step;field.Tables.reconcile;tourney.Tournament.next_hand | same — field.Field.step;field.Tables.reconcile;tourney.Tournament.next_hand |
| telemetry_observation_only | same — telemetry_sync.build_round_bundle;telemetry_sync.emit_round;live2._archive;fieldsim.Field._log_bot_hand | same — telemetry_sync.build_round_bundle;telemetry_sync.emit_round;live2._archive;fieldsim.Field._log_bot_hand | same — telemetry_sync.build_round_bundle;telemetry_sync.emit_round;live2._archive;fieldsim.Field._log_bot_hand | same — telemetry_sync.build_round_bundle;telemetry_sync.emit_round;live2._archive;fieldsim.Field._log_bot_hand |
| legacy_betting_range | not applicable | same — bot.betting_range;bot.equity_vs_betting | same — bot.betting_range;bot.equity_vs_betting | same — bot.betting_range;bot.equity_vs_betting |
| legacy_arch_types | same — archetypes.axes;archetypes.concepts;archetypes.traits;archetypes.open_range | same — archetypes.axes;archetypes.concepts;archetypes.traits;archetypes.open_range | same — archetypes.axes;archetypes.concepts;archetypes.traits;archetypes.open_range | same — archetypes.axes;archetypes.concepts;archetypes.traits;archetypes.open_range |
| legacy_sidepot_helper | missing (production consumer) | missing (production consumer) | missing (production consumer) | missing (production consumer) |
| legacy_icm_overridden | missing (production consumer) | missing (production consumer) | missing (production consumer) | missing (production consumer) |
| dead_generic_error_rate | missing (production consumer) | missing (production consumer) | missing (production consumer) | missing (production consumer) |
| placeholder_gto_adaptation | missing (production consumer) | not applicable | not applicable | not applicable |
| temperament_aggression | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_looseness | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_gamble | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_discipline | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_adaptability | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_consistency | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_attention | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_slowplay_taste | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_tilt_prone | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_tilt_recovery | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_tilt_swing | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |
| temperament_tilt_stack | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper | same — persona.make_player;persona.temper |

## 실제 추출 후 producer 연결

CSV/JSON의 `current_function`이 아래 연결을 포함한다. 원래 `function/evidence`는 before 기준 증거다. 공유 skill scalar를 새로 생성하지 않았다.

| concept | current function |
| --- | --- |
| checkraise_flop_decision | plan.checkraise_draw_street_probability |
| checkraise_turn_decision | plan.checkraise_draw_street_probability |
| checkraise_river_decision | plan.checkraise_river_probability |
| draw_completion_value_gate | plan.draw_completion_supports_value |
| strength_improvement_promotion | plan.strength_improvement_supports_value |
| river_thin_value | plan.river_value_reassessment |
| missed_draw_river_conversion | plan.river_semibluff_resolution |
| flop_cbet_plan | plan.cbet_flop_frequency |
| turn_barrel_plan | plan.barrel_turn_frequency |
| river_barrel_plan | plan.barrel_river_frequency |
| range_reconstruction_grasp | ranges.blend_action_range_by_grasp |
| continue_range_partition | ranges.continuation_support_fraction;ranges._continue_range |
| call_range_partition | ranges.continuation_support_fraction;ranges._call_range |
| legacy_preflop_ordering | preflop.legacy_preflop_order_percentile;preflop.pct |

| concept | preflop | flop | turn | river |
| --- | --- | --- | --- | --- |
| current_board_split_share_shadow | not applicable | same — plan._eq_current | same — plan._eq_current | same — plan._eq_current |
| future_equity_sampling_provenance | not applicable | same — plan._eq_vs | same — plan._eq_vs | same — plan._eq_vs |

## 3차: range_read 소비 경계

[RANGE_READ_CONSUMER_BOUNDARIES](RANGE_READ_CONSUMER_BOUNDARIES.md)에 복원·액션 해석·판단 적용의 실제 함수와 공급/소비 경로를 분리했다. 기존 scalar 공급과 잔여 과적재는 유지한다. 새 skill 도입이나 전체 raise 적용 경로 통일은 하지 않았다.
