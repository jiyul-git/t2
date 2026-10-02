# DUPLICATION_AND_OVERLOAD_LEDGER

전략상 문제가 의심된다는 것과 이번에 행동을 바꾸어도 된다는 것은 다르다. 아래 판정은 의미 분리 목적이다. 변경이 필요한 threshold/skill distribution/EV model/visibility/memory lifecycle은 이번에 고치지 않는다. 수행된 순수 추출은 별도 검증 문서에 기재한다.

| ID | 개념 | 현재 위치 | 겹친 의미와 문제 | 판정 | 처리 경계 |
| --- | --- | --- | --- | --- | --- |
| L001 | bluff | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT ability / evidence / temperament | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L002 | semibluff | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT flop/turn context; river inapplicable | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L006 | checkraise_flop | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT generic trap gate also aliases flop | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L007 | checkraise_late | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT turn semibluff vs river no draw | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L008 | bluffcatch_early | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT capability / subjective call bias | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L009 | bluffcatch_river | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT capability / subjective call bias | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L010 | thin_value_turn | persona.py:224; persona.py:373 / persona.make_player;persona.sk | KEEP; flop uses range_merge | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L012 | blockbet | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT motive / size; flop donk overlap | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L013 | potcontrol | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT motive vs frequency scalar | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L014 | trap | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT no-bite / checkraise gate | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L015 | overbet | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT street semantics at execution function | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L016 | probe | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT poker probe vs bluff_mode probe sizing | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L018 | equity_denial | persona.py:224; persona.py:373 / persona.make_player;persona.sk | KEEP; no river future equity | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L019 | stackoff | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT ability / investment horizon | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L020 | reraise | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT preflop/postflop uses | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L021 | outs | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT raw draw count / perception | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L022 | potodds | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT math precision / reasoning confidence | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L023 | spr | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT ratio / perception / plan | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L024 | range_read | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT reconstruction / line interpretation / observer quality | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L025 | blocker | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT objective blocker / skill usage | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L026 | icm | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT math BF / perception / plan | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L027 | board_texture | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT raw facts / street interpretation | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L028 | sizing_tell | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT tell perception / self sizing camouflage | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L029 | pf_range | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT RFI memory / limp reasoning | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L030 | positional | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT prior condition / reasoning | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L033 | pf_defend | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT knowledge / reasoning gate / family | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L034 | range_merge | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT merged-value / thin-flop skill | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L035 | multiway | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT math pool identity / reasoning | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L036 | fold_equity | persona.py:224; persona.py:373 / persona.make_player;persona.sk | SPLIT probability estimate / utilization | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L037 | money_jump | persona.py:224; persona.py:373 / persona.make_player;persona.sk | preflop range active; later shadow | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L047 | aggressive_street_count | action_events.py:205; session.py:687 / action_events.aggressive_street_count;session._barrel_count | MERGE wrapper already canonical; ranges still reconstructs local count | MERGE | behavior preservation required; follow-up if action/RNG changes |
| L049 | preflop_public_roles | session.py:97; session.py:171; session.py:286 / session._pf_observation_flags;session._preflop_public_action_context;session._cold_reraise_context | SPLIT duplicated raw log _was_3bettor remains | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L054 | called_aggression_ownership | plan.py:1613 / plan._called_prior_street_aggression | SPLIT flop caller stab ownership vs later continuation | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L055 | rfi_width_prior | gto.py:98; gto.py:74; gto.py:86 / gto.rfi;gto.depth_mult;gto.behind_of | KEEP; not combo-level solver policy | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L056 | defend_width_prior | gto.py:184; gto.py:154 / gto.defend_pct;gto.mdf | RENAME mdf is width proxy not exact MDF | RENAME | behavior preservation required; follow-up if action/RNG changes |
| L057 | threebet_width_prior | gto.py:205 / gto.threebet_pct | SPLIT independent solved chart missing | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L058 | chart_memory_accuracy | persona.py:476; persona.py:520 / persona.gto_knowledge;persona.gto_memory_confidence | SPLIT acc also controls temperament deviation | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L059 | studied_condition_match | persona.py:494; persona.py:534 / persona.gto_condition_match;persona.gto_studied_anchor | OPT-IN defaults off | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L060 | preflop_condition_reasoning | persona.py:564; persona.py:606 / persona.preflop_reasoning_confidence;persona.preflop_reasoned_width | OPT-IN defaults off | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L061 | legacy_preflop_ordering | preflop.py:14; preflop.py:9 / preflop.pct;preflop.cls | SPLIT RFI/defend/reraise/calloff/blocker/reconstruction/showdown | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L063 | rfi_personality_deviation | persona.py:631 / persona.open_pct | SPLIT memory accuracy also deviation ceiling | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L064 | limp_entry_motive | preflop.py:160 / preflop.limp_p | SPLIT rfi skill reused as limp knowledge | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L067 | unopened_decision | preflop.py:302 / preflop.open_decision | ARCH_MISMATCH judgment+plan+form in one function | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L068 | isolation_decision | preflop.py:1143 / preflop.iso_decision | SPLIT independent iso prior missing | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L069 | defend_attack_continue_widths | preflop.py:548; preflop.py:46 / preflop.defend_thresholds;preflop._saturate | SEMANTICALLY_OVERLOADED 3bet/4bet/5bet share formula | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L071 | sample_defend_action | preflop.py:805 / preflop.defend_decision | RENAME 3bet label also means higher raises | RENAME | behavior preservation required; follow-up if action/RNG changes |
| L072 | reraise_sizing_form | preflop.py:427; preflop.py:415 / preflop.raise_form;preflop.reraise_mult | SPLIT motive vs stack commitment form | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L073 | reshove_opportunity | preflop.py:497; preflop.py:499; preflop.py:514; preflop.py:528 / preflop.in_hotzone;preflop.reshove_range;preflop.reshove_weight;preflop.hotzone_pressure | SPLIT PCT rank from reshove EV; solver prior missing | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L075 | preflop_card_removal | preflop.py:875 / preflop.preflop_blocker_share | SPLIT PCT ordering from observed mass; not bluff skill | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L077 | legacy_calloff_threshold | preflop.py:1198; preflop.py:1335 / preflop.calloff_cap;preflop.calloff_decision | SPLIT ordering vs true equity/EV; pot/tocall legacy unused | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L078 | layer_calloff_judgment | preflop.py:1268 / preflop.calloff_layer_judgment | SPLIT math vs skill gate; fallback legacy preserved | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L079 | calloff_comparison_shadow | preflop.py:1233 / preflop.calloff_ev_comparison | SHADOW no separate action override | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L082 | range_identity_signature | ranges.py:168; plan.py:337; plan.py:360; plan.py:403 / ranges.range_signature;plan._range_sig;plan._decision_range_sig;plan._opp_ranges_signature | SPLIT cache signatures have distinct contracts | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L083 | preflop_posterior_order | ranges.py:231 / ranges.preflop_reraise_posterior | SPLIT support-count rank vs cumulative mass | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L087 | range_reconstruction_grasp | ranges.py:965; ranges.py:940; ranges.py:910 / ranges.perceived_range;ranges.perceived_continue_range;ranges.perceived_facing_bet_response | MERGE identical blend; retain producer evaluation order | MERGE | behavior preservation required; follow-up if action/RNG changes |
| L089 | bet_range_partition | ranges.py:801; bot.py:398 / ranges._bet_range;bot.pick_bluffs | SPLIT flop/turn draw support vs river blocker-only | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L090 | continue_range_partition | ranges.py:824 / ranges._continue_range | MERGE shared keep width with call; preserve partition distinction | MERGE | behavior preservation required; follow-up if action/RNG changes |
| L093 | raise_range_posterior | ranges.py:1031 / ranges._raise_range | ARCH_MISMATCH forward raise policy differs; missing price fallback | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L095 | hero_made_contribution | bot.py:322 / bot.made_strength | RENAME contribution category; not raw eval score; river same-category strength loses credit | RENAME | behavior preservation required; follow-up if action/RNG changes |
| L097 | current_board_not_behind | plan.py:33; plan.py:91; plan.py:169 / plan.relative_strength;plan.joint_relative_strength;plan._decision_relative_strength | RENAME rel != equity; joint if complete else union fallback | RENAME | behavior preservation required; follow-up if action/RNG changes |
| L099 | unconditioned_equity | bot.py:100; bot.py:236 / bot.equity;bot.equity_vs_range | FALLBACK no dedicated solved strategy | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L102 | strong_region_advantage | ranges.py:505; ranges.py:518; ranges.py:526; plan.py:202 / ranges._strong_share;ranges.nut_advantage;ranges.joint_nut_advantage;plan._decision_nut_advantage | RENAME nut_advantage is not literal nuts | RENAME | behavior preservation required; follow-up if action/RNG changes |
| L103 | strong_support_blocker | ranges.py:589 / ranges.blocker_score | SPLIT support percentile vs mass percentile | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L105 | relative_strength_perception | plan.py:308 / plan.perceived_rel | SPLIT true rel / perceived rel; no exact future EV | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L107 | depth_perception | depth.py:118; depth.py:53; depth.py:63; depth.py:98; depth.py:91; preflop.py:56 / depth.depth_feel;depth.base_feel;depth.field_adjusted_bb;depth.eroded_bb;depth.lookahead_hands;preflop.feel_of | SPLIT objective depth from subjective estimate | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L109 | board_completion_danger | bot.py:117 / bot.board_danger | SPLIT raw danger vs skill-scaled state.danger | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L111 | street_texture_sizing | texture.py:82; texture.py:137 / texture.size_fraction;texture.perceived | SPLIT board facts / learned prior / perceptual noise | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L112 | turn_card_range_shift | texture.py:101 / texture.turn_card_effect | SEMANTICALLY_OVERLOADED river caller uses flop slice and river card, ignores turn | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L114 | calculation_error | persona.py:396 / persona.calc_noise | SPLIT quantities; V3 zero-mean opt-in retains draw bias | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L115 | value_line_selection | plan.py:631 / plan.make_plan | SPLIT long inline judgments; not one generic strength | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L116 | vulnerable_paired_flush | plan.py:631; plan.py:1358 / plan.make_plan;plan.decide_response | SPLIT context thresholds differ; do not merge merely similar | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L118 | deep_one_pair_caution | plan.py:631; plan.py:1358 / plan.make_plan;plan.decide_response | SPLIT context questions and thresholds | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L119 | continue_range_value | plan.py:631; plan.py:1358; plan.py:2881; plan.py:3093 / plan.make_plan;plan.decide_response;plan.river_fix;plan.refresh | SPLIT generic rel from continue eq; street gates differ | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L120 | semibluff_line_selection | plan.py:631; plan.py:1358; plan.py:3093 / plan.make_plan;plan.decide_response;plan.refresh | SPLIT flop two draws vs turn one; river conversion distinct | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L121 | pure_bluff_line_selection | plan.py:631; plan.py:3538 / plan.make_plan;plan.bluff_mode | SPLIT motive / evidence / ability / camouflage | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L122 | potcontrol_motive | plan.py:631; plan.py:3093 / plan.make_plan;plan.refresh | SPLIT label != one frequency scalar | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L123 | potcontrol_bet_propensity | plan.py:1636 / plan.decide_aggression | SPLIT continuation vs caller stab | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L124 | blockbet_motive | plan.py:631 / plan.make_plan | SPLIT flop noninitiative donk overlaps | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L125 | trap_induction | plan.py:549; plan.py:471 / plan.trap_judgment;plan.opp_bet_prob | ARCH_MISMATCH runtime latent use violates generation-only statement | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L127 | draw_completion_value_gate | plan.py:3093; plan.py:2881 / plan.refresh;plan.river_fix | MERGE identical predicate only; split street outcomes | MERGE | behavior preservation required; follow-up if action/RNG changes |
| L129 | missed_draw_river_conversion | plan.py:2881 / plan.river_fix | SPLIT terminal policy from turn draw continuation | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L131 | flop_cbet_plan | plan.py:2088; plan.py:1636 / plan.cbet_freq;plan.decide_aggression | SPLIT flop cbet vs later barrels | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L132 | turn_barrel_plan | plan.py:2088; plan.py:1636 / plan.cbet_freq;plan.decide_aggression | SPLIT turn policy | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L133 | river_barrel_plan | plan.py:2088; plan.py:1636 / plan.cbet_freq;plan.decide_aggression | SPLIT no future draw; current texture call overload | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L134 | probe_after_checkthrough | plan.py:1636 / plan.decide_aggression | SPLIT turn draw-dependent / river no draw | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L138 | planned_bet_sizing | plan.py:1794 / plan.decide_size | SPLIT strength question vs execution size | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L139 | turn_overbet | plan.py:2021 / plan.overbet_frac | SPLIT turn vs river calculation branch | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L140 | river_overbet | plan.py:2021 / plan.overbet_frac | SPLIT union continue range despite joint upstream | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L142 | target_investment_fraction | plan.py:3478 / plan.target_commit | SPLIT fixed horizon from actual street; unused s/street parameters | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L143 | stackoff_spread_horizon | plan.py:3626; plan.py:3592 / plan.stackoff_plan;plan.spread_curve | SEMANTICALLY_OVERLOADED fixed three-street geometry even later street | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L144 | bluff_sizing_camouflage | plan.py:3538; plan.py:3519; plan.py:3509 / plan.bluff_mode;plan.barrel_size;plan.breakeven_fold | RENAME probe here is size mode not public probe opportunity | RENAME | behavior preservation required; follow-up if action/RNG changes |
| L145 | calldown_required_share | plan.py:1137 / plan.calldown_need | SPLIT objective price vs subjective call threshold; read arg unused | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L146 | nonvalue_raise_ev_gate | plan.py:1266 / plan._nonvalue_raise_ev_gate | SPLIT not complete multiway response tree; unknown allows | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L147 | response_plan | plan.py:1358; plan.py:1953 / plan.decide_response;plan.record_response_plan | ARCH_MISMATCH judgment and plan combined | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L148 | call_bias_reapplication | persona.py:1070; persona.py:721; plan.py:1358 / persona.call_bias;persona.bias;plan.decide_response | DUPLICATED remove only in behavior-changing followup | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L149 | checkraise_flop_decision | plan.py:2468 / plan.checkraise_decision | SPLIT actual extraction needed | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L150 | checkraise_turn_decision | plan.py:2468 / plan.checkraise_decision | SPLIT shared late ability preserved initially | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L151 | checkraise_river_decision | plan.py:2468 / plan.checkraise_decision | SPLIT river_bluff label branch gap followup | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L152 | checkraise_sizing | plan.py:3462 / plan.checkraise_size | SPLIT street base and absolute/additional contribution units audit | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L153 | action_adapter_with_reasoning | plan.py:2168 / plan.act_with_plan | ARCH_MISMATCH function is not pure ACTION executor | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L154 | human_planned_size_shape | persona.py:23; persona.py:18; plan.py:2151 / persona.shape_size;persona.sizing_signature;plan.shape_planned_target | RENAME type not display-only; runner wrapper compatibility | RENAME | behavior preservation required; follow-up if action/RNG changes |
| L156 | plan_revision_lifecycle | plan.py:2763; runner.py:280; plan.py:3093 / plan.update_plan;runner.revise_plan;plan.refresh | ARCH_MISMATCH flop first always; replan bb/tilt missing; preserve behavior | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L157 | plan_concept_permission | plan.py:3053 / plan._allowed | SPLIT generic checkraise alias uses flop in trap gate | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L161 | opponent_behavior_memory | reads.py:136; reads.py:296; reads.py:320; reads.py:195 / reads.Book.rec;reads.Book.observe_preflop;reads.Book.observe_postflop;reads.Book.observe_size | ARCH_MISMATCH bot tables recreate Book each hand | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L163 | showdown_strength_observation | reads.py:350; session.py:2672; dynamics.py:191 / reads.Book.observe_showdown;session.HandRun._finish;dynamics.Tilt.note_showdown | ARCH_MISMATCH all live sampled before shown/muck decision; PCT not postflop strength | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L164 | opponent_estimation | reads.py:367; reads.py:360; reads.py:25 / reads.estimate;reads._shrink;reads.obs_from_profile | SPLIT belief uncertainty from exploit strength | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L166 | style_belief_reference | reads.py:765; reads.py:793; reads.py:820 / reads.style_hypotheses;reads.concept_belief;reads.opponent_belief | SHADOW no live decision consumer | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L167 | recency_window | reads.py:66; reads.py:84 / reads._append_hand_snapshot;reads._recent_record | OPT-IN defaults off; default only effective n capped | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L168 | exploit_read_permission | persona.py:1091; persona.py:1107; persona.py:1142; persona.py:1283 / persona._exploit_base_weight;persona.exploit_weight;persona.read_opponent;persona.street_gap | SPLIT legacy exploit_weight != read_opponent weight; v3 optin unifies | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L169 | opponent_sizing_normalization | persona.py:922; persona.py:1048 / persona.opp_size_norm;persona.size_read | SPLIT physical pot odds never replace raw facts | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L170 | shown_hand_range_adjustment | runner.py:318 / runner.adjust_range_by_history | SPLIT Book posterior vs separate history heuristic; visibility mismatch | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L172 | accumulation_variance_drive | persona.py:968; persona.py:1000 / persona.accum_drive;persona.variance_seek | SPLIT from optimal risk-adjusted EV | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L174 | icm_bubble_factor | icm.py:148; icm.py:306; play.py:156 / icm.bubble_factor;icm.table_bf;play.Hand.bf | SPLIT simplified non-zero-sum perturbation, not opponent-specific transfer EV | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L175 | field_icm_proxy | icm.py:269; icm.py:284; icm.py:209 / icm.stage_pressure;icm.stack_pressure;icm.field_bf | REMOVE_COMPAT overwritten old field_bf definition and obsolete tables | REMOVE_COMPAT | behavior preservation required; follow-up if action/RNG changes |
| L177 | icm_required_equity_reference | icm.py:165 / icm.required_equity | FALLBACK not canonical plan formula; do not merge different pot conventions | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L184 | stack_cover_pressure | money_pressure.py:145; money_pressure.py:157; money_pressure.py:178; money_pressure.py:210; money_pressure.py:166; money_pressure.py:192 / money_pressure.cover_strength;money_pressure.topology_safety;money_pressure.structural_pressure;money_pressure.pressure_opportunity;money_pressure.exploit_realization;money_pressure.read_adjustment | SPLIT facts / awareness / exploit channels | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L185 | money_commitment_budget | money_pressure.py:224; money_pressure.py:235 / money_pressure.commitment_budget;money_pressure.low_commit_pressure | SHADOW postflop no action consumer | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L187 | money_open_form_shadow | money_pressure.py:240 / money_pressure.unopened_modifiers | SHADOW not enabled | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L189 | layer_expected_share | session.py:404 / session._diagnostic_layer_equities | RENAME diagnostic prefix misleading: partial ACTIVE | RENAME | behavior preservation required; follow-up if action/RNG changes |
| L194 | showdown_visibility | session.py:2672 / session.HandRun._finish | ARCH_MISMATCH observers recorded before visibility | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L198 | emotion_profile_view | persona.py:866; persona.py:826; persona.py:850; play.py:147; play.py:137 / persona.tilted_view;persona.tilt_decay;persona.tilt_direction;play.Hand.axes;play.Hand.profile_views | ARCH_MISMATCH axes view used for judgments; clean views API not full reroute | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L199 | persona_population_generation | persona.py:224; persona.py:207; persona.py:216; persona.py:285 / persona.make_player;persona._money_jump_skill;persona.skill_bounds;persona.derive | SPLIT generation latent vs runtime study; no evidence pro-player learned data | SPLIT | behavior preservation required; follow-up if action/RNG changes |
| L200 | display_skill_summary | persona.py:1296; persona.py:1311; persona.py:1328; persona.py:1335; persona.py:302 / persona.overall_skill;persona.skill_pct;persona.tier;persona.profile_card;persona.label | SHADOW action indirect label used sizing; error_rate dead | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L206 | legacy_tournament_progress | field.py:81; field.py:143; tourney.py:105 / field.Field.step;field.Tables.reconcile;tourney.Tournament.next_hand | FALLBACK regression does not exercise physical live2 fullfield | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L207 | telemetry_observation_only | telemetry_sync.py:242; telemetry_sync.py:286; live2.py:931; fieldsim.py:608 / telemetry_sync.build_round_bundle;telemetry_sync.emit_round;live2._archive;fieldsim.Field._log_bot_hand | SHADOW no online learner/reasoning feedback | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L208 | legacy_betting_range | bot.py:437; bot.py:454 / bot.betting_range;bot.equity_vs_betting | FALLBACK differs from active ranges._bet_range; do not merge silently | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L209 | legacy_arch_types | archetypes.py:58; archetypes.py:129; archetypes.py:72; archetypes.py:66 / archetypes.axes;archetypes.concepts;archetypes.traits;archetypes.open_range | FALLBACK modern concepts path different | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L210 | legacy_sidepot_helper | table.py:102 / table.Table.sidepots | DEAD relative live2 path; not canonical settlement | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L211 | legacy_icm_overridden | icm.py:296 / icm.field_bf@296 | DEAD overwrite; remove obsolete definition only after reference check | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L212 | dead_generic_error_rate | persona.py:327 / persona.error_rate | DEAD do not pretend active noise | KEEP | behavior preservation required; follow-up if action/RNG changes |
| L213 | placeholder_gto_adaptation | gto.py:132 / gto.adapt_mult | DEAD influence even if called | KEEP | behavior preservation required; follow-up if action/RNG changes |

## 반드시 별도 후속 semantic-fix로 남기는 항목

- PCT를 decision-family별 equity/EV/chart로 교체; 근거 없는 새 순위표 금지.
- flop/turn/river capability 독립값 생성과 population distribution 재설계.
- range_read의 reconstruction/line interpretation 분리 후 서로 다른 skill 도입.
- calldown_need와 decide_response의 station/blufffear 이중 반영 제거.
- trap의 latent.study 직접 접근, generic checkraise flop gate 교체.
- river에서 texture.turn_card_effect(board[:3], board[-1])가 turn 카드를 무시하는 경로.
- make_plan의 scaled danger와 refresh의 raw danger 계약 통일.
- runner.revise_plan의 현재 bb_chips/tilt/상대context 전달 보완.
- stackoff_plan의 고정 3회 투자 horizon을 remaining streets로 변경.
- Book의 실제 공개패만 관측 및 bot-only tables의 관측 기억 지속.
- made_strength의 same-category kicker/overpair 기여와 nuts proxy 정의 교정.
- 일반 multiway nonvalue raise EV 및 sidepot raise branches 확장.
- own range의 자신의 postflop action conditioning; forward raise/inverse posterior 일치.

## 의도적으로 통합하지 않는 것

- 전체 pot / contestable pot / projected layer pot은 다른 금액 질문이다.
- call-only range와 전체 continue range는 raise 가능성에 따라 다른 집합이다.
- current rel / showdown equity / made category / range advantage / strong-region advantage는 서로 다른 양이다.
- 서로 다른 seed/cache signature와 pot convention을 가진 equity/required-equity helper는 이름만 같다고 합치지 않는다.
- hero_table live2와 legacy tourney를 동일 runtime으로 취급하지 않는다.

추가 provenance 문제: `plan._eq_vs(seed=...)`는 받은 seed를 `bot.equity_vs_combos`에 전달하지 않는다. 실제 계산은 content CRC32 seed이고 `eq_seed` 기록과 다를 수 있다. 이번에 전달 경로를 바꾸면 MC/action이 변하므로 RENAME/후속 REROUTE 대상으로 남긴다. `eq_current`는 current-board split-share shadow이며 rel 또는 future equity와 합치지 않는다.

## 2차 정리: defend 판단 계산 경계

`preflop.defend_thresholds`는 공통 producer를 유지하고 다음 순수 계산을 호출한다. 모든 수치와 계산 순서를 보존한다.

| 함수 | 입력 → 출력 | 의미 |
| --- | --- | --- |
| normalize_defend_prior_widths | attack/continue 폭, calibrated 여부 → 정규화한 두 폭 | 기존 prior clamp/saturation 계약 |
| adjust_defend_widths_for_callers | profile, 두 폭, 콜러 수 → 보정한 두 폭 | 콜러·squeeze 문맥 |
| adjust_defend_widths_for_short_stack | 두 폭, bb → 보정한 두 폭 | 기존 short-stack attack/call 구간 |
| tighten_defend_widths_for_raise_level | 두 폭, raise_level → 최종 두 폭 | 상위 재레이즈 축소 및 최종 cap |

모두 preflop / REASONING / JUDGMENT, 기존 authored heuristic, ACTIVE이며 RNG를 호출하지 않는다. 직접 consumer는 defend_thresholds, 이후 defend_action_likelihoods와 관찰자 range 모델이 소비한다. 별도의 4bet solver prior를 추가한 것이 아니므로 기존 SEMANTICALLY_OVERLOADED 판정은 유지한다. 함수 경계는 분리됐지만 공유 지식 문제는 미해결이다.

## 3차: range_read 소비 경계

[RANGE_READ_CONSUMER_BOUNDARIES](RANGE_READ_CONSUMER_BOUNDARIES.md)에 복원·액션 해석·판단 적용의 실제 함수와 공급/소비 경로를 분리했다. 기존 scalar 공급과 잔여 과적재는 유지한다. 새 skill 도입이나 전체 raise 적용 경로 통일은 하지 않았다.

## 4차: 추가 range_read 소비 경계

| 역할 | 현재 함수 | 입력 → 출력 | consumer / 계층 |
| --- | --- | --- | --- |
| 관측 정확도 | reads.observation_accuracy_from_capabilities | attention, observation_read_skill, sizing_tell → 기존 [0.03, 0.98] 정확도 | obs_from_profile → 관측 모델 / PERCEPTION |
| 토너먼트 압박 활용 | money_pressure.pressure_application_capacity | money_jump, fold_equity, pressure_read_skill, attention, adaptability, aggression → 기존 mean01 활용 능력 | exploit_realization → pressure_opportunity / EXPLOIT·ICM |
| 멀티웨이 근거 적용 능력 | preflop.multiway_evidence_application_capacity | read_application_skill, potodds_skill, multiway_skill → 기존 [0, 1] 적용 능력 | multiway_reraise_decision / REASONING |
| 멀티웨이 call/fold 적용 | preflop.apply_multiway_call_evidence | call/fold mass, equity, required_equity, application_capacity → 새 call/fold mass | multiway_reraise_decision / JUDGMENT |

네 함수 모두 기존 계산 본문을 이동한 ACTIVE 경계다. heuristic 지식 공급과 range_read 값은 유지한다. actor/profile adapter는 기존 API를 보존한다. 새로운 압박 prior, equity 공식, skill 분포 또는 threshold는 추가하지 않았다.

멀티웨이 application capacity는 call/fold의 evidence 혼합과 기존 attack 억제 경로에 함께 소비된다. 이번에는 call/fold 혼합 본문을 분리했고, attack 억제 본문은 기존 위치에 남겼다. 따라서 call/raise 정책 전체를 한 적용 함수로 통일했다고 주장하지 않는다.

3차 문서의 관측 품질·멀티웨이·pressure 경계 추출 후보를 여기서 처리했다. 여전히 range_read 값 공급은 공유하며, persona.overpair_love 편향과 perceived_edge 자기 실력 인식, read_opponent의 line visibility, 종합 실력/프로필 생성·진단 직렬화는 별도 역할로 남는다.
