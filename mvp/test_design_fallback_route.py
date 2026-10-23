from pathlib import Path


SERVER = Path(__file__).with_name("server.py").read_text(encoding="utf-8")


def test_design_endpoint_has_explicit_non_llm_fallback_for_malformed_model_output():
    assert 'brief = create_design_brief(source_game, concept_name, None, research_context=research_context)' in SERVER
    assert '"mode": "template_fallback"' in SERVER
    assert '"model_generated": False' in SERVER
    assert '"fallback_reason": type(exc).__name__' in SERVER


def test_design_endpoint_still_requires_current_run_accepted_research():
    route = SERVER[SERVER.index('if self.path == "/api/experience-design":'): ]
    gate = route[:route.index('if self.path == "/api/research":')]
    assert 'research_state.get("status") != "completed"' in gate
    assert 'accepted < 1 or not sources' in gate
