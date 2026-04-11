"""
CLI wrapper for exporting analysis outputs to Jianying drafts.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.composition import CompositionSettings, HeadTailComposer, ShotPoolIndex
from src.exporters import export_to_jianying_draft
from src.exporters.jianying import DEFAULT_DRAFT_ROOT, DEFAULT_TEMPLATE_DIR
from src.models import load_analysis_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export an analysis output directory to a Jianying draft."
    )
    parser.add_argument(
        "output_dir",
        help="Analysis output directory containing report.json/scenes/audio.",
    )
    parser.add_argument(
        "--draft-root",
        help="Target Jianying draft root directory.",
    )
    parser.add_argument(
        "--template-dir",
        help="Plain Jianying template directory.",
    )
    parser.add_argument(
        "--draft-name",
        help="New draft folder name.",
    )
    parser.add_argument(
        "--compose-with-pool",
        help="Compose the tail from a shot pool directory before export.",
    )
    parser.add_argument(
        "--head-mode",
        choices=["first-scene", "fixed-seconds", "none"],
        default="first-scene",
        help="Rule for preserving the original head before filling from the pool.",
    )
    parser.add_argument(
        "--head-duration",
        type=float,
        help="Head duration in seconds when --head-mode=fixed-seconds.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for pool shot selection.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    artifacts = load_analysis_artifacts(args.output_dir)

    timeline = None
    if args.compose_with_pool:
        shot_pool = ShotPoolIndex.from_directory(args.compose_with_pool)
        settings = CompositionSettings(
            head_mode=args.head_mode,
            head_duration_us=(
                int(round(args.head_duration * 1_000_000))
                if args.head_duration is not None
                else None
            ),
            random_seed=args.seed,
        )
        composer = HeadTailComposer(shot_pool, settings)
        timeline = composer.compose(artifacts)
        composer.save_plan(
            Path(artifacts.output_dir) / "composition_plan.json",
            timeline,
        )

    draft_dir = export_to_jianying_draft(
        artifacts,
        timeline_clips=timeline,
        draft_root=args.draft_root or DEFAULT_DRAFT_ROOT,
        template_dir=args.template_dir or DEFAULT_TEMPLATE_DIR,
        draft_name=args.draft_name,
    )
    print(draft_dir)


if __name__ == "__main__":
    main()
