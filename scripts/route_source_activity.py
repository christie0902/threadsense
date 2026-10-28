"""Route a timezone-aware 24-hour source window and optionally persist announcements.

No model calls or embeddings. Use one writer and a new manifest path per invocation.
"""
import argparse
import json
from pathlib import Path

from threadsense.handoff_inputs import ROOT, CANONICAL, load_handoff
from threadsense.source_ingestion import fixture_routes, extraction_report
from threadsense.agents.topic_pipeline import write_json


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cutoff',required=True,help='ISO 8601 with Z or an explicit UTC offset.')
    parser.add_argument('--fixtures',type=Path,default=ROOT/'data/fixtures/slack_generated')
    parser.add_argument('--source-dir',type=Path,default=ROOT/'data/knowledge/decisions')
    parser.add_argument('--canonical',type=Path,default=CANONICAL,help='Carry any matching saved Agent 1 lineage/obligations.')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--write',action='store_true')
    mode.add_argument('--dry-run',action='store_true')
    parser.add_argument('--manifest',type=Path,help='Required fresh receipt path for --write; keep outside knowledge source directories.')
    args=parser.parse_args(argv)
    if args.write and (args.manifest is None or args.manifest.exists()):
        parser.error('--write requires a fresh --manifest path; reruns never overwrite receipts.')
    if args.manifest and args.manifest.resolve().is_relative_to(args.source_dir.resolve()):
        parser.error('Operational manifests must be outside knowledge source directories.')
    try:
        members=load_handoff(args.canonical) if args.canonical.exists() else []
        discussion,announcements,routing=fixture_routes(args.fixtures,cutoff=args.cutoff)
        report=extraction_report(discussion,announcements,routing,
            destination=args.source_dir if args.write else None,canonical_members=members)
        if args.write:write_json(args.manifest,report,exclusive=True)
    except (ValueError,OSError,KeyError,TypeError) as error:
        parser.error(str(error))
    print(json.dumps({k:v for k,v in report.items() if k not in {'entries','announcement_sources','record_outcomes'}},ensure_ascii=False,indent=2))
    return int(report['state']=='complete_with_failures')


if __name__=='__main__':raise SystemExit(main())
