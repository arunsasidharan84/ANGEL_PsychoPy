# ANGEL PsychoPy Recreation

This repository contains a transparent PsychoPy recreation of the ANGEL E-Prime
Level 2 and Level 3 paradigms using the local E-Prime resource folders.

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
- Level 2 side responses with configurable immediate/delayed corollary tones.
- Level 3 meaningful/ambiguous responses with a midpoint rule reversal.
- Optional EEG/event markers over LSL and/or parallel-port TTL.
- Feedback after every two main blocks.

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

Output CSV files are written to `data/`.

## Keys

- Left response: left arrow, `z`, or `1`
- Right response: right arrow, `/`, or `2`
- Continue: space or return
- Quit: escape or `q`

## Notes

The original E-Prime files contain encoded internal document/script content, so
this recreation keeps the logic explicit rather than attempting a binary-level
translation. The resource images and sounds are used directly from:

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
- `--paired-tone-offset-mode continuous|fixed`: use programmatic continuous
  sound onset offsets, or the three E-Prime fixed-offset files.
- `--paired-tone-offset-min` / `--paired-tone-offset-max`: continuous offset
  range in seconds relative to visual onset.
- `--cd-schedule by-block|within-block|all-immediate|all-delayed`: Level 2 CD
  schedule. `by-block` matches the paper; `within-block` randomizes CD on/off
  trials inside every block.
- `--intermix-level-blocks`: shuffle Level 2 and Level 3 blocks into one
  combined sequence.
- `--marker-mode none|lsl|parallel|both`: send markers. LSL uses
  `--lsl-stream-name`; TTL uses `--parallel-address` and `--ttl-pulse-width`.

Each output row includes relative and global onset/offset columns for the trial,
paired tone, visual target, response-window end, post-mask interval, corollary
tone, and trial end. These columns are intended for timing audits and EEG event
verification.
