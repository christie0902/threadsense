"""Synthetic v5 examples derived ONLY from reviewed synthetic fixtures, never raw responses."""
from copy import deepcopy
import json
from tests.agent2_inventory_fixtures import reviewed_draft as reviewed_v4, wiring_draft as wiring_v4


def v5_synthetic(draft):
    draft = deepcopy(draft)
    draft.pop('schema_version')
    for topic in draft['topics']:
        for item in topic['inventory']:
            old_text = item.pop('text')
            item['answer_status'] = ('TENTATIVE' if 'I think' in old_text else 'DIRECT') if item['kind'] == 'ANSWER' else None
            if item['question']:
                # Synthetic unassessed confidence for wiring tests, never historical scores.
                item['question'].update(resolution_confidence=None, uncertainty_note=None)
    return draft


def reviewed_draft(gid):
    return v5_synthetic(reviewed_v4(gid))


def wiring_draft(payload):
    return v5_synthetic(wiring_v4(payload))


def assert_only_versioned_rubric_changed(current_message, historical_message):
    """Keep original source inputs exact while allowing the explicit v2 rubric."""
    from threadsense.agents.operational_severity import RUBRIC, RUBRIC_V2
    current = json.loads(current_message['content'])
    historical = json.loads(historical_message['content'])
    assert current_message['role'] == historical_message['role']
    assert current.pop('provisional_operational_severity_rubric') == RUBRIC_V2
    assert historical.pop('provisional_operational_severity_rubric') == RUBRIC
    assert current.pop('schema_version') == 6
    assert historical.pop('schema_version') == 5
    assert current == historical


def assert_only_question_uncertainty_schema_changed(current, historical):
    current, historical = deepcopy(current), deepcopy(historical)
    assert current['json_schema'].pop('name') == 'threadsense_agent2_inventory_v6'
    assert historical['json_schema'].pop('name') == 'threadsense_agent2_inventory_v5'
    q = current['json_schema']['schema']['$defs']['QuestionState']
    for key in ('resolution_confidence', 'uncertainty_note'):
        q['properties'].pop(key)
        q['required'].remove(key)
    assert current == historical
