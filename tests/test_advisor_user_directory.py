"""Agent 3 reads names and roles from the run's own Slack fixture, not always from the demo fixture."""
import json

import pytest

from threadsense.agents import advisor_checks, advisor_evidence, overnight
from threadsense.retrieval.config import FIXTURE_ROOT


@pytest.fixture(autouse=True)
def restore_default():
    yield
    advisor_evidence.use_fixture_users(FIXTURE_ROOT)


def fixture_with_users(root):
    root.mkdir(parents=True, exist_ok=True)
    (root/'users.json').write_text(json.dumps([{'id': 'U_NEW1', 'name': 'New Lead', 'role': 'TEAM_LEAD'},
                                               {'id': 'U_NEW2', 'name': 'New Tutor', 'role': 'TUTOR'}]), encoding='utf-8')
    return root


def test_default_is_the_demo_fixture():
    demo = advisor_evidence.user_directory()
    assert demo == advisor_evidence.user_directory(FIXTURE_ROOT/'users.json')
    assert 'U_NEW1' not in demo


def test_runtime_points_attribution_checks_at_its_own_fixture(tmp_path):
    root = fixture_with_users(tmp_path/'slack')
    overnight.Runtime(tmp_path/'out', client=None, cutoff=None, fixture_root=root)
    expected = {'U_NEW1': {'name': 'New Lead', 'role': 'TEAM_LEAD'}, 'U_NEW2': {'name': 'New Tutor', 'role': 'TUTOR'}}
    assert advisor_evidence.user_directory() == expected
    assert advisor_checks.user_directory() == expected  # the checks module imported the function, not a copy


def test_fixture_without_users_keeps_the_demo_directory(tmp_path):
    demo = advisor_evidence.user_directory()
    (tmp_path/'slack').mkdir()
    assert advisor_evidence.use_fixture_users(tmp_path/'slack') == advisor_evidence.DEFAULT_USERS
    assert advisor_evidence.user_directory() == demo
