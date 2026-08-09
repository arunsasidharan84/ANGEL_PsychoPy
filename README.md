# ANGEL PsychoPy Recreation

This repository contains a transparent PsychoPy recreation of the ANGEL E-Prime
Level 2 and Level 3 paradigms (renamed as Level 1 and Level 2 respectively) using the local E-Prime resource folders.

Ref: Nair AK, Sasidharan A, John JP, Mehrotra S and Kutty BM (2016) Assessing Neurocognition via Gamified Experimental Logic: A Novel Approach to Simultaneous Acquisition of Multiple ERPs. Front. Neurosci. 10:1. doi: 10.3389/fnins.2016.00001
https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2016.00001/full

The implementation is in `angel_paradigm.py`. It follows the ANGEL paper's core
structure:

- 16 blocks per level by default.
- 25 active trials plus 3 baseline trials per block by default, with a 20+3
  option.
- Configurable target duration, response window, and post-trial masked baseline
  range.
- Frequent visual category in 80% of active trials and two rare categories in
  20% of active trials.
- Auditory distractors with standard, deviant, and blank trials.
- Continuous paired-tone offsets by default, using one standard/deviant sound
  file and programmatic onset timing. The E-Prime fixed offsets are still
  available.
- Level 1 (original Level 2) side responses with configurable immediate, delayed, and no-feedback
  corollary discharge conditions.
- Optional Level 2 (original Level 3) corollary tones with the same CD schedule.
- Level 2 (original Level 3) meaningful/ambiguous responses with a midpoint rule reversal.
- Optional EEG/event markers over LSL, parallel-port TTL, or Cedrus C-Pod serial.
- Feedback after every two main blocks, displayed together with score, mean RT,
  progress, image, and audio.

## Running

The paradigm can be run via Python / Coder script or through PsychoPy Studio / Builder:

### Method 1: PsychoPy Studio / Builder (GUI Interface)
Researchers can open `angel_paradigm.psyexp` directly in PsychoPy Studio / Builder UI. This provides a visual Flow Chart and Routines (`Welcome`, `Instructions`, `TriggerWait`, `TrialRoutine`, `Feedback`, `End`) to inspect, edit, or customize components while retaining 100% of the underlying Coder paradigm logic and timing precision.

### Method 2: Python / Coder Command Line

Run from PsychoPy's Python environment or from a Python environment where `psychopy` is installed:

```bash
python angel_paradigm.py --participant S001 --levels 1,2 --language english
```

Useful test run:

```bash
python angel_paradigm.py --participant test --levels 1 --blocks 1 --practice 2 --no-fullscreen
```

Reduced face-only Level 1/2 run with 8 blocks per level and intermixed blocks:

```bash
python angel_paradigm.py --participant S001 --levels 1,2 --category-set face --blocks 8 --intermix-level-blocks
```

Paper/E-Prime-style fixed paired-tone offsets and blockwise CD on/off:

```bash
python angel_paradigm.py --participant S001 --paired-tone-offset-mode fixed --cd-schedule by-block
```

Output CSV files are written to `data/` unless an output folder is chosen in the
startup dialog or with `--output-dir`.

Startup defaults are stored in `angel_config.json` beside the paradigm script.
This file can be edited manually and shared across lab machines/users.

## Keys

Response keys are configurable in `angel_config.json` via `"left_keys"`, `"right_keys"`, `"continue_keys"`, and `"trigger_keys"` or command line parameters. The defaults are:
- Left response: left arrow, `z`, or `1` (configurable)
- Right response: right arrow, `/` (slash), or `2` (configurable)
- Continue: `any` (any key press advances instruction slides; configurable via `--continue-keys`)
- Scanner Trigger: `s` (exclusively waited on when `--fmri-mode` is enabled)
- Quit: escape or `q`

## Main Options

- `--category-set all|face|shape`: use all visual categories, Mooney-face-only,
  or Kanizsa-triangle-only logic. The reduced modes keep the 80/20 oddball
  structure using the other category in the family as the rare category.
- `--blocks 16|8|4`: allowed block counts. `all` requires 8 or 16 blocks to
  preserve category x side balance; face/shape runs allow 4, 8, or 16.
- `--trials-per-block 25+3|20+3`: active+baseline trials per block. Both keep
  the 80/20 frequent/rare visual oddball proportion.
- `--screen`: PsychoPy monitor/display screen index (0 for primary, 1 for secondary/extended).
- `--pre-stim-duration`, `--stim-duration`, `--response-window`: timing controls in seconds.
- `--trial-duration`, `--inter-trial-jitter`: target trial duration (default 1.50 s) and inter-trial jitter range (default 0.35 s) used to dynamically calculate post-trial masked baseline intervals.
- `--fmri-mode` / `--no-fmri-mode`: toggle fMRI mode for trigger waiting slide and trigger-relative CSV timestamps.
- `--flip-horizontal` / `--flip-vertical`: flip visual stimuli horizontally/vertically for fMRI head-mirror setups.
- `--visual-distractor-mode sync|desync|none`: show visual distractor
  checkerboards with the target, jittered from target onset, or never.
- `--visual-distractor-offset-min` / `--visual-distractor-offset-max`: visual
  distractor offset range in seconds for `desync` mode.
- `--paired-tone-offset-mode continuous|fixed`: use programmatic continuous
  sound onset offsets, or the three E-Prime fixed-offset files.
- `--paired-tone-offset-min` / `--paired-tone-offset-max`: continuous offset
  range in seconds relative to visual onset.
- `--cd-schedule by-block|within-block|all-immediate|all-delayed|all-none`:
  Level 1 CD schedule.
- `--level2-cd` / `--no-level2-cd`: enable or disable corollary feedback in Level 2.
- `--marker-mode none|lsl|parallel|cpod|both`: send markers over LSL, parallel TTL, or Cedrus C-Pod serial.
- `--output-dir`: custom CSV output folder.

Each output row includes relative and global onset/offset columns for the trial,
paired tone, visual target, response-window end, post-mask interval, corollary
tone, response, visual distractor, block name, and trial end. These columns are
intended for timing audits and EEG event verification.
