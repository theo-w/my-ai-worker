import json
import pytest
from mvp.game_action import interpret_and_validate_action

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
