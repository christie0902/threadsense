"""Current imports stay small; historical dispatch remains explicit and usable."""
import json
import subprocess
import sys

import pytest

from threadsense.handoff_inputs import ROOT


def test_current_agent2_imports_do_not_load_historical_semantic_engines():
    # A fresh process is necessary: other tests deliberately import legacy contracts.
    code = """
import json, sys
from threadsense.agents import topic_pipeline, topic_analyst, topic_requests
from threadsense.agents.topic_contracts import TopicTaxonomy
from threadsense.agents.topic_consolidation import validate_input
from threadsense.topic_inputs import validate_input as shared_validation
assert validate_input is shared_validation
assert topic_requests.RESPONSE_SCHEMA_VERSION == 7
assert set(TopicTaxonomy.model_fields) == {'topics', 'rejected_member_ids'}
assert topic_requests.provider_schema(7)['properties'].keys() == TopicTaxonomy.model_fields.keys()
print(json.dumps(sorted(n for n in sys.modules if n.startswith('threadsense.legacy.agent2'))))
"""
    result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize('version,module', [(2,'v2'),(3,'v3'),(4,'v4'),(5,'v6'),(6,'v6')])
def test_historical_dispatch_resolves_archived_contracts(version, module):
    from threadsense.agents.topic_consolidation import _contract
    archived = _contract(version)
    assert archived.__name__ == 'threadsense.legacy.agent2.topic_consolidation_' + module
    assert all(callable(getattr(archived, name)) for name in ('build_request','parse_response','export_result'))


def test_no_numbered_contract_copies_or_dangling_producer_paths():
    from threadsense.agents.topic_pipeline import CODE_FILES
    agents = ROOT/'src/threadsense/agents'
    assert not list(agents.glob('topic_contracts_v*.py'))
    assert not list(agents.glob('topic_consolidation_v*.py'))
    assert all((ROOT/name).is_file() for name in CODE_FILES)
    assert len(CODE_FILES) == len(set(CODE_FILES))
    assert not (agents/'topic_review.py').exists()
    assert not (agents/'review_decisions.py').exists()
