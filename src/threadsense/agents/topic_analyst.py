"""Compatibility factories for factual Agent 2 tasks.

The active batch/sample runner uses topic_pipeline's single-request transport;
these factories preserve configuration callers without enabling an SDK retry loop.
"""
from crewai import Agent, Task
from threadsense.agents.thread_interpreter import create_llm
from threadsense.agents.topic_contracts import TopicConsolidation
from threadsense.agents.topic_consolidation import RULES
from threadsense.terminology import get_terms
import json

def create_topic_analyst():
    return Agent(role='ThreadSense Topic Analyst',
                 goal='Consolidate factual topics and verify membership while preserving evidence and uncertainty.',
                 backstory='You compare original Slack discussions and distinguish reported claims from supported answers.',
                 llm=create_llm(), tools=[], allow_delegation=False, verbose=False,
                 max_iter=1, max_retry_limit=0)

def create_topic_task(agent):
    reference = json.dumps(get_terms(), ensure_ascii=False).replace('{','{{').replace('}','}}')
    return Task(description=RULES + '\nApproved glossary: ' + reference + '\nCandidate:\n{group_json}',
                expected_output='A schema v2 TopicConsolidation with exact membership and cited factual units.',
                agent=agent, output_pydantic=TopicConsolidation)
