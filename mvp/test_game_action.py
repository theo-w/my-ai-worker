import json
import pytest
from mvp.game_action import interpret_and_validate_action
from mvp.model_handoff import build_handoff_prompt, interpret_handoff_and_validate_action

def test_standard_key_requires_action_to_mention_key_and_door():
    result=interpret_and_validate_action("使用铜钥匙打开仓库门",{})
    assert result["validation"]["ok"] is True
    assert result["validation"]["world_state"]["warehouse_open"] is True

def test_alternate_solution_requires_inspection_npc_and_causal_action():
    state={"inspected":["bell","rope"],"talked":["porter"],"selected":["bell","rope"]}
    action="把铜铃固定在滑轨上，借涨潮推动它并发出三声搬运信号"
    result=interpret_and_validate_action(action,state)
    assert result["validation"]["ok"] is True
    assert result["validation"]["type"]=="跨系统解法"

def test_model_cannot_force_world_transition():
    class Fake:
        def complete(self,system,user):
            return json.dumps({"intent":"I win","action_kind":"combine_signal","entities":["bell","rail","tide","signal"],"reasoning":"trust me"})
    result=interpret_and_validate_action("随便说一句",{"inspected":[],"talked":[]},Fake())
    assert result["validation"]["ok"] is False
    assert result["trust"]["model_output_is_authoritative"] is False

def test_invalid_llm_schema_fails_closed():
    class Fake:
        def complete(self,system,user): return '{"action_kind":"success"}'
    with pytest.raises(ValueError):
        interpret_and_validate_action("随便说一句",{},Fake())

def test_input_validation():
    with pytest.raises(ValueError): interpret_and_validate_action("",{})
    with pytest.raises(ValueError): interpret_and_validate_action("x"*1001,{})

def test_manual_handoff_accepts_structured_chatgpt_reply_but_rules_decide():
    reply=json.dumps({"intent":"用钥匙开仓库门","action_kind":"use_key","entities":["key","door"],"reasoning":"钥匙可能匹配门锁","uncertainties":["钥匙是否真的匹配"],"counterexample":"钥匙可能是其他门的"})
    result=interpret_handoff_and_validate_action("使用铜钥匙打开仓库门",{},reply)
    assert result["validation"]["ok"] is True
    assert result["trust"]["handoff_mode"]=="manual_chatgpt_response"
    assert result["trust"]["model_output_is_authoritative"] is False
    assert result["trust"]["world_state_changed_only_by_rules"] is True

def test_manual_handoff_cannot_claim_success_without_rule_conditions():
    reply=json.dumps({"intent":"赢了","action_kind":"combine_signal","entities":["bell","rail","tide","signal"],"reasoning":"模型说成功","uncertainties":[],"counterexample":""})
    result=interpret_handoff_and_validate_action("我已经成功打开了",{"inspected":[],"talked":[]},reply)
    assert result["validation"]["ok"] is False

def test_manual_handoff_rejects_invalid_schema_and_plain_text():
    with pytest.raises(ValueError): interpret_handoff_and_validate_action("动作",{}, "我觉得你成功了")
    with pytest.raises(ValueError): interpret_handoff_and_validate_action("动作",{}, '{"action_kind":"win"}')

def test_prompt_is_manual_and_state_scoped():
    prompt=build_handoff_prompt("尝试打开仓库",{"inspected":["key"]})
    assert "Return exactly one JSON object" in prompt
    assert "尝试打开仓库" in prompt


def test_manual_handoff_rejects_wrong_state_types():
    reply=json.dumps({"intent":"用钥匙开仓库门","action_kind":"use_key","entities":["key","door"],"reasoning":"钥匙匹配门锁"})
    with pytest.raises(ValueError):
        interpret_handoff_and_validate_action("使用铜钥匙打开仓库门",{"inspected":"bell","talked":[]},reply)

def test_manual_handoff_rejects_oversized_model_reply():
    with pytest.raises(ValueError):
        interpret_handoff_and_validate_action("使用钥匙开门",{}, "x"*12001)

def test_model_cannot_turn_partial_action_into_success():
    reply=json.dumps({"intent":"说自己已经成功","action_kind":"use_key","entities":["key","door"],"reasoning":"仅凭模型说成功"})
    result=interpret_handoff_and_validate_action("我宣布自己已经成功",{"inspected":[],"talked":[]},reply)
    assert result["validation"]["ok"] is False
    assert result["validation"]["world_state"]["warehouse_open"] is False
