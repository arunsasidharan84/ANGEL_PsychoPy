"""Isolated tabbed setup UI for ANGEL's PsychoPy runner process.

Run in a child Python process so Qt cannot interfere with PsychoPy's own
window/event loop in Studio. Input and accepted settings are JSON files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


TABS = [
    ("Session", ["participant", "levels", "language", "category_set", "blocks",
                 "trials_per_block", "practice", "intermix_level_blocks",
                 "audio_instructions", "skip_instructions", "instruction_frequency",
                 "passive_mode"]),
    ("Scanner", ["fmri_mode", "tr_s", "dummy_scans", "trigger_keys",
                 "wait_duration_s", "slide_timeout"]),
    ("Timing", ["pre_stim_duration", "stim_duration", "response_window",
                "trial_duration", "inter_trial_jitter", "visual_distractor_mode",
                "visual_distractor_offset_min", "visual_distractor_offset_max",
                "paired_tone_offset_mode", "paired_tone_offset_min",
                "paired_tone_offset_max"]),
    ("Visual layout", ["central_spacing_pct", "distractor_spacing_pct",
                       "flip_horizontal", "flip_vertical", "fullscreen", "screen"]),
    ("Feedback", ["cd_schedule", "level2_cd", "show_feedback", "feedback_frequency",
                  "feedback_show_accuracy", "cd_audio_feedback", "cd_volume",
                  "cd_repeats", "cd_repeat_gap"]),
    ("Keys & markers", ["left_keys", "right_keys", "continue_keys", "marker_mode",
                       "lsl_stream_name", "parallel_address", "ttl_pulse_width",
                       "cpod_pulse_width_ms", "cpod_port", "suppress_practice_markers"]),
    ("Advanced", ["seed", "monitor", "resource_root", "output_dir", "trigger_codes"]),
]

CHOICES = {
    "levels": ["1,2", "1", "2"],
    "language": ["english", "hindi", "kannada"],
    "category_set": ["face", "shape", "all"],
    "blocks": [16, 8, 4],
    "trials_per_block": ["25+3", "20+3"],
    "visual_distractor_mode": ["sync", "desync", "none"],
    "paired_tone_offset_mode": ["continuous", "fixed"],
    "cd_schedule": ["by-block", "within-block", "all-immediate", "all-delayed", "all-none"],
    "instruction_frequency": [2, 1],
    "marker_mode": ["none", "lsl", "parallel", "cpod", "both"],
}

LEVEL_LABELS = {
    "1,2": "Levels 1 and 2 (in sequence)",
    "1": "Level 1 only",
    "2": "Level 2 only",
}

TONE_SCHEDULE_LABELS = {
    "by-block": "By block — immediate or delayed blocks",
    "within-block": "Within block — mix immediate and delayed trials",
    "all-immediate": "Immediate tones on eligible trials",
    "all-delayed": "Delayed tones on eligible trials",
    "all-none": "No trial-level tones",
}


def main(input_path: str, output_path: str) -> int:
    from PyQt6 import QtCore, QtWidgets

    from angel_paradigm_coder import SETUP_LABELS, SETUP_TIPS

    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    values = payload["values"]
    builder = bool(payload.get("builder", False))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("ANGEL experiment setup")
    dialog.resize(780, 660)
    dialog.setMinimumSize(640, 480)
    outer = QtWidgets.QVBoxLayout(dialog)
    title = QtWidgets.QLabel("ANGEL experiment settings")
    font = title.font()
    font.setPointSize(17)
    font.setBold(True)
    title.setFont(font)
    outer.addWidget(title)
    note = QtWidgets.QLabel("Switch tabs freely, then start the experiment with one click. Settings are remembered.")
    note.setWordWrap(True)
    outer.addWidget(note)

    tabs = QtWidgets.QTabWidget()
    tabs.setUsesScrollButtons(True)
    outer.addWidget(tabs, 1)
    widgets = {}
    for tab_name, keys in TABS:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        form.setContentsMargins(18, 18, 18, 18)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for key in keys:
            if key not in values or (builder and key in {"fullscreen", "screen"}):
                continue
            value = values[key]
            if key in CHOICES:
                widget = QtWidgets.QComboBox()
                options = [value, *(option for option in CHOICES[key] if option != value)]
                for option in options:
                    label = LEVEL_LABELS.get(option, str(option)) if key == "levels" else TONE_SCHEDULE_LABELS.get(option, str(option)) if key == "cd_schedule" else str(option)
                    widget.addItem(label, option)
            elif isinstance(value, bool):
                widget = QtWidgets.QCheckBox()
                widget.setChecked(value)
            elif isinstance(value, int):
                widget = QtWidgets.QSpinBox()
                widget.setRange(-1000000 if key == "seed" else 0, 1000000)
                widget.setValue(value)
            elif isinstance(value, float):
                widget = QtWidgets.QDoubleSpinBox()
                widget.setDecimals(3)
                widget.setRange(10.0 if key.endswith("_spacing_pct") else -1000000.0,
                                90.0 if key.endswith("_spacing_pct") else 1000000.0)
                widget.setSingleStep(1.0 if key.endswith("_spacing_pct") else 0.05)
                widget.setValue(value)
                if key.endswith("_spacing_pct"):
                    widget.setSuffix(" %")
            elif isinstance(value, dict):
                widget = QtWidgets.QPlainTextEdit(json.dumps(value, indent=2))
                widget.setMinimumHeight(180)
            else:
                widget = QtWidgets.QLineEdit(
                    ",".join(str(item) for item in value) if isinstance(value, list)
                    else "" if value is None else str(value)
                )
            widget.setToolTip(SETUP_TIPS.get(key, ""))
            label = SETUP_LABELS.get(key, key.replace("_", " ").capitalize())
            if key == "blocks":
                label = "Blocks per level"
            elif key == "seed":
                label = "Random seed (optional)"
            elif key == "trigger_codes":
                label = "Trigger codes (JSON)"
            elif key == "output_dir":
                label = "Output folder (default if blank)"
            form.addRow(label, widget)
            widgets[key] = widget
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        tabs.addTab(scroll, tab_name)

    run_plan = QtWidgets.QLabel()
    run_plan.setWordWrap(True)
    outer.addWidget(run_plan)

    def update_run_plan() -> None:
        levels_text = LEVEL_LABELS.get(widgets["levels"].currentData(), "Selected levels")
        blocks = widgets["blocks"].currentData()
        practice = widgets["practice"].value()
        instruction_note = (
            "Instruction slides skipped."
            if widgets["skip_instructions"].isChecked()
            else f"Instructions before practice and main trials, then every {widgets['instruction_frequency'].currentData()} block(s)."
        )
        run_plan.setText(
            f"Run plan: {levels_text}; {blocks} blocks and {practice} practice trials per level. {instruction_note}"
        )

    widgets["levels"].currentIndexChanged.connect(update_run_plan)
    widgets["blocks"].currentIndexChanged.connect(update_run_plan)
    widgets["practice"].valueChanged.connect(update_run_plan)
    widgets["skip_instructions"].toggled.connect(update_run_plan)
    widgets["instruction_frequency"].currentIndexChanged.connect(update_run_plan)
    update_run_plan()

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok |
        QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("Start experiment")
    outer.addWidget(buttons)

    def accept() -> None:
        result = dict(values)
        try:
            for key, widget in widgets.items():
                original = values[key]
                if key in CHOICES:
                    result[key] = widget.currentData()
                elif isinstance(original, bool):
                    result[key] = widget.isChecked()
                elif isinstance(original, int):
                    result[key] = widget.value()
                elif isinstance(original, float):
                    result[key] = widget.value()
                elif isinstance(original, dict):
                    parsed = json.loads(widget.toPlainText())
                    if not isinstance(parsed, dict):
                        raise ValueError("Trigger codes must be a JSON object.")
                    result[key] = parsed
                elif isinstance(original, list):
                    result[key] = [item.strip() for item in widget.text().split(",") if item.strip()]
                elif key == "seed":
                    text = widget.text().strip()
                    result[key] = int(text) if text else None
                elif key == "output_dir":
                    result[key] = widget.text().strip() or None
                else:
                    result[key] = widget.text().strip()
            if not result["participant"]:
                raise ValueError("Participant ID cannot be empty.")
            if not result["trigger_keys"]:
                raise ValueError("Enter at least one scanner trigger key.")
            Path(output_path).write_text(json.dumps(result), encoding="utf-8")
        except (ValueError, TypeError) as exc:
            QtWidgets.QMessageBox.warning(dialog, "Check setup", str(exc))
            return
        dialog.accept()

    buttons.accepted.connect(accept)
    buttons.rejected.connect(dialog.reject)
    return 0 if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted else 2


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: angel_setup_dialog.py INPUT_JSON OUTPUT_JSON")
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
