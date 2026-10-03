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

<!-- reaudit:start -->
## 재감사 추가 항목 (completeness)

| ID | 개념 | 현재 위치 | 겹친 의미와 문제 | 판정 | 처리 경계 |
| --- | --- | --- | --- | --- | --- |
| L-RA01 | called_aggression_ownership | plan._called_prior_street_aggression;plan.line_owned_by_live_aggressor | registry meaning was inverted ("내 공격이 콜받았나"); code asks whether hero CALLED the opponent's aggression. Flop consumer added in batch 1. | RENAME (doc) + KEEP | registry row corrected; extraction behavior-identical |
| L-RA02 | lead_into_aggressor_policy | plan.decide_aggression (bluff suppression / pot_control 0.04 / value relead) | one poker question "lead into a live aggressor?" answered by three mechanisms with different magnitudes | MERGE (later) | behavior change; needs EV/frequency review |
| L-RA03 | value_when_called_strength | make_plan commit_rel; overbet_frac; river_value_reassessment; refresh improved bluff | same question, four producers, metric rel vs equity, thresholds none/0.50/0.54 | MERGE (later) | behavior change |
| L-RA04 | showdown_value_predicate | plan.has_showdown_value (2 callers) + pure-bluff gate | medium-band fallback uses eq (runout), final branch eq_current; bluff gate omits multiway term | MERGE done for formula; SPLIT equity basis kept explicit | unifying the basis changes behavior |
| L-RA05 | players_behind_risk_premium | plan.calldown_need; preflop.multiway_reraise_decision | identical formula duplicated in two modules | MERGE (done) | icm.players_behind_required_equity_premium, bit-identical |
| L-RA06 | perceived_board_danger | make_plan (scaled) vs refresh/decide_size (raw) | state key "danger" changes meaning between plan creation and refresh | SPLIT (later) | behavior change |
| L-RA07 | turn_card_range_shift | plan.decide_aggression; plan.refresh | on the river both call turn_card_effect(flop, river card): the turn card is ignored and the name says turn | SPLIT / RENAME (later) | river card effect vs turn card effect are different questions |
| L-RA08 | medium_strength_merge_value | plan.make_plan (replan on turn/river) | board-change replan reads sk(range_merge) at turn/river instead of thin_value_<street> | REROUTE (later) | skill supply change |
| L-RA09 | giveup_reentry_on_improvement | plan.refresh | made>=2 / made>=3 can come from a paired board. Root: bot.made_strength returns the full category when it exceeds the board category, so pocket pair + board pair = two pair (2) counts as "made 2" without hero improvement. Same root as HAND 63 / R5c; consumers: refresh giveup re-entry, semibluff_draw_loss_resolution, river_semibluff_resolution showdown branch | SPLIT (later) | hero_made_contribution semantics change = behavior change |
| L-RA10 | multiway_representative_union_range | session.HandRun._run → plan opp_range | equity uses seat pools but continue-range gates (overbet, value raise HU check), blocker_score and plan state read the union | REROUTE (later) | behavior change |
| L-RA11 | opponent_unconsumed_estimates | reads.estimate | fold-to-raise and cold-reraise/backraise/squeeze-response reads are estimated but no decision consumes them | KEEP SHADOW | wiring is an exploit-phase change (tilt/exploit disabled in baseline) |
| L-RA12 | opener_position_attack_table | preflop.OPENER_MULT | reshove-width table reused (audit9 R4) as proxy for depth of players behind an open-shove | SPLIT (later) | behavior change |
| L-RA13 | defend_width_prior | gto.defend_pct / _use_mtt8_ante_defense | calibrated defend table only for seats==8 ante; standard/main/lowbuyin are 9-max and use the legacy formula | KEEP (knowledge gap) | R2 knowledge-accuracy audit |
| L-RA14 | dead_strategy_tables | preflop.DEF_POS_MULT, DEPTH_OPEN_MULT; persona.OPEN_ELASTICITY; plan.PLANS | strategy constants with no production reader | REMOVE_COMPAT (later) | harmless; removal is a separate cleanup |
| L-RA15 | response_equity_basis | plan.act_with_plan | fallback tier 3 models the opponent with the actor's own bluff axis and fixed callers | KEEP FALLBACK | reachable only without perceived ranges |
| L-RA16 | plan_revision_lifecycle | plan.refresh comment | stale in-code comment says the promotion "made term is dead"; the term was removed in audit9 (doc drift in code) | RENAME (comment) | documentation only |
| L-RA17 | self_hand_overconfidence_bias / perceived_player_edge | persona.bias; persona.perceived_edge | range_read supplies self-assessment roles; perceived_edge IS active at baseline through preflop.feel_of (max-skill +0.016 feel) | KEEP (documented) | corrects the earlier claim that perceived_edge has no baseline effect |
| L-RA18 | opponent_concept_inference (range_profile) | session.HandRun._preflop_perceived_range;_locked_postflop_range | observer Book estimates become the opponent preflop-range profile independent of exploit weight w: "exploit neutral" does not switch off opponent adaptation; manual_one_hand audits accumulate the Book | KEEP + document baseline harness | baseline harness must freeze the Book (sim2 T2_BASELINE does) |
<!-- reaudit:end -->

## 9단계 B1 (preflop) — 처리 상태

기준 `e6de033`. 행동 보존 검증:
- `tools/verify_stage9_semantic.py e6de033`: 6,460건(폭 1,800·디펜스 1,500·오픈/iso 1,200·raise_form 800·콜오프 800·멀티웨이/레인지 360)이 출력과 RNG 상태까지 바이트 동일.
- 의미 있는 변경 13/13 을 probe 가 검출했다(뮤테이션 테스트).
- baseline sim 지문이 봉인값과 동일하다.
- 게이트·completeness 결과는 `REFACTOR_AND_VERIFICATION.md` 6차에 있다.

| ID | 상태 | 처리 |
|---|---|---|
| L029 | 처리 완료 | 림프 이론 지식 공급을 `preflop.limp_theory_knowledge` 로 명명(RFI 기억 공급 공유는 유지) |
| L030 | 처리 완료 | `persona.positional_chart_flattening` — 좌석 조건 인식 역할 |
| L033 | 처리 완료 | `preflop.pf_defend_exact_calc_gate` — pf_defend 의 추론 게이트 역할(차트 기억 역할과 분리) |
| L049 | **LATER** | `_was_3bettor` 는 원시 로그의 raise/allin(올인 콜 포함)을 센다. canonical 역할은 full raise 만 센다 → 교체하면 행동 변화 |
| L056 | 처리 완료 | `gto.open_size_defend_scale` — `_MDF` 는 정확한 MDF 가 아닌 폭 보정 대용(출처 MISSING_KNOWLEDGE) |
| L057 | 처리 완료 | 3벳 층 분리: 후보 `attack_candidate_weight`, 증거 `apply_defend_exploit_evidence`, prior `defend_thresholds`, 4벳 `tighten_defend_widths_for_raise_level`(MISSING_KNOWLEDGE 명시) |
| L058 | 처리 완료 | `persona.chart_deviation_room` — acc 의 '이탈 상한' 역할(값 동일) |
| L063 | 처리 완료 | L058 과 같은 함수를 RFI·디펜스·V3 reasoned width 세 곳에서 사용 |
| L064 | 처리 완료 | L029 와 같음 |
| L067 | 처리 완료 | `open_entry_threshold`(판단), `apply_money_open_threshold`(머니점프 반사실 기록), 형태 `open_form`, 사이즈 `open_size_bb` |
| L068 | 처리 완료 | `iso_entry_threshold`(독립 iso prior 없음 — MISSING_KNOWLEDGE) |
| L069 | 처리 완료 | L057 의 층 분리로 2차의 남은 부분 종료 |
| L071 | **KEEP** | `"3bet"` 액션 라벨은 하위 소비처가 읽는다 — 라벨 변경은 행동 변화. 의미는 주석/문서로만 |
| L072 | 처리 완료 | `raise_commit_geometry`(기하) / `shove_form_pressure`(동기) |
| L073 | 처리 완료 | `hot_reshove_probability`: 후보·legacy 폭·legacy 확률 층을 docstring 으로 명시(빈도 MISSING_KNOWLEDGE) |
| L075 | 처리 완료 | `top_value_class_order`(순서) — 질량 계산과 분리 |
| L077 | 처리 완료 | `legacy_calloff_likelihoods` — legacy cap 경로와 그 소비처 3개 명시 |
| L078 | 처리 완료 | `calloff_by_price`(수학) / `pf_defend_exact_calc_gate`(게이트) |
| L083 | 처리 완료 | `ranges.support_rank_quantiles` — 개수 기준 분위(질량 분위 아님) |
| L-RA12 | 처리 완료(이름) | `RESHOVE_OPENER_ATTACK` / `OPEN_SHOVE_BEHIND_PROXY` 가 같은 표를 공유. 값 분리는 LATER |
| R2 S4 | 처리 완료(기록) | 관찰자 레인지 메타 `first_in_allin_read_as_open` |
| R2 S5 | 처리 완료(문서) | `bot.range_combos` = 레인지를 모를 때의 fallback 순서(통합 보류) |

### 새 항목: 가려진 조건 (masked / redundant condition)

| ID | 위치 | 내용 | 판정 |
|---|---|---|---|
| L-S9-01 | `preflop.raise_commit_geometry` `target_bb >= 0.75*stack_bb or spr_after < 0.50` | 호출부는 모두 `facing_bb <= target_bb` 다. 그래서 `target ≥ 0.75·stack` 이면 `rem ≤ 0.25·stack`, `pot_after ≥ target ≥ 0.75·stack`, `spr_after ≤ 0.33 < 0.50` 이 된다. 첫 조건은 항상 둘째 조건에 가려진다. 0.75 → 0.76 뮤테이션이 raise_form 직접 800건 + 디펜스 경로 1,500건 probe 에서 행동을 바꾸지 못했다. 호출부 3곳(preflop.py 핫존·defend_decision·multiway)은 모두 target = open × 배수(≥2.1) 또는 올인 금액 그대로라 facing ≤ target 이 성립한다(0.50 → 0.55 는 검출) | 죽은 조건 정리 후보. 제거는 행동 불변이지만, `facing > target` 호출이 생기면 의미가 달라지므로 별도 커밋으로 한다 |

## 9단계 B2 (ranges / reads) — 처리 상태

기준 `59650db`. 행동 보존 검증 결과는 `REFACTOR_AND_VERIFICATION.md` 7차.

| ID | 상태 | 처리 |
|---|---|---|
| L047 | **KEEP** | `ranges.narrow_by_actions` 의 `aggressive_streets` 는 재생 중 '이 액션 시점까지' 누적된 공격 street 수이고, `action_events.aggressive_street_count` 는 결정 시점의 전체 수(max 1)다. 시간 기준이 다른 질문이라 합치면 값이 바뀐다. 코드에 그 경계를 주석으로 남겼다 |
| L082 | DONE | 네 서명 함수의 계약(시드 payload / 보관용 SHA / 프로세스 내 refresh 해시 / seat-keyed 묶음)을 `plan._opp_ranges_signature` docstring 에 명시. 함수는 이미 분리돼 있어 코드 변경 없음 |
| L089 | DONE | 밸류 폭 `ranges.bet_value_support_fraction`, 블러프 선택 점수 `bot.bluff_barrel_continuation`(flop/turn 전용) / `bot.bluff_nut_blocking`(모든 street) |
| L103 | DONE | `ranges.strong_support_region`(support 개수 분위) / `ranges.blocked_mass_share`(posterior 질량 가중) |
| L164 | DONE | `reads.observed_record_rates` = 관찰 기록의 원시 빈도(FACT). 수축·축 역산·오독 잡음·확신(PERCEPTION)은 `estimate` 에 남김. RNG 소비 순서 동일 |
| L168 | DONE | 두 가중치 함수에 중복된 '증거의 양' 식을 `persona.read_evidence_amount` 하나로 합침(값 동일). 적용 의지/능력 부분은 각 함수에 그대로 |
| L169 | DONE | `plan.perceived_facing_price` — 사실(`sz_true`, `tocall`)과 인지(`sz_seen`, `tocall_seen`, read)를 분리. `calldown_need` 의 지역 이름 `need_true` 는 실제로는 인지된 가격 기반이다 — 이름 정리는 B3(L145) |
| L184 | DONE | 4차에서 이미 함수 분리. 합성 함수 `pressure_opportunity` docstring 에 FACT/PRIOR → APPLICATION → READ 층 명시 |

### 관찰 기록

| ID | 내용 | 판정 |
|---|---|---|
| L-S9-02 | 관찰자가 복원한 상대 레인지에는 hero 카드가 들어간 콤보가 남아 있다. baseline 짧은 sim(시드 11, 15핸드 상한) 에서 `blocker_score` 호출 624건 중 612건이 그랬다. equity 계산은 dead 카드를 따로 거르고, `blocker_score` 는 이 콤보로 블로커 몫을 잰다(486건이 0 이 아님). 의도된 계약으로 보이지만 '레인지 폭'을 콤보 수로 세는 소비처가 hero 카드 콤보를 함께 세는지는 B3 에서 확인한다 | KEEP(기록) |

## 9단계 B3 (plan 포스트플랍) — 처리 상태

기준 `ea07ec4`. 행동 보존 검증 결과는 `REFACTOR_AND_VERIFICATION.md` 8차. 전략 계수, 임계값, 행동 의미는 바꾸지 않았다. 의미 변경이 필요한 나머지 부분은 아래 '후속' 표에 따로 적었다.

| ID | 상태 | 처리 |
|---|---|---|
| L015 | DONE | `overbet_frac` 을 네 단계로 나눴다: `overbet_value_continue_rel`(콜당했을 때 강도) / `overbet_line_polarization`(라인 양극성) / `overbet_selection_base`(선택 확률, river ×1.35) / `overbet_size`(사이즈 + rng 한 번). street 의미는 selection 단계에 드러난다 |
| L016 | DONE(문서) | `bluff_mode` 의 'probe' 는 사이즈 모드이고 포커의 프로브 벳 기회가 아니다. docstring 에 명시. 라벨 문자열 변경은 기록되는 상태값이 바뀌므로 후속 L-S9-05 |
| L105 | DONE | `self_strength_bias_shift`(overpair_love/draw_love/sticky 가산)를 분리. `perceived_rel` = clamp(rel + shift) |
| L115 | DONE | make_plan 밸류 사다리의 문턱 조각을 함수로 분리: `multiway_value_thresholds`, `read_value_threshold_shift`, `relative_strength_value_threshold_shift`, `middle_value_two_street_context/probability`. 하나의 일반 강도로 합치지 않음 |
| L116 | DONE | make_plan 중간 밸류 맥락(`middle_value_two_street_context`)과 decide_response 의 페어드 보드 플러시 감쇠(`paired_board_flush_raise_damp`)를 각각 이름 붙여 분리. 문턱이 달라 합치지 않음 |
| L118 | DONE | `deep_one_pair_vulnerability`. decide_response 쪽에는 같은 계산이 없다(확인) |
| L119 | DONE | `continue_range_commit_strength`(make_plan 커밋 재측정), `continue_range_call_equity`(river 얇은 밸류와 개선된 블러프 재판정에 중복돼 있던 동일 블록을 MERGE, 값 동일), `overbet_value_continue_rel`. 네 소비처의 지표(rel 와 eq)와 문턱(0.50, 0.54) 통일은 후속 L-S9-03 |
| L120 | DONE | `semibluff_line_probability`, `semibluff_barrel_sizing`(make_plan) / `semibluff_raise_probability`, `semibluff_implied_odds_credit`(decide_response). refresh 의 드로우 소멸 해제는 다른 질문이라 유지 |
| L121 | DONE | 동기·증거 `pure_bluff_evidence` / 실행 확률 `pure_bluff_attempt_probability` / 위장은 기존 `bluff_mode` |
| L122 | DONE | `potcontrol_disposition`(성향 스칼라), `medium_potcontrol_probability`(중간강도 자리의 확률) |
| L123 | DONE | `potcontrol_bet_probability` → (p, why). 강도 0.30 미만 / 뒤에 어그레서 / 기본 세 갈래 |
| L124 | DONE | `blockbet_probability`. 플랍 비이니셔티브 동크 억제(`bluff_donk_suppression`)와는 다른 함수로 남김 |
| L134 | DONE | `bluff_donk_suppression`. outs ≥ 8 (턴 드로우) 완화와 체크스루 후 프로브 완화를 한 곳에서 본다 |
| L138 | DONE | `planned_size_base`(계획 → 기준 사이즈, bluff_mode merged/barrel/배수) |
| L139 | DONE | L015 와 같은 분리. 턴/리버 차이는 `overbet_selection_base` 의 street 인자 |
| L140 | DONE | 분리 완료. 멀티웨이에서도 HU `relative_strength` 와 합집합 레인지를 쓰는 의미 문제는 후속 L-S9-04 |
| L142 | DONE(문서) | `target_commit` 의 쓰이지 않는 `s`/`street` 인자를 docstring 에 명시. 시그니처는 유지 |
| L144 | DONE(문서) | L016 과 같다. 이름 변경은 L-S9-05 |
| L145 | DONE | `perceived_call_price_share` → (need_true, call_need_true). docstring 에 층(사실 가격 → 인지 가격 → 주관 문턱)을 적고, `read` 인자가 쓰이지 않음을 명시 |
| L146 | DONE(문서) | `_nonvalue_raise_ev_gate` 범위(HU 콜/폴드만, 멀티웨이 트리 없음, 모르면 allow). hero 카드 질량 문제는 L-S9-02a |
| L147 | DONE | decide_response 의 판단 조각을 분리: `monster_raise_probability`, `value_raise_size_mult`, `value_raise_probability`, `value_raise_qualification`(→ ok, eq_cont, fair_share). plan_state 기록은 호출부에 그대로 둠 — 기록 위치 이동은 후속 L-S9-06 |
| L149 | DONE | `checkraise_street_skill`(개념 street 별 / 아키타입 기본 2) |
| L152 | DONE | `checkraise_street_multiplier`, `checkraise_target_amount`. rng.uniform 순서는 `checkraise_size` 에 유지. 단위 감사 결과: tocall 기준 금액이다. 세션 경로(`check_then_face_bet`)에서는 hero_contrib 가 0 이라 절대 target 과 같다(action_events._response_kind 로 확인) |
| L153 | DONE | `response_equity`(3단계 대체 경로), `response_raise_target`, `intent_chip_amount`. act_with_plan 이 여전히 decide_response 를 부르는 구조(추론과 실행의 결합)는 후속 L-S9-06 |
| L157 | DONE | 개념 게이트 표를 모듈 상수 `PLAN_REQUIRED_CONCEPT` / `PLAN_DOWNGRADE` 로 꺼냄. trap 이 generic 'checkraise' 별칭을 쓰는 문제는 후속 L-S9-07 |

### 후속(의미 변경 필요 — 구조분리 기준점 커밋에서는 수정하지 않음)

사용자 결정(목적 변경)에 따라 아래 LATER 는 미루지 않는다. B3 통합 단계에서 모두 판정하고 최종 실행 경로에 반영한다.

| ID | 내용 | 분류 |
|---|---|---|
| L-S9-02a | `_nonvalue_raise_ev_gate` 의 `fold_p` 가 hero/board 와 겹치는 콤보 질량을 분모와 분자에 넣는다. 이 hero 패에 조건을 건 fold 확률이 아니다. 봉인 sim 에서 219회 중 2회 허용 → 거부로 뒤집힘. 재현 사례와 영향 경로는 `stage9/L_S9_02_HERO_CARD_COUNTING.md` | LATER(행동 변화) |
| L-S9-03 | 'continue range 대비 강도'를 네 곳이 다른 지표와 문턱으로 묻는다: 커밋 rel(min) / 오버벳 HU rel @1.15 / 리버 얇은 밸류 eq ≥ 0.50 / 개선된 블러프 eq ≥ 0.54 + rel ≥ 0.55 | LATER |
| L-S9-04 | 오버벳 밸류 재측정이 멀티웨이에서도 합집합 opp_range 와 HU `relative_strength` 를 쓴다 | LATER |
| L-S9-05 | `bluff_mode` 의 'probe' 라벨 → 사이즈 모드 이름으로 변경(plan_state 기록값이 바뀜) | LATER(RENAME, 기록 변화) |
| L-S9-06 | decide_response 와 act_with_plan 에 판단, 계획 기록, 실행이 남아 있다(ARCH). 함수 경계 이동은 세션 호출 구조를 바꾼다 | LATER |
| L-S9-07 | `_allowed` 에서 trap 이 generic 'checkraise' 별칭(플랍 능력)으로 허용을 묻는다 | LATER |
| L-S9-08 | `_eq_current` docstring 의 '기록 전용'은 사실이 아니었다. make_plan 의 `_sd_eq`(블러프/쇼다운 분기)에 쓰인다. docstring 을 실제 소비에 맞게 고쳤다(코드 불변). 판단 근거로 미래 eq 대신 현재 eq 를 쓰는 것은 의도된 설계(주석 근거)라 KEEP | KEEP(문서 수정) |

### L-S9-02 추적 결론

- 레인지를 액션으로 자르는 것(`_bet/_call/_continue/_check_range`, `narrow`)은 상대 전략 모델이다. hero 패와 무관하게 전체 위에서 자르는 것이 맞다(KEEP).
- equity 와 relative_strength 는 이미 hero/board 를 거른다(KEEP).
- 블로커 계산은 hero 카드와의 상호작용을 일부러 본다(KEEP).
- 개수 기준 안전장치 두 곳은 측정상 영향이 없었다(기록):
  - `narrow_by_actions` 바닥: 2,697건 중 1건
  - `response_equity` 2단계: 1,267건 중 0건
- 실제 왜곡은 `_nonvalue_raise_ev_gate` 의 fold_p 한 곳이다 → L-S9-02a.

## 9단계 B3 통합 (최종 인간모델 — 판정과 단일 경로)

기준 `20e206f7`(B3 구조분리). 목적 변경 이후의 처리다. 충돌은 미루지 않는다. 의도한 행동 변화는 근거와 같은 상태 쌍 비교로 기록한다.

본체 / Human Model 2차 / 3차는 이름이 아니라 도입 commit 과 플래그로 식별했다.
- 2차: `T2_GTO_MEMORY_V2`(22487e9f, persona/preflop)
- 3차: `T2_PREFLOP_REASONING_V3`, `T2_EXPLOIT_WEIGHT_V3`, `T2_CALC_NOISE_V3`, `T2_PREFLOP_TEMPER_DIRECTION_V3`, `T2_READ_RECENCY_V3`(114c846f 이후)
- plan 범위의 플래그 소비처는 `trap_judgment` 의 EXPLOIT_WEIGHT_V3 하나다.
- `hierarchical style belief v3`, `STYLE_CALIB_V2` 는 상대 모델 실험 계열이라 Human Model 2차/3차가 아니다.

| ID | 충돌 | 최종 선택 | 근거 | 검증 |
|---|---|---|---|---|
| L-S9-02a | 비밸류 레이즈 EV gate 의 fold_p: 전체 질량 vs hero 패에 조건을 건 질량 | 슬라이스는 전체 레인지 위에서, fold_p 의 분모와 분자는 hero/board 와 겹치지 않는 질량(`ranges.range_mass_live`) | 상대 전략은 hero 패를 모른다(슬라이스는 전체에서). 이 holding 이 받는 fold 확률은 상대가 실제로 가질 수 있는 콤보로만 정해진다(베이즈) | 같은 상태 쌍 비교: 시드 11/12 각 1건 허용 → 거부. 현재식은 평균 약 1%p 낙관적이었다 |
| L-S9-03 | '콜당했을 때 앞서는가'의 문턱이 셋: river 얇은 밸류 eq ≥ 0.50 / 개선된 블러프 eq ≥ 0.54 + 전체 rel ≥ 0.55 / 밸류 레이즈 eq > 0.5 | 이진 밸류 판정은 `ahead_when_called`(continue range 대비 eq ≥ 0.50) 하나 | 0.50 은 콜받는 부분의 손익분기다(포커 논리). 0.54 는 도입 commit(aae4b908)에 근거가 없고, rel ≥ 0.55 는 그 commit 이 대체하려던 옛 전체 rel 규칙의 잔재다. continue range 는 상대 레인지의 상단이라 이 판정이 통과하면 전체 rel 조건은 사실상 따라온다 | 시드 12 개선된 블러프 1건(eq 0.531) 쇼다운 → 밸류. 시드 11 밸류 레이즈 1건(eq 정확히 0.50) |
| L-S9-03 (연속 강도) | 커밋 재측정(joint+인지 rel) vs 오버벳(HU relative_strength, 인지 편향 없음) | `continue_range_strength` 하나: seat 별 continue range 가 다 있으면 joint, 아니면 기존 HU/합집합 fallback. 인지 편향은 perceived_rel | 같은 질문(그 사이즈를 계속하는 레인지 대비 강도)이다. rel 척도를 쓰는 이유: 소비처(target_commit, 양극성)가 rel 척도로 정의돼 있다 | 커밋 경로는 같은 연산이라 불변. 오버벳은 L-S9-04 |
| L-S9-04 | 오버벳 밸류 강도: 멀티웨이에서도 합집합 레인지 + HU 식 | joint(위 함수). `overbet_frac`/`decide_size`/`attach_intent` 에 n_opp, opp_ranges, seed 전달 | 멀티웨이 오버벳은 콜하는 모두를 동시에 이겨야 한다. 합집합은 강도를 과대평가한다 | 쌍 비교: 오버벳 판정 143회 중 17회 rel 변화. 전부 멀티웨이이고 전부 하향(최대 0.385). HU 는 동일 |
| L-S9-05 | bluff_mode 'probe'(사이즈 모드)와 공개 probe 벳 개념의 이름 충돌 | 라벨을 `'low_cost'` 로 변경 | 같은 단어가 다른 질문 둘을 가리켰다. 라벨 값을 비교하는 코드는 없다(merged/barrel 만 비교) | 기록 라벨만 변하고 행동은 같다 |
| L-S9-06 | decide_response/act_with_plan 의 판단·기록·실행 결합 | **현재 경계를 최종으로 확정** | decide_response 가 plan_state 에 쓰는 것은 `_last_*` 근거 기록과 deviation 로그뿐이고 계획을 바꾸지 않는다. act_with_plan 은 상황마다 한 경로를 고른다(tocall=0 이면 저장된 intent, tocall>0 이면 decide_response 한 번). 같은 질문에 경로가 둘인 곳이 없다 | 코드 변경 없음 |
| L-S9-07 | `_allowed` 가 trap 허용을 generic 'checkraise'(=플랍 능력)로 판정 | street 별 개념(`street_concept`) 으로 판정. 아키타입 경로(street 구분 없음)는 그대로 | trap_judgment 가 이미 같은 alias 버그를 고쳐 street 능력을 쓴다. 턴/리버 트랩은 그 street 의 체크레이즈 능력으로 실행된다 | 필드 프로필 2,000건(턴/리버): 394건 변화(346 강등 / 48 허용). 최대 숙련 baseline 은 불변 |
| HM3 EXPLOIT_WEIGHT_V3 | trap 의 상대 정보 가중치: legacy `exploit_weight`(0.5 adaptability + 0.3 range_read + 0.2 attention) vs 3차(`read_opponent` 공통 w × 빈도/라인 인식) | 3차 경로를 유일 경로로. plan 은 더 이상 `exploit_weight` 를 부르지 않는다 | `read_opponent` 는 상대 읽기의 단일 입구이고, 다른 모든 소비처가 이미 쓴다. legacy 는 인식 능력을 전역 의지 배수에 다시 섞어 이중으로 셌다. 인식 혼합 0.65/0.35 는 opp_bet_prob 자체 식과 같다 | range_read 높음/attention 낮음 프로필: 0.392 → 0.176(벳 빈도 읽기는 세기 = attention). baseline 은 exploit 중립이라 불변. `persona.exploit_weight` 와 플래그는 생산 소비처가 없어졌고, 검증기와 함께 B5(호환 경로 제거)에서 퇴역 |

새 baseline(B3 통합):
- 시드 11 `e6d8b5e5…`: 불변. 위 변화가 시드 11 에서는 실제 행동 분기로 이어지지 않았다.
- 시드 12 `8c33ece5…`: 쌍 비교로 확인한 변화(fold_p 1, 개선된 블러프 1, 멀티웨이 오버벳 rel 10) 중 하나 이상에서 갈라졌다.
- 측정 도구: `tools/b3_integration_attribution.py`. 측정 실행 지문이 일반 sim 지문과 같다.

## 9단계 B4 통합 (persona / concept 역할)

기준 `217bb4c0`.

### 판정

| ID | 충돌 | 최종 선택 | 근거 | 검증 |
|---|---|---|---|---|
| L148 | 콜 문턱 편향이 두 번 적용됨: `calldown_need` → `persona.call_bias`(station, bluff_fear, draw_love, sticky), decide_response 마지막 분기 → `apply_response_biases_to_call_threshold`(station, bluff_fear 재적용 + hero_call) | `persona.call_bias` 한 곳에서 한 번. hero_call 은 거울상인 bluff_fear 와 같은 노출(street × size)로 call_bias 에 편입. 두 번째 적용 함수는 삭제 | call_bias 는 선언된 주관 문턱 층이다(L145). 모든 응답 분기와 layer-call EV 가 이 need 를 쓴다. 두 번째 적용은 마지막 분기에서만 같은 기질을 다시 곱했다 | 같은 상태 쌍 비교(`tools/b4_integration_attribution.py`): 마지막 분기 514회 중 8회 콜 → 폴드(시드 11: 2, 시드 12: 6). 반대 방향 0 |
| L008/L009 | bluffcatch 숙련이 hero_call 편향을 **키움**(0.45·S). 최대 숙련·중립 기질에서 +0.25 | 숙련 항 방향을 bluff_fear 와 같게: 0.45·(10 − S). 계수는 유지 | 숙련은 오류를 줄인다(편향은 최대 숙련에서 0 이하라는 설계 규칙). hero_call 과 bluff_fear 는 같은 블러프 판정 오류의 두 방향이다. 방향을 정하는 것은 기질(aggression, tilt_prone)이다 | 최대 숙련 hero_call +0.25 → −0.65(비활성). 위 8회 뒤집힘이 이 편향 소멸의 결과다 |
| HM3 CALC_NOISE_V3 / L114, L021~L023 | potodds·spr 계산 오차: legacy 공통 양(+) bias vs 3차 평균 0 대칭 오차(outs 는 둘 다 방향성 유지) | 3차를 유일 경로로. 플래그 퇴역 | 산술 오차에는 보편적인 부호가 없다. legacy 는 대칭 경계에서 잘못된 과잉 폴드 0.631 vs 잘못된 콜 0.305 를 만들었다(`tools/verify_calc_noise_v3.py` C5). 사람의 방향성은 station/bluff_fear 가 이미 담당한다. SPR 은 중립 쪽으로 당기는 인지 모델이 따로 있어 legacy 상향 bias 가 그것을 상쇄했다(C6) | 최대 숙련에서는 비트 동일(gauss 한 번, σ = 0.02 에서 clamp 비활성). 검증기 6/6 |
| HM3 PREFLOP_TEMPER_DIRECTION_V3 | 기질 방향 정규화 /4(0 = 1, 9 = 10 으로 잘림) vs /5 | /5 를 유일 경로로. 플래그 퇴역 | 기질은 중점 5 인 0..10 척도다. /4 의 끝점 붕괴는 척도 오류이지 판단이 아니다. 기록된 감사(CONCEPT_SYSTEM §15): 끝점 동점 제거, 디펜스 clamp 감소(q = .4: 7.17% → 5.92%), 끝점과 중점 불변 | 중립 기질 baseline 불변. 검증기 5/5(legacy 는 검증기 안의 참조식으로만 남김) |

### 개념 역할 항목 (같은 질문인가)

아래 항목은 소비처들이 같은 능력 질문을 하므로 공급자 하나가 최종이다. 따로 갈라진 실행 경로는 없다.
- **L001 bluff, L020 reraise**: 포스트플랍 소비처는 같은 질문이다. 프리플랍 소비처(`preflop.py` 3bet bluff_skill, `persona` traits.threebet)는 9-max 3bet 지식(R2)과 얽혀 마지막 B1/B2 통합에서 판정한다.
- **L002 semibluff**: river 에서는 코드가 street != river 로 이미 제외한다.
- **L006/L007 checkraise**: L-S9-07 이후 production 소비처는 모두 street 해석이다. 아키타입 경로는 street 구분이 없는 데이터다.
- **L012 blockbet, L013 potcontrol, L014 trap, L034 range_merge**: 각 소비처가 같은 계획 능력을 묻는다.
- **L019 stackoff**: 중간 밸류 판단, 밸류 레이즈, 커밋 목표가 모두 '스택을 걸 계획을 세우는 능력'이다.
- **L025 blocker, L026 icm, L036 fold_equity**: 각각 한 가지 지식이다.
- **L028 sizing_tell**: 상대 사이즈 읽기와 자기 사이즈 위장은 '사이즈에 정보가 담긴다'는 같은 지식의 두 방향이다.
- **L021~L023 outs/potodds/spr**: 숙련 = 계산 정밀도. 오차의 의미는 CALC_NOISE 판정으로 확정했다.

### B4 에서 남긴 것

- `GTO_MEMORY_V2` 와 `PREFLOP_REASONING_V3` 는 마지막 B1/B2 통합에서 판정한다.
  - 둘 다 프리플랍 차트 기억을 '현재 조건 reference'(9-max `gto.rfi`/`defend_pct`)로 옮기는 것을 다룬다. 이 reference 는 R2 의 미검증 9-max 수치다.
  - 사용자 지시에 따라 그 단계에서 완성된 DB, 자체 계산 결과, 공개 자료 또는 최소 직접 계산으로 근거를 확보해 결론 낸다.
- `persona.exploit_weight` 와 그 플래그는 production 소비처가 없다. B5 에서 검증기와 함께 퇴역한다.

새 baseline(B4): 시드 11 `7ce1561d…`, 시드 12 `ef73996c…`.

## 9단계 B5 통합 (호환 / 이름 / 옛 경로 제거)

기준 `274bdd37`. B5 항목은 실행 경로를 바꾸지 않는 정리다. 그래서 baseline 지문은 B4 와 같아야 한다(검증 결과는 REFACTOR 11차).

| ID | 대상 | 최종 처리 | 근거 |
|---|---|---|---|
| L211 / L175 | `icm.field_bf` 첫 정의(뒤 정의에 덮임) + 그 전용 표 `_PROX`, `_STACK`, `_lerp`, `MAX_PREMIUM`, `EXACT_MAX_SEATS` | 삭제 | 파이썬은 뒤 정의를 묶는다. 첫 정의는 도달 불가였다. 생존 정의(lognorm 곡선)만 남는다 |
| L-RA14 | `preflop.DEF_POS_MULT`, `preflop.DEPTH_OPEN_MULT`, `persona.OPEN_ELASTICITY`, `plan.PLANS` | 삭제 | production 에서 읽는 곳이 없었다. 남겨 두면 감사에서 살아 있는 지식으로 오독된다 |
| L210 | `table.Table.sidepots` | 삭제 | 호출부가 없다. 사이드팟은 F8 layer 경로가 담당한다 |
| L154 | `runner.shape_size`(persona.shape_size 를 감싸는 호환 래퍼) | 삭제. 사이즈 습관 식은 `persona.shape_size` 하나 | 같은 식의 두 진입점. 게이트 `verify_core_sizing_ownership` 은 '래퍼 동일성' 대신 'runner 에 식 없음'을 검사하도록 바꿨다 |
| L189 | `session._diagnostic_layer_equities` | `layer_equities_by_pot_layer` 로 이름 변경, docstring 정정 | '진단/기록 전용'이 아니었다. `_layer_call_summary` → `act_with_plan(call_value=…)` 로 콜 판단에 쓰인다 |
| L095 / L097 / L102 | `made_strength`, `relative_strength`(rel), `nut_advantage` | 이름 유지, docstring 에 정확한 정의 | 널리 쓰이는 API 라 이름을 바꾸면 의미 변화 없이 혼란만 생긴다. 오해의 소지(equity 아님, 문자 그대로의 넛 아님)는 정의로 막는다 |
| HM3 EXPLOIT_WEIGHT_V3 잔여 | 플래그, `persona.exploit_weight`, `persona.opponent_read_application_weight` | 삭제. 적용 가중치는 `_exploit_base_weight` 하나(read_opponent 입구) | B3 통합 뒤 production 소비처가 없었다. 검증기는 단일 가중치 계약으로 갱신했다 |
| response_kind=None 호환 | `act_with_plan` 의 `response_kind is None and checked_before` 체크레이즈 분기와 `checked_before` 인자 | 삭제. 체크레이즈 스팟 판정은 canonical `response_kind == 'check_then_face_bet'` 하나 | 세션은 항상 kind 를 넘긴다(`action_events._response_kind` 는 None 을 내지 않는다). `checked_before` 는 이 분기 말고는 의미가 없었다. f3/f5 fixture 는 canonical kind 를 쓰도록 바꿨다 |
| bias street 기본값 | `bias('bluff_fear'/'hero_call', street=None)` → 리버 숙련으로 대체 | street 를 요구(`_bluffcatch_concept`) | production 은 항상 street 를 넘긴다. 대체값은 다른 street 의 능력을 섞는 호환 기본값이었다 |
| CI 워크플로 | 퇴역 플래그 env | 제거 | 퇴역 플래그는 효과가 없다 |

남은 확인 사항(이번 B5 범위에서 수정하지 않음):
- `oop_legacy_abs` 는 판단 경로가 아니라 기록용 비교값이다(plan 주석). 실행 경로가 둘이 아니므로 유지한다.
- `cbet_freq` 디스패처는 production 단일 진입점이다. continuation 함수군은 GTO terminal-continuation 작업과 맞닿아 있어 손대지 않았다(사용자 지시).
- `tools/verify_f3_checkraise_response.py`, `tools/verify_f5_backaction.py`, `tools/verify_prelogic_execution_boundary.py` 는 B5 이전(HEAD)에도 실패하던 검증기다(기존 결함, B5 원인 아님). f3 는 23-gate 의 기존 실패 6개 중 하나다.
