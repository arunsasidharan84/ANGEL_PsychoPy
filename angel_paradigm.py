#!/usr/bin/env python3
"""PsychoPy recreation of the ANGEL Level 2/3 E-Prime paradigms.

This script intentionally keeps the paradigm logic explicit and auditable:
trials are generated from the ANGEL paper's block structure and the local
E-Prime resource folders, then logged to CSV with all condition columns.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_EPRIME = ROOT / "EPrimeFiles"

LEVEL_TEMPLATES = {
    "2": "CCS_EEG_ANGELv2_Level2_Template",
    "3": "CCS_EEG_ANGELv2_Level3_Template",
}

CATEGORIES = {
    "face_present": {
        "glob": "fpa*.png",
        "meaning": "meaningful",
        "family": "face",
        "description": "Mooney face",
    },
    "face_absent": {
        "glob": "faa*.png",
        "meaning": "ambiguous",
        "family": "face",
        "description": "distorted Mooney face",
    },
    "shape_present": {
        "files": ["knz_wob.png", "knz_bow.png"],
        "meaning": "meaningful",
        "family": "shape",
        "description": "Kanizsa triangle",
    },
    "shape_absent": {
        "files": ["nknz_wob.png", "nknz_bow.png"],
        "meaning": "ambiguous",
        "family": "shape",
        "description": "distorted Kanizsa",
    },
}

CATEGORY_SETS = {
    "all": list(CATEGORIES),
    "face": ["face_present", "face_absent"],
    "shape": ["shape_present", "shape_absent"],
}

BLOCK_CHOICES = [16, 8, 4]
TRIALS_PER_BLOCK_CHOICES = ["25+3", "20+3"]

KEYS = {
    "left": ["left", "z", "1"],
    "right": ["right", "slash", "2"],
    "quit": ["escape", "q"],
    "continue": ["space", "return"],
}


@dataclass(frozen=True)
class Trial:
    level: str
    block: int
    trial_in_block: int
    trial_type: str
    standard_category: str | None
    stimulus_category: str | None
    frequency_class: str
    omitted_category: str | None
    target_side: str | None
    visual_distractor_pos: str | None
    auditory_class: str
    auditory_offset_s: float | None
    corollary_mode: str | None
    correct_response: str | None
    reversal_phase: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the ANGEL Level 2/3 PsychoPy paradigm."
    )
    parser.add_argument(
        "--levels",
        default="2,3",
        help="Comma-separated levels to run: 2, 3, or 2,3. Default: 2,3.",
    )
    parser.add_argument(
        "--language",
        default="english",
        choices=["english", "hindi", "kannada"],
        help="Instruction/resource language. Default: english.",
    )
    parser.add_argument(
        "--participant",
        default="test",
        help="Participant/session identifier used in the output filename.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible schedules. Default: system random.",
    )
    parser.add_argument(
        "--practice",
        type=int,
        default=8,
        help="Practice active trials per level before the main run. Default: 8.",
    )
    parser.add_argument(
        "--blocks",
        type=int,
        choices=BLOCK_CHOICES,
        default=16,
        help="Blocks per level. Choices: 16, 8, or 4.",
    )
    parser.add_argument(
        "--fullscreen",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run fullscreen. Default: true.",
    )
    parser.add_argument(
        "--monitor",
        default="testMonitor",
        help="PsychoPy monitor name. Default: testMonitor.",
    )
    parser.add_argument(
        "--resource-root",
        type=Path,
        default=DEFAULT_EPRIME,
        help="Folder containing the EPrimeFiles templates.",
    )
    parser.add_argument(
        "--skip-instructions",
        action="store_true",
        help="Skip instruction slides and start directly with trials.",
    )
    parser.add_argument(
        "--category-set",
        default="all",
        choices=sorted(CATEGORY_SETS),
        help="Stimulus family to use: all, face, or shape. Face/shape-only runs work well with --blocks 8.",
    )
    parser.add_argument(
        "--paired-tone-offset-mode",
        default="continuous",
        choices=["continuous", "fixed"],
        help="Use uniform continuous paired-tone offsets, or the paper/E-Prime fixed offsets. Default: continuous.",
    )
    parser.add_argument(
        "--paired-tone-offset-min",
        type=float,
        default=-0.240,
        help="Minimum continuous paired-tone offset in seconds relative to visual onset. Default: -0.240.",
    )
    parser.add_argument(
        "--paired-tone-offset-max",
        type=float,
        default=0.160,
        help="Maximum continuous paired-tone offset in seconds relative to visual onset. Default: 0.160.",
    )
    parser.add_argument(
        "--cd-schedule",
        default="by-block",
        choices=["by-block", "within-block", "all-immediate", "all-delayed"],
        help="Level 2 corollary discharge schedule. Default matches the paper: by-block.",
    )
    parser.add_argument(
        "--intermix-level-blocks",
        action="store_true",
        help="Shuffle Level 2 and Level 3 blocks together instead of running each level contiguously.",
    )
    parser.add_argument(
        "--trials-per-block",
        default="25+3",
        choices=TRIALS_PER_BLOCK_CHOICES,
        help="Active+baseline trials per block. Default: 25+3.",
    )
    parser.add_argument(
        "--stim-duration",
        type=float,
        default=0.240,
        help="Visual target duration in seconds. Default: 0.240.",
    )
    parser.add_argument(
        "--response-window",
        type=float,
        default=0.700,
        help="Response window from visual onset in seconds. Default: 0.700.",
    )
    parser.add_argument(
        "--post-mask-min",
        type=float,
        default=0.200,
        help="Minimum post-trial masked baseline in seconds. Default: 0.200.",
    )
    parser.add_argument(
        "--post-mask-max",
        type=float,
        default=0.900,
        help="Maximum post-trial masked baseline in seconds. Default: 0.900.",
    )
    parser.add_argument(
        "--marker-mode",
        default="none",
        choices=["none", "lsl", "parallel", "both"],
        help="Send EEG/event markers over none, LSL, parallel TTL, or both.",
    )
    parser.add_argument(
        "--lsl-stream-name",
        default="ANGELMarkers",
        help="LSL marker stream name. Default: ANGELMarkers.",
    )
    parser.add_argument(
        "--parallel-address",
        default="0x0378",
        help="Parallel port address for TTL markers. Default: 0x0378.",
    )
    parser.add_argument(
        "--ttl-pulse-width",
        type=float,
        default=0.005,
        help="Parallel TTL pulse width before reset to zero, in seconds. Default: 0.005.",
    )
    parser.add_argument(
        "--no-config-dialog",
        action="store_true",
        help="Do not show the PsychoPy configuration dialog when no experiment arguments are supplied.",
    )
    args, _unknown = parser.parse_known_args()
    args.used_cli_config = any(
        arg == option or arg.startswith(f"{option}=")
        for arg in sys.argv[1:]
        for option in EXPERIMENT_CLI_OPTIONS
    )
    return args


EXPERIMENT_CLI_OPTIONS = {
    "--levels",
    "--language",
    "--participant",
    "--seed",
    "--practice",
    "--blocks",
    "--fullscreen",
    "--no-fullscreen",
    "--monitor",
    "--resource-root",
    "--skip-instructions",
    "--category-set",
    "--paired-tone-offset-mode",
    "--paired-tone-offset-min",
    "--paired-tone-offset-max",
    "--cd-schedule",
    "--intermix-level-blocks",
    "--trials-per-block",
    "--stim-duration",
    "--response-window",
    "--post-mask-min",
    "--post-mask-max",
    "--marker-mode",
    "--lsl-stream-name",
    "--parallel-address",
    "--ttl-pulse-width",
    "--no-config-dialog",
}


def get_psychopy():
    try:
        from psychopy import core, event, sound, visual  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PsychoPy is not installed in this Python environment. "
            "Run this with the PsychoPy app/runner, or install psychopy in "
            "the environment used to launch this script."
        ) from exc
    return core, event, sound, visual


def show_config_dialog(args: argparse.Namespace) -> argparse.Namespace:
    try:
        from psychopy import gui  # type: ignore
    except Exception:
        return args

    dialog_data = {
        "participant": args.participant,
        "levels": ["2,3", "2", "3"],
        "language": ["english", "hindi", "kannada"],
        "category_set": ["all", "face", "shape"],
        "blocks": [str(value) for value in BLOCK_CHOICES],
        "trials_per_block": TRIALS_PER_BLOCK_CHOICES,
        "practice": args.practice,
        "stim_duration": args.stim_duration,
        "response_window": args.response_window,
        "post_mask_min": args.post_mask_min,
        "post_mask_max": args.post_mask_max,
        "paired_tone_offset_mode": ["continuous", "fixed"],
        "paired_tone_offset_min": args.paired_tone_offset_min,
        "paired_tone_offset_max": args.paired_tone_offset_max,
        "cd_schedule": ["by-block", "within-block", "all-immediate", "all-delayed"],
        "marker_mode": ["none", "lsl", "parallel", "both"],
        "lsl_stream_name": args.lsl_stream_name,
        "parallel_address": args.parallel_address,
        "ttl_pulse_width": args.ttl_pulse_width,
        "intermix_level_blocks": args.intermix_level_blocks,
        "fullscreen": args.fullscreen,
        "skip_instructions": args.skip_instructions,
        "seed_blank_for_random": "" if args.seed is None else str(args.seed),
    }
    dlg = gui.DlgFromDict(
        dictionary=dialog_data,
        title="ANGEL PsychoPy Configuration",
        order=[
            "participant",
            "levels",
            "language",
            "category_set",
            "blocks",
            "trials_per_block",
            "practice",
            "stim_duration",
            "response_window",
            "post_mask_min",
            "post_mask_max",
            "paired_tone_offset_mode",
            "paired_tone_offset_min",
            "paired_tone_offset_max",
            "cd_schedule",
            "marker_mode",
            "lsl_stream_name",
            "parallel_address",
            "ttl_pulse_width",
            "intermix_level_blocks",
            "fullscreen",
            "skip_instructions",
            "seed_blank_for_random",
        ],
    )
    if not dlg.OK:
        raise KeyboardInterrupt

    args.participant = str(dialog_data["participant"])
    args.levels = str(dialog_data["levels"])
    args.language = str(dialog_data["language"])
    args.category_set = str(dialog_data["category_set"])
    args.blocks = int(dialog_data["blocks"])
    args.trials_per_block = str(dialog_data["trials_per_block"])
    args.practice = int(dialog_data["practice"])
    args.stim_duration = float(dialog_data["stim_duration"])
    args.response_window = float(dialog_data["response_window"])
    args.post_mask_min = float(dialog_data["post_mask_min"])
    args.post_mask_max = float(dialog_data["post_mask_max"])
    args.paired_tone_offset_mode = str(dialog_data["paired_tone_offset_mode"])
    args.paired_tone_offset_min = float(dialog_data["paired_tone_offset_min"])
    args.paired_tone_offset_max = float(dialog_data["paired_tone_offset_max"])
    args.cd_schedule = str(dialog_data["cd_schedule"])
    args.marker_mode = str(dialog_data["marker_mode"])
    args.lsl_stream_name = str(dialog_data["lsl_stream_name"])
    args.parallel_address = str(dialog_data["parallel_address"])
    args.ttl_pulse_width = float(dialog_data["ttl_pulse_width"])
    args.intermix_level_blocks = bool(dialog_data["intermix_level_blocks"])
    args.fullscreen = bool(dialog_data["fullscreen"])
    args.skip_instructions = bool(dialog_data["skip_instructions"])
    seed_value = str(dialog_data["seed_blank_for_random"]).strip()
    args.seed = int(seed_value) if seed_value else None
    return args


def flatten(items: Iterable[Iterable[str]]) -> list[str]:
    return [value for group in items for value in group]


def parse_trials_per_block(value: str) -> tuple[int, int]:
    active, baseline = value.split("+", 1)
    return int(active), int(baseline)


def validate_config(args: argparse.Namespace) -> None:
    if args.paired_tone_offset_min > args.paired_tone_offset_max:
        raise SystemExit("--paired-tone-offset-min must be <= --paired-tone-offset-max.")
    if args.post_mask_min > args.post_mask_max:
        raise SystemExit("--post-mask-min must be <= --post-mask-max.")
    if args.stim_duration <= 0 or args.response_window <= 0:
        raise SystemExit("--stim-duration and --response-window must be positive.")
    if args.stim_duration < max(0.0, args.paired_tone_offset_max):
        raise SystemExit("--stim-duration must be >= positive paired-tone offset maximum.")
    balance_unit = len(CATEGORY_SETS[args.category_set]) * 2
    if args.blocks % balance_unit != 0:
        raise SystemExit(
            f"{args.category_set!r} runs need blocks in multiples of {balance_unit} "
            "to preserve balanced category x side blocks."
        )


def side_to_key(side: str | None) -> str | None:
    if side == "left":
        return "left"
    if side == "right":
        return "right"
    return None


def load_assets(template_dir: Path, language: str) -> dict:
    resources = template_dir / "resources"
    language_dir = template_dir / language
    category_files: dict[str, list[Path]] = {}

    for category, spec in CATEGORIES.items():
        if "glob" in spec:
            files = sorted(resources.glob(str(spec["glob"])))
        else:
            files = [resources / name for name in spec["files"]]  # type: ignore[index]
        missing = [str(path) for path in files if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Missing stimulus files: {missing}")
        category_files[category] = files

    return {
        "resources": resources,
        "language": language_dir,
        "categories": category_files,
        "checkerboard": resources / "cb.png",
        "fixation": resources / "plus.png",
        "blank": resources / "blank.png",
        "practice": resources / "practice.png",
        "paired_tones": {
            "standard": [
                resources / "std1.wav",
                resources / "std2.wav",
                resources / "std3.wav",
            ],
            "deviant": [
                resources / "deviant1.wav",
                resources / "deviant2.wav",
                resources / "deviant3.wav",
            ],
            "blank": [resources / "blank.wav"],
        },
        "single_tones": {
            "standard": resources / "std.wav",
            "deviant": resources / "deviant.wav",
        },
        "corollary": resources / "corollary.wav",
        "nocorollary": resources / "nocorollary.wav",
        "bell_start": resources / "bellStart.wav",
        "bell_end": resources / "bellEnd.wav",
    }


def generate_level_trials(
    level: str,
    blocks: int,
    rng: random.Random,
    category_set: str = "all",
    paired_tone_offset_mode: str = "continuous",
    paired_tone_offset_min: float = -0.240,
    paired_tone_offset_max: float = 0.160,
    cd_schedule: str = "by-block",
    active_trials_per_block: int = 25,
    baseline_trials_per_block: int = 3,
) -> list[Trial]:
    categories = CATEGORY_SETS[category_set]
    block_specs: list[tuple[str, str]] = []

    while len(block_specs) < blocks:
        block_specs.extend((category, side) for category in categories for side in ["left", "right"])
    block_specs = block_specs[:blocks]
    rng.shuffle(block_specs)

    if level == "2":
        immediate_blocks = set(rng.sample(range(1, blocks + 1), blocks // 2))
    else:
        immediate_blocks = set()

    trials: list[Trial] = []
    for block_index, (standard_category, standard_side) in enumerate(block_specs, start=1):
        other_side = "right" if standard_side == "left" else "left"
        candidates = [category for category in categories if category != standard_category]
        if len(candidates) >= 2:
            omitted = rng.choice(candidates)
            rare_categories = [category for category in candidates if category != omitted]
        else:
            omitted = None
            rare_categories = [candidates[0], candidates[0]]

        frequent_count = round(active_trials_per_block * 0.80)
        rare_count = active_trials_per_block - frequent_count
        rare_a_count = (rare_count + 1) // 2
        rare_b_count = rare_count - rare_a_count

        active: list[tuple[str, str]] = [(standard_category, "frequent")] * frequent_count
        active.extend((rare_categories[0], "rare") for _ in range(rare_a_count))
        active.extend((rare_categories[1], "rare") for _ in range(rare_b_count))
        rng.shuffle(active)

        blank_count = max(1, round(active_trials_per_block * 0.08))
        standard_count = frequent_count
        deviant_count = active_trials_per_block - standard_count - blank_count
        auditory = ["standard"] * standard_count
        auditory.extend("deviant" for _ in range(deviant_count))
        auditory.extend("blank" for _ in range(blank_count))
        rng.shuffle(auditory)
        block_cd_modes = make_cd_modes(cd_schedule, block_index, immediate_blocks, active_trials_per_block, rng)

        for trial_index, ((stimulus_category, frequency_class), auditory_class) in enumerate(
            zip(active, auditory), start=1
        ):
            target_side = standard_side if frequency_class == "frequent" else other_side
            auditory_offset = sample_paired_tone_offset(
                auditory_class,
                paired_tone_offset_mode,
                paired_tone_offset_min,
                paired_tone_offset_max,
                rng,
            )
            visual_distractor_pos = rng.choice(["top", "bottom"])
            reversal_phase = None
            correct_response = None

            if level == "2":
                correct_response = side_to_key(target_side)
                corollary_mode = block_cd_modes[trial_index - 1]
            else:
                corollary_mode = None
                reversal_phase = "pre_reversal" if block_index <= blocks // 2 else "post_reversal"
                meaning = CATEGORIES[stimulus_category]["meaning"]
                if reversal_phase == "pre_reversal":
                    correct_response = "left" if meaning == "meaningful" else "right"
                else:
                    correct_response = "right" if meaning == "meaningful" else "left"

            trials.append(
                Trial(
                    level=level,
                    block=block_index,
                    trial_in_block=trial_index,
                    trial_type="active",
                    standard_category=standard_category,
                    stimulus_category=stimulus_category,
                    frequency_class=frequency_class,
                    omitted_category=omitted,
                    target_side=target_side,
                    visual_distractor_pos=visual_distractor_pos,
                    auditory_class=auditory_class,
                    auditory_offset_s=auditory_offset,
                    corollary_mode=corollary_mode,
                    correct_response=correct_response,
                    reversal_phase=reversal_phase,
                )
            )

        for baseline_index in range(1, baseline_trials_per_block + 1):
            trials.append(
                Trial(
                    level=level,
                    block=block_index,
                    trial_in_block=active_trials_per_block + baseline_index,
                    trial_type="baseline",
                    standard_category=standard_category,
                    stimulus_category=None,
                    frequency_class="baseline",
                    omitted_category=omitted,
                    target_side=None,
                    visual_distractor_pos=None,
                    auditory_class="blank",
                    auditory_offset_s=None,
                    corollary_mode=None,
                    correct_response=None,
                    reversal_phase=None,
                )
            )

    return trials


def make_cd_modes(
    cd_schedule: str,
    block_index: int,
    immediate_blocks: set[int],
    active_trials_per_block: int,
    rng: random.Random,
) -> list[str]:
    if cd_schedule == "all-immediate":
        return ["immediate"] * active_trials_per_block
    if cd_schedule == "all-delayed":
        return ["delayed"] * active_trials_per_block
    if cd_schedule == "within-block":
        immediate_count = (active_trials_per_block + 1) // 2
        modes = ["immediate"] * immediate_count
        modes.extend("delayed" for _ in range(active_trials_per_block - immediate_count))
        rng.shuffle(modes)
        return modes
    return ["immediate" if block_index in immediate_blocks else "delayed"] * active_trials_per_block


def sample_paired_tone_offset(
    auditory_class: str,
    paired_tone_offset_mode: str,
    paired_tone_offset_min: float,
    paired_tone_offset_max: float,
    rng: random.Random,
) -> float | None:
    if auditory_class == "blank":
        return None
    if paired_tone_offset_mode == "fixed":
        return rng.choice([-0.240, -0.040, 0.160])
    return rng.uniform(paired_tone_offset_min, paired_tone_offset_max)


def split_blocks(trials: list[Trial]) -> list[list[Trial]]:
    blocks: dict[int, list[Trial]] = {}
    for trial in trials:
        blocks.setdefault(trial.block, []).append(trial)
    return [blocks[block] for block in sorted(blocks)]


def generate_practice(
    level: str,
    count: int,
    rng: random.Random,
    args: argparse.Namespace,
) -> list[Trial]:
    if count <= 0:
        return []
    active_trials, baseline_trials = parse_trials_per_block(args.trials_per_block)
    trials = [
        trial
        for trial in generate_level_trials(
            level,
            1,
            rng,
            args.category_set,
            args.paired_tone_offset_mode,
            args.paired_tone_offset_min,
            args.paired_tone_offset_max,
            args.cd_schedule,
            active_trials,
            baseline_trials,
        )
        if trial.trial_type == "active"
    ]
    return [
        Trial(
            **{
                **trial.__dict__,
                "block": 0,
                "trial_in_block": index,
            }
        )
        for index, trial in enumerate(trials[:count], start=1)
    ]


def wait_for_continue(event) -> None:
    event.clearEvents()
    allowed = KEYS["continue"] + KEYS["quit"]
    while True:
        keys = event.waitKeys(keyList=allowed)
        if keys and keys[0] in KEYS["quit"]:
            raise KeyboardInterrupt
        if keys:
            return


def show_image_slide(win, event, visual, sound, image_path: Path, audio_path: Path | None = None) -> None:
    image_path = existing_case_variant(image_path)
    if audio_path:
        audio_path = existing_case_variant(audio_path)
    if not image_path.exists():
        return
    slide = visual.ImageStim(win, image=str(image_path), size=(1.333, 1.0), units="height")
    audio = sound.Sound(str(audio_path)) if audio_path and audio_path.exists() else None
    if audio:
        audio.play()
    slide.draw()
    win.flip()
    wait_for_continue(event)
    if audio:
        audio.stop()


def existing_case_variant(path: Path) -> Path:
    if path.exists():
        return path
    if not path.parent.exists():
        return path
    wanted = path.name.lower()
    for candidate in path.parent.iterdir():
        if candidate.name.lower() == wanted:
            return candidate
    return path


def make_stimuli(win, visual, assets: dict) -> dict:
    target_size = (0.32, 0.41)
    distractor_size = (0.12, 0.085)
    return {
        "left_mask": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=(-0.42, 0), size=target_size, units="height"),
        "right_mask": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=(0.42, 0), size=target_size, units="height"),
        "fix": visual.ImageStim(win, image=str(assets["fixation"]), pos=(0, 0), size=(0.075, 0.075), units="height"),
        "top_left_distractor": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=(-0.18, 0.34), size=distractor_size, units="height"),
        "top_right_distractor": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=(0.18, 0.34), size=distractor_size, units="height"),
        "bottom_left_distractor": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=(-0.18, -0.34), size=distractor_size, units="height"),
        "bottom_right_distractor": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=(0.18, -0.34), size=distractor_size, units="height"),
        "target_size": target_size,
    }


def draw_masks(win, stimuli: dict, distractor_pos: str | None = None) -> None:
    stimuli["left_mask"].draw()
    stimuli["right_mask"].draw()
    stimuli["fix"].draw()
    if distractor_pos == "top":
        stimuli["top_left_distractor"].draw()
        stimuli["top_right_distractor"].draw()
    elif distractor_pos == "bottom":
        stimuli["bottom_left_distractor"].draw()
        stimuli["bottom_right_distractor"].draw()


def play_sound_at(core, sound_obj, trial_clock, absolute_s: float) -> float:
    while trial_clock.getTime() < absolute_s:
        core.wait(0.001, hogCPUperiod=0.001)
    sound_obj.play()
    return trial_clock.getTime()


def wait_until(core, trial_clock, absolute_s: float) -> None:
    while trial_clock.getTime() < absolute_s:
        core.wait(0.001, hogCPUperiod=0.001)


class MarkerSender:
    CODES = {
        "block_start": 1,
        "trial_start": 10,
        "baseline_start": 11,
        "paired_standard": 20,
        "paired_deviant": 21,
        "visual_frequent": 30,
        "visual_rare": 31,
        "visual_offset": 32,
        "response_left": 40,
        "response_right": 41,
        "response_miss": 42,
        "cd_immediate": 50,
        "cd_delayed": 51,
        "trial_end": 90,
    }

    def __init__(self, args: argparse.Namespace, core, exp_clock) -> None:
        self.args = args
        self.core = core
        self.exp_clock = exp_clock
        self.outlet = None
        self.port = None

        if args.marker_mode in ["lsl", "both"]:
            try:
                from pylsl import StreamInfo, StreamOutlet  # type: ignore

                info = StreamInfo(args.lsl_stream_name, "Markers", 1, 0, "string")
                self.outlet = StreamOutlet(info)
            except Exception as exc:
                print(f"WARNING: Could not initialize LSL markers: {exc}", file=sys.stderr)

        if args.marker_mode in ["parallel", "both"]:
            try:
                from psychopy import parallel  # type: ignore

                address = int(str(args.parallel_address), 0)
                self.port = parallel.ParallelPort(address=address)
                self.port.setData(0)
            except Exception as exc:
                print(f"WARNING: Could not initialize parallel TTL markers: {exc}", file=sys.stderr)

    def send(self, label: str, code: int | None = None) -> float:
        marker_code = self.CODES.get(label, 0) if code is None else code
        timestamp = self.exp_clock.getTime()
        sample = f"{marker_code}:{label}"

        if self.outlet is not None:
            try:
                self.outlet.push_sample([sample])
            except Exception as exc:
                print(f"WARNING: LSL marker failed: {exc}", file=sys.stderr)

        if self.port is not None:
            try:
                self.port.setData(marker_code)
                self.core.callLater(self.args.ttl_pulse_width, self.port.setData, 0)
            except Exception as exc:
                print(f"WARNING: Parallel marker failed: {exc}", file=sys.stderr)

        return timestamp


def run_trial(
    trial: Trial,
    args: argparse.Namespace,
    win,
    core,
    event,
    visual,
    sound,
    stimuli: dict,
    assets: dict,
    rng: random.Random,
    trial_global_index: int,
    exp_clock,
    markers: MarkerSender,
) -> dict:
    event.clearEvents()
    response_keys = flatten([KEYS["left"], KEYS["right"], KEYS["quit"]])
    trial_clock = core.Clock()
    response = None
    rt = None
    accuracy = None
    paired_tone_onset = None
    paired_tone_onset_global = None
    corollary_onset = None
    corollary_onset_global = None
    paired_tone_file = None
    visual_onset = None
    visual_onset_global = None
    visual_offset = None
    visual_offset_global = None
    response_window_end = None
    response_window_end_global = None
    post_mask_start = None
    post_mask_start_global = None
    post_mask_end = None
    post_mask_end_global = None
    trial_start_global = exp_clock.getTime()
    markers.send("trial_start")

    if trial.trial_type == "baseline":
        stimuli["fix"].draw()
        win.flip()
        baseline_onset = exp_clock.getTime()
        markers.send("baseline_start")
        baseline_duration = args.response_window + rng.uniform(args.post_mask_min, args.post_mask_max)
        core.wait(baseline_duration)
        trial_end_global = exp_clock.getTime()
        markers.send("trial_end")
        return row_from_trial(
            trial,
            trial_global_index,
            None,
            None,
            None,
            None,
            None,
            trial_start_global=trial_start_global,
            baseline_onset_global=baseline_onset,
            post_mask_duration=baseline_duration,
            trial_end_global=trial_end_global,
        )

    target_path = rng.choice(assets["categories"][trial.stimulus_category])
    target_pos = (-0.42, 0) if trial.target_side == "left" else (0.42, 0)
    target = visual.ImageStim(
        win,
        image=str(target_path),
        pos=target_pos,
        size=stimuli["target_size"],
        units="height",
    )

    tone = None
    tone_start_s = None
    if trial.auditory_class != "blank" and trial.auditory_offset_s is not None:
        tone_path = paired_tone_path(trial, args, assets)
        paired_tone_file = tone_path.name
        tone = sound.Sound(str(tone_path))
        pre_stim_s = max(0.240, -args.paired_tone_offset_min)
        tone_start_s = max(0.0, pre_stim_s + trial.auditory_offset_s)
    else:
        pre_stim_s = max(0.240, -args.paired_tone_offset_min)

    # Pre-stimulus mask gives room for negative paired-tone offsets.
    draw_masks(win, stimuli, trial.visual_distractor_pos)
    win.flip()
    trial_clock.reset()

    if tone and tone_start_s is not None and tone_start_s < pre_stim_s:
        paired_tone_onset = play_sound_at(core, tone, trial_clock, tone_start_s)
        paired_tone_onset_global = exp_clock.getTime()
        markers.send(f"paired_{trial.auditory_class}")
    tone_pending = tone is not None and tone_start_s is not None and tone_start_s >= pre_stim_s

    while trial_clock.getTime() < pre_stim_s:
        core.wait(0.001, hogCPUperiod=0.001)

    draw_masks(win, stimuli, trial.visual_distractor_pos)
    target.draw()
    win.flip()
    visual_onset = trial_clock.getTime()
    visual_onset_global = exp_clock.getTime()
    markers.send(f"visual_{trial.frequency_class}")

    while trial_clock.getTime() < visual_onset + args.stim_duration:
        if tone_pending and trial_clock.getTime() >= tone_start_s:
            tone.play()
            paired_tone_onset = trial_clock.getTime()
            paired_tone_onset_global = exp_clock.getTime()
            markers.send(f"paired_{trial.auditory_class}")
            tone_pending = False
        keys = event.getKeys(keyList=response_keys, timeStamped=trial_clock)
        if keys and keys[0][0] in KEYS["quit"]:
            raise KeyboardInterrupt
        if keys and response is None:
            response, timestamp = normalize_response(keys[0])
            rt = timestamp - visual_onset
            markers.send(f"response_{response}")
            if trial.level == "2" and trial.corollary_mode == "immediate":
                sound.Sound(str(assets["corollary"])).play()
                corollary_onset = trial_clock.getTime()
                corollary_onset_global = exp_clock.getTime()
                markers.send("cd_immediate")
        core.wait(0.001, hogCPUperiod=0.001)

    draw_masks(win, stimuli, trial.visual_distractor_pos)
    win.flip()
    visual_offset = trial_clock.getTime()
    visual_offset_global = exp_clock.getTime()
    markers.send("visual_offset")

    response_deadline = visual_onset + args.response_window
    while trial_clock.getTime() < response_deadline:
        if tone_pending and trial_clock.getTime() >= tone_start_s:
            tone.play()
            paired_tone_onset = trial_clock.getTime()
            paired_tone_onset_global = exp_clock.getTime()
            markers.send(f"paired_{trial.auditory_class}")
            tone_pending = False
        keys = event.getKeys(keyList=response_keys, timeStamped=trial_clock)
        if keys and keys[0][0] in KEYS["quit"]:
            raise KeyboardInterrupt
        if keys and response is None:
            response, timestamp = normalize_response(keys[0])
            rt = timestamp - visual_onset
            markers.send(f"response_{response}")
            if trial.level == "2" and trial.corollary_mode == "immediate":
                sound.Sound(str(assets["corollary"])).play()
                corollary_onset = trial_clock.getTime()
                corollary_onset_global = exp_clock.getTime()
                markers.send("cd_immediate")
        core.wait(0.001, hogCPUperiod=0.001)

    response_window_end = trial_clock.getTime()
    response_window_end_global = exp_clock.getTime()
    post_mask_start = response_deadline
    post_mask_start_global = exp_clock.getTime()
    post_mask_duration = rng.uniform(args.post_mask_min, args.post_mask_max)
    post_mask_end = post_mask_start + post_mask_duration

    if response is None:
        markers.send("response_miss")

    if trial.level == "2" and trial.corollary_mode == "delayed":
        max_delay = max(0.0, min(0.350, post_mask_duration - 0.005))
        delay = rng.uniform(0.050, max_delay) if max_delay >= 0.050 else max_delay
        play_at = post_mask_start + delay
        corollary_onset = play_sound_at(core, sound.Sound(str(assets["nocorollary"])), trial_clock, play_at)
        corollary_onset_global = exp_clock.getTime()
        markers.send("cd_delayed")

    accuracy = None
    if trial.correct_response:
        accuracy = int(response == trial.correct_response)

    wait_until(core, trial_clock, post_mask_end)
    post_mask_end_global = exp_clock.getTime()
    markers.send("trial_end")

    return row_from_trial(
        trial,
        trial_global_index,
        target_path.name,
        response,
        rt,
        accuracy,
        paired_tone_onset,
        corollary_onset,
        paired_tone_file,
        visual_onset,
        trial_start_global=trial_start_global,
        paired_tone_onset_global=paired_tone_onset_global,
        visual_onset_global=visual_onset_global,
        visual_offset=visual_offset,
        visual_offset_global=visual_offset_global,
        response_window_end=response_window_end,
        response_window_end_global=response_window_end_global,
        post_mask_start=post_mask_start,
        post_mask_start_global=post_mask_start_global,
        post_mask_duration=post_mask_duration,
        post_mask_end=post_mask_end,
        post_mask_end_global=post_mask_end_global,
        corollary_onset_global=corollary_onset_global,
        trial_end_global=post_mask_end_global,
    )


def paired_tone_path(trial: Trial, args: argparse.Namespace, assets: dict) -> Path:
    if args.paired_tone_offset_mode == "continuous":
        return assets["single_tones"][trial.auditory_class]
    fixed_offsets = [-0.240, -0.040, 0.160]
    nearest_index = min(
        range(len(fixed_offsets)),
        key=lambda index: abs(fixed_offsets[index] - float(trial.auditory_offset_s)),
    )
    return assets["paired_tones"][trial.auditory_class][nearest_index]


def normalize_response(key_with_time: tuple[str, float]) -> tuple[str, float]:
    key, timestamp = key_with_time
    if key in KEYS["left"]:
        return "left", timestamp
    if key in KEYS["right"]:
        return "right", timestamp
    return key, timestamp


def row_from_trial(
    trial: Trial,
    trial_global_index: int,
    stimulus_file: str | None,
    response: str | None,
    rt: float | None,
    accuracy: int | None,
    paired_tone_onset: float | None,
    corollary_onset: float | None = None,
    paired_tone_file: str | None = None,
    visual_onset: float | None = None,
    trial_start_global: float | None = None,
    baseline_onset_global: float | None = None,
    paired_tone_onset_global: float | None = None,
    visual_onset_global: float | None = None,
    visual_offset: float | None = None,
    visual_offset_global: float | None = None,
    response_window_end: float | None = None,
    response_window_end_global: float | None = None,
    post_mask_start: float | None = None,
    post_mask_start_global: float | None = None,
    post_mask_duration: float | None = None,
    post_mask_end: float | None = None,
    post_mask_end_global: float | None = None,
    corollary_onset_global: float | None = None,
    trial_end_global: float | None = None,
) -> dict:
    return {
        "trial_global_index": trial_global_index,
        "level": trial.level,
        "block": trial.block,
        "trial_in_block": trial.trial_in_block,
        "trial_type": trial.trial_type,
        "standard_category": trial.standard_category,
        "stimulus_category": trial.stimulus_category,
        "stimulus_file": stimulus_file,
        "stimulus_family": CATEGORIES[trial.stimulus_category]["family"] if trial.stimulus_category else None,
        "stimulus_meaning": CATEGORIES[trial.stimulus_category]["meaning"] if trial.stimulus_category else None,
        "frequency_class": trial.frequency_class,
        "omitted_category": trial.omitted_category,
        "target_side": trial.target_side,
        "visual_distractor_pos": trial.visual_distractor_pos,
        "auditory_class": trial.auditory_class,
        "auditory_offset_s": trial.auditory_offset_s,
        "paired_tone_file": paired_tone_file,
        "paired_tone_onset_s": paired_tone_onset,
        "paired_tone_onset_global_s": paired_tone_onset_global,
        "visual_onset_s": visual_onset,
        "visual_onset_global_s": visual_onset_global,
        "visual_offset_s": visual_offset,
        "visual_offset_global_s": visual_offset_global,
        "response_window_end_s": response_window_end,
        "response_window_end_global_s": response_window_end_global,
        "baseline_onset_global_s": baseline_onset_global,
        "post_mask_start_s": post_mask_start,
        "post_mask_start_global_s": post_mask_start_global,
        "post_mask_duration_s": post_mask_duration,
        "post_mask_end_s": post_mask_end,
        "post_mask_end_global_s": post_mask_end_global,
        "corollary_mode": trial.corollary_mode,
        "corollary_onset_s": corollary_onset,
        "corollary_onset_global_s": corollary_onset_global,
        "reversal_phase": trial.reversal_phase,
        "correct_response": trial.correct_response,
        "response": response,
        "rt_s": rt,
        "accuracy": accuracy,
        "trial_start_global_s": trial_start_global,
        "trial_end_global_s": trial_end_global,
        "trial_duration_s": (
            trial_end_global - trial_start_global
            if trial_end_global is not None and trial_start_global is not None
            else None
        ),
    }


def show_feedback(win, event, visual, sound, language_dir: Path, recent_rows: list[dict]) -> None:
    active = [row for row in recent_rows if row["trial_type"] == "active" and row["accuracy"] is not None]
    if not active:
        return
    accuracy = sum(int(row["accuracy"]) for row in active) / len(active)
    correct_rts = [float(row["rt_s"]) for row in active if row["accuracy"] == 1 and row["rt_s"] not in [None, ""]]
    mean_rt = sum(correct_rts) / len(correct_rts) if correct_rts else None

    if accuracy < 0.85:
        feedback = "FeedbackWelltried"
    elif accuracy <= 0.95:
        feedback = "FeedbackGoodjob"
    else:
        feedback = "FeedbackOutstanding"

    show_image_slide(
        win,
        event,
        visual,
        sound,
        language_dir / f"{feedback}.PNG",
        language_dir / f"{feedback}.mp3",
    )

    text = f"Accuracy: {accuracy * 100:.1f}%"
    if mean_rt is not None:
        text += f"\nMean RT: {mean_rt * 1000:.0f} ms"
    stim = visual.TextStim(win, text=text, color="white", height=0.035, units="height")
    stim.draw()
    win.flip()
    core_wait = 1.5
    try:
        from psychopy import core  # type: ignore
        core.wait(core_wait)
    except Exception:
        pass


def run_level(
    level: str,
    args: argparse.Namespace,
    win,
    core,
    event,
    visual,
    sound,
    writer: csv.DictWriter,
    output_file,
    rng: random.Random,
    trial_counter: int,
    exp_clock,
    markers: MarkerSender,
) -> int:
    template_dir = args.resource_root / LEVEL_TEMPLATES[level]
    assets = load_assets(template_dir, args.language)
    stimuli = make_stimuli(win, visual, assets)
    active_trials, baseline_trials = parse_trials_per_block(args.trials_per_block)
    block_trial_count = active_trials + baseline_trials

    if not args.skip_instructions:
        show_image_slide(win, event, visual, sound, assets["language"] / "WelcomeLevel1.PNG", assets["language"] / "WelcomeLevel1.mp3")
        show_image_slide(win, event, visual, sound, assets["language"] / "InstructionLevel1.PNG", assets["language"] / "InstructionLevel1.mp3")
        show_image_slide(win, event, visual, sound, assets["language"] / "PracticeStart.PNG", assets["language"] / "PracticeStart.mp3")

    for trial in generate_practice(level, args.practice, rng, args):
        trial_counter += 1
        row = run_trial(trial, args, win, core, event, visual, sound, stimuli, assets, rng, trial_counter, exp_clock, markers)
        row["phase"] = "practice"
        writer.writerow(row)
        output_file.flush()

    if args.practice and not args.skip_instructions:
        show_image_slide(win, event, visual, sound, assets["language"] / "PracticeEnd.PNG", assets["language"] / "PracticeEnd.mp3")
    if not args.skip_instructions:
        show_image_slide(win, event, visual, sound, assets["language"] / "ExperimentStart.PNG", assets["language"] / "ExperimentStart.mp3")

    block_rows: list[dict] = []
    for trial in generate_level_trials(
        level,
        args.blocks,
        rng,
        args.category_set,
        args.paired_tone_offset_mode,
        args.paired_tone_offset_min,
        args.paired_tone_offset_max,
        args.cd_schedule,
        active_trials,
        baseline_trials,
    ):
        if trial.trial_in_block == 1:
            markers.send("block_start")
            show_image_slide(win, event, visual, sound, assets["language"] / "Ready.PNG", assets["language"] / "Ready.mp3")

        trial_counter += 1
        row = run_trial(trial, args, win, core, event, visual, sound, stimuli, assets, rng, trial_counter, exp_clock, markers)
        row["phase"] = "main"
        writer.writerow(row)
        output_file.flush()
        block_rows.append(row)

        if trial.trial_in_block == block_trial_count and trial.block % 2 == 0:
            show_feedback(win, event, visual, sound, assets["language"], block_rows[-2 * block_trial_count:])

        if level == "3" and trial.block == args.blocks // 2 and trial.trial_in_block == block_trial_count:
            reversal = visual.TextStim(
                win,
                text="Rule change\n\nMeaningful: RIGHT\nAmbiguous: LEFT\n\nPress space to continue",
                color="white",
                height=0.04,
                units="height",
            )
            reversal.draw()
            win.flip()
            wait_for_continue(event)

    if not args.skip_instructions:
        show_image_slide(win, event, visual, sound, assets["language"] / "ExperimentEnd.PNG", assets["language"] / "ExperimentEnd.mp3")

    return trial_counter


def run_intermixed_levels(
    levels: list[str],
    args: argparse.Namespace,
    win,
    core,
    event,
    visual,
    sound,
    writer: csv.DictWriter,
    output_file,
    rng: random.Random,
    trial_counter: int,
    exp_clock,
    markers: MarkerSender,
) -> int:
    assets_by_level = {
        level: load_assets(args.resource_root / LEVEL_TEMPLATES[level], args.language)
        for level in levels
    }
    stimuli_by_level = {
        level: make_stimuli(win, visual, assets_by_level[level])
        for level in levels
    }
    active_trials, baseline_trials = parse_trials_per_block(args.trials_per_block)
    block_trial_count = active_trials + baseline_trials

    if not args.skip_instructions:
        for level in levels:
            assets = assets_by_level[level]
            show_image_slide(win, event, visual, sound, assets["language"] / "WelcomeLevel1.PNG", assets["language"] / "WelcomeLevel1.mp3")
            show_image_slide(win, event, visual, sound, assets["language"] / "InstructionLevel1.PNG", assets["language"] / "InstructionLevel1.mp3")

    for level in levels:
        for trial in generate_practice(level, args.practice, rng, args):
            trial_counter += 1
            row = run_trial(
                trial,
                args,
                win,
                core,
                event,
                visual,
                sound,
                stimuli_by_level[level],
                assets_by_level[level],
                rng,
                trial_counter,
                exp_clock,
                markers,
            )
            row["phase"] = "practice"
            writer.writerow(row)
            output_file.flush()

    level_blocks: list[tuple[str, list[Trial]]] = []
    for level in levels:
        trials = generate_level_trials(
            level,
            args.blocks,
            rng,
            args.category_set,
            args.paired_tone_offset_mode,
            args.paired_tone_offset_min,
            args.paired_tone_offset_max,
            args.cd_schedule,
            active_trials,
            baseline_trials,
        )
        level_blocks.extend((level, block) for block in split_blocks(trials))
    rng.shuffle(level_blocks)

    recent_rows: list[dict] = []
    completed_level3_blocks = 0
    for mixed_block_index, (level, block_trials) in enumerate(level_blocks, start=1):
        assets = assets_by_level[level]
        stimuli = stimuli_by_level[level]
        markers.send("block_start")
        show_image_slide(win, event, visual, sound, assets["language"] / "Ready.PNG", assets["language"] / "Ready.mp3")

        for trial in block_trials:
            trial_counter += 1
            row = run_trial(trial, args, win, core, event, visual, sound, stimuli, assets, rng, trial_counter, exp_clock, markers)
            row["phase"] = "main"
            row["mixed_block_index"] = mixed_block_index
            writer.writerow(row)
            output_file.flush()
            recent_rows.append(row)

        if level == "3":
            completed_level3_blocks += 1
            if completed_level3_blocks == args.blocks // 2:
                reversal = visual.TextStim(
                    win,
                    text="Rule change\n\nMeaningful: RIGHT\nAmbiguous: LEFT\n\nPress space to continue",
                    color="white",
                    height=0.04,
                    units="height",
                )
                reversal.draw()
                win.flip()
                wait_for_continue(event)

        if mixed_block_index % 2 == 0:
            show_feedback(win, event, visual, sound, assets["language"], recent_rows[-2 * block_trial_count:])

    if not args.skip_instructions and levels:
        assets = assets_by_level[levels[-1]]
        show_image_slide(win, event, visual, sound, assets["language"] / "ExperimentEnd.PNG", assets["language"] / "ExperimentEnd.mp3")
    return trial_counter


def main() -> int:
    args = parse_args()
    if not args.used_cli_config and not args.no_config_dialog:
        args = show_config_dialog(args)
    levels = [level.strip() for level in args.levels.split(",") if level.strip()]
    invalid = [level for level in levels if level not in LEVEL_TEMPLATES]
    if invalid:
        raise SystemExit(f"Invalid level(s): {invalid}. Use 2, 3, or 2,3.")
    validate_config(args)

    rng = random.Random(args.seed)
    output_dir = ROOT / "data"
    output_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"angel_{args.participant}_{'_'.join(levels)}_{stamp}.csv"

    core, event, sound, visual = get_psychopy()
    win = visual.Window(
        fullscr=args.fullscreen,
        color=[0, 0, 0],
        units="height",
        monitor=args.monitor,
    )
    exp_clock = core.Clock()
    markers = MarkerSender(args, core, exp_clock)

    fieldnames = list(row_from_trial(
        Trial("2", 0, 0, "baseline", None, None, "baseline", None, None, None, "blank", None, None, None, None),
        0,
        None,
        None,
        None,
        None,
        None,
    ).keys())
    fieldnames.append("phase")
    fieldnames.append("mixed_block_index")

    trial_counter = 0
    try:
        with output_path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            if args.intermix_level_blocks:
                trial_counter = run_intermixed_levels(
                    levels,
                    args,
                    win,
                    core,
                    event,
                    visual,
                    sound,
                    writer,
                    output_file,
                    rng,
                    trial_counter,
                    exp_clock,
                    markers,
                )
            else:
                for level in levels:
                    trial_counter = run_level(
                        level,
                        args,
                        win,
                        core,
                        event,
                        visual,
                        sound,
                        writer,
                        output_file,
                        rng,
                        trial_counter,
                        exp_clock,
                        markers,
                    )
        if levels:
            last_assets = load_assets(args.resource_root / LEVEL_TEMPLATES[levels[-1]], args.language)
            show_image_slide(win, event, visual, sound, last_assets["language"] / "ThankYou.PNG", last_assets["language"] / "ThankYou.mp3")
    except KeyboardInterrupt:
        print(f"Experiment aborted. Partial data saved to {output_path}", file=sys.stderr)
    finally:
        win.close()

    print(f"Data saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
