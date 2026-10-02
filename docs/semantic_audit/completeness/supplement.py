#!/usr/bin/env python3
"""Completeness supplement for the semantic-audit registry (re-audit, 2026-10-02).

Single source for:
  NEW_ROWS     concepts found inside long functions / inline blocks that the
               first 227-row registry only covered through an umbrella row
  ROW_UPDATES  corrections to existing rows (wrong meaning, stale street)
  SPANS        code span -> concept ownership used by
               tools/check_semantic_completeness.py
  DECOMPOSED   multi-meaning functions that must be covered span by span
  NONSEMANTIC_FUNCTIONS  functions that implement no poker semantic (reason given)

Spans are anchored by (module, function, first-line substring, last-line
substring) so they survive line drift.  Running this file rewrites
CONCEPT_FUNCTION_REGISTRY.csv/.json (rows with origin IMPLICIT_CODE_V2 are
regenerated, other rows are kept, ROW_UPDATES are applied) and SPAN_MAP.json.
"""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.dirname(HERE)

COLS = ['concept', 'poker_meaning', 'street', 'category', 'layer', 'producer',
        'consumer', 'function', 'state_variables', 'inputs', 'output',
        'source_knowledge', 'axis', 'runtime_status', 'action_influence',
        'duplicate_overload', 'recommended_canonical_name', 'evidence',
        'origin', 'current_function', 'parent_concept', 'code_span']


def row(concept, meaning, street, category, layer, producer, consumer, inputs,
        output, knowledge, axis, status, action, overload, canonical, parent,
        span, state=''):
    return {
        'concept': concept, 'poker_meaning': meaning, 'street': street,
        'category': category, 'layer': layer, 'producer': producer,
        'consumer': consumer, 'function': producer, 'state_variables': state,
        'inputs': inputs, 'output': output, 'source_knowledge': knowledge,
        'axis': axis, 'runtime_status': status, 'action_influence': action,
        'duplicate_overload': overload, 'recommended_canonical_name': canonical,
        'evidence': span, 'origin': 'IMPLICIT_CODE_V2',
        'current_function': producer, 'parent_concept': parent,
        'code_span': span,
    }


PF, FL, ALL3 = 'preflop', 'flop turn river', 'flop turn river'
YES = 'YES (direct or upstream)'
YES_BASE = 'YES; baseline(tilt 0, exploit neutral) also'
EXPLOIT_ONLY = 'YES only when read weight w>0; neutral at baseline'

NEW_ROWS = [
    # ---------------- plan.make_plan ----------------
    row('perceived_board_danger',
        '보드 완성 위험을 board_texture 숙련도만큼만 인식한 값',
        ALL3, 'PERCEPTION', 'JUDGMENT', 'plan.make_plan',
        'plan.trap_judgment;plan.stackoff_plan;plan.bluff_mode;plan.make_plan value p2',
        'bot.board_danger(board), sk(board_texture)', 'danger 0..1 (scaled)', 'M/H',
        'reasoning', 'SEMANTICALLY_OVERLOADED', YES,
        'state key "danger" holds the skill-scaled value after make_plan but the raw '
        'bot.board_danger after refresh; decide_size equity denial and make_plan p2 read raw danger. '
        'SPLIT raw_board_danger vs perceived_board_danger (behavior change: deferred)',
        'perceived_board_danger', 'board_completion_danger',
        'plan.make_plan: dang = bot.board_danger(board) .. dang *= min(1.0, PS.sk(profile,\'board_texture\')/6.0)'),
    row('perceived_spr',
        'SPR을 계산 오차(calc_noise)와 spr 숙련도에 따라 중립 5.0 쪽으로 흐리게 본 값',
        ALL3, 'PERCEPTION', 'JUDGMENT', 'plan.make_plan',
        'plan.trap_judgment;plan.bluff_mode;state spr',
        's_true=spr(stack,pot), calc_noise(spr), sk(spr)', 's (perceived)', 'M/H',
        'reasoning', 'ACTIVE', YES,
        'same function also uses s_true (target_commit, value p2 context): two SPR views '
        'consumed by different questions; KEEP but name both', 'perceived_spr', 'spr_ratio',
        'plan.make_plan: s_true = spr(stack, pot) .. s = s*_sa + 5.0*(1.0 - _sa)'),
    row('potcontrol_disposition',
        '팟컨트롤 성향 합성값 pc = (icm + (10-gamble) + (10-aggr))/30',
        ALL3, 'PERSONALITY / TEMPERAMENT', 'PLAN', 'plan.make_plan',
        'plan.make_plan pot_control probability', 'profile icm, gamble, aggr',
        'pc 0..1', 'H', 'reasoning', 'SEMANTICALLY_OVERLOADED', YES,
        'ARCH_MISMATCH: icm (knowledge skill) and gamble/aggr (temperament) summed into '
        'one motive scalar', 'potcontrol_disposition', 'potcontrol_motive',
        'plan.make_plan: pc = max(0.0, min(1.0, (profile[\'icm\']'),
    row('value_when_called_strength',
        '그 사이즈를 실제로 계속(콜/레이즈)할 상대 레인지 대비 내 강도 — "콜당했을 때도 앞서는가"',
        'flop turn river', 'CALCULATION', 'JUDGMENT',
        'plan.make_plan (commit_rel);plan.overbet_frac;plan.river_value_reassessment;plan.refresh (improved bluff)',
        'plan.target_commit;plan.stackoff_plan;overbet polarity;river thin value;bluff re-judgment',
        'R.perceived_continue_range(opp_range, board, street, size, profile), relative_strength/_eq_vs',
        'rel or equity vs continuing range', 'M', 'reasoning', 'DUPLICATED', YES,
        'same poker question answered four times with different metric/threshold: commit uses rel '
        '(min with full rel), overbet uses HU relative_strength at fixed 1.15 pot, river thin value '
        'uses equity >= 0.50, improved bluff uses equity >= 0.54 and rel >= 0.55. MERGE into one '
        'producer only with a behavior-change review (deferred)',
        'value_when_called_strength', 'continue_range_value',
        'plan.make_plan: _commit_rel = rel .. _so[\'commit_rel\']; plan.overbet_frac: if value_line and opp_range and board'),
    row('multiway_value_threshold_shift',
        '상대 수가 늘면 3/2스트리트 밸류·중간강도 문턱을 올림(넛급 면제, 트립스 이상 절반)',
        ALL3, 'REASONING', 'JUDGMENT', 'plan.make_plan', 'make_plan plan ladder',
        'n_opp, made', 'v3, v2, pcz', 'H', 'reasoning', 'ACTIVE', YES,
        'constants 0.06/0.07/0.06 per extra opponent; independent from joint equity already '
        'computed vs all pools (possible double count; behavior change deferred)',
        'multiway_value_threshold_shift', 'value_line_selection',
        'plan.make_plan: mw = max(0, n_opp - 1) .. pcz = 0.50 + 0.06*mw'),
    row('read_value_threshold_shift',
        '그 스트리트 폴드 성향 읽기로 밸류/블러프 문턱 이동(잘 접는 상대 → 밸류 문턱↑)',
        ALL3, 'EXPLOIT / ADAPTATION', 'JUDGMENT', 'plan.make_plan', 'make_plan plan ladder',
        'read_opponent(...).w, street_gap', 'v3,v2,pcz shift', 'H/E', 'exploit',
        'ACTIVE', EXPLOIT_ONLY, 'KEEP; exploit axis separate from baseline ladder',
        'read_value_threshold_shift', 'value_line_selection',
        'plan.make_plan: if rd[\'w\'] > 0: .. pcz += wq * 0.30 * sg'),
    row('bluff_evidence_composite',
        '블러프 계획 근거 합성: bluff 숙련 × 블로커(강콤보) × 넛우위 × 다인원/뒤 인원 감쇠 × 순블로커 × 폴드성향',
        ALL3, 'REASONING', 'PLAN', 'plan.make_plan;plan._blocker_score_bluff_factor;plan._blocker_net_bluff_factor',
        'plan.make_plan pure bluff gate', 'profile bluff, blocker_score, blocker_effect, nut_adv, mw, to_act_behind, read',
        'bluff_ok', 'M/H/E', 'reasoning', 'SEMANTICALLY_OVERLOADED', YES,
        'capability (bluff skill) multiplies evidence in one scalar; unlike preflop R3 it is a '
        'product (skill cannot replace evidence) but ability and evidence are still not separable '
        'in telemetry. SPLIT bluff_evidence vs bluff_execution_skill (semantic-only possible)',
        'bluff_evidence_composite', 'pure_bluff_line_selection',
        'plan.make_plan: bluff_ok = (profile[\'bluff\']/10.0) .. bluff_ok *= max(0.25, 1.0 + rd[\'w\']'),
    row('relative_strength_value_threshold_shift',
        '밸류 분류는 eq(미래 포함)로 하되 rel(현재 not-behind)이 낮으면 문턱을 올리고 넛급이면 낮춤',
        ALL3, 'REASONING', 'JUDGMENT', 'plan.make_plan', 'make_plan plan ladder',
        'rel', 'v3, v2 shift', 'H', 'reasoning', 'SEMANTICALLY_OVERLOADED', YES,
        'value ladder compares eq (runout share incl. draws) while rel adjusts the bar: two '
        'strength notions mixed in one classifier; KEEP, documented in RANGE/CALC split',
        'relative_strength_value_threshold_shift', 'value_line_selection',
        'plan.make_plan: if rel <= 0.45: .. v2 += 0.08 * _pen'),
    row('showdown_value_predicate',
        '쇼다운 가치 있음 = made>=1 또는 equity >= 0.42+0.05*mw',
        ALL3, 'REASONING', 'JUDGMENT', 'plan.has_showdown_value',
        'plan.make_plan pot_control/showdown/giveup routing', 'made, eq or eq_current, mw',
        'bool', 'H', 'reasoning', 'DUPLICATED', YES,
        'three variants in make_plan: medium band uses eq (future equity), final else uses '
        'eq_current, pure-bluff gate uses eq_current < 0.42 without mw. Extracted as '
        'plan.has_showdown_value(made, equity, mw) with the equity basis explicit; the eq vs '
        'eq_current inconsistency is a deferred semantic-fix',
        'plan.has_showdown_value', 'potcontrol_motive',
        'plan.make_plan: _sd_eq = eq_cur .. ; _sd_here = ..; has_sd = ..'),
    row('medium_strength_merge_value',
        '중간 강도(pcz 구간)에서 range_merge 숙련도가 높으면 얇은 2스트리트 밸류로 머지',
        'flop turn', 'MOTIVE / PLAN', 'PLAN', 'plan.make_plan', 'plan intents',
        'rel, made, sk(range_merge)', 'value_2street', 'H', 'reasoning', 'ACTIVE', YES,
        'flop thin value reads range_merge (street_concept thin_value/flop); KEEP',
        'medium_strength_merge_value', 'range_merge',
        'plan.make_plan: elif rel >= max(0.28, 0.52 - 0.080*_mg) and made >= 1'),
    # ---------------- plan.decide_response ----------------
    row('monster_made_hand_raise',
        '넛급(made>=5) + eq>need+0.10 이면 계획과 무관하게 레이즈 확률을 굴림(페어보드 플러시 감산)',
        ALL3, 'MOTIVE / PLAN', 'JUDGMENT', 'plan.decide_response', 'plan.act_with_plan',
        'made_now, eq, need, rel(recomputed), board_paired, aggr, gamble, sk(reraise)',
        'raise/call/fold', 'H', 'reasoning', 'ACTIVE', YES,
        'plan-independent branch evaluated before the value branch; uses board-relative made '
        'category, not continue-range strength', 'monster_made_hand_raise', 'response_plan',
        'plan.decide_response: if made_now >= 5 and eq > need + 0.10 .. return \'call\', 0.0, (_cf_need if _layer_call else need), \'넛급이나'),
    row('value_raise_sizing_from_commit',
        '밸류 레이즈 배수: 목표 커밋(stack*commit)과 현재 콜 금액 차이로 0.75~1.6',
        ALL3, 'EXECUTION FORM', 'PLAN', 'plan.decide_response', 'act_with_plan raise target',
        'stackoff.commit, stack, tocall', 'mult', 'H', 'reasoning', 'ACTIVE', YES,
        'KEEP', 'value_raise_sizing_from_commit', 'target_investment_fraction',
        'plan.decide_response: _so = plan_state.get(\'stackoff\') or {} .. mult = max(0.75, min(1.6'),
    row('value_raise_qualification',
        '밸류 레이즈 자격: eq > N-way fair share, HU면 제안 레이즈를 계속할 레인지 대비 eq > 0.5',
        ALL3, 'CALCULATION', 'JUDGMENT', 'plan.decide_response', 'value raise branch',
        'eq, n_opp, perceived_continue_range at candidate price', 'ok + continue_eq', 'M',
        'reasoning', 'ACTIVE', YES,
        'multiway only checks fair share (no continue-range test): street/opponent-count '
        'asymmetry, deferred', 'value_raise_qualification', 'value_when_called_strength',
        'plan.decide_response: _fair_share = 1.0 / max(2.0 .. (_use_eq, _use_need))'),
    row('value_raise_frequency',
        '자격을 통과한 밸류 레이즈의 실행 확률(reraise 숙련, 커밋, 공격성, value2 감산, rel 하한)',
        ALL3, 'MOTIVE / PLAN', 'PLAN', 'plan.decide_response', 'act_with_plan',
        'sk(reraise), sk(stackoff), committed, aggr, rel_ps', 'raise prob', 'H',
        'reasoning', 'ACTIVE', YES, 'KEEP', 'value_raise_frequency', 'response_plan',
        'plan.decide_response: p = 0.20 + 0.55*rr .. return \'call\', 0.0, (_cf_need if _layer_call else need), \'밸류이나'),
    row('bluff_reraise_frequency',
        '블러프 계획(쇼다운가치 made<2) + eq<need-0.05 일 때 EV gate 통과 후 reraise×bluff 숙련으로 레이즈',
        ALL3, 'MOTIVE / PLAN', 'PLAN', 'plan.decide_response', 'act_with_plan',
        'sk(reraise), sk(bluff), nonvalue EV gate', 'raise', 'M/H', 'reasoning', 'ACTIVE', YES,
        'skill product is frequency, evidence is the EV gate: separated correctly',
        'bluff_reraise_frequency', 'nonvalue_raise_ev_gate',
        'plan.decide_response: if allow_raise and has_c and eq < need - 0.05 and plan in .. \'블러프 레이즈'),
    row('semibluff_raise_frequency',
        '세미블러프(아웃 8+, 리버 제외) 레이즈 확률과 EV gate',
        'flop turn', 'MOTIVE / PLAN', 'PLAN', 'plan.decide_response', 'act_with_plan',
        'sk(semibluff), sk(reraise), aggression, EV gate', 'raise', 'M/H', 'reasoning', 'ACTIVE',
        YES, 'KEEP', 'semibluff_raise_frequency', 'semibluff_line_selection',
        'plan.decide_response: if plan == \'semibluff\' and plan_state.get(\'outs\', 0) >= 8 .. \'세미블러프 레이즈'),
    row('implied_odds_adjustment',
        '드로우 콜의 내재 오즈: 남은 스택/팟 비율과 outs·potodds 숙련으로 필요 승률을 최대 0.12 낮춤',
        'flop turn', 'CALCULATION', 'JUDGMENT', 'plan.decide_response', 'semibluff call/fold',
        'stack, pot, sk(outs), sk(potodds)', 'need reduction', 'M/H', 'reasoning', 'ACTIVE', YES,
        'heuristic implied odds (no future-street EV model); only reachable from semibluff plan',
        'implied_odds_adjustment', 'calldown_required_share',
        'plan.decide_response: if stack > pot: .. _cf_need = max(0.02, _cf_need - implied)'),
    row('giveup_deviation_raise',
        '포기 계획인데 규율이 낮으면 EV gate를 통과한 블러프 레이즈로 계획을 뒤집음',
        ALL3, 'PERSONALITY / TEMPERAMENT', 'PLAN', 'plan.decide_response', 'act_with_plan',
        'discipline, sk(reraise), sk(bluff), EV gate', 'raise (deviation)', 'H', 'reasoning',
        'ACTIVE', YES, 'deviation recorded in plan_state.deviations; KEEP',
        'giveup_deviation_raise', 'response_plan',
        'plan.decide_response: if plan == \'giveup\' and has_c and eq < need - 0.05 .. \'DEVIATE:포기 계획 뒤집은'),
    row('price_overrides_giveup_plan',
        '포기/블러프 계획이어도 eq>=need면 콜, 아니면 폴드(계획이 팟오즈 부등호를 덮지 못함)',
        ALL3, 'CALCULATION', 'JUDGMENT', 'plan.decide_response', 'act_with_plan',
        'eq/need or layer call eq/need', 'call/fold', 'M', 'reasoning', 'ACTIVE', YES, 'KEEP',
        'price_overrides_giveup_plan', 'response_plan',
        'plan.decide_response: if plan in (\'bluff_2street\', \'giveup\', \'river_bluff\'):'),
    # ---------------- plan.decide_aggression ----------------
    row('giveup_initiative_stab_deviation',
        '포기/쇼다운 계획이라도 이니셔티브가 있으면 cbet/지연cbet 빈도×(1-0.085·규율)로 지속벳',
        ALL3, 'PERSONALITY / TEMPERAMENT', 'PLAN', 'plan.decide_aggression', 'plan.attach_intent',
        'cbet_freq, delayed boost, discipline', 'bet prob (DEVIATE)', 'H', 'reasoning', 'ACTIVE',
        YES, 'KEEP', 'giveup_initiative_stab_deviation', 'flop_cbet_plan',
        'plan.decide_aggression: if plan in (\'giveup\', \'showdown\'): .. \'DEVIATE:포기 계획이나'),
    row('bluff_execution_frequency',
        '블러프/세미블러프 계획의 실제 벳 확률: 뒤 2명 이상 포기, 공격 성향 기본값, 폴드성향 읽기, 턴카드, 다인원 감쇠',
        ALL3, 'MOTIVE / PLAN', 'PLAN', 'plan.decide_aggression', 'plan.attach_intent',
        'bluff, gamble, sk(fold_equity), read street gap, turn_card_effect, sk(multiway), n_opp',
        'bet prob', 'H/E', 'reasoning', 'ACTIVE', YES,
        'turn/river share the body; turn-card term uses the last card on river too',
        'bluff_execution_frequency', 'pure_bluff_line_selection',
        'plan.decide_aggression: if plan in (\'bluff_2street\', \'semibluff\', \'river_bluff\'): .. return _fp, \'블러프 계획 실행'),
    row('donk_suppression',
        '알려진 어그레서가 뒤에 있을 때 이니셔티브 없는 블러프 리드(동크) 억제; 드로우·프로브 예외',
        ALL3, 'REASONING', 'PLAN', 'plan.decide_aggression', 'bluff execution prob',
        'oop_vs_aggr, initiative, aggr, bluff, outs, sk(probe), opp_checked_prev', 'multiplier',
        'H', 'reasoning', 'DUPLICATED', YES,
        '"do not lead into the live aggressor" is implemented three ways: bluff plans (this '
        'suppression 0.03..0.70), pot_control (fixed 0.04), value plans (line-ownership relead '
        '0.04..0.16). Same poker question, three producers; MERGE needs behavior review',
        'lead_into_aggressor_policy', 'aggressor_relative_position',
        'plan.decide_aggression: if not initiative and _oop_a: .. p *= max(0.03, 1.0 - max(0.30'),
    row('value_bet_execution_frequency',
        '밸류 계획의 무저항 벳 확률: 공격성·도박성, 지연cbet 배수, rel<0.85면 thin_value 숙련, 리버 감산, rel 곡선',
        ALL3, 'MOTIVE / PLAN', 'PLAN', 'plan.decide_aggression', 'plan.attach_intent',
        'aggr, gamble, sk(thin_value_<street>), rel', 'bet prob', 'H', 'reasoning', 'ACTIVE', YES,
        'flop thin value maps to range_merge via street_concept', 'value_bet_execution_frequency',
        'value_line_selection',
        'plan.decide_aggression: p = 0.30 + 0.058*a .. p *= (0.35 + 0.65 * (rel/0.80) ** 0.8)'),
    # ---------------- plan.decide_size ----------------
    row('value_blocker_size_adjust',
        '밸류 계획에서 콜할 콤보를 지웠으면 작게, 접을 콤보를 지웠으면 크게(0.75~1.25배)',
        ALL3, 'CALCULATION', 'PLAN', 'plan.decide_size', 'bet size',
        'stackoff._blk_net', 'size multiplier', 'M/H', 'reasoning', 'ACTIVE', YES, 'KEEP',
        'value_blocker_size_adjust', 'continue_fold_blocker',
        'plan.decide_size: if base > 0 and plan in (\'value_3street\', \'value_2street\', \'trap\', \'thin_river\'): .. base *= max(0.75, min(1.25'),
    row('deviation_bet_size_fallback',
        '사이즈 표가 0인 계획(giveup/showdown)을 이탈해서 칠 때 쓰는 기본 사이즈',
        ALL3, 'EXECUTION FORM', 'ACTION', 'plan.decide_size', 'bet size',
        'street, deviating', 'size', 'H', 'reasoning', 'ACTIVE', YES, 'KEEP',
        'deviation_bet_size_fallback', 'planned_bet_sizing',
        'plan.decide_size: if base <= 0: .. base = {\'flop\': 0.50'),
    row('weak_hand_size_shrink',
        'rel<0.45면 사이즈 0.8배(merged 위장 블러프는 면제) — 사이즈 텔이 생기는 통로',
        ALL3, 'EXECUTION FORM', 'ACTION', 'plan.decide_size', 'bet size', 'rel, bluff_mode',
        'size multiplier', 'H', 'reasoning', 'ACTIVE', YES,
        'creates a strength tell by design; KEEP', 'weak_hand_size_shrink', 'planned_bet_sizing',
        'plan.decide_size: if rel < 0.45 and _bm != \'merged\':'),
    row('plan_size_band_clamp',
        '계획 목적별 사이즈 대역: thin_river [0.25,0.50], block [0.18,0.40]; 오버벳 경로 차단',
        'turn river', 'EXECUTION FORM', 'ACTION', 'plan.decide_size', 'bet size', 'plan',
        'clamped size', 'H', 'reasoning', 'ACTIVE', YES, 'KEEP', 'plan_size_band_clamp',
        'planned_bet_sizing',
        'plan.decide_size: if plan == \'thin_river\': .. return max(0.18, min(0.40, base))'),
    # ---------------- plan.act_with_plan ----------------
    row('response_equity_basis',
        '벳/레이즈를 맞았을 때 쓰는 equity의 출처 3단계: seat 풀 → (풀 없음) 현재 벳 이벤트로 좁힌 레인지+사이즈 습관 보정 → (레인지 없음) legacy equity_vs_betting',
        ALL3, 'CALCULATION', 'JUDGMENT', 'plan.act_with_plan', 'plan.decide_response;plan.checkraise_decision',
        'opp pools, opp_range, opp_est.sz_mean, size_info, profile bluff (legacy)', 'eq',
        'M/E', 'reasoning', 'FALLBACK', YES,
        'tier 2/3 are fallbacks; tier 3 uses the actor\'s own bluff axis as the opponent model '
        '(self-projection) and fixed callers (0.30,5)', 'response_equity_basis',
        'showdown_equity_share',
        'plan.act_with_plan: if tocall > 0: .. eq = bot.equity_vs_betting('),
    row('spr_commitment_flag',
        'SPR<1.2 이면 커밋 구간으로 보고 밸류 레이즈 확률 +0.25, 낮은 stackoff 숙련이면 절반',
        ALL3, 'CALCULATION', 'JUDGMENT', 'plan.act_with_plan', 'plan.decide_response',
        'stack, pot', 'committed bool', 'M', 'reasoning', 'ACTIVE', YES,
        'distinct from runner.effective_allin_v1 (post-action residual) and target_commit',
        'spr_commitment_flag', 'spr_ratio',
        'plan.act_with_plan: committed = spr(stack, pot) < 1.2'),
    row('raise_target_coordinate',
        '레이즈 배수를 street 총 기여 좌표 target으로 환산, call target 이하이면 콜로 강등',
        ALL3, 'EXECUTION FORM', 'ACTION', 'plan.act_with_plan', 'session.HandRun._run',
        'pot, tocall, mult, hero_contrib, stack', 'raise target', 'M', 'reasoning', 'ACTIVE', YES,
        'KEEP', 'raise_target_coordinate', 'legal_action_application',
        'plan.act_with_plan: if act == \'raise\': .. return (\'raise\', int(amt)), eq, need'),
    row('intent_chip_conversion',
        '무저항 의도(팟 비율)를 100칩 단위 금액으로 환산, 0이 되면 체크로 기록',
        ALL3, 'EXECUTION FORM', 'ACTION', 'plan.act_with_plan', 'session.HandRun._run',
        'intent size, pot, stack', 'bet amount', 'M', 'reasoning', 'ACTIVE', YES, 'KEEP',
        'intent_chip_conversion', 'aggression_intent_sampling',
        'plan.act_with_plan: it = intent_of(plan_state, street) .. return (\'bet\', int(amt)), None, None'),
    # ---------------- calldown / multiway shared ----------------
    row('players_behind_risk_premium',
        '뒤에 남은 플레이어 위험: 필요승률에 (1-need_base)*min(0.18, 0.06*n) 가산',
        'preflop flop turn river', 'CALCULATION', 'JUDGMENT',
        'icm.players_behind_required_equity_premium',
        'plan.calldown_need;preflop.multiway_reraise_decision', 'need_base, n_behind',
        'need increment', 'H', 'reasoning', 'ACTIVE', YES,
        'was DUPLICATED (identical formula in plan.calldown_need and '
        'preflop.multiway_reraise_decision); merged into one bit-identical helper',
        'icm.players_behind_required_equity_premium', 'calldown_required_share',
        'plan.calldown_need: if to_act_behind:; preflop.multiway_reraise_decision: if players_behind:'),
    # ---------------- plan.refresh ----------------
    row('value_degradation_thresholds',
        '밸류 계획 강등: rel<ctrl(0.30)·give(0.12) 문턱(폴드성향 읽기·턴카드로 이동)으로 pot_control/giveup, value3는 rel<0.62면 value2',
        'turn river', 'REASONING', 'PLAN', 'plan.refresh', 'plan.update_plan',
        'rel, made, read street gap, turn_card_effect, sk(board_texture)', 'plan', 'H/E',
        'reasoning', 'ACTIVE', YES,
        'turn_card_effect also used by decide_aggression with a different aggressor flag',
        'value_degradation_thresholds', 'plan_revision_lifecycle',
        'plan.refresh: give_thr, ctrl_thr = 0.12, 0.30 .. why.append(\'%s: 상대강도 %.2f → 3스트리트 철회'),
    row('semibluff_draw_loss_resolution',
        '턴에 아웃이 6 미만이 된 세미블러프: 완성(draw_completion_supports_value)이면 밸류, 투페어+면 쇼다운, 아니면 포기',
        'turn', 'REASONING', 'PLAN', 'plan.refresh', 'plan.update_plan', 'outs, made, rel',
        'plan', 'H', 'reasoning', 'ACTIVE', YES,
        'made>=2 showdown branch shares the paired-board ambiguity of R5c (board pair counts)',
        'semibluff_draw_loss_resolution', 'draw_completion_value_gate',
        'plan.refresh: elif old == \'semibluff\' and outs < 6 and street != \'river\': .. why.append(\'%s: 드로우 소멸(%d아웃) → 포기'),
    row('giveup_reentry_on_improvement',
        '포기 계획이 rel>=0.55 또는 made>=2가 되면 value2/쇼다운으로 복귀',
        'turn river', 'REASONING', 'PLAN', 'plan.refresh', 'plan.update_plan', 'rel, made',
        'plan', 'H', 'reasoning', 'SEMANTICALLY_OVERLOADED', YES,
        'made>=2 / made>=3 can be produced by a paired board (same known issue as R5c / '
        'HAND 63); deferred semantic-fix (behavior change)', 'giveup_reentry_on_improvement',
        'plan_revision_lifecycle',
        'plan.refresh: elif old == \'giveup\' and (rel >= 0.55 or made >= 2):'),
    row('improved_bluff_rejudgment',
        '블러프 계획이 made>=1 또는 rel>=0.75가 되면 계속 레인지 대비 eq>=0.54 & rel>=0.55일 때만 밸류, 아니면 쇼다운',
        'turn river', 'REASONING', 'PLAN', 'plan.refresh', 'plan.update_plan',
        'perceived_continue_range at value_2street size, _eq_vs, rel', 'plan', 'M/H', 'reasoning',
        'ACTIVE', YES, 'member of value_when_called_strength duplicate family (0.54 threshold)',
        'improved_bluff_rejudgment', 'value_when_called_strength',
        'plan.refresh: elif old == \'bluff_2street\' and ( .. \' 콜 레인지 상대 eq %.2f → 밸류 아님, 쇼다운\''),
    row('value2_budget_exhaustion_upgrade',
        'value_2street 예산을 다 쓴 뒤 made가 실제로 오르고 rel>=max(0.85, 이전 rel)이면 value_3street로 승격',
        'river', 'REASONING', 'PLAN', 'plan.refresh', 'plan.update_plan',
        'made, prev made, rel, prev rel, budget_left', 'plan', 'H', 'reasoning', 'ACTIVE', YES,
        'uses made increase; paired-board increases are filtered only by rel>=0.85',
        'value2_budget_exhaustion_upgrade', 'plan_revision_lifecycle',
        'plan.refresh: elif (old == \'value_2street\' .. why.append(\'%s: 예산 소진 후 강도 상승'),
    # ---------------- plan.preflop_plan ----------------
    row('preflop_decision_routing',
        '프리플랍 판단 경로 선택: 오픈 / 아이소 / cold 재레이즈 / multiway backaction / 일반 디펜스',
        PF, 'REASONING', 'JUDGMENT', 'plan.preflop_plan',
        'preflop.open_decision;preflop.iso_decision;preflop.cold_reraise_decision;preflop.multiway_reraise_decision;preflop.defend_decision',
        'aggressor_pos, n_limpers, raise_level, prior_pf, opener_allin, can_raise, cold_context, opp_ranges, pot_layers',
        'routed action', 'H', 'reasoning', 'ACTIVE', YES,
        'locked all-in seats are derived here from pot_layers for R3', 'preflop_decision_routing',
        'unopened_decision', 'plan.preflop_plan: if aggressor_pos is None and not n_limpers: .. role = \'defend\''),
    row('preflop_decision_class',
        '이번 프리플랍 판단 사건의 종류(unopened, face_first_open, cold_vs_reraise, opener/caller/reraiser backaction, multiway backaction)',
        PF, 'FACT', 'JUDGMENT', 'plan.preflop_plan', 'pf_seed.pf_decision_kind → session range story, telemetry',
        'aggressor_pos, prior_pf, raise_level, cold audit', 'decision kind', 'M', 'reasoning',
        'ACTIVE', YES, 'KEEP', 'preflop_decision_class', 'preflop_public_roles',
        'plan.preflop_plan: _prev = dict(prior_pf or {}) .. _decision_kind = \'reraiser_backaction\''),
    # ---------------- preflop.py ----------------
    row('preflop_read_width_exploit',
        '상대 프리플랍 성향 읽기로 3벳/콜 폭(tp, tot) 이동: 오픈 대면은 open_gap/f2tb/fb_gap, 재레이즈 대면은 tb_gap/tb_polar/f2fb',
        PF, 'EXPLOIT / ADAPTATION', 'JUDGMENT', 'preflop.defend_action_likelihoods',
        'mixed defend likelihoods', 'exploit read gaps, w', 'tp, tot', 'H/E', 'exploit', 'ACTIVE',
        EXPLOIT_ONLY,
        'observer-side range models call the same function without exploit (asymmetry by design)',
        'preflop_read_width_exploit', 'mixed_preflop_action_likelihood',
        'preflop.defend_action_likelihoods: if exploit and exploit.get(\'w\', 0) > 0: .. tp = max(min(tp, 0.06), tp * (1.0 - w*1.1*fbg))'),
    row('preflop_premium_slowplay_mix',
        '수동적이고 슬로플레이 취향인 사람은 프리미엄(상위 10%)을 3벳 대신 플랫하는 비중을 늘림',
        PF, 'PERSONALITY / TEMPERAMENT', 'PLAN', 'preflop.defend_action_likelihoods',
        'w_raise, w_call', 'aggression, slowplay_taste, hand pct', 'mix weights', 'H', 'reasoning',
        'ACTIVE', YES, 'KEEP', 'preflop_premium_slowplay_mix', 'mixed_preflop_action_likelihood',
        'preflop.defend_action_likelihoods: _pf_slow = 0.0 .. w_raise *= max(0.30, 1.0 - 0.70*_pf_slow)'),
    row('allin_form_fold_equity_read',
        '레이즈를 올인 형태로 칠지에 상대 3벳/4벳 폴드 성향과 4벳 성향을 반영',
        PF, 'EXPLOIT / ADAPTATION', 'PLAN', 'preflop.raise_form', 'shove vs raise form',
        'exploit f2tb/f2fb/fb_gap, w', 'shove pressure multiplier', 'H/E', 'exploit', 'ACTIVE',
        EXPLOIT_ONLY, 'KEEP', 'allin_form_fold_equity_read', 'reraise_sizing_form',
        'preflop.raise_form: if exploit and exploit.get(\'w\', 0) > 0: .. sh *= max(0.35'),
    row('short_stack_open_widening',
        'feel<0.20 (짧은 체감 스택)이면 오픈 문턱에 성향 trait shove_add를 더함',
        PF, 'PERSONALITY / TEMPERAMENT', 'JUDGMENT', 'preflop.open_decision', 'open threshold',
        'traits_of(prof).shove_add, feel', 'thr', 'H', 'reasoning', 'ACTIVE', YES,
        'trait derived from gamble temperament via persona.traits_of', 'short_stack_open_widening',
        'unopened_decision', 'preflop.open_decision: thr = min(0.9, thr + t[\'shove_add\']'),
    row('open_size_behind_read_adjust',
        '뒤 플레이어가 잘 접고 수동적일수록 오픈 사이즈를 키움(table_soft)',
        PF, 'EXPLOIT / ADAPTATION', 'PLAN', 'preflop.open_decision', 'preflop.open_size_bb',
        'behind_reads fold_gap/passive', 'table_soft 0..1', 'H/E', 'exploit', 'ACTIVE',
        EXPLOIT_ONLY, 'KEEP', 'open_size_behind_read_adjust', 'open_sizing',
        'preflop.open_decision: _soft = 0.0 .. for r in _bl)/len(_bl)))'),
    row('locked_allin_price_gate',
        '이미 올인한 상대가 있으면 내 공격은 그 상대에게 콜이므로, 올인 상대 레인지 대비 eq가 가격 need 미만이면 공격의 reason_skill 몫을 폴드로',
        PF, 'CALCULATION', 'JUDGMENT', 'preflop.multiway_reraise_decision', 'attack mass',
        'locked_keys (pot_layers.locked_allin_opponents), locked ranges, need, reason_skill',
        'attack, fold', 'M', 'reasoning', 'ACTIVE', YES,
        'inline in multiway_reraise_decision (was missing from registry); KEEP',
        'locked_allin_price_gate', 'multiway_reraise_reasoning',
        'preflop.multiway_reraise_decision: eq_locked = None .. fold += _rm'),
    row('reraise_attack_evidence',
        '재레이즈 공격 근거: eq<N-way fair share이면 reason_skill만큼 억제, 근거=max(4bet 폴드 읽기, 블러프 숙련×폴드 가능한 상대 최상단 블로커 몫)',
        PF, 'REASONING', 'JUDGMENT', 'preflop.multiway_reraise_decision;preflop.preflop_blocker_share',
        'attack mass', 'eq, fair, reason_skill, exploit f2fb, bluff skill, blocker share',
        'attack keep', 'M/H/E', 'reasoning', 'ACTIVE', YES,
        'blocker ordering uses PCT (R2 dependency)', 'reraise_attack_evidence',
        'multiway_reraise_reasoning',
        'preflop.multiway_reraise_decision: fair = 1.0 / (1.0 + len(pools)) .. fold += removed'),
    row('iso_limper_read_widening',
        '림퍼가 아이소 레이즈에 잘 접고 수동적이며 림프가 넓을수록 아이소 폭 확대(0.70~1.60배)',
        PF, 'EXPLOIT / ADAPTATION', 'JUDGMENT', 'preflop.iso_decision', 'iso threshold',
        'limper_reads w, f2iso_gap, passive, limp_gap', 'thr multiplier', 'H/E', 'exploit',
        'ACTIVE', EXPLOIT_ONLY, 'KEEP', 'iso_limper_read_widening', 'isolation_decision',
        'preflop.iso_decision: if limper_reads: .. + 0.30*max(0.0, _lg)))'),
    # ---------------- persona ----------------
    row('self_hand_overconfidence_bias',
        '자기 패 과신 편향: overpair_love(원페어 과신), draw_love(드로우 과대), sticky(매몰비용) — perceived_rel과 call_bias가 소비',
        ALL3, 'PERSONALITY / TEMPERAMENT', 'JUDGMENT', 'persona.bias',
        'plan.perceived_rel;persona.call_bias',
        'range_read, potodds, discipline, outs, gamble, looseness, tilt_prone', 'bias -1..1',
        'H', 'reasoning', 'SEMANTICALLY_OVERLOADED', 'YES (inactive at max skill: bias <= 0 clipped)',
        'overpair_love reads range_read (opponent-range reconstruction skill) as a self-assessment '
        'input; consumer clips at 0 so max-skill baseline sees 0', 'self_hand_overconfidence_bias',
        'relative_strength_perception',
        'persona.bias: name in overpair_love / draw_love / sticky'),
    row('call_threshold_bias',
        '콜 문턱 성향 편향: station(넓게 콜), bluff_fear(상대 블러프를 과소평가해 접음), hero_call(블러프로 몰아 콜)',
        ALL3, 'PERSONALITY / TEMPERAMENT', 'JUDGMENT', 'persona.bias;persona.interpret_bluff_threat_bias',
        'persona.call_bias;plan.apply_response_biases_to_call_threshold',
        'looseness, gamble, discipline, potodds, street bluffcatch, aggression, range_read, tilt_prone',
        'bias -1..1', 'H', 'reasoning', 'DUPLICATED', YES,
        'applied twice (calldown_need via call_bias and decide_response via '
        'apply_response_biases): registered as call_bias_reapplication; producer row added here',
        'call_threshold_bias', 'call_bias_reapplication',
        'persona.bias: station / bluff_fear / hero_call'),
    row('preflop_temperament_direction',
        '루즈함·공격성(0~10)을 프리플랍 폭 이동 방향(-1~+1)으로 변환',
        PF, 'PERSONALITY / TEMPERAMENT', 'JUDGMENT', 'persona.preflop_temper_direction',
        'persona.open_pct;preflop.defend_thresholds', 'temperament scores', 'direction', 'H',
        'reasoning', 'ACTIVE', YES, 'OPT-IN V3 span 5.0 vs legacy 4.0',
        'preflop_temperament_direction', 'rfi_personality_deviation',
        'persona.preflop_temper_direction'),
    row('concept_skill_gate',
        '개념 숙련도를 0..1 실행 게이트로 변환(0.5 이하 floor)',
        'all', 'KNOWLEDGE', 'JUDGMENT', 'persona.gate', 'preflop.calloff_layer_judgment',
        'sk(concept), floor', 'gate prob', 'H', 'reasoning', 'ACTIVE', YES, 'KEEP',
        'concept_skill_gate', 'persona_population_generation', 'persona.gate'),
    row('street_concept_alias',
        '같은 행동 질문을 스트리트별 숙련 개념으로 매핑(cbet→barrel, checkraise_flop/late, bluffcatch_early/river, thin_value flop=range_merge)',
        'flop turn river', 'KNOWLEDGE', 'JUDGMENT', 'persona.street_concept',
        'plan.*;persona.bias', 'base concept, street', 'concept name', 'H', 'reasoning',
        'SEMANTICALLY_OVERLOADED', YES,
        'this table IS the street-split policy: checkraise_late and bluffcatch_early still share '
        'two streets', 'street_concept_alias', 'positional', 'persona.street_concept'),
    row('legacy_trait_adapter',
        '기질 벡터에서 구형 trait(limp, iso, threebet, call, shove_add) 파생',
        PF, 'PERSONALITY / TEMPERAMENT', 'JUDGMENT', 'persona.traits_of;preflop._tr',
        'preflop.open_decision;preflop.iso_decision;preflop.limp_p;ranges.preflop_range',
        'looseness, aggression, gamble, discipline', 'trait dict', 'H', 'reasoning', 'ACTIVE',
        YES, 'adapter keeps archetype-era trait semantics alive for concept profiles',
        'legacy_trait_adapter', 'legacy_arch_types', 'persona.traits_of'),
    row('read_polarity_signal',
        '관측 3벳 빈도 중 밸류 기준(0.055)을 넘는 몫 = 폴라라이즈된 3벳 비율',
        PF, 'PERCEPTION', 'JUDGMENT', 'persona._polar',
        'persona.read_opponent tb_polar;session preflop range polar', 'observed rate, value base',
        'polarity 0..1', 'H', 'exploit', 'ACTIVE', EXPLOIT_ONLY, 'KEEP', 'read_polarity_signal',
        'exploit_read_permission', 'persona._polar'),
    # ---------------- session / ranges / bot ----------------
    row('forced_bet_posting',
        '블라인드와 BB 앤티 징수, 징수로 올인된 좌석 표시',
        PF, 'FACT', 'ACTION', 'session.HandRun._run', 'runner.Round', 'stacks, sb, bb, ante',
        'contrib, ante_pot, allin', 'M', 'reasoning', 'ACTIVE', YES, 'KEEP', 'forced_bet_posting',
        'legal_action_application', 'session.HandRun._run: if sb_s: .. rnd.current = h.bb'),
    row('multiway_representative_union_range',
        '다인원에서 계획/응답용 단일 opp_range를 seat 레인지 합집합으로 만듦(빈 경우 ALL 폴백 + 감사 기록)',
        ALL3, 'RANGE', 'JUDGMENT', 'session.HandRun._run', 'plan.make_plan/refresh/act_with_plan opp_range',
        'opp_ranges by seat', 'opp_r', 'M', 'reasoning', 'SEMANTICALLY_OVERLOADED', YES,
        'equity paths use seat pools (joint), but several single-range consumers (perceived '
        'continue range in overbet/raise gates, blocker_score) still read the union',
        'multiway_representative_union_range', 'weighted_range_transform',
        'session.HandRun._run: opp_r = R.range_union(*['),
    row('primary_opponent_selection',
        '주 상대 = 살아 있는 공격자, 없으면 가장 깊은 스택; 계획/갱신/실행의 opp_est·스택 기준',
        ALL3, 'REASONING', 'JUDGMENT', 'session.HandRun._run',
        'plan.make_plan opp_est/opp_stack_bb;plan.act_with_plan', 'aggressor, live stacks',
        '_main seat', 'H', 'reasoning', 'ACTIVE', YES,
        'differs from plan.select_field_opponent (purpose-specific); two selectors coexist',
        'primary_opponent_selection', 'opponent_fold_constraint',
        'session.HandRun._run: _main = aggressor if (aggressor is not None and aggressor != s'),
    row('preflop_range_action_label',
        '관측된 프리플랍 라인을 레인지 라벨로 변환(open/limp/call/3bet/iso, BB iso, 올인 위 레이즈=open)',
        PF, 'PERCEPTION', 'JUDGMENT', 'session.HandRun._pf_range_action;session._preflop_public_action_context',
        'session._preflop_story_range', 'pf seed/public action', 'range action label', 'H',
        'reasoning', 'ACTIVE', YES, 'two producers (bot record vs public story) kept aligned by tests',
        'preflop_range_action_label', 'preflop_range_reconstruction',
        'session.HandRun._pf_range_action'),
    row('range_ordering_strength',
        '레인지 분할(bet/call/continue/check)용 콤보 정렬 키: 현재 쇼다운 카테고리 + min(1.8, outs*0.11) 드로우 보너스',
        ALL3, 'CALCULATION', 'JUDGMENT', 'bot._sd_strength;ranges._ranked',
        'ranges._bet_range;_continue_range;_call_range;_check_range;bot.pick_bluffs',
        'combo, board', 'sortable strength tuple', 'M/H', 'reasoning', 'ACTIVE', YES,
        'single ordering serves value, continue and bluff partitions (draw bonus 0.11/out is a '
        'heuristic); river/no-board use pure made', 'range_ordering_strength',
        'postflop_action_posterior', 'bot._sd_strength'),
    row('checkraise_value_probability_floor',
        '밸류 계획 체크레이즈 확률 하한: rel 0.72~0.94 구간에서 숙련·공격성으로 바닥값',
        ALL3, 'MOTIVE / PLAN', 'PLAN', 'plan._checkraise_value_floor_probability',
        'plan.checkraise_draw_street_probability;plan.checkraise_river_probability',
        'plan probability, rel, skill, aggression', 'probability', 'H', 'reasoning', 'ACTIVE',
        YES, 'shared by all streets (same question)', 'checkraise_value_probability_floor',
        'checkraise_flop_decision', 'plan._checkraise_value_floor_probability'),
    row('continuation_bet_frequency_core',
        'cbet/턴 배럴/리버 배럴 공통 본문: 스트리트 기본값, 다인원, 텍스처, rel, 레인지 우위, 폴드 성향',
        ALL3, 'MOTIVE / PLAN', 'PLAN', 'plan._continuation_frequency',
        'plan.cbet_flop_frequency;plan.barrel_turn_frequency;plan.barrel_river_frequency',
        'street capability, n_opp, board, rel, range_adv, read', 'frequency', 'H/E',
        'reasoning', 'ACTIVE', YES, 'street base table distinct; body shared (same question)',
        'continuation_bet_frequency_core', 'flop_cbet_plan', 'plan._continuation_frequency'),
    row('overbet_selection_core',
        '오버벳 선택 공통 본문(턴/리버): overbet 숙련 × 넛우위 × 양극화 × 공격성, 리버 ×1.35, 블러프 ×0.65, 폴드성향 읽기; 크기는 넛우위로',
        'turn river', 'MOTIVE / PLAN', 'PLAN', 'plan.overbet_frac', 'plan.decide_size',
        'sk(overbet), nut_adv, rel (value: vs continue range), aggr, read', 'size or None', 'H/E',
        'reasoning', 'ACTIVE', YES,
        'turn_overbet/river_overbet rows are street views of this one body (river multiplier only)',
        'overbet_selection_core', 'turn_overbet', 'plan.overbet_frac'),
    row('opponent_unconsumed_estimates',
        '관측·추정은 되지만 어떤 판단도 소비하지 않는 상대 통계: 포스트플랍 fold-to-raise(전체/스트리트별), 프리플랍 backraise·cold re-raise 반응·squeeze 대면 콜 후 폴드, limp-raise 표본',
        'preflop flop turn river', 'PERCEPTION', 'JUDGMENT', 'reads.Book.observe_postflop;reads.Book.observe_cold_reraise;reads.Book.observe_backraise;reads.estimate',
        'none (checkraise_decision explicitly declines to use fold-to-bet as a fold-to-raise proxy)',
        'Book counters', 'est fold_to_raise, ftr_<street>, pf_backraise, pf_cold_reraise_*, pf_fold_after_call_squeeze',
        'E', 'exploit', 'SHADOW', 'NO',
        'observation exists without an application path: bluff check-raise / bluff re-raise reads and '
        'cold-4bet/squeeze exploits have evidence but no consumer (wiring = behavior change, later phase)',
        'opponent_unconsumed_estimates', 'opponent_estimation', 'reads.estimate: est[fold_to_raise]..'),
    row('dead_strategy_tables',
        '프로덕션에서 읽히지 않는 전략 상수 표: preflop.DEF_POS_MULT, preflop.DEPTH_OPEN_MULT, persona.OPEN_ELASTICITY, plan.PLANS',
        'preflop flop turn river', 'KNOWLEDGE', 'JUDGMENT', 'preflop.DEF_POS_MULT;preflop.DEPTH_OPEN_MULT;persona.OPEN_ELASTICITY;plan.PLANS',
        'none', '-', '-', 'H', 'reasoning', 'DEAD', 'NO',
        'REMOVE_COMPAT candidates (DEF_POS_MULT/OPENER_MULT copies also live in legacy/players.py)',
        'dead_strategy_tables', 'legacy_arch_types', 'module constants'),
    row('opener_position_attack_table',
        'OPENER_MULT: 오프너 포지션별로 필드가 그 오픈을 공격(리쇼브)하는 상대 폭',
        'preflop', 'KNOWLEDGE', 'JUDGMENT', 'preflop.OPENER_MULT',
        'preflop.reshove_range (pos_mult);preflop.open_form (position shove depth, audit9 R4)',
        'opener position', 'multiplier', 'H', 'reasoning', 'SEMANTICALLY_OVERLOADED', YES,
        'same table answers two questions: how wide the field reshoves vs this opener (reshove_range) '
        'and how many/strong players remain behind an opener when deciding an open-shove (open_form '
        '2.6/OPENER_MULT depth). SPLIT candidate: behind-player depth from actual seats behind '
        '(behavior change, deferred)', 'opener_position_attack_table', 'reshove_opportunity',
        'preflop.OPENER_MULT'),
    row('iso_sizing',
        '아이소 레이즈 크기 = 3.0 + 림퍼 수 (bb)',
        PF, 'EXECUTION FORM', 'ACTION', 'preflop.iso_decision', 'session apply', 'n_limpers',
        'size bb', 'H', 'reasoning', 'ACTIVE', YES, 'fixed; open_size_bb skill not used',
        'iso_sizing', 'isolation_decision', 'preflop.iso_decision: return (\'raise\', 3.0 + n_limpers)'),
]

ROW_UPDATES = {
    'called_aggression_ownership': {
        'poker_meaning': '직전 스트리트에 상대의 공격을 내가 콜했고 그 공격자가 뒤에 살아 있으면 라인은 그 사람 것; '
                         '플랍에서는 직전 스트리트가 프리플랍이므로 이니셔티브 없는 OOP + 살아 있는 프리플랍 어그레서가 같은 사실이다',
        'street': 'flop turn river',
        'duplicate_overload': 'earlier registry text inverted the meaning ("내 공격이 콜받았나"); '
                              'code checks hero CALLED opponent aggression. Flop consumer added in batch 1 '
                              '(R5a-ext); same question as donk_suppression and pot_control lead ban '
                              '(see lead_into_aggressor_policy)',
        'current_function': 'plan.line_owned_by_live_aggressor;plan._called_prior_street_aggression',
    },
    'multiway_reraise_reasoning': {
        'duplicate_overload': 'KEEP seat identity; independent 4bet prior absent; sub-semantics '
                              'locked_allin_price_gate, reraise_attack_evidence, players_behind_risk_premium '
                              'registered separately (re-audit)',
    },
    'defend_width_prior': {
        'duplicate_overload': 'calibrated MTT8-ante defend table applies only when seats==8 and ante; '
                              '9-max formats (standard/main/lowbuyin) use the uncalibrated legacy formula '
                              '(knowledge coverage gap, see KNOWLEDGE_COVERAGE_MATRIX)',
    },
}

# spans: (concept, module, function, from-substring, to-substring)
S = []


def sp(concept, module, func, a=None, b=None):
    S.append({'concept': concept, 'module': module, 'func': func, 'from': a, 'to': b})


NS = '@nonsemantic:'

# ---- plan.make_plan ----
sp('opponent_fold_constraint', 'plan', 'make_plan', '_field_fold = (', "if int(n_opp or 1) > 1 else opp_stack_bb)")
sp('perceived_board_danger', 'plan', 'make_plan', 'dang = bot.board_danger(board)', "dang *= min(1.0, PS.sk(profile,'board_texture')/6.0)")
sp('strong_support_blocker', 'plan', 'make_plan', 'blk_true = R.blocker_score(hero, opp_range, board)', 'blk = blk_true * _bg')
sp('continue_fold_blocker', 'plan', 'make_plan', "_typ = {'flop': 0.60", 'blk_net = _blk_raw * _bg')
sp('perceived_spr', 'plan', 'make_plan', 's_true = spr(stack, pot)', 's = s*_sa + 5.0*(1.0 - _sa)')
sp('potcontrol_disposition', 'plan', 'make_plan', "pc = max(0.0, min(1.0, (profile['icm']")
sp('target_investment_fraction', 'plan', 'make_plan', '_opp_eff = None', 'opp_eff=_opp_eff)')
sp('value_when_called_strength', 'plan', 'make_plan', '_commit_rel = rel', "_so['commit_rel'] = round(float(_commit_rel), 3)")
sp('multiway_value_threshold_shift', 'plan', 'make_plan', 'mw = max(0, n_opp - 1)', 'pcz = 0.50 + 0.06*mw')
sp('read_value_threshold_shift', 'plan', 'make_plan', "if rd['w'] > 0:", 'pcz += wq * 0.30 * sg')
sp('bluff_evidence_composite', 'plan', 'make_plan', "bluff_ok = (profile['bluff']/10.0)", "bluff_ok *= max(0.25, 1.0 + rd['w']")
sp('relative_strength_value_threshold_shift', 'plan', 'make_plan', 'if rel <= 0.45:', 'v2 += 0.08 * _pen')
sp('showdown_value_predicate', 'plan', 'make_plan', '_sd_eq = eq_cur if eq_cur is not None else eq')
sp('value_line_selection', 'plan', 'make_plan', 'if eq >= v3:', "'중간 밸류이나 3스트리트 유지")
sp('hero_made_contribution', 'plan', 'make_plan', 'made = bot.made_strength(hero, board) if board else 0')
sp('relative_strength_perception', 'plan', 'make_plan', 'rel = perceived_rel(profile, rel_true, hero, board,', 'bot.made_strength(hero, board) if board else 0)')
sp('trap_induction', 'plan', 'make_plan', 'p_trap, trap_why = trap_judgment(', "_goal, _mode = 'value_3street', 'trap'")
sp('deep_one_pair_caution', 'plan', 'make_plan', '_vulnerable_deep = (', 'if made <= 1 else 0.0)')
sp('blockbet_motive', 'plan', 'make_plan', 'elif eq >= pcz:', "plan = 'block'; why.append('OOP 중간강도")
sp('potcontrol_motive', 'plan', 'make_plan', '_mg = sk(\'range_merge\')', "plan = 'pot_control'; why.append('중간강도(eq %.2f, rel %.2f) → 팟 컨트롤'")
sp('medium_strength_merge_value', 'plan', 'make_plan', "elif rel >= max(0.28, 0.52 - 0.080*_mg) and made >= 1:", "why.append('중간강도(eq %.2f, rel %.2f, 머징")
sp('showdown_value_predicate', 'plan', 'make_plan', '_sd_here = ', "% (rel, made, plan))")
sp('semibluff_line_selection', 'plan', 'make_plan', 'elif outs >= 8 and to_act_behind <= 1', "% (_fe*100, _bluff_mul*100))")
sp('bluff_sizing_camouflage', 'plan', 'make_plan', '_fe = 0.5', "_fe = float(_plan_opp_est['fold'])")
sp('pure_bluff_line_selection', 'plan', 'make_plan', "elif (_sd_eq < 0.42 and sk('bluff') >= 1", "why.append('블러프 세부: %s — %s' % (_bm, _bwhy))")
sp('showdown_value_predicate', 'plan', 'make_plan', 'has_sd = has_showdown_value(', "plan = 'giveup'; why.append('쇼다운 가치 없고")
sp('potcontrol_motive', 'plan', 'make_plan', "if has_sd and sk('potcontrol') >= 1 and rng.random() < 0.72:")
sp(NS + 'plan-state provenance/logging record (no decision)', 'plan', 'make_plan', "st = {'plan': plan, 'street_made': street", "'opp_est': _plan_opp_est, 'opp_stack_bb': _plan_opp_stack_bb,")

# ---- plan.decide_response ----
sp('response_plan', 'plan', 'decide_response', "rel_ps = plan_state.get('rel', 0.5)")
sp('layer_investment_ev', 'plan', 'decide_response', '_layer_call = (call_eq is not None and call_need is not None)', '_cf_need = float(call_need) if _layer_call else need')
sp('monster_made_hand_raise', 'plan', 'decide_response', 'if made_now >= 5 and eq > need + 0.10:', "'넛급이나 콜 선택'")
sp('value_line_selection', 'plan', 'decide_response', "if plan in ('value_3street', 'value_2street', 'trap') and eq > need + 0.15:", "so = PS.sk(profile, 'stackoff')/10.0 if has_c else 0.5")
sp('value_raise_sizing_from_commit', 'plan', 'decide_response', "_so = plan_state.get('stackoff') or {}", 'mult = max(0.75, min(1.6, 0.75 + 0.85*gap))')
sp('value_raise_qualification', 'plan', 'decide_response', '_fair_share = 1.0 / max(2.0, float(n_opp) + 1.0)', "if _vr_eq_cont is not None else 'n/a')))")
sp('value_raise_frequency', 'plan', 'decide_response', 'p = 0.20 + 0.55*rr + (0.25 if committed else 0.0)', "'밸류이나 콜 선택(상대가 팟을 키워줌)'")
sp('bluff_reraise_frequency', 'plan', 'decide_response', "if allow_raise and has_c and eq < need - 0.05 and plan in ('bluff_2street', 'semibluff', 'river_bluff'):", "% (blr, _g_bl.get('ev')))")
sp('semibluff_raise_frequency', 'plan', 'decide_response', "if plan == 'semibluff' and plan_state.get('outs', 0) >= 8 and street != 'river':", "% (_p_sb*100, _g_sb.get('ev')))")
sp('implied_odds_adjustment', 'plan', 'decide_response', 'if stack > pot:', '_cf_need = max(0.02, _cf_need - implied)')
sp('price_overrides_giveup_plan', 'plan', 'decide_response', "act = 'call' if _use_eq >= _use_need else 'fold'", "% (' + layer call EV' if _layer_call else '', _gate_note))")
sp('giveup_deviation_raise', 'plan', 'decide_response', "if plan == 'giveup' and has_c and eq < need - 0.05:", "% _g_dev.get('ev'))")
sp('price_overrides_giveup_plan', 'plan', 'decide_response', "if plan in ('bluff_2street', 'giveup', 'river_bluff'):", "% (' [layer]' if _layer_call else ''))")
sp('call_bias_reapplication', 'plan', 'decide_response', 'need_seen = _cf_need if _layer_call else need', "% (_eq_seen, need_seen, need, ' [layer-call]' if _layer_call else ''))")

# ---- plan.decide_aggression ----
sp('turn_delayed_cbet', 'plan', 'decide_aggression', "if (street == 'turn' and initiative and has_c", '_dc_boost = 1.0')
sp('giveup_initiative_stab_deviation', 'plan', 'decide_aggression', "if plan in ('giveup', 'showdown'):", "return max(0.0, min(0.9, cf)), 'DEVIATE:포기 계획이나")
sp('bluff_execution_frequency', 'plan', 'decide_aggression', "if plan in ('bluff_2street', 'semibluff', 'river_bluff'):", "return _fp, '블러프 계획 실행(%.0f%%)' % (_fp*100)")
sp('turn_card_range_shift', 'plan', 'decide_aggression', "if street in ('turn', 'river') and len(board) >= 4 and has_c:", 'p *= max(0.35, min(1.70, 1.0 + 0.75*_tce*_bt))')
sp('donk_suppression', 'plan', 'decide_aggression', '_oop_a = (oop_vs_aggr is True)', 'p *= max(0.03, 1.0 - max(0.30, min(0.97, supp)))')
sp('probe_after_checkthrough', 'plan', 'decide_aggression', "if has_c and (plan_state or {}).get('opp_checked_prev'):", "supp *= max(0.25, 1.0 - 0.085*PS.sk(profile, 'probe'))")
sp('blockbet', 'plan', 'decide_aggression', "if plan == 'block':", "return max(0.15, min(0.92, _bb))")
sp('potcontrol_bet_propensity', 'plan', 'decide_aggression', "if plan == 'pot_control':", "return max(0.05, min(0.6, 0.18 + 0.035*a))")
sp('value_bet_execution_frequency', 'plan', 'decide_aggression', 'p = 0.30 + 0.058*a + 0.018*profile.get', "p *= (0.35 + 0.65 * (rel/0.80) ** 0.8)")
sp('called_aggression_ownership', 'plan', 'decide_aggression', 'if line_owned_by_live_aggressor(', "' (재리드 %.0f%%)' % (_fp*100))")
sp('called_aggression_ownership', 'plan', 'line_owned_by_live_aggressor')
sp('showdown_value_predicate', 'plan', 'has_showdown_value')
sp('players_behind_risk_premium', 'icm', 'players_behind_required_equity_premium')

# ---- plan.decide_size ----
sp('planned_bet_sizing', 'plan', 'decide_size', "base = SIZING.get(plan, {}).get(street, 0.0)")
sp('bluff_sizing_camouflage', 'plan', 'decide_size', "_bm = (plan_state or {}).get('bluff_mode')", "base *= float((plan_state or {}).get('bluff_mul') or 1.0)")
sp('bet_budget', 'plan', 'decide_size', 'if not deviating:', 'return 0.0')
sp('street_texture_sizing', 'plan', 'decide_size', 'if base > 0:', "base = base*(1.0 - 0.45*_bt2) + _tf*(0.45*_bt2)")
sp('value_blocker_size_adjust', 'plan', 'decide_size', "if base > 0 and plan in ('value_3street', 'value_2street', 'trap', 'thin_river'):", 'base *= max(0.75, min(1.25, 1.0 - 2.0*_bn))')
sp('equity_denial_sizing', 'plan', 'decide_size', "if base > 0 and profile.get('concepts') and street != 'river':", 'base *= 1.0 + 0.55*_ed*_dg')
sp('stackoff_spread_horizon', 'plan', 'decide_size', "if base > 0 and stackoff and stackoff.get('ok') and plan == 'value_3street':", 'base = 0.35*base + 0.65*float(_sf)')
sp('deviation_bet_size_fallback', 'plan', 'decide_size', 'if base <= 0:', "base = {'flop': 0.50, 'turn': 0.55, 'river': 0.60}.get(street, 0.50)")
sp('street_texture_sizing', 'plan', 'decide_size', "if profile.get('concepts'):", 'base = 0.45*base + 0.55*tex')
sp('planned_bet_sizing', 'plan', 'decide_size', "base *= (0.85 + 0.05*profile.get('aggr', 5))")
sp('weak_hand_size_shrink', 'plan', 'decide_size', "if rel < 0.45 and _bm != 'merged':", 'base *= 0.80')
sp('plan_size_band_clamp', 'plan', 'decide_size', "if plan == 'thin_river':", 'return max(0.18, min(0.40, base))')

# ---- plan.overbet_frac ----
sp('value_when_called_strength', 'plan', 'overbet_frac', 'if value_line and opp_range and board:', 'rel = min(rel, relative_strength(hero, board, _ob_cr))')
sp('river_overbet', 'plan', 'overbet_frac', "if street == 'river': p *= 1.35")
sp('exploit_read_permission', 'plan', 'overbet_frac', 'if opp_est:', "p = PS.blend(p, p*max(0.25, mult), _rdo['w'])")

# ---- plan.act_with_plan ----
sp('perceived_icm_pressure', 'plan', 'act_with_plan', "if profile.get('concepts') and bf and bf > 1.0:", 'bf = PS.icm_bf(profile, bf)')
sp('spr_commitment_flag', 'plan', 'act_with_plan', 'committed = spr(stack, pot) < 1.2')
sp('response_equity_basis', 'plan', 'act_with_plan', 'if tocall > 0:', 'street, sims=600, seed=seed)')
sp('opponent_sizing_normalization', 'plan', 'act_with_plan', "if _rdo['w'] > 0 and opp_est and opp_est.get('sz_mean'):", "sz = sz*(1.0 - _pull) + float(opp_est['sz_mean'])*_pull")
sp('calldown_required_share', 'plan', 'act_with_plan', '_objective_be = (', "_call_eq = float(call_value.get('effective_equity'))")
sp('checkraise_flop_decision', 'plan', 'act_with_plan', '_is_checkraise_spot = (', "return ('raise', _amt), eq, need")
sp('nonvalue_raise_ev_gate', 'plan', 'act_with_plan', "if (plan in ('bluff_2street', 'semibluff', 'giveup', 'river_bluff')", 'target=_amt)')
sp('response_plan', 'plan', 'act_with_plan', '_direct_raise = bool(can_raise and not _is_checkraise_spot)', 'eq=round(eq, 3), why=why, plan=plan, tocall=tocall, pot=pot)')
sp('raise_target_coordinate', 'plan', 'act_with_plan', "if act == 'raise':", "return ('raise', int(amt)), eq, need")
sp('response_plan', 'plan', 'act_with_plan', "if act == 'call':", "return ('fold', 0), eq, need")
sp('hero_made_contribution', 'plan', 'act_with_plan', 'made_now = bot.made_strength(hero, board) if board else 0')
sp('intent_chip_conversion', 'plan', 'act_with_plan', 'it = intent_of(plan_state, street)', "return ('bet', int(amt)), None, None")

# ---- plan.calldown_need ----
sp('opponent_sizing_normalization', 'plan', 'calldown_need', "if profile.get('concepts') and board:", '_tocall_seen = float(tocall) * (_sz_seen / _sz_true)')
sp('calculation_error', 'plan', 'calldown_need', 'nz = PS.calc_noise(profile', 'call_need = call_need_true * nz')
sp('players_behind_risk_premium', 'plan', 'calldown_need', 'if to_act_behind:', 'call_need += ')
sp('call_bias_reapplication', 'plan', 'calldown_need', '_cbias = PS.call_bias(profile', 'call_need *= _cbias')

# ---- plan.refresh ----
sp('turn_delayed_cbet', 'plan', 'refresh', "if street == 'turn':", "st['flop_checked'] = (_fi.get('act') in (None, 'check'))")
sp('value_degradation_thresholds', 'plan', 'refresh', 'give_thr, ctrl_thr = 0.12, 0.30', "why.append('%s: 상대강도 %.2f → 3스트리트 철회")
sp('semibluff_draw_loss_resolution', 'plan', 'refresh', "elif old == 'semibluff' and outs < 6 and street != 'river':", "why.append('%s: 드로우 소멸(%d아웃) → 포기'")
sp('draw_completion_value_gate', 'plan', 'refresh', 'if draw_completion_supports_value(made, rel):', "why.append('%s: 드로우 완성(made %d) → 밸류 전환'")
sp('trap_release_no_bite', 'plan', 'refresh', "elif old == 'trap' and st.get('_no_bite', 0) >= 1:", "why.append('%s: 상대가 벳하지 않음 → 함정 해제")
sp('giveup_reentry_on_improvement', 'plan', 'refresh', "elif old == 'giveup' and (rel >= 0.55 or made >= 2):", "% (street, rel, made, st['plan']))")
sp('strength_improvement_promotion', 'plan', 'refresh', "elif old in ('pot_control', 'block', 'showdown') and (", "why.append('%s: 강도 상승(rel %.2f, made %d) → 밸류 전환'")
sp('improved_bluff_rejudgment', 'plan', 'refresh', "elif old == 'bluff_2street' and (", "% (street, made, rel, float(_call_eq)))")
sp('value2_budget_exhaustion_upgrade', 'plan', 'refresh', "elif (old == 'value_2street'", "why.append('%s: 예산 소진 후 강도 상승")

# ---- plan.preflop_plan ----
sp('layer_calloff_judgment', 'plan', 'preflop_plan', '_calloff_compare = None', "'strategy_consumer': bool(_layer_j.get('gate_pass')),")
sp('preflop_decision_class', 'plan', 'preflop_plan', '_prev = dict(prior_pf or {})', "_decision_kind = 'reraiser_backaction'")
sp('preflop_role_memory', 'plan', 'preflop_plan', 'seed_info = {', "'money_open': dict(money_open or {}) if role == 'open' else None,")
sp('human_planned_size_shape', 'plan', 'preflop_plan', '_pf_shape = None', "seed_info['pf_size_shape'] = _pf_shape")

# ---- other plan functions ----
sp('bluff_sizing_camouflage', 'plan', 'bluff_mode')
sp('continuation_bet_frequency_core', 'plan', '_continuation_frequency')
sp('trap_induction', 'plan', 'opp_bet_prob')
sp('opponent_trap_target', 'plan', 'select_field_opponent', "if purpose == 'bet_probability':", 'score=opp_bet_prob(est,w,street)')
sp('opponent_fold_constraint', 'plan', 'select_field_opponent', 'else:', "score=float(rd.get('w',0.0))*float(PS.street_gap(rd,street) or 0.0)")
sp('call_bias_reapplication', 'plan', 'apply_response_biases_to_call_threshold')
sp('checkraise_value_probability_floor', 'plan', '_checkraise_value_floor_probability')
sp('checkraise_river_decision', 'plan', 'checkraise_decision', "if street == 'river':")
sp('checkraise_flop_decision', 'plan', 'checkraise_draw_street_probability')
sp('river_thin_value', 'plan', 'river_fix')
sp('river_thin_value', 'plan', 'river_value_reassessment')
sp('value_when_called_strength', 'plan', 'river_value_reassessment', 'if int(n_opp or 1) > 1 and isinstance(opp_ranges, dict):', "'리버: 전체 rel %.2f지만 콜 레인지 상대 eq %.2f < 0.50'")
sp('plan_revision_lifecycle', 'plan', 'update_plan')
sp('pure_bluff_line_selection', 'plan', '_blocker_score_bluff_factor')
sp('pure_bluff_line_selection', 'plan', '_blocker_net_bluff_factor')

# ---- preflop.py ----
sp('legacy_calloff_threshold', 'preflop', 'legacy_calloff_likelihoods')  # stage9 B1
sp('preflop_read_width_exploit', 'preflop', 'apply_defend_exploit_evidence')  # stage9 B1
sp('reshove_opportunity', 'preflop', 'hot_reshove_probability')  # stage9 B1
sp('mixed_preflop_action_likelihood', 'preflop', 'defend_action_likelihoods', 'a = prof_aggr(prof)', "'hand_pct': r,")
sp('preflop_premium_slowplay_mix', 'preflop', 'preflop_slowplay_share')  # stage9 B1
sp('preflop_premium_slowplay_mix', 'preflop', 'defend_action_likelihoods', '_pf_slow = preflop_slowplay_share(prof, r, a)', 'w_raise *= max(0.30, 1.0 - 0.70*_pf_slow)')
sp('mixed_preflop_action_likelihood', 'preflop', 'attack_candidate_weight')  # stage9 B1
sp('allin_form_fold_equity_read', 'preflop', 'shove_form_pressure', "if exploit and exploit.get('w', 0) > 0:", "sh *= max(0.35, 1.0 - w*0.5*max(0.0, exploit.get('fb_gap', 0.0)))")  # stage9 B1
sp('accumulation_variance_drive', 'preflop', 'open_decision', 'vs = (PS.variance_seek(', "if prof.get('concepts') else 0.0)")
sp('short_stack_open_widening', 'preflop', 'open_entry_threshold', "return min(0.9, thr + traits['shove_add']")  # stage9 B1
sp('money_open_range_modifier', 'preflop', 'apply_money_open_threshold')  # stage9 B1
sp('limp_entry_motive', 'preflop', 'open_decision', '_base_limp_p = limp_p(prof, feel, r, pos, t)', "money_open['sb_limp_currently_blocked'] = False")
sp('open_size_behind_read_adjust', 'preflop', 'open_decision', '_soft = 0.0', 'for r in _bl)/len(_bl)))')
sp('players_behind_risk_premium', 'preflop', 'multiway_reraise_decision', 'if players_behind:', 'need += ')
sp('locked_allin_price_gate', 'preflop', 'multiway_reraise_decision', 'eq_locked = None', 'fold += _rm')
sp('reraise_attack_evidence', 'preflop', 'multiway_reraise_decision', 'fair = 1.0 / (1.0 + len(pools))', 'fold += removed')
sp('reraise_sizing_form', 'preflop', 'multiway_reraise_decision', 'x = rng.random()', "action = ('fold', 0)")
sp(NS + 'decision audit record (provenance only)', 'preflop', 'multiway_reraise_decision', "return action[0], action[1], {", "'selected_action': action[0],")
sp('iso_limper_read_widening', 'preflop', 'iso_decision', 'if limper_reads:', '+ 0.30*max(0.0, _lg)))')
sp('iso_sizing', 'preflop', 'iso_decision', 'if r <= thr:', "return ('raise', 3.0 + n_limpers)")
sp('limp_entry_motive', 'preflop', 'iso_decision', '_lp = limp_p(prof, feel, r, pos, t)', "return ('limp', 1.0)")
sp('rfi_width_prior', 'preflop', '_open')
sp('legacy_trait_adapter', 'preflop', '_tr_loose')
sp('multiway_reraise_reasoning', 'preflop', 'multiway_evidence_application_capacity')
sp('multiway_reraise_reasoning', 'preflop', 'apply_multiway_call_evidence')

# ---- persona ----
sp('call_threshold_bias', 'persona', 'bias', "if name == 'station':", 'T(\'discipline\')) - 0.30*(S(\'potodds\') - 5))')
sp('call_threshold_bias', 'persona', 'bias', "if name == 'bluff_fear':", "return interpret_bluff_threat_bias(S(_bc), T('aggression'), S('range_read'))")
sp('call_threshold_bias', 'persona', 'bias', "if name == 'hero_call':", "+ 0.20*T('tilt_prone'))")
sp('call_threshold_bias', 'persona', 'interpret_bluff_threat_bias')
sp('preflop_temperament_direction', 'persona', 'preflop_temper_direction')
sp('concept_skill_gate', 'persona', 'gate')
sp('street_concept_alias', 'persona', 'street_concept')
sp('legacy_trait_adapter', 'persona', 'traits_of')
sp('read_polarity_signal', 'persona', '_polar')
sp('exploit_read_permission', 'persona', 'blend')
sp('chart_memory_accuracy', 'persona', '_pos_equiv')
sp('exploit_read_permission', 'persona', 'interpret_opponent_action_signals')
sp('persona_population_generation', 'persona', 'make_player')

# ---- session ----
sp('forced_bet_posting', 'session', 'HandRun._run', 'if sb_s:', 'rnd.current = h.bb; rnd.min_raise = h.bb')
sp('opponent_concept_inference', 'session', 'HandRun._run', '_opp_est_pf = (RD.perceived_profile(', 'if aggressor is not None and aggressor != s else None)')
sp('money_jump_seat_topology', 'session', 'HandRun._run', "'kind': ('vs_raise' if aggressor is not None else", "'vs_limp' if limpers else 'unopened'),")
sp('preflop_decision_routing', 'session', 'HandRun._run', '_behind = [rnd.stacks[x]/h.bb for x in rnd.order', 'cold_decision_seed=self._dseed(')
sp('preflop_role_memory', 'session', 'HandRun._run', "if a == 'fold':", "elif a == 'shove':")
sp('preflop_public_roles', 'session', 'HandRun._run', "if a_ == 'call' and not m.get('raised'):", "if m.get('raised'):")
sp('forced_bet_posting', 'session', 'HandRun._run', 'if bb_s: contrib[bb_s] = contrib.get(bb_s, 0)')
sp('initiative_owner', 'session', 'HandRun._run', 'if r2.action_meta and r2.action_meta[-1].get(\'raised\'):')
sp('aggressor_relative_position', 'session', 'HandRun._run', '_oop_a = (oop_vs(order, s, aggressor)', 'else None)')
sp('preflop_range_reconstruction', 'session', 'HandRun._run', 'opp_stack_bbs[o] = float(r2.stacks.get(o, 0) or 0)', 'and self._was_3bettor(o)')
sp('layer_investment_ev', 'session', 'HandRun._run', '_layer_call_value = None', "'call_chip_ev': call_ev_shadow.get('call_chip_ev'),")
sp('multiway_representative_union_range', 'session', 'HandRun._run', 'opp_r = R.range_union(*[', "'reason': 'empty_union_opponent_range',")
sp(NS + 'plan street bookkeeping', 'session', 'HandRun._run', "if key in h.plans and street != h.plans[key].get('street_made'):", "h.plans[key].setdefault('streets', []).append(street)")
sp('primary_opponent_selection', 'session', 'HandRun._run', '_others = [x for x in r2.live() if x != s]', "_ostk = (r2.stacks.get(_main, 0)/h.bb) if _main is not None else None")
sp('probe_after_checkthrough', 'session', 'HandRun._run', "_prev_street = {'turn': 'flop', 'river': 'turn'}.get(street)", "x[1] == aggressor and x[2] == 'check' for x in _pr)")
sp('money_jump_seat_topology', 'session', 'HandRun._run', '_mj_obs = _money_jump_observe(', "facing_read=(_est if tc > 0 and aggressor == _main else None))")
sp('fold_call_bet_ev', 'session', 'HandRun._run', 'bet_ev_shadow = None', '_call_target_range = R.perceived_facing_bet_response(')
sp('opponent_concept_inference', 'session', 'HandRun._run', 'if tc > 0 and aggressor is not None and aggressor != s:', None)
sp('opponent_concept_inference', 'session', 'HandRun._run', 'opp_est=(est if tc > 0 and aggressor is not None', None)
sp(NS + 'intent trace bookkeeping', 'session', 'HandRun._run', "if _i['street'] == street and _i['seat'] == s and 'trace' not in _i:", None)
sp('bet_budget', 'session', 'HandRun._run', "if a in ('bet', 'raise', 'allin'):", "h.plans[key]['bet_streets'].append(street)")
sp('human_planned_size_shape', 'session', 'HandRun._run', "_shape_meta0.get('before')", "_shape_meta0.get('after')")
sp('effective_allin_promotion', 'session', 'HandRun._run', "if not _replayed and a in ('bet', 'raise'):", "if a in ('bet', 'raise'):")
sp(NS + 'action/intent audit record fields', 'session', 'HandRun._run', "_row[2] if _row[1] in ('bet', 'raise', 'allin') else None)", '_allin_execution_mode')
sp('opponent_behavior_memory', 'session', 'HandRun._run', "if e.get('action_kind') in ('bet', 'raise'):", "if e.get('action_kind') in ('bet', 'raise'):")
sp('replan_board_change', 'session', 'HandRun._run', 'if len(h.board) > len(board):')
sp('preflop_range_action_label', 'session', 'HandRun._pf_range_action')
sp('preflop_public_roles', 'session', '_preflop_public_action_context')
sp('preflop_range_action_label', 'session', '_preflop_public_action_context', 'if full_before and all(x.get(\'actor_allin_after\')', "action = 'open'")
sp('preflop_range_reconstruction', 'session', 'HandRun._locked_postflop_range')
sp('preflop_public_roles', 'session', 'HandRun._was_3bettor')
sp('emotion_loss_shock', 'session', 'HandRun._tilt_update')
sp('pot_award_settlement', 'session', 'HandRun._finish')
sp('money_open_form_shadow', 'session', '_money_jump_attach_action')

# ---- ranges / bot / action_events / misc ----
sp('weighted_range_transform', 'ranges', 'legacy_range')
sp('weighted_range_transform', 'ranges', 'range_support')
sp('weighted_range_transform', 'ranges', '_range_combo')
sp('postflop_action_posterior', 'ranges', 'narrow')
sp('postflop_action_posterior', 'ranges', '_damp')
sp('continue_range_partition', 'ranges', 'continuation_support_fraction')
sp('range_ordering_strength', 'bot', '_sd_strength')
sp('future_draw_outs', 'bot', 'draw_strength.straight_outs')
sp('bet_range_partition', 'bot', 'pick_bluffs.score')
sp('facing_response_kind', 'action_events', '_response_kind')
sp('public_postflop_story', 'action_events', 'aggressive_seats')
sp('legal_action_application', 'runner', 'Round.needs_action')
sp('icm_bubble_factor', 'icm', 'icm_pressure')
sp('legacy_icm_overridden', 'icm', 'field_bf')
sp('field_icm_proxy', 'icm', 'field_bf#2')
sp('money_self_preservation', 'money_pressure', 'bf_signal')
sp('money_open_form_shadow', 'money_pressure', 'unopened_modifiers', 'skill01(state.get(\'open_size_skill\', 5.0))')
sp('emotion_profile_view', 'play', 'Hand.emotion_level')
sp('field_table_balance', 'fieldsim', 'Table.worst_open_seat.score')
sp('persona_population_generation', 'fieldsim', 'Field.__init__')
sp('emotion_profile_view', 'fieldsim', 'Field._init_runtime')
sp('field_context_producer', 'fieldsim', 'Field.avg_stack')
sp('field_table_balance', 'fieldsim', 'Field._collect_busts')
sp('field_context_producer', 'fieldsim', 'Field.advance_level')
sp('legacy_tournament_progress', 'fieldsim', 'Field.step_others')
sp('parallel_round_isolation', 'live2', '_load_field')
sp('parallel_round_isolation', 'live2', '_resume_parallel_others')
sp('parallel_round_isolation', 'live2', 'resume_others')
sp('forced_bet_posting', 'live2', '_opening_raw')
for f in ('Tournament.__init__', 'Tournament.field_descriptor', 'Tournament.finish_hand'):
    sp('legacy_tournament_progress', 'tourney', f)
for f in ('draw_type', 'make_player', 'Field.__init__', 'Field.descriptor', 'Field.avg_stack_bb'):
    sp('legacy_tournament_progress', 'field', f)

# ---- explicit spans replacing umbrella coverage (decomposed functions) ----
sp('perceived_icm_pressure', 'plan', 'calldown_need', "if profile.get('concepts') and bf and bf > 1.0 and not _bf_gated:", 'bf = PS.icm_bf(profile, bf)')
sp('calldown_required_share', 'plan', 'calldown_need', '_p0 = max(1.0, float(pot) - float(tocall))', 'float(objective_breakeven) * float(bf) * _size_ratio)')
sp('calldown_required_share', 'plan', 'calldown_need', 'need = max(0.01, min(0.97, need))', 'call_need = max(0.01, min(0.95, call_need))')
sp('hero_made_contribution', 'plan', 'calldown_need', 'made_now = bot.made_strength(hero, board) if board else 0')
sp('call_bias_reapplication', 'plan', 'calldown_need', "if profile.get('concepts') and board:@@2", "return need, max(0.03, min(0.95, call_need))")
sp('overbet_selection_core', 'plan', 'overbet_frac', "if street == 'flop': return None", 'return round(min(2.2, base * rng.uniform(0.92, 1.10)), 2)')
sp('checkraise_flop_decision', 'plan', 'checkraise_decision', 'rng = random.Random(seed)', "outs = plan_state.get('outs', 0)")
sp('checkraise_turn_decision', 'plan', 'checkraise_decision', 'else:@@2', 'plan, rel, outs, sk, profile.get(\'aggr\', 5))')
sp('continue_fold_blocker', 'plan', 'refresh', 'if opp_range and board:', "st['stackoff'] = _so")
sp('strength_improvement_promotion', 'plan', 'refresh', "_prev_made = st.get('made') or 0", "_prev_rel = st.get('rel') or 0.0")
sp('opponent_fold_constraint', 'plan', 'refresh', '_field_refresh = (', 'if int(n_opp or 1) > 1 else None)')
sp('opponent_fold_constraint', 'plan', 'select_field_opponent', "if purpose == 'bet_probability':@@2", 'return min(rows')
sp('preflop_decision_routing', 'plan', 'preflop_plan', 'if aggressor_pos is None and not n_limpers:', "role = 'defend'")
sp('reraise_sizing_form', 'preflop', 'raise_form', 'if stack_bb is None or target_bb >= stack_bb:', 'sh = shove_form_pressure(spr_after, exploit, level, n_opp)')  # stage9 B1
sp('reraise_sizing_form', 'preflop', 'raise_commit_geometry')
sp('reraise_sizing_form', 'preflop', 'shove_form_pressure')
sp('reraise_sizing_form', 'preflop', 'raise_form', 'aware = 1.0', "return ('raise', target_bb)")
sp('multiway_reraise_reasoning', 'preflop', 'multiway_reraise_decision', 'if len(pools) < 2 or pot_bb is None or to_call_bb is None:', "'opponent_range_seats': range_seats,")
sp('multiway_reraise_reasoning', 'preflop', 'multiway_reraise_decision', 'cost = max(0.0, float(to_call_bb or 0.0))', 'need = max(0.01, min(0.95, need))')
sp('multiway_reraise_reasoning', 'preflop', 'multiway_reraise_decision', 'lik = defend_action_likelihoods(', 'call, fold = apply_multiway_call_evidence(call, fold, eq, need, reason_skill)')
sp('isolation_decision', 'preflop', 'iso_entry_threshold')  # stage9 B1
sp('unopened_decision', 'preflop', 'open_entry_threshold')  # stage9 B1
sp('defend_width_prior', 'gto', 'open_size_defend_scale')  # stage9 B1 (L056)
sp('positional', 'persona', 'positional_chart_flattening')  # stage9 B1 (L030)
sp('rfi_personality_deviation', 'persona', 'chart_deviation_room')  # stage9 B1 (L058/L063)
sp('limp_entry_motive', 'preflop', 'limp_theory_knowledge')  # stage9 B1 (L064)
sp('preflop_card_removal', 'preflop', 'top_value_class_order')  # stage9 B1 (L075)
sp('layer_calloff_judgment', 'preflop', 'pf_defend_exact_calc_gate')  # stage9 B1 (L033/L078)
sp('layer_calloff_judgment', 'preflop', 'calloff_by_price')  # stage9 B1 (L078)
sp('preflop_posterior_order', 'ranges', 'support_rank_quantiles')  # stage9 B1 (L083)
sp('open_execution_form', 'preflop', 'open_decision', '_in_raise_range = (r <= thr)', 'if act: return (act, amt)')
sp('self_hand_overconfidence_bias', 'persona', 'bias', "if name == 'overpair_love':", "+ 0.30*(10 - T('discipline')))")
sp('self_hand_overconfidence_bias', 'persona', 'bias', "if name == 'draw_love':", "return _z(0.50*(10 - S('outs'))")
sp('self_hand_overconfidence_bias', 'persona', 'bias', "if name == 'sticky':", "+ 0.20*T('tilt_prone'))")
sp('initiative_owner', 'session', 'HandRun._run', "if r2.action_meta and r2.action_meta[-1].get('raised'):@@2")
sp('opponent_sizing_normalization', 'session', 'HandRun._run', "h.book.observe_size(")
sp('opponent_behavior_memory', 'session', 'HandRun._run', "if e.get('action_kind') in ('bet', 'raise'):@@2")
sp('money_open_range_modifier', 'money_pressure', 'unopened_modifiers', 'preserve = clamp01(', 'range_factor = (1.0 + drive) / (1.0 + range_brake)')
sp('money_open_form_shadow', 'money_pressure', 'unopened_modifiers', 'pot_brake = preserve * (1.0 - urgency)', None)
sp('money_open_form_shadow', 'money_pressure', 'unopened_modifiers', 'restraint = union01(pot_brake, pressure) * (1.0 - urgency)', None)

sp('opponent_behavior_memory', 'reads', 'Book.observe_postflop')
sp('opponent_unconsumed_estimates', 'reads', 'Book.observe_postflop', 'if facing_raise:', "if action == 'fold': r['f2r_' + street] += 1")
sp('preflop_raise_observation', 'reads', 'Book.observe_backraise')
sp('preflop_raise_observation', 'reads', 'Book.observe_cold_reraise')
sp('opponent_estimation', 'reads', 'estimate')
sp('opponent_unconsumed_estimates', 'reads', 'estimate', 'ftr = _raw(', "ftr_r = _raw('f2r_river', 'fr_river')")

# module-level knowledge/parameter tables -> concept (checked by part 3 of the checker)
TABLES = {
    'plan:PLANS': 'dead_strategy_tables', 'plan:BUDGET': 'bet_budget', 'plan:SIZING': 'planned_bet_sizing',
    'preflop:PCT': 'legacy_preflop_ordering', 'preflop:RV': '@nonsemantic:card rank map',
    'preflop:OPENER_MULT': 'opener_position_attack_table', 'preflop:DEF_POS_MULT': 'dead_strategy_tables',
    'preflop:DEPTH_OPEN_MULT': 'dead_strategy_tables', 'preflop:LEVEL_TIGHTEN': 'defend_attack_continue_widths',
    'preflop:CALLOFF_TIGHTEN': 'legacy_calloff_threshold',
    'ranges:_LIK_MIN': 'inverse_defend_likelihood', 'ranges:_MIN_KEEP': 'postflop_action_posterior',
    'ranges:_MIN_FRAC': 'postflop_action_posterior', 'ranges:_DECAY': 'postflop_action_posterior',
    'reads:PRIOR': 'opponent_estimation', 'reads:FAMILY_OBS': 'opponent_estimation',
    'reads:DEFAULT_OBS': 'opponent_estimation', 'reads:READ_RECENCY_V3': 'recency_window',
    'reads:_MAX_RECENCY_HISTORY': 'recency_window', 'reads:_SIG_SCALE': 'style_belief_reference',
    'persona:SIZING_FAMILY_SIG': 'human_planned_size_shape', 'persona:LOADING': 'persona_population_generation',
    'persona:DEFAULT_SPREAD': 'persona_population_generation', 'persona:SPREAD': 'persona_population_generation',
    'persona:OPEN_ELASTICITY': 'dead_strategy_tables', 'persona:GTO_MEMORY_V2': 'chart_memory_accuracy',
    'persona:PREFLOP_REASONING_V3': 'preflop_condition_reasoning', 'persona:EXPLOIT_WEIGHT_V3': 'exploit_read_permission',
    'persona:CALC_NOISE_V3': 'calculation_error', 'persona:PREFLOP_TEMPER_DIRECTION_V3': 'preflop_temperament_direction',
    'persona:GTO_STUDIED': 'studied_condition_match', 'persona:TILT_CONCEPT_K': 'emotion_profile_view',
    'persona:_PCTL': 'display_skill_summary', 'persona:TIERS': 'display_skill_summary',
    'gto:RFI_BY_BEHIND': 'rfi_width_prior', 'gto:RFI_SB': 'rfi_width_prior', 'gto:_DEPTH_EARLY': 'rfi_width_prior',
    'gto:_DEPTH_LATE': 'rfi_width_prior', 'gto:ANTE_MULT': 'rfi_width_prior', 'gto:DEF_VS_SB': 'defend_width_prior',
    'gto:_MDF': 'defend_width_prior', 'gto:DEF_SEAT': 'defend_width_prior', 'gto:TB_SHARE': 'threebet_width_prior',
    'gto:_MTT8_ANTE_DEF_A': 'defend_width_prior', 'gto:_MTT8_ANTE_DEF_B': 'defend_width_prior',
    'gto:_MTT8_ANTE_DEF_VS_SB': 'defend_width_prior', 'gto:_MTT8_ANTE_DEF_SEAT': 'defend_width_prior',
    'gto:_MTT8_ANTE_TB_SHARE': 'threebet_width_prior',
    'icm:_ICM_PRUNE': 'icm_exact_share', 'icm:EXACT_MAX_SEATS': 'icm_exact_share', 'icm:EXACT_MAX': 'icm_exact_share',
    'icm:MAX_PREMIUM': 'field_icm_proxy', 'icm:_PROX': 'field_icm_proxy', 'icm:_STACK': 'field_icm_proxy',
    'icm:_SIGMA_STAGE': 'field_icm_proxy', 'icm:_SIGMA_HI': 'field_icm_proxy', 'icm:_SIGMA_LO': 'field_icm_proxy',
    'icm:_LADDER_W': 'field_icm_proxy', 'icm:_LADDER_P': 'field_icm_proxy', 'icm:_K': 'field_icm_proxy',
    'icm:_FLAT_GAIN': 'field_icm_proxy', 'texture:RANK_HELP': 'turn_card_range_shift',
    'bot:RANKS': '@nonsemantic:card ranks', 'bot:RV': '@nonsemantic:card rank map', 'bot:_E7_MAX': '@nonsemantic:cache size',
    'bot:_ALLCOMBOS': '@nonsemantic:combo list',
    'depth:_CURVE': 'depth_perception', 'depth:FIELD_POW': 'depth_perception', 'depth:FIELD_CLAMP': 'depth_perception',
    'depth:LOOKAHEAD_MAX': 'depth_perception', 'depth:OFFSET_MAX': 'depth_perception', 'depth:EDGE_GAIN': 'depth_perception',
    'depth:ICM_GAIN': 'depth_perception',
    'dynamics:HIT_MIN': 'emotion_loss_shock', 'dynamics:HIT_FULL': 'emotion_loss_shock', 'dynamics:HIT_BASE': 'emotion_loss_shock',
    'dynamics:RELIEF_MIN': 'emotion_recovery', 'dynamics:RELIEF_FULL': 'emotion_recovery', 'dynamics:RELIEF_MAX': 'emotion_recovery',
    'dynamics:DECAY_BASE': 'emotion_recovery', 'dynamics:HEAT_DECAY': 'emotion_recovery', 'dynamics:HEAT_GAIN': 'emotion_loss_shock',
    'dynamics:REP_CLAMP': 'emotion_loss_shock', 'context:SPEC': 'field_context_producer',
}

DECOMPOSED = [
    'plan:make_plan', 'plan:decide_response', 'plan:decide_aggression', 'plan:decide_size',
    'plan:overbet_frac', 'plan:act_with_plan', 'plan:calldown_need', 'plan:refresh',
    'plan:preflop_plan', 'plan:select_field_opponent', 'plan:checkraise_decision',
    'preflop:defend_action_likelihoods', 'preflop:raise_form', 'preflop:open_decision',
    'preflop:multiway_reraise_decision', 'preflop:iso_decision', 'persona:bias',
    'session:HandRun._run', 'money_pressure:unopened_modifiers',
]

NONSEMANTIC_FUNCTIONS = {
    # pure helpers / plumbing / provenance with no poker meaning of their own
    'plan:_normalize_opp_pools': 'shape adapter for pool lists',
    'plan:decide_response._nv_gate': 'closure that calls _nonvalue_raise_ev_gate and records it',
    'plan:_trace': 'trace logging', 'plan:_prof_hint': 'display hint', 'plan:record_deviation': 'logging',
    'preflop:_tr': 'trait accessor (see legacy_trait_adapter)', 'preflop:prof_aggr': 'temperament accessor',
    'preflop:_defend_logistic': 'math helper (logistic)',
    'ranges:range_is_uniform': 'container predicate', 'ranges:range_mean_mass': 'container stat',
    'ranges:range_unique_sorted': 'container helper', 'ranges:_def_thresholds': 'forwarder to preflop.defend_thresholds',
    'ranges:_prof_key': 'cache key', 'ranges:_ranked': 'sort by range_ordering_strength',
    'ranges:_action_event_fields': 'event schema adapter',
    'session:_cache_key': 'replay cache key', 'session:_money_jump_observe._target_state': 'state record builder',
    'session:HandRun.__init__': 'runtime init', 'session:HandRun._emit_bot_action': 'telemetry/UI emit',
    'session:HandRun._emit_street': 'telemetry/UI emit', 'session:HandRun.start': 'generator plumbing',
    'session:HandRun.send': 'generator plumbing', 'session:HandRun._pid': 'id mapping',
    'session:HandRun._dseed': 'deterministic seed derivation', 'session:HandRun._reads_for': 'loops perceived_profile',
    'session:HandRun._finish._left_of_button_order': 'seat order helper for odd-chip', 'session:HandRun._finish._rotate_to': 'seat order helper',
    'reads:_ObsMap.__getitem__': 'container', 'reads:_ObsMap.get': 'container', 'reads:_numeric_snapshot': 'snapshot copy',
    'reads:Book.__init__': 'init', 'reads:Book._k': 'key', 'reads:estimate._rate': 'ratio helper',
    'reads:save_book': 'io', 'reads:load_book': 'io', 'reads:_sig_scale': 'math helper',
    'reads:prior_spread': 'style_belief_reference helper (SHADOW)', 'reads:style_certainty': 'style_belief_reference helper (SHADOW)',
    'persona:dump_loading': 'debug dump', 'persona:_clamp': 'math', 'persona:skill': 'accessor', 'persona:has': 'accessor',
    'persona:describe': 'display', 'persona:_z': 'math', 'persona:read_opponent._see': 'gate curve helper inside read_opponent',
    'gto:_interp': 'math', 'gto:avg_rfi': 'rfi_width_prior helper (positional flattening input)',
    'gto:table': 'display table', 'gto:_use_mtt8_ante_defense': 'defend_width_prior calibration switch (8-max ante only)',
    'icm:_icm_equity_reference.rec': 'recursion helper', 'icm:_lerp': 'math', 'icm:_lognorm': 'math',
    'money_pressure:clamp01': 'math', 'money_pressure:sat': 'math', 'money_pressure:inv1p': 'math',
    'money_pressure:mean01': 'math', 'money_pressure:union01': 'math', 'money_pressure:skill01': 'math',
    'money_pressure:actor_from_profile': 'profile adapter', 'money_pressure:signals': 'telemetry summary',
    'texture:label': 'display label', 'bot:draw_strength.flush_count': 'card count helper',
    'bot:draw_strength.straight_run': 'card helper', 'bot:bluff_count': 'line_bluff_composition helper',
    'bot:_ck': 'cache key', 'depth:_interp': 'math',
    'runner:P': 'debug print', 'runner:_sig': 'signature', 'runner:_SigMap.__getitem__': 'container',
    'runner:shape_size': 'compat wrapper of persona.shape_size', 'runner:Round.__init__': 'init',
    'runner:Round.live': 'accessor', 'runner:Round.pot_contrib': 'accessor',
    'action_events:_response_kind': None, 'action_events:aggressive_seats': None,
    'dynamics:_t': 'accessor', 'dynamics:Tilt.__init__': 'init', 'dynamics:Tilt._s': 'accessor',
    'dynamics:Tilt.level': 'accessor', 'dynamics:Tilt.heat': 'accessor', 'dynamics:Tilt.shown': 'accessor',
    'context:Context.__init__': 'init', 'context:Context.update': 'container', 'context:Context.missing': 'container',
    'context:Context.__repr__': 'display',
}
NONSEMANTIC_FUNCTIONS = {k: v for k, v in NONSEMANTIC_FUNCTIONS.items() if v}
NONSEMANTIC_MODULES = {
    'fieldsim': 'physical table/field runtime (registered rows: physical_button_rotation, field_table_balance, field_context_producer); helpers without poker meaning',
    'live2': 'UI/runtime state, parallel rounds, persistence (replay_decision_cache, parallel_round_isolation)',
    'field': 'legacy tournament field runtime (legacy_tournament_progress)',
    'tourney': 'legacy tournament runtime (legacy_tournament_progress)',
    'play': 'hand container (emotion_profile_view, icm_bubble_factor via Hand.bf)',
    'archetypes': 'legacy archetype tables (legacy_arch_types)',
}


def build():
    path_csv = os.path.join(DOC, 'CONCEPT_FUNCTION_REGISTRY.csv')
    rows = list(csv.DictReader(open(path_csv, encoding='utf-8')))
    rows = [r for r in rows if r.get('origin') != 'IMPLICIT_CODE_V2']
    for r in rows:
        r.setdefault('parent_concept', '')
        r.setdefault('code_span', '')
        upd = ROW_UPDATES.get(r['concept'])
        if upd:
            r.update(upd)
    names = {r['concept'] for r in rows}
    for nr in NEW_ROWS:
        assert nr['concept'] not in names, nr['concept']
        names.add(nr['concept'])
        rows.append(nr)
    with open(path_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in COLS})
    json.dump(rows, open(os.path.join(DOC, 'CONCEPT_FUNCTION_REGISTRY.json'), 'w',
                         encoding='utf-8'), ensure_ascii=False, indent=2)
    json.dump({'decomposed': DECOMPOSED, 'spans': S, 'tables': TABLES,
               'nonsemantic_functions': NONSEMANTIC_FUNCTIONS,
               'nonsemantic_modules': NONSEMANTIC_MODULES},
              open(os.path.join(HERE, 'SPAN_MAP.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('registry rows', len(rows), 'new', len(NEW_ROWS), 'spans', len(S))


if __name__ == '__main__':
    build()


# ---------------------------------------------------------------------------
# street semantics of the re-audit rows: (preflop, flop, turn, river)
NA, SAME, DIST, MISS, OVER = 'not applicable', 'same', 'distinct', 'missing', 'overloaded'
STREET = {
    'perceived_board_danger': (NA, OVER + ' — make_plan scaled danger', OVER + ' — refresh stores raw danger in same key', OVER + ' — same'),
    'perceived_spr': (NA, SAME + ' — make_plan', SAME + ' — only on board-change replan', SAME + ' — only on board-change replan'),
    'potcontrol_disposition': (NA, SAME, SAME, SAME),
    'value_when_called_strength': (NA, SAME + ' — make_plan commit_rel', OVER + ' — commit_rel / overbet@1.15 / improved bluff eq>=0.54', OVER + ' — river_value_reassessment eq>=0.50 / overbet / improved bluff'),
    'multiway_value_threshold_shift': (NA, SAME, SAME, SAME),
    'read_value_threshold_shift': (NA, SAME + ' — street_gap(flop)', SAME + ' — street_gap(turn)', SAME + ' — street_gap(river)'),
    'bluff_evidence_composite': (NA, SAME, SAME, SAME),
    'relative_strength_value_threshold_shift': (NA, SAME, SAME, SAME),
    'showdown_value_predicate': (NA, OVER + ' — plan.has_showdown_value with eq vs eq_current', OVER, OVER),
    'medium_strength_merge_value': (NA, DIST + ' — sk(range_merge)', OVER + ' — replan still reads range_merge, not thin_value_turn', OVER + ' — replan still reads range_merge, not thin_value_river'),
    'monster_made_hand_raise': (NA, SAME, SAME, SAME),
    'value_raise_sizing_from_commit': (NA, SAME, SAME, SAME),
    'value_raise_qualification': (NA, SAME, SAME, SAME),
    'value_raise_frequency': (NA, SAME, SAME, DIST + ' — rel floor ×0.85'),
    'bluff_reraise_frequency': (NA, SAME, SAME, SAME),
    'semibluff_raise_frequency': (NA, SAME, SAME, NA),
    'implied_odds_adjustment': (NA, SAME, SAME, NA),
    'giveup_deviation_raise': (NA, SAME, SAME, SAME),
    'price_overrides_giveup_plan': (NA, SAME, SAME, SAME),
    'giveup_initiative_stab_deviation': (NA, DIST + ' — cbet_flop_frequency', DIST + ' — barrel_turn_frequency × delayed boost', DIST + ' — barrel_river_frequency'),
    'bluff_execution_frequency': (NA, SAME + ' — no card term', DIST + ' — turn_card_effect(turn card)', OVER + ' — turn_card_effect(flop, river card) ignores the turn'),
    'donk_suppression': (NA, SAME, SAME, SAME),
    'value_bet_execution_frequency': (NA, DIST + ' — range_merge', DIST + ' — thin_value_turn', DIST + ' — thin_value_river ×0.92'),
    'value_blocker_size_adjust': (NA, SAME, SAME, SAME),
    'deviation_bet_size_fallback': (NA, DIST + ' — 0.50', DIST + ' — 0.55', DIST + ' — 0.60'),
    'weak_hand_size_shrink': (NA, SAME, SAME, SAME),
    'plan_size_band_clamp': (NA, SAME + ' — block', SAME + ' — block', DIST + ' — thin_river + block'),
    'response_equity_basis': (NA, SAME, SAME, SAME),
    'spr_commitment_flag': (NA, SAME, SAME, SAME),
    'raise_target_coordinate': (NA, SAME, SAME, SAME),
    'intent_chip_conversion': (NA, SAME, SAME, SAME),
    'players_behind_risk_premium': (SAME + ' — icm.players_behind_required_equity_premium', SAME, SAME, SAME),
    'value_degradation_thresholds': (NA, NA, DIST + ' — turn_card_effect(turn)', OVER + ' — turn_card_effect(flop, river card)'),
    'semibluff_draw_loss_resolution': (NA, NA, DIST + ' — refresh', NA + ' (river: river_semibluff_resolution)'),
    'giveup_reentry_on_improvement': (NA, NA, OVER + ' — made>=2 includes board pair', OVER + ' — same'),
    'improved_bluff_rejudgment': (NA, NA, SAME, SAME),
    'value2_budget_exhaustion_upgrade': (NA, NA, SAME, SAME),
    'preflop_decision_routing': (DIST + ' — plan.preflop_plan', NA, NA, NA),
    'preflop_decision_class': (DIST, NA, NA, NA),
    'preflop_read_width_exploit': (DIST, NA, NA, NA),
    'preflop_premium_slowplay_mix': (DIST, NA, NA, NA),
    'allin_form_fold_equity_read': (DIST, NA, NA, NA),
    'short_stack_open_widening': (DIST, NA, NA, NA),
    'open_size_behind_read_adjust': (DIST, NA, NA, NA),
    'locked_allin_price_gate': (DIST, NA, NA, NA),
    'reraise_attack_evidence': (DIST, NA, NA, NA),
    'iso_limper_read_widening': (DIST, NA, NA, NA),
    'self_hand_overconfidence_bias': (NA, SAME, SAME, SAME),
    'call_threshold_bias': (NA, DIST + ' — bluffcatch_early w0.35', OVER + ' — bluffcatch_early shared with flop', DIST + ' — bluffcatch_river'),
    'preflop_temperament_direction': (DIST, NA, NA, NA),
    'concept_skill_gate': (DIST + ' — pf_defend', NA, NA, NA),
    'street_concept_alias': (NA, DIST + ' — alias table', DIST, DIST),
    'legacy_trait_adapter': (DIST, NA, NA, NA),
    'read_polarity_signal': (DIST, NA, NA, NA),
    'forced_bet_posting': (DIST, NA, NA, NA),
    'multiway_representative_union_range': (NA, OVER, OVER, OVER),
    'primary_opponent_selection': (NA, SAME, SAME, SAME),
    'preflop_range_action_label': (DIST, NA, NA, NA),
    'range_ordering_strength': (NA, SAME + ' — draw bonus', SAME + ' — draw bonus', DIST + ' — no draw term'),
    'checkraise_value_probability_floor': (NA, SAME, SAME, SAME),
    'continuation_bet_frequency_core': (NA, DIST + ' — base 0.42', DIST + ' — base 0.30', DIST + ' — base 0.22'),
    'overbet_selection_core': (NA, NA, SAME, DIST + ' — ×1.35'),
    'opponent_unconsumed_estimates': (MISS + ' — cold re-raise/backraise reads unconsumed', MISS + ' — fold-to-raise unconsumed', MISS, MISS),
    'dead_strategy_tables': (NA, NA, NA, NA),
    'opener_position_attack_table': (OVER + ' — reshove width + open-shove position depth', NA, NA, NA),
    'iso_sizing': (DIST, NA, NA, NA),
}

# ledger additions: (id, concept, location, problem, verdict, boundary)
LEDGER = [
    ('L-RA01', 'called_aggression_ownership', 'plan._called_prior_street_aggression;plan.line_owned_by_live_aggressor',
     'registry meaning was inverted ("내 공격이 콜받았나"); code asks whether hero CALLED the opponent\'s aggression. Flop consumer added in batch 1.',
     'RENAME (doc) + KEEP', 'registry row corrected; extraction behavior-identical'),
    ('L-RA02', 'lead_into_aggressor_policy', 'plan.decide_aggression (bluff suppression / pot_control 0.04 / value relead)',
     'one poker question "lead into a live aggressor?" answered by three mechanisms with different magnitudes',
     'MERGE (later)', 'behavior change; needs EV/frequency review'),
    ('L-RA03', 'value_when_called_strength', 'make_plan commit_rel; overbet_frac; river_value_reassessment; refresh improved bluff',
     'same question, four producers, metric rel vs equity, thresholds none/0.50/0.54', 'MERGE (later)', 'behavior change'),
    ('L-RA04', 'showdown_value_predicate', 'plan.has_showdown_value (2 callers) + pure-bluff gate',
     'medium-band fallback uses eq (runout), final branch eq_current; bluff gate omits multiway term',
     'MERGE done for formula; SPLIT equity basis kept explicit', 'unifying the basis changes behavior'),
    ('L-RA05', 'players_behind_risk_premium', 'plan.calldown_need; preflop.multiway_reraise_decision',
     'identical formula duplicated in two modules', 'MERGE (done)', 'icm.players_behind_required_equity_premium, bit-identical'),
    ('L-RA06', 'perceived_board_danger', 'make_plan (scaled) vs refresh/decide_size (raw)',
     'state key "danger" changes meaning between plan creation and refresh', 'SPLIT (later)', 'behavior change'),
    ('L-RA07', 'turn_card_range_shift', 'plan.decide_aggression; plan.refresh',
     'on the river both call turn_card_effect(flop, river card): the turn card is ignored and the name says turn',
     'SPLIT / RENAME (later)', 'river card effect vs turn card effect are different questions'),
    ('L-RA08', 'medium_strength_merge_value', 'plan.make_plan (replan on turn/river)',
     'board-change replan reads sk(range_merge) at turn/river instead of thin_value_<street>', 'REROUTE (later)', 'skill supply change'),
    ('L-RA09', 'giveup_reentry_on_improvement', 'plan.refresh',
     'made>=2 / made>=3 can come from a paired board. Root: bot.made_strength returns the full category when it '
     'exceeds the board category, so pocket pair + board pair = two pair (2) counts as "made 2" without hero '
     'improvement. Same root as HAND 63 / R5c; consumers: refresh giveup re-entry, semibluff_draw_loss_resolution, '
     'river_semibluff_resolution showdown branch', 'SPLIT (later)', 'hero_made_contribution semantics change = behavior change'),
    ('L-RA10', 'multiway_representative_union_range', 'session.HandRun._run → plan opp_range',
     'equity uses seat pools but continue-range gates (overbet, value raise HU check), blocker_score and plan state read the union',
     'REROUTE (later)', 'behavior change'),
    ('L-RA11', 'opponent_unconsumed_estimates', 'reads.estimate',
     'fold-to-raise and cold-reraise/backraise/squeeze-response reads are estimated but no decision consumes them',
     'KEEP SHADOW', 'wiring is an exploit-phase change (tilt/exploit disabled in baseline)'),
    ('L-RA12', 'opener_position_attack_table', 'preflop.OPENER_MULT',
     'reshove-width table reused (audit9 R4) as proxy for depth of players behind an open-shove', 'SPLIT (later)', 'behavior change'),
    ('L-RA13', 'defend_width_prior', 'gto.defend_pct / _use_mtt8_ante_defense',
     'calibrated defend table only for seats==8 ante; standard/main/lowbuyin are 9-max and use the legacy formula',
     'KEEP (knowledge gap)', 'R2 knowledge-accuracy audit'),
    ('L-RA14', 'dead_strategy_tables', 'preflop.DEF_POS_MULT, DEPTH_OPEN_MULT; persona.OPEN_ELASTICITY; plan.PLANS',
     'strategy constants with no production reader', 'REMOVE_COMPAT (later)', 'harmless; removal is a separate cleanup'),
    ('L-RA15', 'response_equity_basis', 'plan.act_with_plan',
     'fallback tier 3 models the opponent with the actor\'s own bluff axis and fixed callers', 'KEEP FALLBACK', 'reachable only without perceived ranges'),
    ('L-RA16', 'plan_revision_lifecycle', 'plan.refresh comment',
     'stale in-code comment says the promotion "made term is dead"; the term was removed in audit9 (doc drift in code)',
     'RENAME (comment)', 'documentation only'),
    ('L-RA17', 'self_hand_overconfidence_bias / perceived_player_edge', 'persona.bias; persona.perceived_edge',
     'range_read supplies self-assessment roles; perceived_edge IS active at baseline through preflop.feel_of (max-skill +0.016 feel)',
     'KEEP (documented)', 'corrects the earlier claim that perceived_edge has no baseline effect'),
    ('L-RA18', 'opponent_concept_inference (range_profile)', 'session.HandRun._preflop_perceived_range;_locked_postflop_range',
     'observer Book estimates become the opponent preflop-range profile independent of exploit weight w: '
     '"exploit neutral" does not switch off opponent adaptation; manual_one_hand audits accumulate the Book',
     'KEEP + document baseline harness', 'baseline harness must freeze the Book (sim2 T2_BASELINE does)'),
]


def _section(path, title, body):
    start, end = '<!-- reaudit:start -->', '<!-- reaudit:end -->'
    txt = open(path, encoding='utf-8').read()
    block = '%s\n## %s\n\n%s\n%s' % (start, title, body.rstrip('\n'), end)
    if start in txt:
        a = txt.index(start); b = txt.index(end) + len(end)
        txt = txt[:a] + block + txt[b:]
    else:
        txt = txt.rstrip('\n') + '\n\n' + block + '\n'
    open(path, 'w', encoding='utf-8').write(txt)


def write_docs():
    missing = [r['concept'] for r in NEW_ROWS if r['concept'] not in STREET]
    assert not missing, missing
    # street matrix
    lines = ['재감사(2026-10-02)에서 추가된 개념. 열 의미는 위 표와 같다.', '',
             '| concept | preflop | flop | turn | river |', '| --- | --- | --- | --- | --- |']
    for r in NEW_ROWS:
        lines.append('| %s | %s |' % (r['concept'], ' | '.join(STREET[r['concept']])))
    lines += ['', '기존 행 정정: `called_aggression_ownership` — flop distinct(프리플랍 어그레서 라인 소유, '
              '`plan.line_owned_by_live_aggressor`), turn/river same.']
    _section(os.path.join(DOC, 'STREET_SEMANTIC_MATRIX.md'), '재감사 추가 행 (completeness)', '\n'.join(lines))
    # ledger
    lines = ['| ID | 개념 | 현재 위치 | 겹친 의미와 문제 | 판정 | 처리 경계 |', '| --- | --- | --- | --- | --- | --- |']
    for row_ in LEDGER:
        lines.append('| %s |' % ' | '.join(x.replace('|', '/') for x in row_))
    _section(os.path.join(DOC, 'DUPLICATION_AND_OVERLOAD_LEDGER.md'), '재감사 추가 항목 (completeness)', '\n'.join(lines))
    # registry quick table
    lines = ['재감사에서 추가한 %d개 행(origin `IMPLICIT_CODE_V2`, `parent_concept`·`code_span` 열 포함). '
             '전체 필드는 CSV/JSON. 코드 위치 소유는 [completeness/SPAN_MAP.json](completeness/SPAN_MAP.json).' % len(NEW_ROWS), '',
             '| concept / 의미 | street / 분류 / 층 | producer → consumer | source / status / 영향 | duplicate·overload / parent |',
             '| --- | --- | --- | --- | --- |']
    for r in NEW_ROWS:
        lines.append('| %s — %s | %s / %s / %s | %s → %s | %s / %s / %s | %s / parent `%s` |' % tuple(
            str(x).replace('|', '/') for x in (
                r['concept'], r['poker_meaning'], r['street'], r['category'], r['layer'],
                r['producer'], r['consumer'], r['source_knowledge'], r['runtime_status'],
                r['action_influence'], r['duplicate_overload'], r['parent_concept'])))
    lines += ['', '기존 행 정정: ' + ', '.join('`%s`' % k for k in ROW_UPDATES) + ' (CSV/JSON 반영).']
    _section(os.path.join(DOC, 'CONCEPT_FUNCTION_REGISTRY.md'), '재감사 추가 행 (completeness)', '\n'.join(lines))


if __name__ == '__main__':
    write_docs()
