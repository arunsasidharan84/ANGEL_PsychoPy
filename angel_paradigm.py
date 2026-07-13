#!/usr/bin/env python3
"""PsychoPy recreation of the ANGEL Level 2/3 E-Prime paradigms.

This script intentionally keeps the paradigm logic explicit and auditable:
trials are generated from the ANGEL paper's block structure and the local
E-Prime resource folders, then logged to CSV with all condition columns.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_EPRIME = ROOT / "EPrimeFiles"
DEFAULT_CONFIG = ROOT / "angel_config.json"

CURRENT_ARGS = None


def adjust_pos(pos: tuple[float, float] | list[float] | None) -> tuple[float, float] | None:
    if pos is None:
        return None
    x, y = pos
    if CURRENT_ARGS:
        if CURRENT_ARGS.flip_horizontal:
            x = -x
        if CURRENT_ARGS.flip_vertical:
            y = -y
    return (x, y)


def get_flip_params() -> dict:
    if CURRENT_ARGS:
        return {
            "flipHoriz": CURRENT_ARGS.flip_horizontal,
            "flipVert": CURRENT_ARGS.flip_vertical,
        }
    return {"flipHoriz": False, "flipVert": False}


LEVEL_TEMPLATES = {
    "1": "CCS_EEG_ANGELv2_Level2_Template",
    "2": "CCS_EEG_ANGELv2_Level3_Template",
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

CONFIG_DEFAULTS = {
    "levels": "1,2",
    "language": "english",
    "participant": "test",
    "seed": None,
    "practice": 8,
    "blocks": 16,
    "fullscreen": True,
    "monitor": "testMonitor",
    "resource_root": "EPrimeFiles",  # relative to this script's folder; stays portable when copied to a new machine
    "skip_instructions": False,
    "category_set": "all",
    "paired_tone_offset_mode": "continuous",
    "paired_tone_offset_min": -0.240,
    "paired_tone_offset_max": 0.160,
    "cd_schedule": "by-block",
    "level2_cd": False,
    "intermix_level_blocks": False,
    "fmri_mode": False,
    "trials_per_block": "25+3",
    "stim_duration": 0.240,
    "response_window": 0.700,
    "post_mask_min": 0.200,
    "post_mask_max": 0.900,
    "visual_distractor_mode": "sync",
    "visual_distractor_offset_min": -0.240,
    "visual_distractor_offset_max": 0.160,
    "output_dir": None,
    "marker_mode": "none",
    "lsl_stream_name": "ANGELMarkers",
    "parallel_address": "0x0378",
    "ttl_pulse_width": 0.005,
    "cpod_pulse_width_ms": 20,
    "cpod_port": "",
    "suppress_practice_markers": False,
    "cd_audio_feedback": True,
    "cd_volume": 0.7,
    "cd_repeats": 1,
    "cd_repeat_gap": 0.250,
    "left_keys": ["left", "z", "1"],
    "right_keys": ["right", "slash", "2"],
    "trigger_keys": ["space", "s"],
    "wait_duration_s": 11.0,
    "audio_instructions": True,
    "show_feedback": True,
    "flip_horizontal": False,
    "flip_vertical": False,
}

KEYS = {
    "left": ["left", "z", "1"],
    "right": ["right", "slash", "2"],
    "quit": ["escape", "q"],
    "continue": ["space", "return"],
    "trigger": ["space", "s"],
}


def parse_keys_list(val) -> list[str]:
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        return [x.strip() for x in val.split(",") if x.strip()]
    return []


def _dlg_scalar(value):
    """Unwrap a value returned by gui.DlgFromDict for a dropdown/choice field.

    Depending on the installed PsychoPy version (and its wx/Qt GUI backend),
    a field whose *default* value is a list of choices can come back from the
    dialog either as the selected scalar (recent PsychoPy) or as a one-item
    list, e.g. ['16'] instead of '16' (observed on PsychoPy 2024.1.5). Left
    unhandled, this breaks every int()/float()/bool() conversion downstream
    with cryptic TypeErrors.

    This also defensively repairs a value that was previously corrupted by
    that same bug and saved to angel_config.json as the str() of a Python
    list (e.g. "['1', '2']"), so a bad config file self-heals on the next
    run instead of producing a cascading error every time.
    """
    seen = 0
    while isinstance(value, list):
        if not value:
            return ""
        value = value[0]
        seen += 1
        if seen > 5:
            break
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            import ast

            try:
                parsed = ast.literal_eval(text)
            except Exception:
                parsed = None
            if isinstance(parsed, list) and parsed:
                return str(parsed[0]).strip()
        return text
    return value


def _resolve_resource_root(value) -> Path:
    """Resolve a configured/CLI resource_root to an absolute Path.

    A relative value (e.g. the default "EPrimeFiles") is resolved against the
    script's own directory (ROOT), so the resource folder is always found
    next to angel_paradigm.py regardless of which machine or user account the
    project was copied to. An absolute value (a deliberately customized
    location) is used as-is, but if it doesn't exist on this machine -- e.g.
    a config.json copied over from someone else's computer, still pointing at
    their path -- we fall back to the script-relative default and warn,
    instead of failing later with a confusing FileNotFoundError deep inside
    load_assets().
    """
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        fallback = DEFAULT_EPRIME.resolve()
        if fallback.exists() and fallback != path:
            print(
                f"WARNING: resource_root '{path}' not found; falling back to "
                f"'{fallback}'. Pass --resource-root to point at a custom "
                "EPrimeFiles location.",
                file=sys.stderr,
            )
            path = fallback
    return path


def _resource_root_to_config_value(value) -> str:
    """Convert a resource_root Path back to a value safe to persist in
    angel_config.json. If it points at the default EPrimeFiles folder next
    to this script, store it as a relative path so the config stays portable
    across machines/users. A deliberately customized location elsewhere is
    stored as an absolute path, same as before."""
    path = Path(value).resolve()
    try:
        rel = path.relative_to(ROOT.resolve())
        return str(rel)
    except ValueError:
        return str(path)


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
    config_defaults = load_config_defaults()
    parser = argparse.ArgumentParser(
        description="Run the ANGEL Level 1/2 PsychoPy paradigm."
    )
    parser.add_argument(
        "--levels",
        default=config_defaults["levels"],
        help="Comma-separated levels to run: 1, 2, or 1,2. Default: 1,2.",
    )
    parser.add_argument(
        "--language",
        default=config_defaults["language"],
        choices=["english", "hindi", "kannada"],
        help="Instruction/resource language. Default: english.",
    )
    parser.add_argument(
        "--participant",
        default=config_defaults["participant"],
        help="Participant/session identifier used in the output filename.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=config_defaults["seed"],
        help="Random seed for reproducible schedules. Default: system random.",
    )
    parser.add_argument(
        "--practice",
        type=int,
        default=config_defaults["practice"],
        help="Practice active trials per level before the main run. Default: 8.",
    )
    parser.add_argument(
        "--blocks",
        type=int,
        choices=BLOCK_CHOICES,
        default=config_defaults["blocks"],
        help="Blocks per level. Choices: 16, 8, or 4.",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        dest="fullscreen",
        help="Run fullscreen. Default: true.",
    )
    parser.add_argument(
        "--no-fullscreen",
        action="store_false",
        dest="fullscreen",
        help="Do not run fullscreen.",
    )
    parser.set_defaults(fullscreen=config_defaults["fullscreen"])
    parser.add_argument(
        "--monitor",
        default=config_defaults["monitor"],
        help="PsychoPy monitor name. Default: testMonitor.",
    )
    parser.add_argument(
        "--resource-root",
        type=Path,
        default=_resolve_resource_root(config_defaults["resource_root"]),
        help="Folder containing the EPrimeFiles templates. Relative paths are "
        "resolved against this script's own folder, so the default stays "
        "portable when the project is copied to a new machine.",
    )
    parser.add_argument(
        "--skip-instructions",
        action="store_true",
        help="Skip instruction slides and start directly with trials.",
    )
    parser.add_argument(
        "--category-set",
        default=config_defaults["category_set"],
        choices=sorted(CATEGORY_SETS),
        help="Stimulus family to use: all, face, or shape. Face/shape-only runs work well with --blocks 8.",
    )
    parser.add_argument(
        "--paired-tone-offset-mode",
        default=config_defaults["paired_tone_offset_mode"],
        choices=["continuous", "fixed"],
        help="Use uniform continuous paired-tone offsets, or the paper/E-Prime fixed offsets. Default: continuous.",
    )
    parser.add_argument(
        "--paired-tone-offset-min",
        type=float,
        default=config_defaults["paired_tone_offset_min"],
        help="Minimum continuous paired-tone offset in seconds relative to visual onset. Default: -0.240.",
    )
    parser.add_argument(
        "--paired-tone-offset-max",
        type=float,
        default=config_defaults["paired_tone_offset_max"],
        help="Maximum continuous paired-tone offset in seconds relative to visual onset. Default: 0.160.",
    )
    parser.add_argument(
        "--cd-schedule",
        default=config_defaults["cd_schedule"],
        choices=["by-block", "within-block", "all-immediate", "all-delayed", "all-none"],
        help="CD schedule: immediate, delayed, or none by block, within block, or forced to one mode.",
    )
    parser.add_argument(
        "--level2-cd",
        action="store_true",
        dest="level2_cd",
        help="Enable corollary feedback in Level 2. Default from config.",
    )
    parser.add_argument(
        "--no-level2-cd",
        action="store_false",
        dest="level2_cd",
        help="Disable corollary feedback in Level 2.",
    )
    parser.set_defaults(level2_cd=config_defaults["level2_cd"])

    parser.add_argument(
        "--cd-audio-feedback",
        action="store_true",
        dest="cd_audio_feedback",
        help="Play the corollary-discharge (CD) audio tone after a response. "
        "Default: true. Event markers/timing for CD conditions are always "
        "logged either way -- this only controls whether the tone is heard.",
    )
    parser.add_argument(
        "--no-cd-audio-feedback",
        action="store_false",
        dest="cd_audio_feedback",
        help="Disable the CD audio tone. Useful when no response pad/keyboard "
        "is connected, so no sound implying a response was made ever plays.",
    )
    parser.set_defaults(cd_audio_feedback=config_defaults["cd_audio_feedback"])

    parser.add_argument(
        "--audio-instructions",
        action="store_true",
        dest="audio_instructions",
        help="Play audio instructions narrations. Default: true.",
    )
    parser.add_argument(
        "--no-audio-instructions",
        action="store_false",
        dest="audio_instructions",
        help="Disable playing audio instructions narrations.",
    )
    parser.set_defaults(audio_instructions=config_defaults["audio_instructions"])

    parser.add_argument(
        "--show-feedback",
        action="store_true",
        dest="show_feedback",
        help="Show block and practice performance feedback. Default: true.",
    )
    parser.add_argument(
        "--no-show-feedback",
        action="store_false",
        dest="show_feedback",
        help="Disable showing block and practice performance feedback.",
    )
    parser.set_defaults(show_feedback=config_defaults["show_feedback"])

    parser.add_argument(
        "--flip-horizontal",
        action="store_true",
        dest="flip_horizontal",
        help="Flip visual stimuli horizontally for fMRI setup. Default: false.",
    )
    parser.add_argument(
        "--no-flip-horizontal",
        action="store_false",
        dest="flip_horizontal",
        help="Do not flip visual stimuli horizontally.",
    )
    parser.set_defaults(flip_horizontal=config_defaults["flip_horizontal"])

    parser.add_argument(
        "--flip-vertical",
        action="store_true",
        dest="flip_vertical",
        help="Flip visual stimuli vertically. Default: false.",
    )
    parser.add_argument(
        "--no-flip-vertical",
        action="store_false",
        dest="flip_vertical",
        help="Do not flip visual stimuli vertically.",
    )
    parser.set_defaults(flip_vertical=config_defaults["flip_vertical"])
    parser.add_argument(
        "--intermix-level-blocks",
        action="store_true",
        default=config_defaults["intermix_level_blocks"],
        help="Shuffle Level 1 and Level 2 blocks together instead of running each level contiguously.",
    )
    parser.add_argument(
        "--fmri-mode",
        action="store_true",
        dest="fmri_mode",
        help="fMRI session: the CSV gets extra *_from_trigger_s columns with "
        "every stimulus/response timestamp re-zeroed to the moment the "
        "scanner trigger key (default 's') is pressed. Default: false.",
    )
    parser.add_argument(
        "--no-fmri-mode",
        action="store_false",
        dest="fmri_mode",
        help="Behavioral/EEG session: timestamps are only recorded relative "
        "to experiment start, not a scanner trigger (default).",
    )
    parser.set_defaults(fmri_mode=config_defaults["fmri_mode"])
    parser.add_argument(
        "--trials-per-block",
        default=config_defaults["trials_per_block"],
        choices=TRIALS_PER_BLOCK_CHOICES,
        help="Active+baseline trials per block. Default: 25+3.",
    )
    parser.add_argument(
        "--stim-duration",
        type=float,
        default=config_defaults["stim_duration"],
        help="Visual target duration in seconds. Default: 0.240.",
    )
    parser.add_argument(
        "--response-window",
        type=float,
        default=config_defaults["response_window"],
        help="Response window from visual onset in seconds. Default: 0.700.",
    )
    parser.add_argument(
        "--post-mask-min",
        type=float,
        default=config_defaults["post_mask_min"],
        help="Minimum post-trial masked baseline in seconds. Default: 0.200.",
    )
    parser.add_argument(
        "--post-mask-max",
        type=float,
        default=config_defaults["post_mask_max"],
        help="Maximum post-trial masked baseline in seconds. Default: 0.900.",
    )
    parser.add_argument(
        "--visual-distractor-mode",
        default=config_defaults["visual_distractor_mode"],
        choices=["sync", "desync", "none"],
        help="Visual distractor timing: with target, jittered from target, or absent. Default: sync.",
    )
    parser.add_argument(
        "--visual-distractor-offset-min",
        type=float,
        default=config_defaults["visual_distractor_offset_min"],
        help="Minimum visual distractor offset in seconds for desync mode. Default: -0.240.",
    )
    parser.add_argument(
        "--visual-distractor-offset-max",
        type=float,
        default=config_defaults["visual_distractor_offset_max"],
        help="Maximum visual distractor offset in seconds for desync mode. Default: 0.160.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(config_defaults["output_dir"]).expanduser() if config_defaults["output_dir"] else None,
        help="Folder for CSV logs. Default: data folder beside this script.",
    )
    parser.add_argument(
        "--marker-mode",
        default=config_defaults["marker_mode"],
        choices=["none", "lsl", "parallel", "cpod", "both"],
        help="Send EEG/event markers over none, LSL, parallel TTL, Cedrus C-Pod "
        "(serial), or both/all of the above.",
    )
    parser.add_argument(
        "--lsl-stream-name",
        default=config_defaults["lsl_stream_name"],
        help="LSL marker stream name. Default: ANGELMarkers.",
    )
    parser.add_argument(
        "--parallel-address",
        default=config_defaults["parallel_address"],
        help="Parallel port address for TTL markers. Default: 0x0378.",
    )
    parser.add_argument(
        "--ttl-pulse-width",
        type=float,
        default=config_defaults["ttl_pulse_width"],
        help="Parallel TTL pulse width before reset to zero, in seconds. Default: 0.005.",
    )
    parser.add_argument(
        "--cpod-pulse-width-ms",
        type=int,
        default=config_defaults["cpod_pulse_width_ms"],
        help="Cedrus C-Pod TTL output pulse width in milliseconds. Default: 20. "
        "Only used when --marker-mode is cpod or both.",
    )
    parser.add_argument(
        "--cpod-port",
        default=config_defaults["cpod_port"],
        help="Force a specific COM/serial port for the C-Pod (e.g. COM7), "
        "skipping auto-scan. Leave blank to auto-detect. Only used when "
        "--marker-mode is cpod or both.",
    )
    parser.add_argument(
        "--suppress-practice-markers",
        action="store_true",
        dest="suppress_practice_markers",
        help="During practice, send a single 'trial_start' marker on the first "
        "practice trial and suppress all other markers for the rest of "
        "practice (main-session markers are unaffected). Useful to keep "
        "practice trials out of an EEG/marker recording.",
    )
    parser.add_argument(
        "--no-suppress-practice-markers",
        action="store_false",
        dest="suppress_practice_markers",
        help="Send markers normally during practice (default).",
    )
    parser.set_defaults(suppress_practice_markers=config_defaults["suppress_practice_markers"])
    parser.add_argument(
        "--cd-volume",
        type=float,
        default=config_defaults["cd_volume"],
        help="Corollary feedback sound volume. Default from config.",
    )
    parser.add_argument(
        "--cd-repeats",
        type=int,
        default=config_defaults["cd_repeats"],
        help="Number of times to play corollary feedback sound per event. Default from config.",
    )
    parser.add_argument(
        "--cd-repeat-gap",
        type=float,
        default=config_defaults["cd_repeat_gap"],
        help="Gap between repeated corollary sounds in seconds. Default from config.",
    )
    parser.add_argument(
        "--no-config-dialog",
        action="store_true",
        help="Do not show the PsychoPy configuration dialog when no experiment arguments are supplied.",
    )
    left_default = config_defaults["left_keys"]
    if isinstance(left_default, list):
        left_default = ",".join(left_default)
    right_default = config_defaults["right_keys"]
    if isinstance(right_default, list):
        right_default = ",".join(right_default)
    trigger_default = config_defaults["trigger_keys"]
    if isinstance(trigger_default, list):
        trigger_default = ",".join(trigger_default)

    parser.add_argument(
        "--left-keys",
        default=left_default,
        help=f"Comma-separated keys for left button response. Default: {left_default}",
    )
    parser.add_argument(
        "--right-keys",
        default=right_default,
        help=f"Comma-separated keys for right button response. Default: {right_default}",
    )
    parser.add_argument(
        "--trigger-keys",
        default=trigger_default,
        help=f"Comma-separated keys to start the main task. Default: {trigger_default}",
    )
    parser.add_argument(
        "--wait-duration-s",
        type=float,
        default=config_defaults["wait_duration_s"],
        help="Duration of the 'Waiting...' slide in seconds. Default: 11.0.",
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
    "--level2-cd",
    "--no-level2-cd",
    "--left-keys",
    "--right-keys",
    "--trigger-keys",
    "--wait-duration-s",
    "--intermix-level-blocks",
    "--trials-per-block",
    "--stim-duration",
    "--response-window",
    "--post-mask-min",
    "--post-mask-max",
    "--visual-distractor-mode",
    "--visual-distractor-offset-min",
    "--visual-distractor-offset-max",
    "--output-dir",
    "--marker-mode",
    "--lsl-stream-name",
    "--parallel-address",
    "--ttl-pulse-width",
    "--cd-volume",
    "--cd-repeats",
    "--cd-repeat-gap",
    "--no-config-dialog",
    "--audio-instructions",
    "--no-audio-instructions",
    "--show-feedback",
    "--no-show-feedback",
    "--flip-horizontal",
    "--no-flip-horizontal",
    "--flip-vertical",
    "--no-flip-vertical",
}


def load_config_defaults() -> dict:
    if not DEFAULT_CONFIG.exists():
        save_config_defaults(CONFIG_DEFAULTS)
        return dict(CONFIG_DEFAULTS)
    try:
        with DEFAULT_CONFIG.open("r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
    except Exception as exc:
        print(f"WARNING: Could not read {DEFAULT_CONFIG}: {exc}", file=sys.stderr)
        return dict(CONFIG_DEFAULTS)

    config = dict(CONFIG_DEFAULTS)
    # "levels" is excluded here because it gets its own multi-token-aware
    # recovery below; running it through the generic single-value _dlg_scalar
    # first would collapse a multi-level selection like "1,2" down to just
    # its first token before that recovery ever sees the original value.
    skip_generic_unwrap = {"left_keys", "right_keys", "trigger_keys", "levels"}
    for key, value in loaded.items():
        if key not in CONFIG_DEFAULTS:
            continue
        # Self-heal values corrupted by older-PsychoPy dialog quirks (see
        # _dlg_scalar): e.g. a "blocks" entry saved as a stray one-item
        # list, or as the str() of a Python list.
        if key not in skip_generic_unwrap:
            value = _dlg_scalar(value)
        config[key] = value

    # "levels" specifically supports "1", "2", or "1,2" -- rebuild it from
    # whatever tokens are recoverable so a badly corrupted value (e.g.
    # "['1', '2', '1', '2']" left over from a previous crash) resolves to a
    # clean, valid selection instead of raising "Invalid level(s)" forever.
    raw_levels = str(config.get("levels", CONFIG_DEFAULTS["levels"]))
    cleaned = raw_levels.translate(str.maketrans("", "", "[]'\" "))
    valid_tokens: list[str] = []
    for token in cleaned.split(","):
        if token in LEVEL_TEMPLATES and token not in valid_tokens:
            valid_tokens.append(token)
    config["levels"] = ",".join(valid_tokens) if valid_tokens else CONFIG_DEFAULTS["levels"]

    return config


def save_config_defaults(config: dict) -> None:
    with DEFAULT_CONFIG.open("w", encoding="utf-8") as config_file:
        json.dump(config, config_file, indent=2)
        config_file.write("\n")


def args_to_config(args: argparse.Namespace) -> dict:
    config = {}
    for key in CONFIG_DEFAULTS:
        value = getattr(args, key, CONFIG_DEFAULTS[key])
        if key == "resource_root":
            value = _resource_root_to_config_value(value)
        elif isinstance(value, Path):
            value = str(value)
        if key in ("left_keys", "right_keys", "trigger_keys") and isinstance(value, str):
            value = parse_keys_list(value)
        config[key] = value
    return config


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

    run_data = {
        "participant": args.participant,
        "levels": ["1,2", "1", "2"],
        "language": ["english", "hindi", "kannada"],
        "category_set": ["all", "face", "shape"],
        "blocks": [str(value) for value in BLOCK_CHOICES],
        "trials_per_block": TRIALS_PER_BLOCK_CHOICES,
        "practice": args.practice,
        "intermix_level_blocks": args.intermix_level_blocks,
        "fullscreen": args.fullscreen,
        "audio_instructions": args.audio_instructions,
        "skip_instructions": args.skip_instructions,
        "fmri_mode": args.fmri_mode,
        "seed_blank_for_random": "" if args.seed is None else str(args.seed),
    }
    show_dialog_page(
        gui,
        run_data,
        "ANGEL Config 1/3: Run",
        [
            "participant",
            "levels",
            "language",
            "category_set",
            "blocks",
            "trials_per_block",
            "practice",
            "intermix_level_blocks",
            "fullscreen",
            "audio_instructions",
            "skip_instructions",
            "fmri_mode",
            "seed_blank_for_random",
        ],
    )

    timing_data = {
        "stim_duration": args.stim_duration,
        "response_window": args.response_window,
        "post_mask_min": args.post_mask_min,
        "post_mask_max": args.post_mask_max,
        "visual_distractor_mode": ["sync", "desync", "none"],
        "visual_distractor_offset_min": args.visual_distractor_offset_min,
        "visual_distractor_offset_max": args.visual_distractor_offset_max,
        "paired_tone_offset_mode": ["continuous", "fixed"],
        "paired_tone_offset_min": args.paired_tone_offset_min,
        "paired_tone_offset_max": args.paired_tone_offset_max,
        "cd_schedule": ["by-block", "within-block", "all-immediate", "all-delayed", "all-none"],
        "level2_cd": args.level2_cd,
        "show_feedback": args.show_feedback,
        "cd_audio_feedback": args.cd_audio_feedback,
        "cd_volume": args.cd_volume,
        "cd_repeats": args.cd_repeats,
        "cd_repeat_gap": args.cd_repeat_gap,
    }
    show_dialog_page(
        gui,
        timing_data,
        "ANGEL Config 2/3: Timing/CD",
        [
            "stim_duration",
            "response_window",
            "post_mask_min",
            "post_mask_max",
            "visual_distractor_mode",
            "visual_distractor_offset_min",
            "visual_distractor_offset_max",
            "paired_tone_offset_mode",
            "paired_tone_offset_min",
            "paired_tone_offset_max",
            "cd_schedule",
            "level2_cd",
            "show_feedback",
            "cd_audio_feedback",
            "cd_volume",
            "cd_repeats",
            "cd_repeat_gap",
        ],
    )

    io_data = {
        "marker_mode": ["none", "lsl", "parallel", "cpod", "both"],
        "lsl_stream_name": args.lsl_stream_name,
        "parallel_address": args.parallel_address,
        "ttl_pulse_width": args.ttl_pulse_width,
        "cpod_pulse_width_ms": args.cpod_pulse_width_ms,
        "cpod_port_blank_for_autoscan": args.cpod_port,
        "suppress_practice_markers": args.suppress_practice_markers,
        "left_keys": ",".join(args.left_keys) if isinstance(args.left_keys, list) else args.left_keys,
        "right_keys": ",".join(args.right_keys) if isinstance(args.right_keys, list) else args.right_keys,
        "trigger_keys": ",".join(args.trigger_keys) if isinstance(args.trigger_keys, list) else args.trigger_keys,
        "wait_duration_s": args.wait_duration_s,
        "flip_horizontal": args.flip_horizontal,
        "flip_vertical": args.flip_vertical,
        "output_dir_blank_for_default": "" if args.output_dir is None else str(args.output_dir),
    }
    show_dialog_page(
        gui,
        io_data,
        "ANGEL Config 3/3: Output",
        [
            "marker_mode",
            "lsl_stream_name",
            "parallel_address",
            "ttl_pulse_width",
            "cpod_pulse_width_ms",
            "cpod_port_blank_for_autoscan",
            "suppress_practice_markers",
            "left_keys",
            "right_keys",
            "trigger_keys",
            "wait_duration_s",
            "flip_horizontal",
            "flip_vertical",
            "output_dir_blank_for_default",
        ],
    )

    dialog_data = {}
    dialog_data.update(run_data)
    dialog_data.update(timing_data)
    dialog_data.update(io_data)

    # NOTE: every value pulled from dialog_data is passed through _dlg_scalar
    # first. On PsychoPy 2024.1.5 (and possibly other older wx/Qt combos),
    # gui.DlgFromDict can return a dropdown/choice field as a one-item list
    # (e.g. ['16']) instead of the plain scalar ('16') that newer PsychoPy
    # returns. Without unwrapping, int()/float()/bool() calls below raise
    # TypeErrors like "int() argument must be ... not 'list'". _dlg_scalar
    # also repairs a value that got corrupted into a stringified list by
    # that same bug on a previous run.
    args.participant = str(_dlg_scalar(dialog_data["participant"]))
    args.levels = str(_dlg_scalar(dialog_data["levels"]))
    args.language = str(_dlg_scalar(dialog_data["language"]))
    args.category_set = str(_dlg_scalar(dialog_data["category_set"]))
    args.blocks = int(_dlg_scalar(dialog_data["blocks"]))
    args.trials_per_block = str(_dlg_scalar(dialog_data["trials_per_block"]))
    args.practice = int(_dlg_scalar(dialog_data["practice"]))
    args.stim_duration = float(_dlg_scalar(dialog_data["stim_duration"]))
    args.response_window = float(_dlg_scalar(dialog_data["response_window"]))
    args.post_mask_min = float(_dlg_scalar(dialog_data["post_mask_min"]))
    args.post_mask_max = float(_dlg_scalar(dialog_data["post_mask_max"]))
    args.visual_distractor_mode = str(_dlg_scalar(dialog_data["visual_distractor_mode"]))
    args.visual_distractor_offset_min = float(_dlg_scalar(dialog_data["visual_distractor_offset_min"]))
    args.visual_distractor_offset_max = float(_dlg_scalar(dialog_data["visual_distractor_offset_max"]))
    args.paired_tone_offset_mode = str(_dlg_scalar(dialog_data["paired_tone_offset_mode"]))
    args.paired_tone_offset_min = float(_dlg_scalar(dialog_data["paired_tone_offset_min"]))
    args.paired_tone_offset_max = float(_dlg_scalar(dialog_data["paired_tone_offset_max"]))
    args.cd_schedule = str(_dlg_scalar(dialog_data["cd_schedule"]))
    args.level2_cd = bool(_dlg_scalar(dialog_data["level2_cd"]))
    args.show_feedback = bool(_dlg_scalar(dialog_data["show_feedback"]))
    args.cd_audio_feedback = bool(_dlg_scalar(dialog_data["cd_audio_feedback"]))
    args.cd_volume = float(_dlg_scalar(dialog_data["cd_volume"]))
    args.cd_repeats = int(_dlg_scalar(dialog_data["cd_repeats"]))
    args.cd_repeat_gap = float(_dlg_scalar(dialog_data["cd_repeat_gap"]))
    args.left_keys = parse_keys_list(dialog_data["left_keys"])
    args.right_keys = parse_keys_list(dialog_data["right_keys"])
    args.trigger_keys = parse_keys_list(dialog_data["trigger_keys"])
    args.wait_duration_s = float(_dlg_scalar(dialog_data["wait_duration_s"]))
    args.marker_mode = str(_dlg_scalar(dialog_data["marker_mode"]))
    args.lsl_stream_name = str(_dlg_scalar(dialog_data["lsl_stream_name"]))
    args.parallel_address = str(_dlg_scalar(dialog_data["parallel_address"]))
    args.ttl_pulse_width = float(_dlg_scalar(dialog_data["ttl_pulse_width"]))
    args.cpod_pulse_width_ms = int(_dlg_scalar(dialog_data["cpod_pulse_width_ms"]))
    args.cpod_port = str(_dlg_scalar(dialog_data["cpod_port_blank_for_autoscan"])).strip()
    args.suppress_practice_markers = bool(_dlg_scalar(dialog_data["suppress_practice_markers"]))
    output_dir = str(_dlg_scalar(dialog_data["output_dir_blank_for_default"])).strip()
    args.output_dir = Path(output_dir).expanduser() if output_dir else None
    args.intermix_level_blocks = bool(_dlg_scalar(dialog_data["intermix_level_blocks"]))
    args.fullscreen = bool(_dlg_scalar(dialog_data["fullscreen"]))
    args.audio_instructions = bool(_dlg_scalar(dialog_data["audio_instructions"]))
    args.skip_instructions = bool(_dlg_scalar(dialog_data["skip_instructions"]))
    args.fmri_mode = bool(_dlg_scalar(dialog_data["fmri_mode"]))
    args.flip_horizontal = bool(_dlg_scalar(dialog_data["flip_horizontal"]))
    args.flip_vertical = bool(_dlg_scalar(dialog_data["flip_vertical"]))
    seed_value = str(_dlg_scalar(dialog_data["seed_blank_for_random"])).strip()
    args.seed = int(seed_value) if seed_value else None

    # Defense in depth: if "levels" still isn't clean (e.g. a completely
    # novel corruption shape), rebuild it from whatever valid tokens can be
    # recovered rather than letting main() raise "Invalid level(s)".
    cleaned_levels = args.levels.translate(str.maketrans("", "", "[]'\" "))
    valid_levels = [tok for tok in cleaned_levels.split(",") if tok in LEVEL_TEMPLATES]
    if valid_levels:
        args.levels = ",".join(dict.fromkeys(valid_levels))
    return args


def show_dialog_page(gui, data: dict, title: str, order: list[str]) -> None:
    dlg = gui.DlgFromDict(
        dictionary=data,
        title=title,
        order=order,
    )
    if not dlg.OK:
        raise KeyboardInterrupt


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
    if args.visual_distractor_offset_min > args.visual_distractor_offset_max:
        raise SystemExit("--visual-distractor-offset-min must be <= --visual-distractor-offset-max.")
    if args.stim_duration <= 0 or args.response_window <= 0:
        raise SystemExit("--stim-duration and --response-window must be positive.")
    if args.stim_duration < max(0.0, args.paired_tone_offset_max):
        raise SystemExit("--stim-duration must be >= positive paired-tone offset maximum.")
    if args.visual_distractor_mode == "desync" and args.stim_duration < max(0.0, args.visual_distractor_offset_max):
        raise SystemExit("--stim-duration must be >= positive visual distractor offset maximum.")
    if args.cd_repeats < 1:
        raise SystemExit("--cd-repeats must be >= 1.")
    if args.cd_repeat_gap < 0:
        raise SystemExit("--cd-repeat-gap must be >= 0.")
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
    level2_cd: bool = False,
) -> list[Trial]:
    categories = CATEGORY_SETS[category_set]
    block_specs: list[tuple[str, str]] = []

    while len(block_specs) < blocks:
        block_specs.extend((category, side) for category in categories for side in ["left", "right"])
    block_specs = block_specs[:blocks]
    rng.shuffle(block_specs)

    if level == "1":
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

            if level == "1":
                correct_response = side_to_key(target_side)
                corollary_mode = block_cd_modes[trial_index - 1]
            else:
                corollary_mode = block_cd_modes[trial_index - 1] if level2_cd else None
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
    none_count = max(1, round(active_trials_per_block * 0.20))
    feedback_count = active_trials_per_block - none_count
    if cd_schedule == "all-immediate":
        modes = ["immediate"] * feedback_count + ["none"] * none_count
        rng.shuffle(modes)
        return modes
    if cd_schedule == "all-delayed":
        modes = ["delayed"] * feedback_count + ["none"] * none_count
        rng.shuffle(modes)
        return modes
    if cd_schedule == "all-none":
        return ["none"] * active_trials_per_block
    if cd_schedule == "within-block":
        immediate_count = (feedback_count + 1) // 2
        delayed_count = feedback_count - immediate_count
        modes = (
            ["immediate"] * immediate_count
            + ["delayed"] * delayed_count
            + ["none"] * none_count
        )
        rng.shuffle(modes)
        return modes
    feedback_mode = "immediate" if block_index in immediate_blocks else "delayed"
    modes = [feedback_mode] * feedback_count + ["none"] * none_count
    rng.shuffle(modes)
    return modes


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
            2,  # NOTE: must be >=2 so blocks//2 >= 1 and block_index(1) <= blocks//2,
                # otherwise reversal_phase always evaluates to "post_reversal" and
                # Level 2 practice trains the reversed (mismatched) key mapping.
            rng,
            args.category_set,
            args.paired_tone_offset_mode,
            args.paired_tone_offset_min,
            args.paired_tone_offset_max,
            args.cd_schedule,
            active_trials,
            baseline_trials,
            args.level2_cd,
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
    if not image_path.exists():
        return
    slide = visual.ImageStim(win, image=str(image_path), size=(1.333, 1.0), units="height", **get_flip_params())
    
    play_audio = True
    if CURRENT_ARGS and not CURRENT_ARGS.audio_instructions:
        play_audio = False
        
    audio = None
    if play_audio and audio_path:
        audio_path = existing_case_variant(audio_path)
        if audio_path.exists():
            try:
                audio = sound.Sound(str(audio_path))
            except Exception:
                audio = None
                
    if audio:
        audio.play()
    slide.draw()
    win.flip()
    wait_for_continue(event)
    if audio:
        audio.stop()


def show_transition_text(win, event, visual, message: str) -> None:
    stim = visual.TextStim(
        win,
        text=f"{message}\n\nPress space to continue",
        color="white",
        height=0.04,
        units="height",
        wrapWidth=1.5,
        **get_flip_params(),
    )
    stim.draw()
    win.flip()
    wait_for_continue(event)


def show_welcome_slide(win, event, visual, level: str, phase: str = "main") -> None:
    if phase == "practice":
        text = f"LEVEL - {level} - Practice Session\n\nWelcome To this Level!\n\nPress any button to begin..."
    else:
        text = f"LEVEL - {level}\n\nWelcome To this Level!\n\nPress any button to begin..."
    stim = visual.TextStim(
        win,
        text=text,
        color="white",
        height=0.06,
        units="height",
        wrapWidth=1.5,
        **get_flip_params(),
    )
    stim.draw()
    win.flip()
    wait_for_continue(event)


def show_level_instruction(win, event, visual, sound, assets: dict, level: str, phase: str) -> None:
    show_image_slide(
        win,
        event,
        visual,
        sound,
        assets["language"] / "InstructionLevel1.PNG",
        assets["language"] / "InstructionLevel1.mp3",
    )


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
        "left_mask": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=adjust_pos((-0.42, 0)), size=target_size, units="height", **get_flip_params()),
        "right_mask": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=adjust_pos((0.42, 0)), size=target_size, units="height", **get_flip_params()),
        "fix": visual.ImageStim(win, image=str(assets["fixation"]), pos=adjust_pos((0, 0)), size=(0.075, 0.075), units="height", **get_flip_params()),
        "top_left_distractor": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=adjust_pos((-0.18, 0.34)), size=distractor_size, units="height", **get_flip_params()),
        "top_right_distractor": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=adjust_pos((0.18, 0.34)), size=distractor_size, units="height", **get_flip_params()),
        "bottom_left_distractor": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=adjust_pos((-0.18, -0.34)), size=distractor_size, units="height", **get_flip_params()),
        "bottom_right_distractor": visual.ImageStim(win, image=str(assets["checkerboard"]), pos=adjust_pos((0.18, -0.34)), size=distractor_size, units="height", **get_flip_params()),
        "target_size": target_size,
    }


def make_audio_cache(sound, assets: dict) -> dict:
    cache = {
        "corollary": sound.Sound(str(assets["corollary"])),
        "nocorollary": sound.Sound(str(assets["nocorollary"])),
    }
    return cache


def set_sound_volume(sound_obj, volume: float) -> None:
    try:
        sound_obj.setVolume(volume)
    except Exception:
        try:
            sound_obj.volume = volume
        except Exception:
            pass


def get_sound_duration(sound_obj, fallback: float = 0.200) -> float:
    for attr in ("getDuration", "duration", "secs"):
        try:
            value = getattr(sound_obj, attr)
            duration = value() if callable(value) else value
            if duration is not None and float(duration) > 0:
                return float(duration)
        except Exception:
            continue
    return fallback


def play_cd_feedback(
    audio_cache: dict,
    name: str,
    args: argparse.Namespace,
    trial_clock=None,
    scheduled_sounds: list | None = None,
) -> None:
    sound_obj = audio_cache[name]
    set_sound_volume(sound_obj, args.cd_volume)
    sound_obj.play()
    repeat_gap = max(args.cd_repeat_gap, get_sound_duration(sound_obj) + 0.020)
    for repeat_index in range(1, args.cd_repeats):
        if trial_clock is not None and scheduled_sounds is not None:
            scheduled_sounds.append((trial_clock.getTime() + repeat_index * repeat_gap, sound_obj))
        else:
            threading.Timer(repeat_index * repeat_gap, sound_obj.play).start()


def cd_condition_from_mode(corollary_mode: str | None) -> str | None:
    if corollary_mode == "immediate":
        return "cd_immediate"
    if corollary_mode == "delayed":
        return "cd_delayed"
    if corollary_mode == "none":
        return "cd_none"
    return None


def service_scheduled_sounds(trial_clock, scheduled_sounds: list) -> None:
    now = trial_clock.getTime()
    pending = []
    for play_time, sound_obj in scheduled_sounds:
        if now >= play_time:
            sound_obj.play()
        else:
            pending.append((play_time, sound_obj))
    scheduled_sounds[:] = pending


def draw_masks(win, stimuli: dict, distractor_pos: str | None = None, show_distractor: bool = False) -> None:
    stimuli["left_mask"].draw()
    stimuli["right_mask"].draw()
    stimuli["fix"].draw()
    if not show_distractor:
        return
    if distractor_pos == "top":
        stimuli["top_left_distractor"].draw()
        stimuli["top_right_distractor"].draw()
    elif distractor_pos == "bottom":
        stimuli["bottom_left_distractor"].draw()
        stimuli["bottom_right_distractor"].draw()


def draw_trial_frame(stimuli: dict, target, distractor_pos: str | None, show_distractor: bool) -> None:
    draw_masks(None, stimuli, distractor_pos, show_distractor)
    target.draw()


def play_sound_at(core, sound_obj, trial_clock, absolute_s: float) -> float:
    while trial_clock.getTime() < absolute_s:
        core.wait(0.001, hogCPUperiod=0.001)
    sound_obj.play()
    return trial_clock.getTime()


def wait_until(core, trial_clock, absolute_s: float, scheduled_sounds: list | None = None) -> None:
    while trial_clock.getTime() < absolute_s:
        if scheduled_sounds is not None:
            service_scheduled_sounds(trial_clock, scheduled_sounds)
        core.wait(0.001, hogCPUperiod=0.001)


def find_cpod(port: str | None = None):
    """Detect (or connect to) a Cedrus C-Pod on a serial (virtual COM) port.

    Optional feature: only called when --marker-mode/config marker_mode is
    "cpod" or "both". Requires the `pyserial` package (`pip install pyserial`),
    which is NOT a hard dependency of this script -- it's only imported here,
    so runs that don't use C-Pod markers are unaffected either way.

    The C-Pod is a serial/XID device, not a parallel-port device: it enumerates
    as a standard COM port over USB and is queried with Cedrus's XID handshake
    (`_c1` -> `_xid0`). This is independent of the psychopy.parallel backend
    used by --marker-mode parallel.

    If `port` is given (e.g. "COM7"), that port is opened directly and no
    scan is performed -- this is the safest and fastest option once you know
    which port the C-Pod is on. Otherwise, all serial ports are scanned,
    preferring FTDI-identified ports (VID 0403, which Cedrus devices use)
    and skipping known-risky virtual ports such as Bluetooth SPP links.
    """
    import serial  # type: ignore
    import serial.tools.list_ports  # type: ignore

    def _probe(device_name: str, description: str = ""):
        print(f"  {device_name}: probing ({description})")
        dev = None
        try:
            dev = serial.Serial(device_name, 115200, timeout=1)
            dev.reset_input_buffer()
            dev.write(b"_c1")
            resp = dev.read(5)
            if resp == b"_xid0":
                print(f"C-Pod found on {device_name}")
                return dev
            dev.close()
        except Exception as exc:
            print(f"  {device_name}: not a C-Pod ({exc})")
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
        return None

    if port:
        # User forced a specific port (e.g. --cpod-port COM7): open only that
        # one, skipping auto-scan entirely.
        print(f"Using forced C-Pod port: {port}")
        result = _probe(port)
        if result is None:
            print(f"No Cedrus C-Pod responded on forced port {port}.")
            # Help the user pick the right port next time, rather than
            # leaving them to guess or dig through Device Manager/System
            # Information themselves.
            try:
                available = list(serial.tools.list_ports.comports())
            except Exception:
                available = []
            if available:
                print("Available serial ports on this machine:")
                for p in available:
                    print(f"  {p.device}  ({p.description or 'no description'})")
                print("Set --cpod-port to one of the above, or leave it blank to auto-scan.")
            else:
                print("No serial ports were detected at all -- check the C-Pod is plugged in and powered.")
        return result

    ports = list(serial.tools.list_ports.comports())
    print(f"Scanning {len(ports)} serial port(s) for a Cedrus C-Pod...")

    # Cedrus devices (including the C-Pod) enumerate as FTDI USB-serial
    # adapters, VID 0403. Prefer these first since they're safe to open.
    ftdi_ports = [p for p in ports if "vid:pid=0403" in (p.hwid or "").lower()]
    other_ports = [p for p in ports if p not in ftdi_ports]

    for p in ftdi_ports:
        result = _probe(p.device, p.description or "")
        if result is not None:
            return result

    for p in other_ports:
        desc = (p.description or "").lower()
        # Skip virtual/system ports known to misbehave (Bluetooth SPP, modem,
        # print-to-fax, etc.) -- opening these can cause a native crash on
        # some Windows driver stacks rather than a catchable Python exception.
        if any(bad in desc for bad in ("bluetooth", "modem", "fax", "standard serial over")):
            print(f"  {p.device}: skipping ({p.description})")
            continue
        result = _probe(p.device, p.description or "")
        if result is not None:
            return result

    print("No Cedrus C-Pod found on any serial port.")
    return None


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
        "cd_none": 52,
        "trial_end": 90,
    }

    def __init__(self, args: argparse.Namespace, core, exp_clock) -> None:
        self.args = args
        self.core = core
        self.exp_clock = exp_clock
        self.outlet = None
        self.port = None
        self.cpod = None
        self.log: list[dict] = []

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

        # Optional: Cedrus C-Pod over serial. Only attempted when explicitly
        # enabled via --marker-mode cpod/both, so this is a no-op (and
        # pyserial is never imported) for everyone else.
        if args.marker_mode in ["cpod", "both"]:
            try:
                self.cpod = find_cpod(port=getattr(args, "cpod_port", "") or None)
                if self.cpod is None:
                    print("WARNING: No Cedrus C-Pod found on any serial port.", file=sys.stderr)
                else:
                    self._cpod_set_pulse_width(getattr(args, "cpod_pulse_width_ms", 20))
            except Exception as exc:
                print(f"WARNING: Could not initialize C-Pod markers: {exc}", file=sys.stderr)
                self.cpod = None

    def _cpod_set_pulse_width(self, ms: int) -> None:
        duration = int(ms)
        self.cpod.write(bytes([
            ord('m'), ord('p'),
            duration & 0xFF,
            (duration >> 8) & 0xFF,
            (duration >> 16) & 0xFF,
            (duration >> 24) & 0xFF,
        ]))

    def _cpod_send(self, code: int) -> None:
        # C-Pod marker codes are single bytes (0-255).
        self.cpod.write(bytes([ord('m'), ord('h'), code & 0xFF, 0]))

    def close(self) -> None:
        if self.cpod is not None:
            try:
                self.cpod.close()
            except Exception as exc:
                print(f"WARNING: Error closing C-Pod: {exc}", file=sys.stderr)

    def save_log(self, path: Path) -> None:
        """Write every marker sent this session to a CSV file (index, timestamp, label, code).

        Populated regardless of marker_mode (as long as at least one marker
        was sent), so it's a useful audit trail even for lsl/parallel-only
        runs, not just C-Pod ones.
        """
        if not self.log:
            return
        try:
            with path.open("w", newline="", encoding="utf-8") as log_file:
                writer = csv.DictWriter(log_file, fieldnames=["marker_index", "timestamp_s", "label", "code"])
                writer.writeheader()
                writer.writerows(self.log)
            print(f"Marker log written to {path}")
        except Exception as exc:
            print(f"WARNING: Could not write marker log: {exc}", file=sys.stderr)

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
                if hasattr(self.core, "callLater"):
                    self.core.callLater(self.args.ttl_pulse_width, self.port.setData, 0)
                else:
                    threading.Timer(self.args.ttl_pulse_width, self.port.setData, args=(0,)).start()
            except Exception as exc:
                print(f"WARNING: Parallel marker failed: {exc}", file=sys.stderr)

        if self.cpod is not None:
            try:
                self._cpod_send(marker_code)
            except Exception as exc:
                print(f"WARNING: C-Pod marker failed: {exc}", file=sys.stderr)

        self.log.append({
            "marker_index": len(self.log) + 1,
            "timestamp_s": timestamp,
            "label": label,
            "code": marker_code,
        })

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
    audio_cache: dict,
    rng: random.Random,
    trial_global_index: int,
    exp_clock,
    markers: MarkerSender,
    block_name: str,
    send_markers: bool = True,
    force_trial_start: bool = False,
) -> dict:
    event.clearEvents()
    response_keys = flatten([KEYS["left"], KEYS["right"], KEYS["quit"]])
    trial_clock = core.Clock()
    response = None
    response_onset = None
    response_onset_global = None
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
    cd_none_marker_sent = False
    scheduled_sounds: list = []
    trial_start_global = exp_clock.getTime()
    # When send_markers is False (practice trials with marker suppression
    # enabled), every in-trial marker except a single forced "trial_start"
    # is silently skipped -- the trial itself still runs and is logged to
    # CSV as normal, it just doesn't emit hardware/LSL/C-Pod markers.
    if send_markers or force_trial_start:
        markers.send("trial_start")
    send_marker = markers.send if send_markers else (lambda label, code=None: None)

    if trial.trial_type == "baseline":
        stimuli["fix"].draw()
        win.flip()
        baseline_onset = exp_clock.getTime()
        send_marker("baseline_start")
        baseline_duration = args.response_window + rng.uniform(args.post_mask_min, args.post_mask_max)
        core.wait(baseline_duration)
        trial_end_global = exp_clock.getTime()
        send_marker("trial_end")
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
            block_name=block_name,
            trigger_onset_global=getattr(args, "trigger_onset_global", None),
        )

    target_path = rng.choice(assets["categories"][trial.stimulus_category])
    target_pos = adjust_pos((-0.42, 0) if trial.target_side == "left" else (0.42, 0))
    target = visual.ImageStim(
        win,
        image=str(target_path),
        pos=target_pos,
        size=stimuli["target_size"],
        units="height",
        **get_flip_params(),
    )
    visual_distractor_offset = None
    visual_distractor_onset = None
    visual_distractor_onset_global = None
    visual_distractor_offset_time = None
    visual_distractor_offset_global = None
    if args.visual_distractor_mode == "desync":
        visual_distractor_offset = rng.uniform(
            args.visual_distractor_offset_min,
            args.visual_distractor_offset_max,
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
    distractor_start_s = (
        pre_stim_s + visual_distractor_offset
        if args.visual_distractor_mode == "desync" and visual_distractor_offset is not None
        else None
    )
    distractor_end_s = (
        distractor_start_s + args.stim_duration
        if distractor_start_s is not None
        else None
    )
    distractor_visible = False
    draw_masks(win, stimuli, trial.visual_distractor_pos, False)
    win.flip()
    trial_clock.reset()

    if tone and tone_start_s is not None and tone_start_s < pre_stim_s:
        paired_tone_onset = play_sound_at(core, tone, trial_clock, tone_start_s)
        paired_tone_onset_global = exp_clock.getTime()
        send_marker(f"paired_{trial.auditory_class}")
    tone_pending = tone is not None and tone_start_s is not None and tone_start_s >= pre_stim_s

    while trial_clock.getTime() < pre_stim_s:
        service_scheduled_sounds(trial_clock, scheduled_sounds)
        if distractor_start_s is not None and distractor_end_s is not None:
            should_show = distractor_start_s <= trial_clock.getTime() < distractor_end_s
            if should_show != distractor_visible:
                draw_masks(win, stimuli, trial.visual_distractor_pos, should_show)
                win.flip()
                distractor_visible = should_show
                if should_show:
                    visual_distractor_onset = trial_clock.getTime()
                    visual_distractor_onset_global = exp_clock.getTime()
                elif visual_distractor_offset_time is None:
                    visual_distractor_offset_time = trial_clock.getTime()
                    visual_distractor_offset_global = exp_clock.getTime()
        core.wait(0.001, hogCPUperiod=0.001)

    show_sync_distractor = args.visual_distractor_mode == "sync"
    show_desync_at_visual = (
        args.visual_distractor_mode == "desync"
        and distractor_start_s is not None
        and distractor_end_s is not None
        and distractor_start_s <= pre_stim_s < distractor_end_s
    )
    draw_trial_frame(stimuli, target, trial.visual_distractor_pos, show_sync_distractor or show_desync_at_visual)
    win.flip()
    distractor_visible = show_sync_distractor or show_desync_at_visual
    visual_onset = trial_clock.getTime()
    visual_onset_global = exp_clock.getTime()
    send_marker(f"visual_{trial.frequency_class}")
    if show_sync_distractor:
        visual_distractor_onset = visual_onset
        visual_distractor_onset_global = visual_onset_global
    elif show_desync_at_visual and visual_distractor_onset is None:
        visual_distractor_onset = visual_onset + float(visual_distractor_offset)
        visual_distractor_onset_global = exp_clock.getTime()

    while trial_clock.getTime() < visual_onset + args.stim_duration:
        service_scheduled_sounds(trial_clock, scheduled_sounds)
        if tone_pending and trial_clock.getTime() >= tone_start_s:
            tone.play()
            paired_tone_onset = trial_clock.getTime()
            paired_tone_onset_global = exp_clock.getTime()
            send_marker(f"paired_{trial.auditory_class}")
            tone_pending = False
        keys = event.getKeys(keyList=response_keys, timeStamped=trial_clock)
        if keys and keys[0][0] in KEYS["quit"]:
            raise KeyboardInterrupt
        if keys and response is None:
            response, timestamp = normalize_response(keys[0])
            rt = timestamp - visual_onset
            response_onset = timestamp
            response_onset_global = exp_clock.getTime()
            send_marker(f"response_{response}")
            if trial.corollary_mode == "immediate":
                # cd_audio_feedback only gates the audible tone -- the
                # cd_immediate marker/onset timestamps below are always
                # recorded so trial timing/epoching stays consistent
                # whether or not a response device is actually connected.
                if args.cd_audio_feedback:
                    play_cd_feedback(audio_cache, "corollary", args, trial_clock, scheduled_sounds)
                corollary_onset = trial_clock.getTime()
                corollary_onset_global = exp_clock.getTime()
                send_marker("cd_immediate")
            elif trial.corollary_mode == "none":
                send_marker("cd_none")
                cd_none_marker_sent = True
        if args.visual_distractor_mode == "desync" and distractor_start_s is not None and distractor_end_s is not None:
            should_show = (
                distractor_start_s <= trial_clock.getTime() < distractor_end_s
            )
            if should_show and visual_distractor_onset is None:
                visual_distractor_onset = trial_clock.getTime()
                visual_distractor_onset_global = exp_clock.getTime()
            if not should_show and visual_distractor_onset is not None and visual_distractor_offset_time is None:
                visual_distractor_offset_time = trial_clock.getTime()
                visual_distractor_offset_global = exp_clock.getTime()
            if should_show != distractor_visible:
                draw_trial_frame(stimuli, target, trial.visual_distractor_pos, should_show)
                win.flip()
                distractor_visible = should_show
        core.wait(0.001, hogCPUperiod=0.001)

    draw_masks(win, stimuli, trial.visual_distractor_pos, False)
    win.flip()
    visual_offset = trial_clock.getTime()
    visual_offset_global = exp_clock.getTime()
    send_marker("visual_offset")
    if args.visual_distractor_mode == "sync":
        visual_distractor_offset_time = visual_offset
        visual_distractor_offset_global = visual_offset_global
    elif args.visual_distractor_mode == "desync" and visual_distractor_onset is not None and visual_distractor_offset_time is None:
        visual_distractor_offset_time = visual_offset
        visual_distractor_offset_global = visual_offset_global

    response_deadline = visual_onset + args.response_window
    while trial_clock.getTime() < response_deadline:
        service_scheduled_sounds(trial_clock, scheduled_sounds)
        if args.visual_distractor_mode == "desync" and distractor_start_s is not None and distractor_end_s is not None:
            should_show = distractor_start_s <= trial_clock.getTime() < distractor_end_s
            if should_show and visual_distractor_onset is None:
                visual_distractor_onset = trial_clock.getTime()
                visual_distractor_onset_global = exp_clock.getTime()
            if should_show != distractor_visible:
                draw_masks(win, stimuli, trial.visual_distractor_pos, should_show)
                win.flip()
                distractor_visible = should_show
            if not should_show and visual_distractor_onset is not None and visual_distractor_offset_time is None:
                visual_distractor_offset_time = trial_clock.getTime()
                visual_distractor_offset_global = exp_clock.getTime()
        if tone_pending and trial_clock.getTime() >= tone_start_s:
            tone.play()
            paired_tone_onset = trial_clock.getTime()
            paired_tone_onset_global = exp_clock.getTime()
            send_marker(f"paired_{trial.auditory_class}")
            tone_pending = False
        keys = event.getKeys(keyList=response_keys, timeStamped=trial_clock)
        if keys and keys[0][0] in KEYS["quit"]:
            raise KeyboardInterrupt
        if keys and response is None:
            response, timestamp = normalize_response(keys[0])
            rt = timestamp - visual_onset
            response_onset = timestamp
            response_onset_global = exp_clock.getTime()
            send_marker(f"response_{response}")
            if trial.corollary_mode == "immediate":
                # cd_audio_feedback only gates the audible tone -- the
                # cd_immediate marker/onset timestamps below are always
                # recorded so trial timing/epoching stays consistent
                # whether or not a response device is actually connected.
                if args.cd_audio_feedback:
                    play_cd_feedback(audio_cache, "corollary", args, trial_clock, scheduled_sounds)
                corollary_onset = trial_clock.getTime()
                corollary_onset_global = exp_clock.getTime()
                send_marker("cd_immediate")
            elif trial.corollary_mode == "none":
                send_marker("cd_none")
                cd_none_marker_sent = True
        core.wait(0.001, hogCPUperiod=0.001)

    response_window_end = trial_clock.getTime()
    response_window_end_global = exp_clock.getTime()
    post_mask_start = response_deadline
    post_mask_start_global = exp_clock.getTime()
    post_mask_duration = rng.uniform(args.post_mask_min, args.post_mask_max)
    post_mask_end = post_mask_start + post_mask_duration

    if response is None:
        send_marker("response_miss")
        if trial.corollary_mode == "none" and not cd_none_marker_sent:
            send_marker("cd_none")
            cd_none_marker_sent = True

    if trial.corollary_mode == "delayed":
        cd_anchor = visual_onset + rt if rt is not None else response_deadline
        delay = rng.uniform(0.300, 0.500)
        play_at = cd_anchor + delay
        post_mask_end = max(post_mask_end, play_at + 0.005)
        wait_until(core, trial_clock, play_at, scheduled_sounds)
        if args.cd_audio_feedback:
            play_cd_feedback(audio_cache, "corollary", args, trial_clock, scheduled_sounds)
        corollary_onset = trial_clock.getTime()
        corollary_onset_global = exp_clock.getTime()
        send_marker("cd_delayed")

    accuracy = None
    if trial.correct_response:
        accuracy = int(response == trial.correct_response)

    wait_until(core, trial_clock, post_mask_end, scheduled_sounds)
    post_mask_end_global = exp_clock.getTime()
    send_marker("trial_end")

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
        response_onset=response_onset,
        response_onset_global=response_onset_global,
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
        visual_distractor_offset=visual_distractor_offset,
        visual_distractor_onset=visual_distractor_onset,
        visual_distractor_onset_global=visual_distractor_onset_global,
        visual_distractor_offset_time=visual_distractor_offset_time,
        visual_distractor_offset_global=visual_distractor_offset_global,
        block_name=block_name,
        trigger_onset_global=getattr(args, "trigger_onset_global", None),
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


def _from_trigger(value: float | None, trigger_onset_global: float | None) -> float | None:
    """Re-zero a global-clock timestamp to the scanner/EEG trigger onset.

    Returns None whenever either input is missing -- i.e. for practice
    trials (which run before the trigger), or any run where fmri_mode is
    off, so these columns simply stay empty rather than misleadingly
    showing a value.
    """
    if value is None or trigger_onset_global is None:
        return None
    return value - trigger_onset_global


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
    response_onset: float | None = None,
    response_onset_global: float | None = None,
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
    visual_distractor_offset: float | None = None,
    visual_distractor_onset: float | None = None,
    visual_distractor_onset_global: float | None = None,
    visual_distractor_offset_time: float | None = None,
    visual_distractor_offset_global: float | None = None,
    block_name: str | None = None,
    trigger_onset_global: float | None = None,
) -> dict:
    return {
        "trial_global_index": trial_global_index,
        "level": trial.level,
        "block": trial.block,
        "block_name": block_name,
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
        "visual_distractor_offset_s": visual_distractor_offset,
        "visual_distractor_onset_s": visual_distractor_onset,
        "visual_distractor_onset_global_s": visual_distractor_onset_global,
        "visual_distractor_offset_time_s": visual_distractor_offset_time,
        "visual_distractor_offset_global_s": visual_distractor_offset_global,
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
        "cd_condition": cd_condition_from_mode(trial.corollary_mode),
        "cd_feedback_onset_s": corollary_onset,
        "cd_feedback_onset_global_s": corollary_onset_global,
        "corollary_onset_s": corollary_onset,
        "corollary_onset_global_s": corollary_onset_global,
        "cd_feedback_delay_from_response_s": (
            corollary_onset - (visual_onset + rt)
            if corollary_onset is not None and visual_onset is not None and rt is not None
            else None
        ),
        "corollary_delay_from_response_s": (
            corollary_onset - (visual_onset + rt)
            if trial.corollary_mode == "immediate"
            and corollary_onset is not None
            and visual_onset is not None
            and rt is not None
            else None
        ),
        "reversal_phase": trial.reversal_phase,
        "correct_response": trial.correct_response,
        "response": response,
        "response_onset_s": response_onset,
        "response_onset_global_s": response_onset_global,
        "rt_s": rt,
        "accuracy": accuracy,
        "trial_start_global_s": trial_start_global,
        "trial_end_global_s": trial_end_global,
        "trial_duration_s": (
            trial_end_global - trial_start_global
            if trial_end_global is not None and trial_start_global is not None
            else None
        ),
        # fMRI trigger-relative timestamps: only populated when fmri_mode is
        # on (see main()/show_trigger_and_wait). Empty otherwise, including
        # for every practice trial (which always runs before the trigger).
        "trigger_onset_global_s": trigger_onset_global,
        "trial_start_from_trigger_s": _from_trigger(trial_start_global, trigger_onset_global),
        "baseline_onset_from_trigger_s": _from_trigger(baseline_onset_global, trigger_onset_global),
        "visual_onset_from_trigger_s": _from_trigger(visual_onset_global, trigger_onset_global),
        "visual_offset_from_trigger_s": _from_trigger(visual_offset_global, trigger_onset_global),
        "visual_distractor_onset_from_trigger_s": _from_trigger(visual_distractor_onset_global, trigger_onset_global),
        "visual_distractor_offset_from_trigger_s": _from_trigger(visual_distractor_offset_global, trigger_onset_global),
        "paired_tone_onset_from_trigger_s": _from_trigger(paired_tone_onset_global, trigger_onset_global),
        "response_onset_from_trigger_s": _from_trigger(response_onset_global, trigger_onset_global),
        "corollary_onset_from_trigger_s": _from_trigger(corollary_onset_global, trigger_onset_global),
        "trial_end_from_trigger_s": _from_trigger(trial_end_global, trigger_onset_global),
    }


def show_trigger_and_wait(
    win, event, core, visual, trigger_keys: list[str], wait_duration: float, exp_clock=None
) -> float | None:
    """Wait for the scanner/EEG trigger key (default "s") and return the
    moment it was pressed, on the same clock used for every other timestamp
    in the CSV (exp_clock). That moment is TR0 / session t=0 for fMRI runs,
    and is what --fmri-mode timestamp correction is computed relative to.
    Returns None if exp_clock wasn't provided (trigger-relative columns will
    then simply stay empty).
    """
    stim = visual.TextStim(
        win,
        text="Ready to start Main Task?\n\nWaiting for trigger...",
        color="white",
        height=0.04,
        units="height",
    )
    stim.draw()
    win.flip()

    event.clearEvents()
    trigger_onset_global = None
    while True:
        keys = event.waitKeys(keyList=trigger_keys + ["escape", "q"])
        if keys:
            key = keys[0]
            if key in ["escape", "q"]:
                raise KeyboardInterrupt
            if key in trigger_keys:
                if exp_clock is not None:
                    trigger_onset_global = exp_clock.getTime()
                break

    if wait_duration > 0:
        stim_wait = visual.TextStim(
            win,
            text="Waiting...",
            color="white",
            height=0.04,
            units="height",
        )
        stim_wait.draw()
        win.flip()
        core.wait(wait_duration)

    return trigger_onset_global


def show_practice_feedback(
    win,
    event,
    visual,
    sound,
    language_dir: Path,
    practice_rows: list[dict],
) -> bool:
    active = [row for row in practice_rows if row["trial_type"] == "active" and row["accuracy"] is not None]
    if not active:
        return False
    accuracy = sum(int(row["accuracy"]) for row in active) / len(active)
    correct_rts = [float(row["rt_s"]) for row in active if row["accuracy"] == 1 and row["rt_s"] not in [None, ""]]
    mean_rt = sum(correct_rts) / len(correct_rts) if correct_rts else None

    if accuracy < 0.85:
        feedback = "FeedbackWelltried"
    elif accuracy <= 0.95:
        feedback = "FeedbackGoodjob"
    else:
        feedback = "FeedbackOutstanding"

    text = f"Practice Session complete!\n\nAccuracy: {accuracy * 100:.1f}%"
    if mean_rt is not None:
        text += f"\nMean RT: {mean_rt * 1000:.0f} ms"
    text += "\n\nPress R to repeat practice, or Space to continue to the experiment."

    image_path = existing_case_variant(language_dir / f"{feedback}.PNG")
    audio_path = existing_case_variant(language_dir / f"{feedback}.mp3")
    if audio_path.exists():
        try:
            audio = sound.Sound(str(audio_path))
            audio.play()
        except Exception:
            audio = None
    else:
        audio = None

    if image_path.exists():
        image = visual.ImageStim(win, image=str(image_path), pos=adjust_pos((0, 0.14)), size=(1.05, 0.78), units="height", **get_flip_params())
        image.draw()
    stim = visual.TextStim(win, text=text, pos=adjust_pos((0, -0.34)), color="white", height=0.035, units="height", **get_flip_params())
    stim.draw()
    win.flip()

    event.clearEvents()
    while True:
        keys = event.waitKeys(keyList=["r", "space", "escape", "q"])
        if keys:
            key = keys[0]
            if key in ["escape", "q"]:
                raise KeyboardInterrupt
            if audio:
                audio.stop()
            if key == "r":
                return True
            if key == "space":
                return False


def run_practice_phase(
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
    # Optional (default off): when args.suppress_practice_markers is set,
    # only the very first practice trial in the whole phase sends a single
    # "trial_start" marker, and every other in-trial marker is suppressed
    # for all practice trials (main-session markers are unaffected). This
    # keeps practice out of an EEG/marker recording while still logging
    # practice trials to CSV as normal. Off by default: practice sends
    # markers exactly like the main session, same as before this option
    # existed.
    trial_start_marker_sent = False
    for level in levels:
        template_dir = args.resource_root / LEVEL_TEMPLATES[level]
        assets = load_assets(template_dir, args.language)
        stimuli = make_stimuli(win, visual, assets)
        audio_cache = make_audio_cache(sound, assets)

        while True:
            practice_trials = list(generate_practice(level, args.practice, rng, args))
            if not practice_trials:
                break

            if not args.skip_instructions:
                show_welcome_slide(win, event, visual, level, phase="practice")
                show_level_instruction(win, event, visual, sound, assets, level, "practice")
                show_image_slide(win, event, visual, sound, assets["language"] / "PracticeStart.PNG", assets["language"] / "PracticeStart.mp3")

            practice_rows = []
            for trial in practice_trials:
                trial_counter += 1
                row = run_trial(
                    trial, args, win, core, event, visual, sound, stimuli, assets, audio_cache,
                    rng, trial_counter, exp_clock, markers, f"practice_level{level}",
                    send_markers=not args.suppress_practice_markers,
                    force_trial_start=not trial_start_marker_sent,
                )
                trial_start_marker_sent = True
                row["phase"] = "practice"
                writer.writerow(row)
                output_file.flush()
                practice_rows.append(row)

            if not args.skip_instructions:
                show_image_slide(win, event, visual, sound, assets["language"] / "PracticeEnd.PNG", assets["language"] / "PracticeEnd.mp3")

            # Check if user wants to repeat
            repeat = False
            if args.show_feedback:
                repeat = show_practice_feedback(
                    win,
                    event,
                    visual,
                    sound,
                    assets["language"],
                    practice_rows,
                )
            if not repeat:
                break

    return trial_counter


def show_feedback(
    win,
    event,
    visual,
    sound,
    language_dir: Path,
    recent_rows: list[dict],
    completed_trials: int,
    total_trials: int,
) -> None:
    active = [row for row in recent_rows if row["trial_type"] == "active" and row["accuracy"] is not None]
    if not active:
        return
    accuracy = sum(int(row["accuracy"]) for row in active) / len(active)

    if accuracy < 0.85:
        feedback = "FeedbackWelltried"
        message = "Well tried!"
    elif accuracy <= 0.95:
        feedback = "FeedbackGoodjob"
        message = "Good job!"
    else:
        feedback = "FeedbackOutstanding"
        message = "Outstanding!"

    progress = 100 * completed_trials / total_trials if total_trials else 0
    text = f"Task completed: {progress:.1f}%\n\nPress space to continue"

    image_path = existing_case_variant(language_dir / f"{feedback}.PNG")
    audio_path = existing_case_variant(language_dir / f"{feedback}.mp3")
    if audio_path.exists():
        audio = sound.Sound(str(audio_path))
        audio.play()
    else:
        audio = None
    if image_path.exists():
        image = visual.ImageStim(win, image=str(image_path), pos=adjust_pos((0, 0.14)), size=(1.05, 0.78), units="height", **get_flip_params())
        image.draw()
    else:
        fallback = visual.TextStim(win, text=message, pos=adjust_pos((0, 0.14)), color="white", height=0.08, units="height", **get_flip_params())
        fallback.draw()
    stim = visual.TextStim(win, text=text, pos=adjust_pos((0, -0.34)), color="white", height=0.035, units="height", **get_flip_params())
    stim.draw()
    win.flip()
    wait_for_continue(event)
    if audio:
        audio.stop()


def show_session_summary(
    win,
    event,
    visual,
    sound,
    language_dir: Path,
    session_rows: list[dict],
    label: str = "Session",
) -> None:
    """End-of-run accuracy summary for the main trial block.

    Mirrors show_practice_feedback (which already prints/displays accuracy
    at the end of practice), but for the full main session: no repeat
    option, and it is computed over *all* active trials run so far rather
    than just the most recent couple of blocks (that's what show_feedback,
    the per-block nudge, already does).
    """
    active = [row for row in session_rows if row["trial_type"] == "active" and row["accuracy"] is not None]
    if not active:
        return
    accuracy = sum(int(row["accuracy"]) for row in active) / len(active)
    correct_rts = [float(row["rt_s"]) for row in active if row["accuracy"] == 1 and row["rt_s"] not in [None, ""]]
    mean_rt = sum(correct_rts) / len(correct_rts) if correct_rts else None

    summary_line = f"{label} complete. Accuracy: {accuracy * 100:.1f}% ({len(active)} active trials)"
    if mean_rt is not None:
        summary_line += f", Mean RT: {mean_rt * 1000:.0f} ms"
    print(summary_line)

    if accuracy < 0.85:
        feedback = "FeedbackWelltried"
    elif accuracy <= 0.95:
        feedback = "FeedbackGoodjob"
    else:
        feedback = "FeedbackOutstanding"

    text = f"{label} complete!\n\nAccuracy: {accuracy * 100:.1f}%"
    if mean_rt is not None:
        text += f"\nMean RT: {mean_rt * 1000:.0f} ms"
    text += "\n\nPress space to continue"

    image_path = existing_case_variant(language_dir / f"{feedback}.PNG")
    audio_path = existing_case_variant(language_dir / f"{feedback}.mp3")
    audio = None
    if audio_path.exists():
        try:
            audio = sound.Sound(str(audio_path))
            audio.play()
        except Exception:
            audio = None

    if image_path.exists():
        image = visual.ImageStim(win, image=str(image_path), pos=adjust_pos((0, 0.14)), size=(1.05, 0.78), units="height", **get_flip_params())
        image.draw()
    else:
        fallback = visual.TextStim(win, text=f"{label} complete!", pos=adjust_pos((0, 0.14)), color="white", height=0.08, units="height", **get_flip_params())
        fallback.draw()
    stim = visual.TextStim(win, text=text, pos=adjust_pos((0, -0.34)), color="white", height=0.035, units="height", **get_flip_params())
    stim.draw()
    win.flip()
    wait_for_continue(event)
    if audio:
        audio.stop()


def run_main_level(
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
    audio_cache = make_audio_cache(sound, assets)
    active_trials, baseline_trials = parse_trials_per_block(args.trials_per_block)
    block_trial_count = active_trials + baseline_trials
    total_main_trials = args.blocks * block_trial_count

    if not args.skip_instructions:
        show_welcome_slide(win, event, visual, level)
        show_level_instruction(win, event, visual, sound, assets, level, "main")
        show_image_slide(win, event, visual, sound, assets["language"] / "Ready.PNG", assets["language"] / "Ready.mp3")

    block_rows: list[dict] = []
    ready_pending = False
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
        args.level2_cd,
    ):
        if trial.trial_in_block == 1:
            markers.send("block_start")
            if ready_pending:
                show_image_slide(win, event, visual, sound, assets["language"] / "Ready.PNG", assets["language"] / "Ready.mp3")
                ready_pending = False

        trial_counter += 1
        block_name = f"level{level}_block{trial.block:02d}"
        row = run_trial(
            trial, args, win, core, event, visual, sound, stimuli, assets, audio_cache,
            rng, trial_counter, exp_clock, markers, block_name
        )
        row["phase"] = "main"
        writer.writerow(row)
        output_file.flush()
        block_rows.append(row)

        if trial.trial_in_block == block_trial_count and trial.block % 2 == 0:
            if args.show_feedback:
                show_feedback(
                    win, event, visual, sound, assets["language"],
                    block_rows[-2 * block_trial_count:],
                    len(block_rows),
                    total_main_trials,
                )
            ready_pending = True

        if level == "2" and trial.block == args.blocks // 2 and trial.trial_in_block == block_trial_count:
            reversal = visual.TextStim(
                win,
                text="Rule change\n\nMeaningful: RIGHT\nAmbiguous: LEFT\n\nPress space to continue",
                color="white",
                height=0.04,
                units="height",
                **get_flip_params(),
            )
            reversal.draw()
            win.flip()
            wait_for_continue(event)
            ready_pending = True

    if args.show_feedback:
        show_session_summary(win, event, visual, sound, assets["language"], block_rows, label=f"Level {level} Session")

    if not args.skip_instructions:
        show_image_slide(win, event, visual, sound, assets["language"] / "ExperimentEnd.PNG", assets["language"] / "ExperimentEnd.mp3")

    return trial_counter


def run_intermixed_main_levels(
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
    audio_by_level = {
        level: make_audio_cache(sound, assets_by_level[level])
        for level in levels
    }
    active_trials, baseline_trials = parse_trials_per_block(args.trials_per_block)
    block_trial_count = active_trials + baseline_trials
    total_main_trials = len(levels) * args.blocks * block_trial_count

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
            args.level2_cd,
        )
        level_blocks.extend((level, block) for block in split_blocks(trials))
    rng.shuffle(level_blocks)

    recent_rows: list[dict] = []
    completed_level2_blocks = 0
    ready_pending = False
    active_instruction_level = None
    welcome_shown = True

    for mixed_block_index, (level, block_trials) in enumerate(level_blocks, start=1):
        assets = assets_by_level[level]
        stimuli = stimuli_by_level[level]
        if not args.skip_instructions and level != active_instruction_level:
            if not welcome_shown:
                show_welcome_slide(win, event, visual, level)
                welcome_shown = True
            show_level_instruction(win, event, visual, sound, assets, level, "main")
            show_image_slide(win, event, visual, sound, assets["language"] / "Ready.PNG", assets["language"] / "Ready.mp3")
            ready_pending = False
            active_instruction_level = level
        markers.send("block_start")
        if ready_pending:
            show_image_slide(win, event, visual, sound, assets["language"] / "Ready.PNG", assets["language"] / "Ready.mp3")
            ready_pending = False

        for trial in block_trials:
            trial_counter += 1
            block_name = f"mixed{mixed_block_index:02d}_level{level}_block{trial.block:02d}"
            row = run_trial(
                trial, args, win, core, event, visual, sound, stimuli, assets,
                audio_by_level[level], rng, trial_counter, exp_clock, markers, block_name
            )
            row["phase"] = "main"
            row["mixed_block_index"] = mixed_block_index
            writer.writerow(row)
            output_file.flush()
            recent_rows.append(row)

        if level == "2":
            completed_level2_blocks += 1
            if completed_level2_blocks == args.blocks // 2:
                show_transition_text(win, event, visual, "Rule change\nMeaningful: RIGHT\nAmbiguous: LEFT")
                ready_pending = True

        if mixed_block_index % 2 == 0:
            if args.show_feedback:
                show_feedback(
                    win, event, visual, sound, assets["language"],
                    recent_rows[-2 * block_trial_count:],
                    len(recent_rows),
                    total_main_trials,
                )
            ready_pending = True

    if levels:
        assets = assets_by_level[levels[-1]]
        if args.show_feedback:
            show_session_summary(win, event, visual, sound, assets["language"], recent_rows, label="Main Session")
        if not args.skip_instructions:
            show_image_slide(win, event, visual, sound, assets["language"] / "ExperimentEnd.PNG", assets["language"] / "ExperimentEnd.mp3")
    return trial_counter


def main() -> int:
    global CURRENT_ARGS
    args = parse_args()
    if not args.used_cli_config and not args.no_config_dialog:
        args = show_config_dialog(args)
        save_config_defaults(args_to_config(args))
    CURRENT_ARGS = args
    # Populated once the scanner/EEG trigger key is pressed (see
    # show_trigger_and_wait), and only when fmri_mode is on. Practice trials
    # always run before the trigger wait, so they never get a trigger
    # reference -- their *_from_trigger_s columns are simply empty.
    args.trigger_onset_global = None
    levels = [level.strip() for level in args.levels.split(",") if level.strip()]
    invalid = [level for level in levels if level not in LEVEL_TEMPLATES]
    if invalid:
        raise SystemExit(f"Invalid level(s): {invalid}. Use 1, 2, or 1,2.")
    validate_config(args)

    KEYS["left"] = parse_keys_list(args.left_keys)
    KEYS["right"] = parse_keys_list(args.right_keys)
    KEYS["trigger"] = parse_keys_list(args.trigger_keys)

    rng = random.Random(args.seed)
    output_dir = args.output_dir if args.output_dir is not None else ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
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
        Trial("1", 0, 0, "baseline", None, None, "baseline", None, None, None, "blank", None, None, None, None),
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
            trial_counter = run_practice_phase(
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
            trigger_onset_global = show_trigger_and_wait(
                win,
                event,
                core,
                visual,
                KEYS["trigger"],
                args.wait_duration_s,
                exp_clock=exp_clock,
            )
            # Only recorded/used when fmri_mode is on; otherwise this stays
            # None and every *_from_trigger_s CSV column is simply empty.
            args.trigger_onset_global = trigger_onset_global if args.fmri_mode else None
            if args.intermix_level_blocks:
                trial_counter = run_intermixed_main_levels(
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
                    trial_counter = run_main_level(
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
        marker_log_path = output_path.with_name(output_path.stem + "_markers.csv")
        markers.save_log(marker_log_path)
        markers.close()
        win.close()

    print(f"Data saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
