import json

import pytest

from mvp.experience_design import create_design_brief


def test_default_design_brief_is_structured_and_honest_about_evidence():
    brief = create_design_brief()
    assert brief["source_game"] == "塞尔达传说：王国之泪"
    assert brief["original_concept"]["title"].startswith("潮痕档案馆")
    assert len(brief["mechanism_analysis"]) >= 2
    assert len(brief["player_perspectives"]) >= 3
    assert len(brief["falsifiable_hypotheses"]) >= 2
    assert brief["evidence_status"]["market_validated"] is False
    assert brief["evidence_status"]["playtested"] is False
    assert brief["generation"]["mode"] == "template_fallback"


def test_design_brief_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        create_design_brief("")
    with pytest.raises(ValueError):
        create_design_brief("Zelda", "x" * 161)


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def complete(self, system_prompt, user_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


def test_llm_output_cannot_claim_market_validation_or_playtest():
    payload = {
        "source_game": "example",
        "mechanism_analysis": [],
        "transferable_principles": [],
        "original_concept": {},
        "player_perspectives": [],
        "falsifiable_hypotheses": [],
        "prototype_plan": {},
        "evidence_status": {
            "observations": [],
            "hypotheses": [],
            "unknowns": [],
            "market_validated": True,
            "playtested": True,
        },
    }
    brief = create_design_brief("example", "new concept", FakeLLM(json.dumps(payload)))
    assert brief["evidence_status"]["market_validated"] is False
    assert brief["evidence_status"]["playtested"] is False
    assert brief["generation"]["mode"] == "llm"


def test_invalid_llm_json_fails_explicitly():
    with pytest.raises(ValueError, match="valid JSON"):
        create_design_brief("example", "new concept", FakeLLM("not json"))


def test_llm_missing_schema_fields_fails_explicitly():
    with pytest.raises(ValueError, match="missing required"):
        create_design_brief("example", "new concept", FakeLLM('{"source_game":"example"}'))
