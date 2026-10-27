"""Compatibility factories for canonical-interpretation taxonomy tasks.

The active batch/sample runner uses topic_pipeline's single-request transport;
these factories preserve configuration callers without enabling an SDK retry loop.
"""
from crewai import Agent, Task
from threadsense.agents.thread_interpreter import create_llm
from threadsense.agents.topic_contracts import TopicTaxonomy
from threadsense.agents.topic_consolidation import RULES
from threadsense.agents.topic_taxonomy import model_input
from threadsense.terminology import get_terms
import json

def create_topic_analyst():
    return Agent(role='ThreadSense Topic Analyst',
                 goal='Organize canonical Agent 1 interpretations into coherent named topics and identify outliers.',
                 backstory='You assign taxonomy membership without reinterpreting sources, judging answers or assessing severity.',
                 llm=create_llm(), tools=[], allow_delegation=False, verbose=False,
                 max_iter=1, max_retry_limit=0)

def create_topic_task(agent, *, payload):
    # Never interpolate an arbitrary full/raw group into the compatibility task.
    candidate = json.dumps(model_input(payload, get_terms()), ensure_ascii=False).replace('{','{{').replace('}','}}')
    return Task(description=RULES + '\nCandidate:\n' + candidate,
                expected_output='A v7 TopicTaxonomy: named topics with brief grouping rationales and stable member IDs, plus rejected_member_ids.',
                agent=agent, output_pydantic=TopicTaxonomy)
