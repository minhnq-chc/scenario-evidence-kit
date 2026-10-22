"""No paid provider requests are made by these tests."""

from types import SimpleNamespace

import pytest

from scenario_evidence.provider import ScenarioPlan, generate_with_openai


class FakeResponses:
    def __init__(self, plan):
        self.plan = plan
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=self.plan,
                               usage=SimpleNamespace(input_tokens=12, output_tokens=20))


def test_structured_plan_is_checked_and_snapshotted():
    plan = ScenarioPlan(kind='lead_brake', weather='rain', ego_speed_mps=15,
                        actor_speed_mps=10, distance_m=25, title='Lead braking')
    responses = FakeResponses(plan)
    scenarios, metadata = generate_with_openai('A lead car brakes', 2, 42, 'DemoStraight',
                                              client=SimpleNamespace(responses=responses))
    assert len(scenarios) == 2 and scenarios[0]['kind'] == 'lead_brake'
    assert metadata['reproducible_generation'] is False
    assert responses.kwargs['store'] is False and responses.kwargs['max_output_tokens'] == 1200


def test_unsafe_plan_is_rejected():
    plan = ScenarioPlan(kind='pedestrian_crossing', weather='clear', ego_speed_mps=15,
                        actor_speed_mps=100, distance_m=25, title='Invalid pedestrian')
    with pytest.raises(ValueError, match='deterministic validation'):
        generate_with_openai('cross', 1, 42, 'DemoStraight',
                             client=SimpleNamespace(responses=FakeResponses(plan)))


def test_refusal_is_not_a_saved_scenario():
    with pytest.raises(ValueError, match='refused'):
        generate_with_openai('test', 1, 42, 'DemoStraight',
                             client=SimpleNamespace(responses=FakeResponses(None)))
