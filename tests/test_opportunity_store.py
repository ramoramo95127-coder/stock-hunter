from stock_hunter.judge.models import OpportunityState


def test_opportunity_states_are_stable_for_persistence() -> None:
    assert OpportunityState.PRIME_CANDIDATE.value == "prime_candidate"
    assert OpportunityState.WEAKENING.value == "weakening"
