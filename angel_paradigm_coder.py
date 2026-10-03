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

DEFAULT_TRIGGER_CODES = {
    # Session & Block Boundaries
    "block_start": 1,
    "trial_start": 10,
    "baseline_start": 11,
    "trial_end": 90,
    "experiment_end": 99,
    "instruction_start": 101,
    "instruction_end": 102,
    "practice_start": 103,
    "practice_end": 104,
    "trigger_wait_start": 105,
    "trigger_received": 106,
    "feedback_start": 107,
    "feedback_end": 108,
    "reversal_rule_start": 109,
    "reversal_rule_end": 110,

    # Auditory Distractor Tones
    "paired_standard": 20,
    "paired_deviant": 21,

    # Visual Targets (General)
    "visual_frequent": 30,
    "visual_rare": 31,
    "visual_offset": 32,

    # Visual Targets (Hemifield specific - vital for N170/P1/LRP)
    "visual_frequent_left": 33,
    "visual_frequent_right": 34,
    "visual_rare_left": 35,
    "visual_rare_right": 36,

    # Participant Responses
    "response_left": 40,
    "response_right": 41,
    "response_miss": 42,

    # Corollary Discharge Feedback
    "cd_immediate": 50,
    "cd_delayed": 51,
    "cd_none": 52,
}

TRIGGER_CODE_METADATA = {
    "block_start": {"category": "Boundary", "description": "Start of an experimental block"},
    "trial_start": {"category": "Boundary", "description": "Onset of a trial epoch (fixation onset)"},
    "baseline_start": {"category": "Boundary", "description": "Start of baseline/rest trial"},
    "trial_end": {"category": "Boundary", "description": "End of trial epoch"},
    "experiment_end": {"category": "Boundary", "description": "Session completed slide"},
    "instruction_start": {"category": "Slide", "description": "Instruction slide presented"},
    "instruction_end": {"category": "Slide", "description": "Instruction slide dismissed"},
    "practice_start": {"category": "Boundary", "description": "Practice block started"},
    "practice_end": {"category": "Boundary", "description": "Practice block completed"},
    "trigger_wait_start": {"category": "Scanner", "description": "Waiting for scanner trigger"},
    "trigger_received": {"category": "Scanner", "description": "Scanner trigger pulse received"},
    "feedback_start": {"category": "Slide", "description": "Block performance feedback slide presented"},
    "feedback_end": {"category": "Slide", "description": "Feedback slide dismissed"},
    "reversal_rule_start": {"category": "Slide", "description": "Level 2 midpoint rule reversal instruction slide"},
    "reversal_rule_end": {"category": "Slide", "description": "Level 2 rule reversal slide dismissed"},
    "paired_standard": {"category": "Auditory", "description": "Auditory distractor standard tone (800 Hz)"},
    "paired_deviant": {"category": "Auditory", "description": "Auditory distractor deviant tone (500 Hz)"},
    "visual_frequent": {"category": "Visual", "description": "Frequent visual target stimulus (80%)"},
    "visual_rare": {"category": "Visual", "description": "Rare visual oddball stimulus (20%)"},
    "visual_offset": {"category": "Visual", "description": "Offset of visual target stimulus"},
    "visual_frequent_left": {"category": "Visual", "description": "Frequent visual target on left hemifield"},
    "visual_frequent_right": {"category": "Visual", "description": "Frequent visual target on right hemifield"},
    "visual_rare_left": {"category": "Visual", "description": "Rare visual target on left hemifield"},
    "visual_rare_right": {"category": "Visual", "description": "Rare visual target on right hemifield"},
    "response_left": {"category": "Response", "description": "Participant left key response"},
    "response_right": {"category": "Response", "description": "Participant right key response"},
    "response_miss": {"category": "Response", "description": "Trial omission / no response within response window"},
    "cd_immediate": {"category": "Corollary", "description": "Corollary discharge immediate tone (50 ms)"},
    "cd_delayed": {"category": "Corollary", "description": "Corollary discharge delayed tone (250 ms)"},
    "cd_none": {"category": "Corollary", "description": "Corollary discharge condition without tone feedback"},
}

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
    "category_set": "face",
    "paired_tone_offset_mode": "continuous",
    "paired_tone_offset_min": -0.240,
    "paired_tone_offset_max": 0.160,
    "cd_schedule": "by-block",
    "level2_cd": False,
    "intermix_level_blocks": False,
    "fmri_mode": False,
    "trials_per_block": "25+3",
    "continue_keys": ["any"],
    "slide_timeout": 5.0,
    "passive_mode": False,
    "tr_s": 2.0,
    "dummy_scans": 5,
    "screen": 0,
    "pre_stim_duration": 0.240,
    "stim_duration": 0.240,
    "response_window": 0.700,
    "trial_duration": 1.50,
    "inter_trial_jitter": 0.35,
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
    "left_keys": ["left", "z", "1", "4"],
    "right_keys": ["right", "slash", "2", "9"],
    "trigger_keys": ["space", "s", "4", "9"],
    "wait_duration_s": 11.0,
    "audio_instructions": True,
    "show_feedback": True,
    "feedback_frequency": 2,
    "feedback_show_accuracy": True,
    "flip_horizontal": False,
    "flip_vertical": False,
    "trigger_codes": dict(DEFAULT_TRIGGER_CODES),
}

KEYS = {
    "left": ["left", "z", "1", "4"],
    "right": ["right", "slash", "2", "9"],
    "quit": ["escape", "q"],
    "continue": ["any"],
    "trigger": ["space", "s", "4", "9"],
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


def parse_args(args_list: list[str] | None = None) -> argparse.Namespace:
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
    continue_default = config_defaults.get("continue_keys", ["any"])
    if isinstance(continue_default, list):
        continue_default = ",".join(continue_default)
    parser.add_argument(
        "--continue-keys",
        default=continue_default,
        help=f"Comma-separated keys to advance slides (use 'any' for any keypress). Default: {continue_default}",
    )
    parser.add_argument(
        "--slide-timeout",
        type=float,
        default=config_defaults.get("slide_timeout", 5.0),
        help="Timeout in seconds for instruction and feedback slides before auto-advancing (default: 5.0; 0 = no timeout).",
    )
    parser.add_argument(
        "--passive-mode",
        action="store_true",
        dest="passive_mode",
        help="Passive viewing mode: participant does not press buttons. Slides and trials auto-advance.",
    )
    parser.add_argument(
        "--no-passive-mode",
        action="store_false",
        dest="passive_mode",
        help="Active participant mode with button responses (default).",
    )
    parser.set_defaults(passive_mode=config_defaults.get("passive_mode", False))
    parser.add_argument(
        "--tr-s",
        type=float,
        default=config_defaults.get("tr_s", 2.0),
        help="fMRI Repetition Time (TR) in seconds. Default: 2.0.",
    )
    parser.add_argument(
        "--dummy-scans",
        type=int,
        default=config_defaults.get("dummy_scans", 5),
        help="Number of dummy scans before experiment starts. Default: 5.",
    )
    parser.add_argument(
        "--screen",
        type=int,
        default=config_defaults.get("screen", 0),
        help="Screen index to present experiment window on (0 for primary, 1 for extended). Default: 0.",
    )
    parser.add_argument(
        "--pre-stim-duration",
        type=float,
        default=config_defaults.get("pre_stim_duration", 0.240),
        help="Pre-stimulus baseline duration in seconds. Default: 0.240.",
    )
    parser.add_argument(
        "--trial-duration",
        type=float,
        default=config_defaults.get("trial_duration", 1.500),
        help="Total target trial duration in seconds. Default: 1.500.",
    )
    parser.add_argument(
        "--inter-trial-jitter",
        type=float,
        default=config_defaults.get("inter_trial_jitter", 0.350),
        help="Inter-trial jitter variation (+/- seconds) added to trial duration. Default: 0.350.",
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
    parser.add_argument(
        "--trigger-codes",
        default=None,
        help="Path to a custom trigger codes JSON file or inline JSON string to override codes.",
    )
    parser.add_argument(
        "--export-trigger-codes",
        default=None,
        help="Export current trigger codes to the specified JSON file and exit.",
    )
    args, _unknown = parser.parse_known_args(args_list)
    raw_argv = sys.argv[1:] if args_list is None else args_list
    args.used_cli_config = any(
        arg == option or arg.startswith(f"{option}=")
        for arg in raw_argv
        for option in EXPERIMENT_CLI_OPTIONS
    )
    active_codes = dict(config_defaults.get("trigger_codes", DEFAULT_TRIGGER_CODES))
    if getattr(args, "trigger_codes", None):
        tc_arg = str(args.trigger_codes).strip()
        tc_p = Path(tc_arg)
        if tc_p.exists() and tc_p.is_file():
            try:
                with tc_p.open("r", encoding="utf-8") as f:
                    loaded_tc = json.load(f)
                    if "event_id" in loaded_tc:
                        loaded_tc = loaded_tc["event_id"]
                    elif "trigger_codes" in loaded_tc:
                        loaded_tc = loaded_tc["trigger_codes"]
                    for k, v in loaded_tc.items():
                        active_codes[str(k)] = int(v)
            except Exception as exc:
                print(f"WARNING: Could not load trigger codes from {tc_p}: {exc}", file=sys.stderr)
        else:
            try:
                loaded_tc = json.loads(tc_arg)
                if isinstance(loaded_tc, dict):
                    for k, v in loaded_tc.items():
                        active_codes[str(k)] = int(v)
            except Exception as exc:
                print(f"WARNING: Could not parse --trigger-codes inline JSON: {exc}", file=sys.stderr)
    args.trigger_codes = active_codes
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
    "--trigger-codes",
    "--export-trigger-codes",
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
    skip_generic_unwrap = {"left_keys", "right_keys", "trigger_keys", "levels", "trigger_codes"}
    for key, value in loaded.items():
        if key not in CONFIG_DEFAULTS:
            continue
        if key not in skip_generic_unwrap:
            value = _dlg_scalar(value)
        config[key] = value

    if "trigger_codes" in loaded and isinstance(loaded["trigger_codes"], dict):
        merged = dict(DEFAULT_TRIGGER_CODES)
        for k, v in loaded["trigger_codes"].items():
            try:
                merged[str(k)] = int(v)
            except (ValueError, TypeError):
                pass
        config["trigger_codes"] = merged
    else:
        config["trigger_codes"] = dict(DEFAULT_TRIGGER_CODES)

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
    """Show the configuration dialog. Attempts modern PyQt6 tabbed dialog first;
    falls back to PsychoPy DlgFromDict if PyQt6 is not available."""
    res = _show_qt_config_dialog(args)
    if res is not None:
        return res
    return _show_psychopy_config_dialog(args)



def _show_qt_config_dialog(args: argparse.Namespace) -> argparse.Namespace | None:
    try:
        from PyQt6 import QtWidgets, QtCore, QtGui
    except Exception:
        return None

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class AngelConfigDialog(QtWidgets.QDialog):
        def __init__(self, args, parent=None):
            super().__init__(parent)
            self.args = args
            self.setWindowTitle("ANGEL Cognitive Paradigm Setup")
            self.resize(680, 640)
            self.setMinimumSize(600, 540)
            self._init_ui()

        def _init_ui(self):
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(18, 18, 18, 18)
            main_layout.setSpacing(14)

            # Title Header Banner
            header_widget = QtWidgets.QWidget()
            header_layout = QtWidgets.QVBoxLayout(header_widget)
            header_layout.setContentsMargins(0, 0, 0, 4)
            header_layout.setSpacing(2)

            title_label = QtWidgets.QLabel("ANGEL Cognitive Paradigm")
            title_font = QtGui.QFont()
            title_font.setPointSize(17)
            title_font.setBold(True)
            title_label.setFont(title_font)
            title_label.setStyleSheet("color: #1565C0; margin-bottom: 1px;")
            header_layout.addWidget(title_label)

            sub_label = QtWidgets.QLabel("Assessing Neurocognition via Gamified Experimental Logic — Setup & Parameters")
            sub_label.setStyleSheet("color: #616161; font-size: 12px;")
            header_layout.addWidget(sub_label)
            main_layout.addWidget(header_widget)

            # Tab Widget
            self.tabs = QtWidgets.QTabWidget()
            self.tabs.setStyleSheet("""
                QTabWidget::pane { border: 1px solid #CCCCCC; border-radius: 4px; background: #FAFAFA; }
                QTabBar::tab { font-size: 13px; font-weight: bold; padding: 8px 16px; margin-right: 2px; }
                QTabBar::tab:selected { background: #FFFFFF; color: #1565C0; border-bottom: 2px solid #1565C0; }
                QTabBar::tab:!selected { background: #E0E0E0; color: #555555; }
            """)
            main_layout.addWidget(self.tabs)

            self._build_tab_run()
            self._build_tab_timing()
            self._build_tab_io()
            self._build_tab_trigger_codes()

            # Connect listeners for instant live fMRI volume autocalculation
            for widget in [self.cb_levels, self.cb_blocks, self.cb_trials_per_block, self.cb_feedback_freq]:
                widget.currentIndexChanged.connect(self._update_fmri_calc)
            for widget in [self.dsb_tr, self.sb_dummy_scans, self.dsb_trial_dur, self.dsb_jitter, self.dsb_slide_timeout]:
                widget.valueChanged.connect(self._update_fmri_calc)
            for widget in [self.chk_feedback, self.chk_passive, self.chk_fmri]:
                widget.toggled.connect(self._update_fmri_calc)

            self._update_fmri_calc()

            # Footer Action Buttons
            btn_layout = QtWidgets.QHBoxLayout()
            btn_layout.setContentsMargins(0, 4, 0, 0)
            
            note_label = QtWidgets.QLabel("💡 All settings will be automatically remembered for subsequent runs.")
            note_label.setStyleSheet("color: #757575; font-size: 11px;")
            btn_layout.addWidget(note_label)
            btn_layout.addStretch()

            self.btn_cancel = QtWidgets.QPushButton("Cancel")
            self.btn_cancel.setFixedWidth(100)
            self.btn_cancel.setStyleSheet("padding: 7px 14px; font-size: 13px;")
            self.btn_cancel.clicked.connect(self.reject)
            btn_layout.addWidget(self.btn_cancel)

            self.btn_start = QtWidgets.QPushButton("▶ Start Experiment")
            self.btn_start.setFixedWidth(170)
            self.btn_start.setDefault(True)
            self.btn_start.setStyleSheet(
                "QPushButton { background-color: #1565C0; color: white; font-weight: bold; "
                "padding: 8px 18px; border-radius: 4px; font-size: 13px; } "
                "QPushButton:hover { background-color: #0D47A1; } "
                "QPushButton:pressed { background-color: #0A3880; }"
            )
            self.btn_start.clicked.connect(self._on_start)
            btn_layout.addWidget(self.btn_start)

            main_layout.addLayout(btn_layout)

        def _build_tab_run(self):
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QFormLayout(tab)
            layout.setContentsMargins(16, 18, 16, 16)
            layout.setSpacing(12)
            layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

            self.ed_participant = QtWidgets.QLineEdit(str(getattr(self.args, "participant", "test")))
            self.ed_participant.setStyleSheet("padding: 5px; font-size: 13px; font-weight: bold;")
            layout.addRow("<b>Participant ID:</b>", self.ed_participant)

            self.cb_levels = QtWidgets.QComboBox()
            self.cb_levels.addItem("Levels 1 & 2 (Full Experiment)", "1,2")
            self.cb_levels.addItem("Level 1 Only (Spatial Rule)", "1")
            self.cb_levels.addItem("Level 2 Only (Semantic Rule)", "2")
            cur_lvl = str(getattr(self.args, "levels", "1,2")).strip()
            idx = self.cb_levels.findData(cur_lvl)
            if idx >= 0: self.cb_levels.setCurrentIndex(idx)
            layout.addRow("<b>Experiment Levels:</b>", self.cb_levels)

            self.cb_category = QtWidgets.QComboBox()
            self.cb_category.addItem("Face (Mooney Faces) [Recommended]", "face")
            self.cb_category.addItem("Shape (Kanizsa Shapes)", "shape")
            self.cb_category.addItem("All (Face & Shape)", "all")
            cur_cat = str(getattr(self.args, "category_set", "face")).strip()
            idx = self.cb_category.findData(cur_cat)
            if idx >= 0: self.cb_category.setCurrentIndex(idx)
            layout.addRow("<b>Stimulus Family:</b>", self.cb_category)

            self.cb_language = QtWidgets.QComboBox()
            for lang in ["english", "hindi", "kannada"]:
                self.cb_language.addItem(lang.capitalize(), lang)
            cur_lang = str(getattr(self.args, "language", "english")).strip().lower()
            idx = self.cb_language.findData(cur_lang)
            if idx >= 0: self.cb_language.setCurrentIndex(idx)
            layout.addRow("Language:", self.cb_language)

            self.cb_blocks = QtWidgets.QComboBox()
            for b in [16, 8, 4]:
                self.cb_blocks.addItem(f"{b} Blocks per level", b)
            cur_b = int(getattr(self.args, "blocks", 16))
            idx = self.cb_blocks.findData(cur_b)
            if idx >= 0: self.cb_blocks.setCurrentIndex(idx)
            layout.addRow("Blocks per Level:", self.cb_blocks)

            self.cb_trials_per_block = QtWidgets.QComboBox()
            self.cb_trials_per_block.addItem("25 Active + 3 Baseline (Standard)", "25+3")
            self.cb_trials_per_block.addItem("20 Active + 3 Baseline (Shorter)", "20+3")
            cur_tpb = str(getattr(self.args, "trials_per_block", "25+3")).strip()
            idx = self.cb_trials_per_block.findData(cur_tpb)
            if idx >= 0: self.cb_trials_per_block.setCurrentIndex(idx)
            layout.addRow("Trials per Block:", self.cb_trials_per_block)

            self.sb_practice = QtWidgets.QSpinBox()
            self.sb_practice.setRange(0, 40)
            self.sb_practice.setValue(int(getattr(self.args, "practice", 6)))
            layout.addRow("Practice Trials per Level:", self.sb_practice)

            self.chk_fullscreen = QtWidgets.QCheckBox("Enable Fullscreen Mode")
            self.chk_fullscreen.setChecked(bool(getattr(self.args, "fullscreen", True)))
            layout.addRow("Display:", self.chk_fullscreen)

            self.chk_audio_inst = QtWidgets.QCheckBox("Play Audio Instruction Narrations")
            self.chk_audio_inst.setChecked(bool(getattr(self.args, "audio_instructions", True)))
            layout.addRow("Audio Narration:", self.chk_audio_inst)

            self.chk_skip_inst = QtWidgets.QCheckBox("Skip Instructions Directly to Trials")
            self.chk_skip_inst.setChecked(bool(getattr(self.args, "skip_instructions", False)))
            layout.addRow("Skip Instructions:", self.chk_skip_inst)

            self.chk_passive = QtWidgets.QCheckBox("Passive Viewing Mode (No button press required)")
            self.chk_passive.setChecked(bool(getattr(self.args, "passive_mode", False)))
            layout.addRow("Passive Viewing:", self.chk_passive)

            self.tabs.addTab(tab, "📋 Run & Session")

        def _build_tab_timing(self):
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QFormLayout(tab)
            layout.setContentsMargins(16, 18, 16, 16)
            layout.setSpacing(12)
            layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

            self.dsb_trial_dur = QtWidgets.QDoubleSpinBox()
            self.dsb_trial_dur.setRange(0.5, 5.0)
            self.dsb_trial_dur.setSingleStep(0.1)
            self.dsb_trial_dur.setDecimals(3)
            self.dsb_trial_dur.setValue(float(getattr(self.args, "trial_duration", 1.500)))
            layout.addRow("Trial Duration (s):", self.dsb_trial_dur)

            self.dsb_jitter = QtWidgets.QDoubleSpinBox()
            self.dsb_jitter.setRange(0.0, 2.0)
            self.dsb_jitter.setSingleStep(0.05)
            self.dsb_jitter.setDecimals(3)
            self.dsb_jitter.setValue(float(getattr(self.args, "inter_trial_jitter", 0.350)))
            layout.addRow("Inter-Trial Jitter (±s):", self.dsb_jitter)

            self.dsb_stim_dur = QtWidgets.QDoubleSpinBox()
            self.dsb_stim_dur.setRange(0.05, 1.0)
            self.dsb_stim_dur.setSingleStep(0.01)
            self.dsb_stim_dur.setDecimals(3)
            self.dsb_stim_dur.setValue(float(getattr(self.args, "stim_duration", 0.240)))
            layout.addRow("Stimulus Duration (s):", self.dsb_stim_dur)

            self.dsb_resp_win = QtWidgets.QDoubleSpinBox()
            self.dsb_resp_win.setRange(0.2, 2.0)
            self.dsb_resp_win.setSingleStep(0.05)
            self.dsb_resp_win.setDecimals(3)
            self.dsb_resp_win.setValue(float(getattr(self.args, "response_window", 0.700)))
            layout.addRow("Response Window (s):", self.dsb_resp_win)

            self.dsb_pre_stim = QtWidgets.QDoubleSpinBox()
            self.dsb_pre_stim.setRange(0.05, 1.0)
            self.dsb_pre_stim.setSingleStep(0.01)
            self.dsb_pre_stim.setDecimals(3)
            self.dsb_pre_stim.setValue(float(getattr(self.args, "pre_stim_duration", 0.240)))
            layout.addRow("Pre-Stimulus Baseline (s):", self.dsb_pre_stim)

            self.dsb_slide_timeout = QtWidgets.QDoubleSpinBox()
            self.dsb_slide_timeout.setRange(0.0, 60.0)
            self.dsb_slide_timeout.setSingleStep(1.0)
            self.dsb_slide_timeout.setDecimals(1)
            self.dsb_slide_timeout.setValue(float(getattr(self.args, "slide_timeout", 5.0)))
            self.dsb_slide_timeout.setToolTip("Seconds before instruction and feedback slides auto-advance. Set to 0 to wait indefinitely.")
            layout.addRow("<b>Slide Timeout (s):</b>", self.dsb_slide_timeout)

            self.chk_feedback = QtWidgets.QCheckBox("Show Block Performance Feedback")
            self.chk_feedback.setChecked(bool(getattr(self.args, "show_feedback", True)))
            layout.addRow("Block Feedback:", self.chk_feedback)

            self.cb_feedback_freq = QtWidgets.QComboBox()
            self.cb_feedback_freq.addItem("After Every 2nd Block (Standard)", 2)
            self.cb_feedback_freq.addItem("After Every Block", 1)
            cur_ff = int(getattr(self.args, "feedback_frequency", 2))
            idx = self.cb_feedback_freq.findData(cur_ff)
            if idx >= 0: self.cb_feedback_freq.setCurrentIndex(idx)
            layout.addRow("Feedback Frequency:", self.cb_feedback_freq)

            self.chk_show_acc = QtWidgets.QCheckBox("Show Accuracy % and Reaction Time on Feedback")
            self.chk_show_acc.setChecked(bool(getattr(self.args, "feedback_show_accuracy", True)))
            layout.addRow("Feedback Metrics:", self.chk_show_acc)

            self.cb_cd_sched = QtWidgets.QComboBox()
            for s in ["by-block", "within-block", "all-immediate", "all-delayed", "all-none"]:
                self.cb_cd_sched.addItem(s, s)
            cur_cd = str(getattr(self.args, "cd_schedule", "by-block"))
            idx = self.cb_cd_sched.findData(cur_cd)
            if idx >= 0: self.cb_cd_sched.setCurrentIndex(idx)
            layout.addRow("CD Schedule:", self.cb_cd_sched)

            self.chk_cd_audio = QtWidgets.QCheckBox("Play Corollary Tone on Response")
            self.chk_cd_audio.setChecked(bool(getattr(self.args, "cd_audio_feedback", True)))
            layout.addRow("CD Audio Sound:", self.chk_cd_audio)

            self.tabs.addTab(tab, "⏱️ Timing & Feedback")

        def _build_tab_io(self):
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QFormLayout(tab)
            layout.setContentsMargins(16, 18, 16, 16)
            layout.setSpacing(12)
            layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

            self.cb_marker = QtWidgets.QComboBox()
            self.cb_marker.addItem("None (No Hardware Markers)", "none")
            self.cb_marker.addItem("LSL Stream (LabStreamingLayer)", "lsl")
            self.cb_marker.addItem("Parallel Port TTL", "parallel")
            self.cb_marker.addItem("Cedrus C-Pod (USB Serial)", "cpod")
            self.cb_marker.addItem("Both (LSL + Parallel/C-Pod)", "both")
            cur_m = str(getattr(self.args, "marker_mode", "none"))
            idx = self.cb_marker.findData(cur_m)
            if idx >= 0: self.cb_marker.setCurrentIndex(idx)
            layout.addRow("<b>Marker Output Mode:</b>", self.cb_marker)

            self.ed_lsl = QtWidgets.QLineEdit(str(getattr(self.args, "lsl_stream_name", "ANGELMarkers")))
            layout.addRow("LSL Stream Name:", self.ed_lsl)

            self.ed_parallel = QtWidgets.QLineEdit(str(getattr(self.args, "parallel_address", "0x0378")))
            layout.addRow("Parallel Port Address:", self.ed_parallel)

            self.ed_cpod = QtWidgets.QLineEdit(str(getattr(self.args, "cpod_port", "")))
            self.ed_cpod.setPlaceholderText("Leave blank to auto-detect")
            layout.addRow("C-Pod Serial Port:", self.ed_cpod)

            self.chk_suppress_practice = QtWidgets.QCheckBox("Suppress Markers during Practice Phase")
            self.chk_suppress_practice.setChecked(bool(getattr(self.args, "suppress_practice_markers", False)))
            layout.addRow("Practice Markers:", self.chk_suppress_practice)

            self.chk_fmri = QtWidgets.QCheckBox("fMRI Scanner Session (Wait for scanner trigger)")
            self.chk_fmri.setChecked(bool(getattr(self.args, "fmri_mode", False)))
            layout.addRow("fMRI Mode:", self.chk_fmri)

            self.dsb_tr = QtWidgets.QDoubleSpinBox()
            self.dsb_tr.setRange(0.5, 6.0)
            self.dsb_tr.setSingleStep(0.1)
            self.dsb_tr.setDecimals(2)
            self.dsb_tr.setValue(float(getattr(self.args, "tr_s", 2.0)))
            layout.addRow("Repetition Time TR (s):", self.dsb_tr)

            self.sb_dummy_scans = QtWidgets.QSpinBox()
            self.sb_dummy_scans.setRange(0, 30)
            self.sb_dummy_scans.setValue(int(getattr(self.args, "dummy_scans", 5)))
            layout.addRow("Dummy Scans (Discards):", self.sb_dummy_scans)

            # Live fMRI scan calculation banner
            self.fmri_banner = QtWidgets.QFrame()
            self.fmri_banner.setStyleSheet("QFrame { background-color: #E3F2FD; border: 1px solid #90CAF9; border-radius: 6px; padding: 6px; }")
            banner_layout = QtWidgets.QVBoxLayout(self.fmri_banner)
            banner_layout.setContentsMargins(6, 6, 6, 6)
            self.lbl_fmri_calc = QtWidgets.QLabel()
            self.lbl_fmri_calc.setStyleSheet("color: #0D47A1; font-size: 11px;")
            banner_layout.addWidget(self.lbl_fmri_calc)
            layout.addRow("Scan Plan Estimator:", self.fmri_banner)

            def _fmt_keys(k):
                return ", ".join(k) if isinstance(k, list) else str(k)

            self.ed_trigger_keys = QtWidgets.QLineEdit(_fmt_keys(getattr(self.args, "trigger_keys", ["space", "s", "4", "9"])))
            layout.addRow("Scanner Trigger Keys:", self.ed_trigger_keys)

            self.dsb_wait_dur = QtWidgets.QDoubleSpinBox()
            self.dsb_wait_dur.setRange(1.0, 60.0)
            self.dsb_wait_dur.setValue(float(getattr(self.args, "wait_duration_s", 11.0)))
            layout.addRow("Trigger Wait Duration (s):", self.dsb_wait_dur)

            self.ed_left_keys = QtWidgets.QLineEdit(_fmt_keys(getattr(self.args, "left_keys", ["left", "z", "1", "4"])))
            layout.addRow("Left Response Keys:", self.ed_left_keys)

            self.ed_right_keys = QtWidgets.QLineEdit(_fmt_keys(getattr(self.args, "right_keys", ["right", "slash", "2", "9"])))
            layout.addRow("Right Response Keys:", self.ed_right_keys)

            self.ed_continue_keys = QtWidgets.QLineEdit(_fmt_keys(getattr(self.args, "continue_keys", ["any"])))
            layout.addRow("Continue Keys:", self.ed_continue_keys)

            self.sb_screen = QtWidgets.QSpinBox()
            self.sb_screen.setRange(0, 5)
            self.sb_screen.setValue(int(getattr(self.args, "screen", 0)))
            layout.addRow("Screen Index:", self.sb_screen)

            self.tabs.addTab(tab, "🔌 EEG, fMRI & Hardware")

        def _build_tab_trigger_codes(self):
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            info_label = QtWidgets.QLabel(
                "Hardware marker trigger codes (0–255). Changes are saved to angel_config.json "
                "and automatically exported as a companion JSON file for ERP analysis."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #424242; font-size: 11px;")
            layout.addWidget(info_label)

            self.table_triggers = QtWidgets.QTableWidget()
            self.table_triggers.setColumnCount(4)
            self.table_triggers.setHorizontalHeaderLabels(["Event Label", "Code (0-255)", "Category", "Description"])
            self.table_triggers.horizontalHeader().setStretchLastSection(True)
            self.table_triggers.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            self.table_triggers.setAlternatingRowColors(True)

            current_codes = getattr(self.args, "trigger_codes", {}) or DEFAULT_TRIGGER_CODES
            self.code_spinboxes = {}

            self.table_triggers.setRowCount(len(DEFAULT_TRIGGER_CODES))
            for row, (label, default_code) in enumerate(DEFAULT_TRIGGER_CODES.items()):
                code_val = int(current_codes.get(label, default_code))
                meta = TRIGGER_CODE_METADATA.get(label, {})
                cat = meta.get("category", "General")
                desc = meta.get("description", label)

                item_label = QtWidgets.QTableWidgetItem(label)
                item_label.setFlags(item_label.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

                sb = QtWidgets.QSpinBox()
                sb.setRange(0, 255)
                sb.setValue(code_val)
                self.code_spinboxes[label] = sb

                item_cat = QtWidgets.QTableWidgetItem(cat)
                item_cat.setFlags(item_cat.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

                item_desc = QtWidgets.QTableWidgetItem(desc)
                item_desc.setFlags(item_desc.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

                self.table_triggers.setItem(row, 0, item_label)
                self.table_triggers.setCellWidget(row, 1, sb)
                self.table_triggers.setItem(row, 2, item_cat)
                self.table_triggers.setItem(row, 3, item_desc)

            self.table_triggers.setColumnWidth(0, 160)
            self.table_triggers.setColumnWidth(1, 95)
            self.table_triggers.setColumnWidth(2, 95)
            layout.addWidget(self.table_triggers)

            btn_row = QtWidgets.QHBoxLayout()
            btn_reset = QtWidgets.QPushButton("Reset Codes to Defaults")
            btn_reset.clicked.connect(self._reset_trigger_codes)
            btn_row.addWidget(btn_reset)

            btn_export = QtWidgets.QPushButton("Export Trigger Codes JSON...")
            btn_export.clicked.connect(self._export_trigger_codes_dialog)
            btn_row.addWidget(btn_export)

            btn_row.addStretch()
            layout.addLayout(btn_row)

            self.tabs.addTab(tab, "🏷️ Trigger Codes")

        def _reset_trigger_codes(self):
            for label, default_code in DEFAULT_TRIGGER_CODES.items():
                if label in self.code_spinboxes:
                    self.code_spinboxes[label].setValue(default_code)

        def _get_active_trigger_codes(self) -> dict[str, int]:
            return {
                label: sb.value()
                for label, sb in self.code_spinboxes.items()
            }

        def _export_trigger_codes_dialog(self):
            codes = self._get_active_trigger_codes()
            default_path = str(ROOT / "data" / "angel_trigger_codes.json")
            out_file, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export Trigger Codes JSON", default_path, "JSON Files (*.json)"
            )
            if out_file:
                path = Path(out_file)
                sender = MarkerSender(self.args, None, None)
                sender.codes = codes
                p_text = self.ed_participant.text().strip() if hasattr(self, "ed_participant") else ""
                sender.save_trigger_codes_json(path, participant=p_text or "test")
                QtWidgets.QMessageBox.information(
                    self, "Export Successful", f"Trigger codes successfully saved to:\n{path}"
                )

        def _update_fmri_calc(self):
            import math
            levels_count = 2 if "1,2" in str(self.cb_levels.currentData()) else 1
            blocks = int(self.cb_blocks.currentData() or 16) * levels_count
            active_n, base_n = (25, 3) if "25+3" in str(self.cb_trials_per_block.currentData()) else (20, 3)
            t_per_block = active_n + base_n
            total_trials = blocks * t_per_block

            tr = self.dsb_tr.value()
            dummy_n = self.sb_dummy_scans.value()
            dummy_time = dummy_n * tr
            self.dsb_wait_dur.setValue(dummy_time)

            trial_dur = self.dsb_trial_dur.value()
            jitter = self.dsb_jitter.value()
            fb_enabled = self.chk_feedback.isChecked()
            fb_freq = int(self.cb_feedback_freq.currentData() or 2)
            timeout = self.dsb_slide_timeout.value()
            passive = self.chk_passive.isChecked()

            num_fb = (blocks // fb_freq) if (fb_enabled and fb_freq > 0) else 0
            min_fb_dur = timeout if passive else min(1.0, timeout)
            max_fb_dur = timeout
            mean_fb_dur = timeout if passive else (timeout + 1.0) / 2.0

            min_time = dummy_time + total_trials * max(0.5, trial_dur - jitter) + num_fb * min_fb_dur
            max_time = dummy_time + total_trials * (trial_dur + jitter) + num_fb * max_fb_dur
            mean_time = dummy_time + total_trials * trial_dur + num_fb * mean_fb_dur

            min_vols = math.ceil(min_time / tr)
            max_vols = math.ceil(max_time / tr)
            exp_vols = math.ceil(mean_time / tr)

            min_m, min_s = divmod(int(min_time), 60)
            max_m, max_s = divmod(int(max_time), 60)
            exp_m, exp_s = divmod(int(mean_time), 60)

            text = (
                f"<b>Expected Scan Volumes:</b> <b>{exp_vols} volumes</b> (Min: {min_vols}, Max: {max_vols})<br>"
                f"<b>Estimated Duration:</b> ~{exp_m}m {exp_s:02d}s (Range: {min_m}m {min_s:02d}s – {max_m}m {max_s:02d}s)<br>"
                f"<b>Dummy Equilibration:</b> {dummy_n} TRs = {dummy_time:.1f}s | Total Trials: {total_trials} across {blocks} blocks"
            )
            self.lbl_fmri_calc.setText(text)

        def _on_start(self):
            p_id = self.ed_participant.text().strip()
            self.args.participant = p_id if p_id else "test"
            self.args.levels = self.cb_levels.currentData()
            self.args.category_set = self.cb_category.currentData()
            self.args.language = self.cb_language.currentData()
            self.args.blocks = self.cb_blocks.currentData()
            self.args.trials_per_block = self.cb_trials_per_block.currentData()
            self.args.practice = self.sb_practice.value()
            self.args.fullscreen = self.chk_fullscreen.isChecked()
            self.args.audio_instructions = self.chk_audio_inst.isChecked()
            self.args.skip_instructions = self.chk_skip_inst.isChecked()
            self.args.passive_mode = self.chk_passive.isChecked()
            self.args.tr_s = self.dsb_tr.value()
            self.args.dummy_scans = self.sb_dummy_scans.value()

            self.args.trial_duration = self.dsb_trial_dur.value()
            self.args.inter_trial_jitter = self.dsb_jitter.value()
            self.args.stim_duration = self.dsb_stim_dur.value()
            self.args.response_window = self.dsb_resp_win.value()
            self.args.pre_stim_duration = self.dsb_pre_stim.value()
            self.args.slide_timeout = self.dsb_slide_timeout.value()

            self.args.show_feedback = self.chk_feedback.isChecked()
            self.args.feedback_frequency = self.cb_feedback_freq.currentData()
            self.args.feedback_show_accuracy = self.chk_show_acc.isChecked()
            self.args.cd_schedule = self.cb_cd_sched.currentData()
            self.args.cd_audio_feedback = self.chk_cd_audio.isChecked()

            self.args.marker_mode = self.cb_marker.currentData()
            self.args.lsl_stream_name = self.ed_lsl.text().strip()
            self.args.parallel_address = self.ed_parallel.text().strip()
            self.args.cpod_port = self.ed_cpod.text().strip()
            self.args.suppress_practice_markers = self.chk_suppress_practice.isChecked()
            self.args.fmri_mode = self.chk_fmri.isChecked()
            self.args.wait_duration_s = self.dsb_wait_dur.value()

            def _parse_keys(text):
                return [k.strip() for k in text.split(",") if k.strip()]

            self.args.left_keys = _parse_keys(self.ed_left_keys.text())
            self.args.right_keys = _parse_keys(self.ed_right_keys.text())
            self.args.trigger_keys = _parse_keys(self.ed_trigger_keys.text())
            self.args.continue_keys = _parse_keys(self.ed_continue_keys.text())
            self.args.screen = self.sb_screen.value()
            self.args.trigger_codes = self._get_active_trigger_codes()

            self.accept()

    dialog = AngelConfigDialog(args)
    if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        # Save updated configuration to angel_config.json so it is remembered
        try:
            save_config_defaults(args_to_config(args))
        except Exception:
            pass
        return args
    else:
        raise KeyboardInterrupt


def _show_psychopy_config_dialog(args: argparse.Namespace) -> argparse.Namespace:
    try:
        from psychopy import gui  # type: ignore
    except Exception:
        return args

    run_data = {
        "participant": args.participant,
        "levels": ["1,2", "1", "2"],
        "language": ["english", "hindi", "kannada"],
        "category_set": ["all", "face", "shape"],
        "blocks_per_level": [str(value) for value in BLOCK_CHOICES],
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
            "blocks_per_level",
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
        "pre_stim_duration": getattr(args, "pre_stim_duration", 0.240),
        "stim_duration": args.stim_duration,
        "response_window": args.response_window,
        "trial_duration": getattr(args, "trial_duration", 1.500),
        "inter_trial_jitter": getattr(args, "inter_trial_jitter", 0.350),
        "visual_distractor_mode": ["sync", "desync", "none"],
        "visual_distractor_offset_min": args.visual_distractor_offset_min,
        "visual_distractor_offset_max": args.visual_distractor_offset_max,
        "paired_tone_offset_mode": ["continuous", "fixed"],
        "paired_tone_offset_min": args.paired_tone_offset_min,
        "paired_tone_offset_max": args.paired_tone_offset_max,
        "cd_schedule": ["by-block", "within-block", "all-immediate", "all-delayed", "all-none"],
        "level2_cd": args.level2_cd,
        "show_feedback": args.show_feedback,
        "feedback_frequency": getattr(args, "feedback_frequency", 2),
        "feedback_show_accuracy": getattr(args, "feedback_show_accuracy", True),
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
            "pre_stim_duration",
            "stim_duration",
            "response_window",
            "trial_duration",
            "inter_trial_jitter",
            "visual_distractor_mode",
            "visual_distractor_offset_min",
            "visual_distractor_offset_max",
            "paired_tone_offset_mode",
            "paired_tone_offset_min",
            "paired_tone_offset_max",
            "cd_schedule",
            "level2_cd",
            "show_feedback",
            "feedback_frequency",
            "feedback_show_accuracy",
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
        "continue_keys": ",".join(args.continue_keys) if isinstance(args.continue_keys, list) else args.continue_keys,
        "trigger_keys": ",".join(args.trigger_keys) if isinstance(args.trigger_keys, list) else args.trigger_keys,
        "wait_duration_s": args.wait_duration_s,
        "screen": getattr(args, "screen", 0),
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
            "continue_keys",
            "trigger_keys",
            "wait_duration_s",
            "screen",
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
    args.blocks = int(_dlg_scalar(dialog_data["blocks_per_level"]))
    args.trials_per_block = str(_dlg_scalar(dialog_data["trials_per_block"]))
    args.practice = int(_dlg_scalar(dialog_data["practice"]))
    args.pre_stim_duration = float(_dlg_scalar(dialog_data["pre_stim_duration"]))
    args.stim_duration = float(_dlg_scalar(dialog_data["stim_duration"]))
    args.response_window = float(_dlg_scalar(dialog_data["response_window"]))
    args.trial_duration = float(_dlg_scalar(dialog_data["trial_duration"]))
    args.inter_trial_jitter = float(_dlg_scalar(dialog_data["inter_trial_jitter"]))
    args.visual_distractor_mode = str(_dlg_scalar(dialog_data["visual_distractor_mode"]))
    args.visual_distractor_offset_min = float(_dlg_scalar(dialog_data["visual_distractor_offset_min"]))
    args.visual_distractor_offset_max = float(_dlg_scalar(dialog_data["visual_distractor_offset_max"]))
    args.paired_tone_offset_mode = str(_dlg_scalar(dialog_data["paired_tone_offset_mode"]))
    args.paired_tone_offset_min = float(_dlg_scalar(dialog_data["paired_tone_offset_min"]))
    args.paired_tone_offset_max = float(_dlg_scalar(dialog_data["paired_tone_offset_max"]))
    args.cd_schedule = str(_dlg_scalar(dialog_data["cd_schedule"]))
    args.level2_cd = bool(_dlg_scalar(dialog_data["level2_cd"]))
    args.show_feedback = bool(_dlg_scalar(dialog_data["show_feedback"]))
    args.feedback_frequency = int(_dlg_scalar(dialog_data["feedback_frequency"]))
    args.feedback_show_accuracy = bool(_dlg_scalar(dialog_data["feedback_show_accuracy"]))
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
    pre_stim_duration = getattr(args, "pre_stim_duration", 0.240)
    trial_duration = getattr(args, "trial_duration", 1.500)
    inter_trial_jitter = getattr(args, "inter_trial_jitter", 0.350)
    if pre_stim_duration <= 0 or args.stim_duration <= 0 or args.response_window <= 0 or trial_duration <= 0:
        raise SystemExit("--pre-stim-duration, --stim-duration, --response-window, and --trial-duration must be positive.")
    if inter_trial_jitter < 0:
        raise SystemExit("--inter-trial-jitter must be >= 0.")
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

        # Pre-generate target sides for the block.
        #
        # Level 1: rare always on other_side (both category and side deviant) so
        #          that position is a valid and unambiguous response cue.
        #
        # Level 2: frequent stays on standard_side (defines the 80% standard).
        #          Rare trials are split into two deviant types:
        #   - Type A  ≥50%: non-standard_category + other_side
        #             (BOTH category AND side changed → maximum deviance, most
        #              error-inducing because position conflicts with semantics)
        #   - Type B  ≤50%: non-standard_category + standard_side
        #             (category-only change → subtler deviant, still conflict-free
        #              for position but unexpected image)
        #
        #          This prevents position from being a reliable proxy for the
        #          correct (semantic) response, raising task difficulty.
        if level == "1":
            trial_target_sides = [
                standard_side if freq == "frequent" else other_side
                for _, freq in active
            ]
        else:
            _rare_n = sum(1 for _, freq in active if freq == "rare")
            _rare_type_a = (_rare_n + 1) // 2          # ceil → ≥50% on other_side
            _rare_type_b = _rare_n - _rare_type_a      # floor → ≤50% on standard_side
            _rare_sides = [other_side] * _rare_type_a + [standard_side] * _rare_type_b
            rng.shuffle(_rare_sides)                   # randomise order within block

            trial_target_sides = []
            _rare_idx = 0
            for _, freq in active:
                if freq == "frequent":
                    trial_target_sides.append(standard_side)
                else:
                    trial_target_sides.append(_rare_sides[_rare_idx])
                    _rare_idx += 1

        for trial_index, ((stimulus_category, frequency_class), auditory_class) in enumerate(
            zip(active, auditory), start=1
        ):
            target_side = trial_target_sides[trial_index - 1]
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


def _continue_hint() -> str:
    """Human-readable description of the configured continue key(s)."""
    keys = KEYS.get("continue", ["space"])
    if not keys or "any" in keys:
        return "any key"
    return " / ".join(keys)


def wait_for_continue(event, timeout: float | None = None) -> None:
    if timeout is None and CURRENT_ARGS:
        timeout = getattr(CURRENT_ARGS, "slide_timeout", 5.0)
    event.clearEvents()
    allowed = None if "any" in KEYS.get("continue", ["any"]) else (KEYS.get("continue", []) + KEYS.get("quit", ["escape", "q"]))
    max_wait = timeout if (timeout is not None and timeout > 0) else None
    keys = event.waitKeys(maxWait=max_wait, keyList=allowed)
    if keys and keys[0] in KEYS.get("quit", ["escape", "q"]):
        raise KeyboardInterrupt
    # If key pressed or timeout expired, advance immediately
    return


_SOUND_CACHE: dict[str, Any] = {}


def get_cached_sound(sound, path: Path | str | None):
    """Retrieve or instantiate a cached sound.Sound object to prevent stream exhaustion."""
    if not path or sound is None:
        return None
    try:
        p = str(Path(path).resolve())
    except Exception:
        p = str(path)
    if p not in _SOUND_CACHE:
        try:
            _SOUND_CACHE[p] = sound.Sound(p)
        except Exception as exc:
            logging.warning("Could not load sound %s: %s", p, exc)
            return None
    return _SOUND_CACHE.get(p)


def clear_sound_cache() -> None:
    """Stop all cached sounds and clear cache to drain audio buffers safely."""
    for snd in list(_SOUND_CACHE.values()):
        try:
            if snd is not None:
                snd.stop()
        except Exception:
            pass
    _SOUND_CACHE.clear()


def show_image_slide(win, event, visual, sound, image_path: Path, audio_path: Path | None = None, timeout: float | None = None) -> None:
    image_path = existing_case_variant(image_path)
    if not image_path.exists():
        return
    slide = visual.ImageStim(win, image=str(image_path), size=(1.333, 1.0), units="height", **get_flip_params())
    
    play_audio = True
    if CURRENT_ARGS and not getattr(CURRENT_ARGS, "audio_instructions", True):
        play_audio = False
        
    audio = None
    if play_audio and audio_path:
        audio_path = existing_case_variant(audio_path)
        if audio_path.exists():
            audio = get_cached_sound(sound, audio_path)
                
    if audio:
        try:
            audio.play()
        except Exception:
            pass
    slide.draw()
    win.flip()
    wait_for_continue(event, timeout=timeout)
    if audio:
        try:
            audio.stop()
        except Exception:
            pass


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
    return {
        "corollary": get_cached_sound(sound, assets["corollary"]),
        "nocorollary": get_cached_sound(sound, assets["nocorollary"]),
    }


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
    CODES = dict(DEFAULT_TRIGGER_CODES)

    def __init__(self, args: argparse.Namespace, core, exp_clock) -> None:
        self.args = args
        self.core = core
        self.exp_clock = exp_clock
        self.outlet = None
        self.port = None
        self.cpod = None
        self.log: list[dict] = []

        self.codes = dict(DEFAULT_TRIGGER_CODES)
        custom_codes = getattr(args, "trigger_codes", None)
        if isinstance(custom_codes, dict):
            for k, v in custom_codes.items():
                try:
                    self.codes[str(k)] = int(v)
                except (ValueError, TypeError):
                    pass
        elif isinstance(custom_codes, str):
            try:
                parsed = json.loads(custom_codes)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        self.codes[str(k)] = int(v)
            except Exception:
                pass
        self.CODES = self.codes

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

    def _generate_mne_event_id(self) -> dict[str, int]:
        mne_map = {}
        for label, code in self.codes.items():
            slash_label = label.replace("_", "/")
            mne_map[slash_label] = code
        return mne_map

    def save_trigger_codes_json(self, path: Path, participant: str = "") -> None:
        """Write a clean, MNE/EEGLAB-ready JSON dictionary mapping trigger codes to events for ERP analysis."""
        from datetime import datetime
        data = {
            "paradigm": "ANGEL_PsychoPy",
            "participant": participant,
            "export_time": datetime.now().isoformat(),
            "event_id": dict(self.codes),
            "codes_to_labels": {str(v): k for k, v in self.codes.items()},
            "mne_event_id": self._generate_mne_event_id(),
            "descriptions": {
                k: TRIGGER_CODE_METADATA.get(k, {}).get("description", k)
                for k in self.codes
            },
            "trigger_metadata": {
                k: {
                    "code": v,
                    "category": TRIGGER_CODE_METADATA.get(k, {}).get("category", "General"),
                    "description": TRIGGER_CODE_METADATA.get(k, {}).get("description", k),
                }
                for k, v in self.codes.items()
            }
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"Trigger codes JSON written to {path}")
        except Exception as exc:
            print(f"WARNING: Could not write trigger codes JSON: {exc}", file=sys.stderr)

    def save_log(self, path: Path) -> None:
        """Write every marker sent this session to a CSV file (index, timestamp, label, code).

        Populated regardless of marker_mode (as long as at least one marker
        was sent), so it's a useful audit trail even for lsl/parallel-only
        runs, not just C-Pod ones.
        """
        if not self.log:
            return
        try:
            trig = getattr(self.args, "trigger_onset_global", None)
            enriched_log = []
            for entry in self.log:
                row_copy = dict(entry)
                ts = float(entry.get("timestamp_s", 0.0))
                if trig is not None:
                    row_copy["timestamp_from_trigger_s"] = f"{ts - trig:.6f}"
                else:
                    row_copy["timestamp_from_trigger_s"] = ""
                enriched_log.append(row_copy)
            with path.open("w", newline="", encoding="utf-8") as log_file:
                writer = csv.DictWriter(
                    log_file,
                    fieldnames=["marker_index", "timestamp_s", "timestamp_from_trigger_s", "label", "code"]
                )
                writer.writeheader()
                writer.writerows(enriched_log)
            print(f"Marker log written to {path}")
        except Exception as exc:
            print(f"WARNING: Could not write marker log: {exc}", file=sys.stderr)

    def send(self, label: str, code: int | None = None) -> float:
        marker_code = self.codes.get(label, 0) if code is None else code
        timestamp = self.exp_clock.getTime() if self.exp_clock is not None else 0.0
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


def save_fmri_events(path: Path, session_rows: list[dict], trigger_onset_global: float | None) -> None:
    """Save a clean, trigger-offset corrected event CSV (BIDS/SPM/FSL ready)."""
    if not session_rows or trigger_onset_global is None:
        return
    main_rows = [r for r in session_rows if r.get("phase") == "main"]
    if not main_rows:
        return
    fieldnames = [
        "onset",
        "duration",
        "trial_type",
        "stimulus_category",
        "target_side",
        "frequency_class",
        "auditory_class",
        "response_key",
        "rt_s",
        "accuracy",
    ]
    events = []
    for r in main_rows:
        t_type = r.get("trial_type")
        if t_type == "baseline":
            onset = r.get("baseline_onset_from_trigger_s")
            duration = r.get("trial_duration_actual_s") or 1.500
            events.append({
                "onset": f"{float(onset):.4f}" if onset not in [None, ""] else "",
                "duration": f"{float(duration):.4f}",
                "trial_type": "baseline",
                "stimulus_category": "baseline",
                "target_side": "",
                "frequency_class": "baseline",
                "auditory_class": "blank",
                "response_key": "",
                "rt_s": "",
                "accuracy": "",
            })
        else:
            onset = r.get("visual_onset_from_trigger_s")
            cat = r.get("stimulus_category") or ""
            freq = r.get("frequency_class") or ""
            side = r.get("target_side") or ""
            events.append({
                "onset": f"{float(onset):.4f}" if onset not in [None, ""] else "",
                "duration": f"{float(r.get('stim_duration') or 0.240):.4f}",
                "trial_type": f"{cat}_{freq}_{side}".strip("_"),
                "stimulus_category": cat,
                "target_side": side,
                "frequency_class": freq,
                "auditory_class": r.get("auditory_class") or "",
                "response_key": r.get("response_key") or "",
                "rt_s": f"{float(r['rt_s']):.4f}" if r.get("rt_s") not in [None, ""] else "",
                "accuracy": r.get("accuracy") if r.get("accuracy") is not None else "",
            })
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(events)
        print(f"fMRI BOLD events written to {path}")
    except Exception as exc:
        print(f"WARNING: Could not write fMRI events: {exc}", file=sys.stderr)


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
    response_keys = KEYS["quit"] if getattr(args, "passive_mode", False) else flatten([KEYS["left"], KEYS["right"], KEYS["quit"]])
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

    pre_stim_duration = getattr(args, "pre_stim_duration", 0.240)
    pre_stim_s = max(pre_stim_duration, -args.paired_tone_offset_min)
    fixed_active = pre_stim_s + args.response_window
    post_mask_min = max(0.05, args.trial_duration - args.inter_trial_jitter - fixed_active)
    post_mask_max = max(post_mask_min, args.trial_duration + args.inter_trial_jitter - fixed_active)

    if trial.trial_type == "baseline":
        stimuli["fix"].draw()
        win.flip()
        baseline_onset = exp_clock.getTime()
        send_marker("baseline_start")
        baseline_duration = rng.uniform(max(0.2, args.trial_duration - args.inter_trial_jitter), max(0.2, args.trial_duration + args.inter_trial_jitter))
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

    # Trial Timeline and Duration Documentation:
    # ----------------------------------------
    # Total Trial Duration = pre_stim_s + response_window + post_mask_duration
    # - pre_stim_s: Pre-stimulus mask duration (args.pre_stim_duration, default 0.240s, or larger if needed for negative tone offsets).
    # - response_window: Active response window from visual onset (args.response_window, default 0.700s). Note that stim_duration (0.240s) occurs within response_window.
    # - post_mask_duration: Post-stimulus mask duration dynamically calculated from trial_duration (default 1.50s) and inter_trial_jitter (default 0.35s).
    #
    # Derivation Formula:
    #   fixed_active = pre_stim_s + args.response_window
    #   target_duration = trial_duration +/- inter_trial_jitter
    #   post_mask_min = max(0.05, args.trial_duration - args.inter_trial_jitter - fixed_active)
    #   post_mask_max = max(post_mask_min, args.trial_duration + args.inter_trial_jitter - fixed_active)
    #   post_mask_duration = rng.uniform(post_mask_min, post_mask_max)
    tone = None
    tone_start_s = None

    if trial.auditory_class != "blank" and trial.auditory_offset_s is not None:
        tone_path = paired_tone_path(trial, args, assets)
        paired_tone_file = tone_path.name
        tone = get_cached_sound(sound, tone_path)
        tone_start_s = max(0.0, pre_stim_s + trial.auditory_offset_s)

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
    visual_label = f"visual_{trial.frequency_class}"
    side_label = f"visual_{trial.frequency_class}_{trial.target_side}" if trial.target_side else None
    if side_label and side_label in getattr(markers, "codes", {}):
        send_marker(side_label)
    else:
        send_marker(visual_label)
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
    post_mask_duration = rng.uniform(post_mask_min, post_mask_max)
    post_mask_end = post_mask_start + post_mask_duration

    if response is None:
        if not getattr(args, "passive_mode", False):
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
    if trial.correct_response and not getattr(args, "passive_mode", False):
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
    if CURRENT_ARGS and not getattr(CURRENT_ARGS, "show_feedback", True):
        return False
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
    if getattr(CURRENT_ARGS, "passive_mode", False):
        text += "\n\nContinuing automatically..."
    else:
        text += "\n\nPress R to repeat practice, or Space / Continue key to continue."

    image_path = existing_case_variant(language_dir / f"{feedback}.PNG")
    audio_path = existing_case_variant(language_dir / f"{feedback}.mp3")
    play_audio = True
    if CURRENT_ARGS and not getattr(CURRENT_ARGS, "audio_instructions", True):
        play_audio = False

    audio = None
    if play_audio and audio_path.exists():
        audio = get_cached_sound(sound, audio_path)
    if audio:
        try:
            audio.play()
        except Exception:
            pass

    if image_path.exists():
        image = visual.ImageStim(win, image=str(image_path), pos=adjust_pos((0, 0.14)), size=(1.05, 0.78), units="height", **get_flip_params())
        image.draw()
    stim = visual.TextStim(win, text=text, pos=adjust_pos((0, -0.34)), color="white", height=0.035, units="height", **get_flip_params())
    stim.draw()
    win.flip()

    timeout = getattr(CURRENT_ARGS, "slide_timeout", 5.0)
    max_wait = timeout if (timeout is not None and timeout > 0) else None

    event.clearEvents()
    if getattr(CURRENT_ARGS, "passive_mode", False):
        keys = event.waitKeys(maxWait=max_wait, keyList=KEYS.get("quit", ["escape", "q"]))
        if keys and keys[0] in KEYS.get("quit", ["escape", "q"]):
            raise KeyboardInterrupt
        if audio:
            try:
                audio.stop()
            except Exception:
                pass
        return False

    allowed = ["r", "escape", "q"]
    cont_keys = KEYS.get("continue", ["any"])
    if "any" in cont_keys:
        allowed = None
    else:
        allowed = list(set(allowed + cont_keys + ["space"]))

    keys = event.waitKeys(maxWait=max_wait, keyList=allowed)
    if audio:
        try:
            audio.stop()
        except Exception:
            pass
    if keys:
        key = keys[0]
        if key in KEYS.get("quit", ["escape", "q"]):
            raise KeyboardInterrupt
        if key == "r":
            return True
        return False
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
    show_instructions: bool = False,
) -> int:
    trial_start_marker_sent = False
    for level in levels:
        template_dir = args.resource_root / LEVEL_TEMPLATES[level]
        assets = load_assets(template_dir, args.language)
        stimuli = make_stimuli(win, visual, assets)
        audio_cache = make_audio_cache(sound, assets)
        should_show_inst = show_instructions

        while True:
            practice_trials = list(generate_practice(level, args.practice, rng, args))
            if not practice_trials:
                break

            if should_show_inst and not args.skip_instructions:
                show_level_instruction(win, event, visual, sound, assets, level, "practice")

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
                if hasattr(output_file, "flush"):
                    output_file.flush()
                practice_rows.append(row)

            # Check if user wants to repeat
            repeat = False
            if getattr(args, "show_feedback", True):
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
            should_show_inst = True

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
    if CURRENT_ARGS and not getattr(CURRENT_ARGS, "show_feedback", True):
        return
    active = [row for row in recent_rows if row["trial_type"] == "active" and row["accuracy"] is not None]
    if not active:
        return
    accuracy = sum(int(row["accuracy"]) for row in active) / len(active)
    correct_rts = [float(row["rt_s"]) for row in active if row["accuracy"] == 1 and row["rt_s"] not in [None, ""]]
    mean_rt = sum(correct_rts) / len(correct_rts) if correct_rts else None

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
    hint = _continue_hint()
    show_acc = getattr(CURRENT_ARGS, "feedback_show_accuracy", True)
    text = f"Task completed: {progress:.1f}%"
    if show_acc:
        text += f"\nAccuracy: {accuracy * 100:.1f}%"
        if mean_rt is not None:
            text += f"\nMean RT: {mean_rt * 1000:.0f} ms"
    if getattr(CURRENT_ARGS, "passive_mode", False):
        text += "\n\nContinuing automatically..."
    else:
        text += f"\n\nPress {hint} to continue"

    image_path = existing_case_variant(language_dir / f"{feedback}.PNG")
    audio_path = existing_case_variant(language_dir / f"{feedback}.mp3")
    play_audio = True
    if CURRENT_ARGS and not getattr(CURRENT_ARGS, "audio_instructions", True):
        play_audio = False

    audio = None
    if play_audio and audio_path.exists():
        audio = get_cached_sound(sound, audio_path)
    if audio:
        try:
            audio.play()
        except Exception:
            pass

    if image_path.exists():
        image = visual.ImageStim(win, image=str(image_path), pos=adjust_pos((0, 0.14)), size=(1.05, 0.78), units="height", **get_flip_params())
        image.draw()
    else:
        fallback = visual.TextStim(win, text=message, pos=adjust_pos((0, 0.14)), color="white", height=0.08, units="height", **get_flip_params())
        fallback.draw()
    stim = visual.TextStim(win, text=text, pos=adjust_pos((0, -0.34)), color="white", height=0.035, units="height", **get_flip_params())
    stim.draw()
    win.flip()
    wait_for_continue(event, timeout=getattr(CURRENT_ARGS, "slide_timeout", 5.0))
    if audio:
        try:
            audio.stop()
        except Exception:
            pass


def show_session_summary(
    win,
    event,
    visual,
    sound,
    language_dir: Path,
    session_rows: list[dict],
    label: str = "Session",
) -> None:
    if CURRENT_ARGS and not getattr(CURRENT_ARGS, "show_feedback", True):
        return
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

    show_acc = getattr(CURRENT_ARGS, "feedback_show_accuracy", True)
    text = f"{label} complete!"
    if show_acc:
        text += f"\n\nAccuracy: {accuracy * 100:.1f}%"
        if mean_rt is not None:
            text += f"\nMean RT: {mean_rt * 1000:.0f} ms"
    if getattr(CURRENT_ARGS, "passive_mode", False):
        text += "\n\nContinuing automatically..."
    else:
        text += f"\n\nPress {_continue_hint()} to continue"

    image_path = existing_case_variant(language_dir / f"{feedback}.PNG")
    audio_path = existing_case_variant(language_dir / f"{feedback}.mp3")
    play_audio = True
    if CURRENT_ARGS and not getattr(CURRENT_ARGS, "audio_instructions", True):
        play_audio = False

    audio = None
    if play_audio and audio_path.exists():
        audio = get_cached_sound(sound, audio_path)
    if audio:
        try:
            audio.play()
        except Exception:
            pass

    if image_path.exists():
        image = visual.ImageStim(win, image=str(image_path), pos=adjust_pos((0, 0.14)), size=(1.05, 0.78), units="height", **get_flip_params())
        image.draw()
    else:
        fallback = visual.TextStim(win, text=f"{label} complete!", pos=adjust_pos((0, 0.14)), color="white", height=0.08, units="height", **get_flip_params())
        fallback.draw()
    stim = visual.TextStim(win, text=text, pos=adjust_pos((0, -0.34)), color="white", height=0.035, units="height", **get_flip_params())
    stim.draw()
    win.flip()
    wait_for_continue(event, timeout=getattr(CURRENT_ARGS, "slide_timeout", 5.0))
    if audio:
        try:
            audio.stop()
        except Exception:
            pass


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

    if not args.skip_instructions and args.practice == 0:
        # Show instruction slide if practice was skipped
        show_level_instruction(win, event, visual, sound, assets, level, "main")

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
    if getattr(args, "export_trigger_codes", None):
        out_p = Path(args.export_trigger_codes)
        ms = MarkerSender(args, None, None)
        ms.save_trigger_codes_json(out_p, participant=getattr(args, "participant", "test"))
        print(f"Trigger codes successfully exported to {out_p}")
        return 0

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
    KEYS["continue"] = parse_keys_list(getattr(args, "continue_keys", "any"))
    KEYS["trigger"] = parse_keys_list(args.trigger_keys)

    rng = random.Random(args.seed)
    output_dir = args.output_dir if args.output_dir is not None else ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"angel_{args.participant}_{'_'.join(levels)}_{stamp}.csv"

    core, event, sound, visual = get_psychopy()
    win = visual.Window(
        fullscr=args.fullscreen,
        screen=getattr(args, "screen", 0),
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
                show_instructions=True,
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
        trig_json_path = output_path.with_name(output_path.stem + "_trigger_codes.json")
        markers.save_trigger_codes_json(trig_json_path, participant=args.participant)
        try:
            markers.save_trigger_codes_json(output_path.parent / "angel_trigger_codes.json", participant=args.participant)
        except Exception:
            pass
        if args.fmri_mode and getattr(args, "trigger_onset_global", None) is not None:
            fmri_events_path = output_path.with_name(output_path.stem + "_fmri_events.csv")
            try:
                with output_path.open("r", encoding="utf-8") as f:
                    csv_rows = list(csv.DictReader(f))
                save_fmri_events(fmri_events_path, csv_rows, args.trigger_onset_global)
            except Exception as e:
                print(f"Could not export fMRI events: {e}", file=sys.stderr)
        markers.close()
        win.close()

    print(f"Data saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
