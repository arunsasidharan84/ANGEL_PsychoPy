import random
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import angel_paradigm_coder as engine
from angel_setup_dialog import TABS


ROOT = Path(__file__).resolve().parents[1]


class _Clock:
    def __init__(self):
        self.value = 0.0

    def reset(self):
        self.value = 0.0

    def getTime(self):
        self.value += 0.01
        return self.value


class _Core:
    Clock = _Clock

    @staticmethod
    def wait(*_args, **_kwargs):
        return None


class _Stim:
    def draw(self):
        return None


class _Visual:
    @staticmethod
    def ImageStim(*_args, **_kwargs):
        return _Stim()


class _Window:
    def flip(self):
        return None


class _Event:
    @staticmethod
    def clearEvents():
        return None

    @staticmethod
    def getKeys(*_args, **_kwargs):
        return []


class _Markers:
    codes = engine.DEFAULT_TRIGGER_CODES

    def send(self, *_args, **_kwargs):
        return None


class PortabilityTests(unittest.TestCase):
    def test_ready_slide_is_not_presented_between_blocks(self):
        source = (ROOT / "angel_paradigm_coder.py").read_text(encoding="utf-8")
        self.assertNotIn('assets["language"] / "Ready.PNG"', source)
        self.assertNotIn('assets["language"] / "Ready.mp3"', source)

    def test_builder_data_filename_does_not_duplicate_data_folder(self):
        root = ET.parse(ROOT / "angel_paradigm.psyexp").getroot()
        value = next(
            node.attrib["val"]
            for node in root.iter("Param")
            if node.attrib.get("name") == "Data filename"
        )
        self.assertNotIn("u'data/", value)

    def test_builder_uses_portable_keyboard_backend(self):
        root = ET.parse(ROOT / "angel_paradigm.psyexp").getroot()
        value = next(
            node.attrib["val"]
            for node in root.iter("Param")
            if node.attrib.get("name") == "keyboardBackend"
        )
        self.assertEqual(value, "Pyglet")

    def test_cli_launch_can_skip_nested_config_dialog(self):
        args = engine.parse_args(["--participant", "smoke", "--no-config-dialog"])
        self.assertIs(engine.show_config_dialog(args), args)

    def test_studio_launch_context_is_detected(self):
        args = engine.parse_args(
            ["--pilot", "--prefs-json", "/tmp/psychopy-preferences.json"]
        )
        self.assertTrue(args.launched_from_studio)
        self.assertIs(engine.show_config_dialog(args), args)

    def test_setup_labels_preserve_internal_keys(self):
        class Gui:
            @staticmethod
            def DlgFromDict(dictionary, title, order, tip, alwaysOnTop=False):
                self.assertEqual(order, ["Participant ID", "Wait for scanner trigger"])
                self.assertTrue(alwaysOnTop)
                dictionary["Participant ID"] = "p001"
                dictionary["Wait for scanner trigger"] = True
                return SimpleNamespace(OK=True)

        data = {"participant": "", "fmri_mode": False}
        engine.show_dialog_page(Gui, data, "Session", list(data))
        self.assertEqual(data, {"participant": "p001", "fmri_mode": True})

    def test_builder_scanner_trigger_uses_configured_keys(self):
        root = ET.parse(ROOT / "angel_paradigm.psyexp").getroot()
        values = [node.attrib.get("val", "") for node in root.iter("Param")]
        self.assertIn("ANGEL_TRIGGER_KEYS", values)
        self.assertTrue(any("fallback_keys = event.getKeys" in value for value in values))
        self.assertFalse(any("record_trigger_onset" in value for value in values))

    def test_builder_setup_pages_fit_a_laptop_screen(self):
        pages = []

        class Gui:
            @staticmethod
            def DlgFromDict(dictionary, title, order, tip, alwaysOnTop=False):
                pages.append((title, len(order)))
                return SimpleNamespace(OK=True)

        args = engine.parse_args(["--participant", "screen-test"])
        with patch.dict(sys.modules, {"psychopy": SimpleNamespace(gui=Gui)}):
            result = engine._show_psychopy_config_dialog(args, builder=True)
        self.assertEqual(result.participant, "screen-test")
        self.assertEqual(len(pages), 6)
        self.assertTrue(all(count <= 10 for _, count in pages))

    def test_tabbed_setup_exposes_every_config_setting(self):
        fields = [key for _, keys in TABS for key in keys]
        self.assertEqual(set(fields), set(engine.CONFIG_DEFAULTS))
        self.assertEqual(len(fields), len(set(fields)))

    def test_horizontal_spacing_is_percent_of_screen_width(self):
        class Visual:
            @staticmethod
            def ImageStim(_win, **kwargs):
                return SimpleNamespace(**kwargs)

        previous = engine.CURRENT_ARGS
        try:
            engine.CURRENT_ARGS = SimpleNamespace(
                central_spacing_pct=38.0,
                distractor_spacing_pct=50.0,
                flip_horizontal=False,
                flip_vertical=False,
            )
            stimuli = engine.make_stimuli(
                SimpleNamespace(size=(1280, 800)), Visual,
                {"checkerboard": Path("checkerboard.png"), "fixation": Path("fixation.png")},
            )
        finally:
            engine.CURRENT_ARGS = previous
        central_gap_px = (stimuli["right_mask"].pos[0] - stimuli["left_mask"].pos[0]) * 800
        distractor_gap_px = (
            stimuli["top_right_distractor"].pos[0] - stimuli["top_left_distractor"].pos[0]
        ) * 800
        self.assertAlmostEqual(central_gap_px / 1280, 0.38)
        self.assertAlmostEqual(distractor_gap_px / 1280, 0.50)
        self.assertEqual(stimuli["left_target_pos"], stimuli["left_mask"].pos)

    def test_spacing_settings_are_available_to_cli_and_config(self):
        args = engine.parse_args([
            "--central-spacing-pct", "41",
            "--distractor-spacing-pct", "54",
            "--no-config-dialog",
        ])
        self.assertEqual(args.central_spacing_pct, 41.0)
        self.assertEqual(engine.args_to_config(args)["distractor_spacing_pct"], 54.0)
        engine.validate_config(args)

    def test_isolated_tabbed_setup_returns_edited_values(self):
        import json

        def fake_run(command, **_kwargs):
            request = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            self.assertTrue(request["builder"])
            values = request["values"]
            values["central_spacing_pct"] = 42.0
            Path(command[3]).write_text(json.dumps(values), encoding="utf-8")
            return SimpleNamespace(returncode=0, stderr="")

        args = engine.parse_args(["--participant", "tab-test"])
        with patch("subprocess.run", side_effect=fake_run):
            updated = engine._show_isolated_tabbed_config_dialog(args, builder=True)
        self.assertEqual(updated.central_spacing_pct, 42.0)
        self.assertNotEqual(args.central_spacing_pct, 42.0)

    def test_active_trial_records_visual_onset(self):
        args = SimpleNamespace(
            passive_mode=True,
            paired_tone_offset_min=0.0,
            paired_tone_offset_max=0.0,
            pre_stim_duration=0.01,
            stim_duration=0.01,
            response_window=0.02,
            trial_duration=0.04,
            inter_trial_jitter=0.0,
            visual_distractor_mode="none",
            cd_audio_feedback=False,
            cd_repeats=1,
            cd_repeat_gap=0.0,
            trigger_onset_global=None,
            flip_horizontal=False,
            flip_vertical=False,
        )
        engine.CURRENT_ARGS = args
        trial = engine.Trial(
            level="1",
            block=1,
            trial_in_block=1,
            trial_type="active",
            standard_category="face_present",
            stimulus_category="face_present",
            frequency_class="frequent",
            omitted_category=None,
            target_side="left",
            visual_distractor_pos=None,
            auditory_class="blank",
            auditory_offset_s=None,
            corollary_mode="none",
            correct_response="left",
            reversal_phase=None,
        )
        stimuli = {
            "left_mask": _Stim(),
            "right_mask": _Stim(),
            "fix": _Stim(),
            "top_left_distractor": _Stim(),
            "top_right_distractor": _Stim(),
            "bottom_left_distractor": _Stim(),
            "bottom_right_distractor": _Stim(),
            "target_size": (0.32, 0.41),
        }
        row = engine.run_trial(
            trial,
            args,
            _Window(),
            _Core(),
            _Event(),
            _Visual(),
            None,
            stimuli,
            {"categories": {"face_present": [Path("stimulus.png")]}},
            {},
            random.Random(1),
            1,
            _Clock(),
            _Markers(),
            "level1_block01",
        )
        self.assertIsNotNone(row["visual_onset_s"])
        self.assertIsNotNone(row["visual_onset_global_s"])


if __name__ == "__main__":
    unittest.main()
