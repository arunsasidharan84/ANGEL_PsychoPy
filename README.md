# ANGEL PsychoPy Recreation

This repository contains a transparent PsychoPy recreation of the ANGEL E-Prime
Level 2 and Level 3 paradigms using the local E-Prime resource folders.

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
- Level 2 side responses with configurable immediate, delayed, and no-feedback
  corollary discharge conditions.
- Optional Level 3 corollary tones with the same CD schedule.
- Level 3 meaningful/ambiguous responses with a midpoint rule reversal.
- Optional EEG/event markers over LSL and/or parallel-port TTL.
- Feedback after every two main blocks, displayed together with score, mean RT,
  progress, image, and audio.

## Running

Run from PsychoPy's Python environment or from a Python environment where
`psychopy` is installed:

```bash
python angel_paradigm.py --participant S001 --levels 2,3 --language english
```

Useful test run:

```bash
python angel_paradigm.py --participant test --levels 2 --blocks 1 --practice 2 --no-fullscreen
```

Reduced face-only Level 2/3 run with 8 blocks per level and intermixed blocks:

```bash
python angel_paradigm.py --participant S001 --levels 2,3 --category-set face --blocks 8 --intermix-level-blocks
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

- Left response: left arrow, `z`, or `1`
- Right response: right arrow, `/`, or `2`
- Continue: space or return
- Quit: escape or `q`

## Notes

The E-Prime (version 3) files are placed within the corresponding Template folders, 
and represent the original paper version of the paradigm. 
This Psychopy recreation keeps the logic explicit and has more options for shorter implementation 
rather than attempting a binary-level translation of the paper. 

The resource images and sounds are shared by Psychopy and EPrime versions, directly from:
- `EPrimeFiles/CCS_EEG_ANGELv2_Level2_Template`
- `EPrimeFiles/CCS_EEG_ANGELv2_Level3_Template`

The generated CSV includes condition columns for level, block, active/baseline
trial, visual category, meaningful/ambiguous class, frequent/rare class, target
side, visual distractor position, auditory class, tone offset, corollary mode,
reversal phase, response, RT, and accuracy.

## Main Options

- `--category-set all|face|shape`: use all visual categories, Mooney-face-only,
  or Kanizsa-triangle-only logic. The reduced modes keep the 80/20 oddball
  structure using the other category in the family as the rare category.
- `--blocks 16|8|4`: allowed block counts. `all` requires 8 or 16 blocks to
  preserve category x side balance; face/shape runs allow 4, 8, or 16.
- `--trials-per-block 25+3|20+3`: active+baseline trials per block. Both keep
  the 80/20 frequent/rare visual oddball proportion.
- `--stim-duration`, `--response-window`, `--post-mask-min`,
  `--post-mask-max`: timing controls in seconds.
- `--visual-distractor-mode sync|desync|none`: show visual distractor
  checkerboards with the target, jittered from target onset, or never.
- `--visual-distractor-offset-min` / `--visual-distractor-offset-max`: visual
  distractor offset range in seconds for `desync` mode.
- `--paired-tone-offset-mode continuous|fixed`: use programmatic continuous
  sound onset offsets, or the three E-Prime fixed-offset files.
- `--paired-tone-offset-min` / `--paired-tone-offset-max`: continuous offset
  range in seconds relative to visual onset.
- `--cd-schedule by-block|within-block|all-immediate|all-delayed|all-none`:
  Level 2 CD schedule. Trials are logged as `cd_condition=cd_immediate`,
  `cd_condition=cd_delayed`, or `cd_condition=cd_none`. Except for the explicit
  `all-none` test mode, `cd_none` is held at 20% of active trials in each block.
  `by-block` assigns the feedback trials in a block to either immediate or
  delayed CD; `within-block` randomizes immediate, delayed, and none trials
  inside every block.
- `--level3-cd` / `--no-level3-cd`: enable or disable corollary feedback in
  Level 3.
- `--cd-volume`, `--cd-repeats`, `--cd-repeat-gap`: tune corollary feedback
  audibility. The bundled CD WAV is 200 ms long; repeated plays are automatically
  spaced far enough apart to avoid overlap.
- `--intermix-level-blocks`: shuffle Level 2 and Level 3 blocks into one
  combined sequence.
- `--marker-mode none|lsl|parallel|both`: send markers. LSL uses
  `--lsl-stream-name`; TTL uses `--parallel-address` and `--ttl-pulse-width`.
- `--output-dir`: custom CSV output folder.

Each output row includes relative and global onset/offset columns for the trial,
paired tone, visual target, response-window end, post-mask interval, corollary
tone, response, visual distractor, block name, and trial end. These columns are
intended for timing audits and EEG event verification.
