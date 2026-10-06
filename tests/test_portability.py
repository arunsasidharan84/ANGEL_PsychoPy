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

    def test_builder_instruction_has_keyboard_and_mouse_fallbacks(self):
        root = ET.parse(ROOT / "angel_paradigm.psyexp").getroot()
        instruction = next(
            node for node in root.iter("CodeComponent")
            if node.attrib.get("name") == "instruction_code"
        )
        values = {node.attrib["name"]: node.attrib.get("val", "") for node in instruction.iter("Param")}
        self.assertIn("activate_experiment_window(win)", values["Begin Routine"])
        self.assertIn("event.getKeys()", values["Each Frame"])
        self.assertIn("instruction_mouse.getPressed()", values["Each Frame"])

    def test_two_levels_are_preserved_and_second_instruction_is_shown(self):
        args = SimpleNamespace(levels="['1', '2']")
        self.assertEqual(engine.selected_levels(args), ["1", "2"])
        self.assertEqual(args.levels, "1,2")
        root = ET.parse(ROOT / "angel_paradigm.psyexp").getroot()
        main_code = next(
            node for node in root.iter("CodeComponent")
            if node.attrib.get("name") == "trial_runner"
        )
        source = next(
            node.attrib["val"] for node in main_code.iter("Param")
            if node.attrib.get("name") == "Begin Routine"
        )
        self.assertIn("for level in levels:", source)
        self.assertIn("engine.show_level_instruction", source)
        self.assertIn("engine.main_instruction_due(args, trial.block)", source)
        self.assertIn("if trial.trial_in_block == 1:", source)

    def test_main_instruction_schedule_is_independent_of_feedback(self):
        args = SimpleNamespace(skip_instructions=False, instruction_frequency=2, show_feedback=False)
        self.assertEqual(
            [block for block in range(1, 6) if engine.main_instruction_due(args, block)],
            [1, 3, 5],
        )
        args.instruction_frequency = 1
        self.assertEqual(
            [block for block in range(1, 4) if engine.main_instruction_due(args, block)],
            [1, 2, 3],
        )
        args.skip_instructions = True
        self.assertFalse(engine.main_instruction_due(args, 1))

    def test_instruction_cli_override_and_saved_interval(self):
        self.assertEqual(engine.parse_args(["--instruction-frequency", "1"]).instruction_frequency, 1)
        self.assertTrue(engine.parse_args(["--skip-instructions"]).skip_instructions)
        self.assertFalse(engine.parse_args(["--show-instructions"]).skip_instructions)

    def test_skip_instructions_does_not_discard_practice_trials(self):
        root = ET.parse(ROOT / "angel_paradigm.psyexp").getroot()
        practice_code = next(
            node for node in root.iter("CodeComponent")
            if node.attrib.get("name") == "practice_code"
        )
        source = next(
            node.attrib["val"] for node in practice_code.iter("Param")
            if node.attrib.get("name") == "Begin Routine"
        )
        self.assertIn("if getattr(args, 'practice', 0) > 0:", source)
        self.assertNotIn("and not getattr(args, 'skip_instructions'", source)

    def test_instruction_slide_can_advance_with_mouse_click(self):
        class Mouse:
            presses = iter([(0, 0, 0), (1, 0, 0)])

            def getPressed(self):
                return next(self.presses)

        class Event:
            Mouse = staticmethod(lambda win: Mouse())

            @staticmethod
            def clearEvents():
                return None

            @staticmethod
            def waitKeys(**_kwargs):
                return None

        win = SimpleNamespace(winHandle=SimpleNamespace(activate=lambda: None))
        engine.wait_for_continue(Event, timeout=1.0, win=win)

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
            values["levels"] = "1,2"
            Path(command[3]).write_text(json.dumps(values), encoding="utf-8")
            return SimpleNamespace(returncode=0, stderr="")

        args = engine.parse_args(["--participant", "tab-test"])
        with patch("subprocess.run", side_effect=fake_run):
            updated = engine._show_isolated_tabbed_config_dialog(args, builder=True)
        self.assertEqual(updated.central_spacing_pct, 42.0)
        self.assertEqual(updated.levels, "1,2")
        self.assertNotEqual(args.central_spacing_pct, 42.0)

    def test_builder_launcher_arguments_do_not_silently_skip_setup(self):
        args = engine.parse_args(["--participant", "studio-test"])
        self.assertTrue(args.used_cli_config)
        with patch.object(engine, "_show_isolated_tabbed_config_dialog", return_value=args) as dialog:
            with patch.object(engine, "save_config_defaults"):
                engine.show_builder_config_dialog(args)
        dialog.assert_called_once_with(args, builder=True)

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
