# ANGEL: Assessing Neurocognition via Gamified Experimental Logic (PsychoPy Recreation)

<p align="center">
  <img src="docs/assets/ccs_logo.png" width="220" alt="CCS NIMHANS Logo">
</p>

<p align="center">
  Developed by the <b>Team from Centre for Consciousness Studies (CCS)</b>,<br>
  Department of Neurophysiology,<br>
  <b>National Institute of Mental Health and Neurosciences (NIMHANS)</b>, Bangalore, India.
</p>

<p align="center">
  <a href="https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2016.00001/full"><img src="https://img.shields.io/badge/DOI-10.3389%2Ffnins.2016.00001-blue.svg" alt="DOI"></a>
  <a href="https://www.psychopy.org"><img src="https://img.shields.io/badge/PsychoPy-2024%20%7C%202026-brightgreen.svg" alt="PsychoPy"></a>
  <a href="https://github.com/sccn/labstreaminglayer"><img src="https://img.shields.io/badge/LSL-Compatible-orange.svg" alt="LSL"></a>
  <a href="https://bids.neuroimaging.io"><img src="https://img.shields.io/badge/BIDS-Events%20Export-purple.svg" alt="BIDS"></a>
</p>

---

## 📖 Scientific Background

The **ANGEL (Assessing Neurocognition via Gamified Experimental Logic)** paradigm is an advanced cognitive neuroscience protocol designed to simultaneously assess multiple neurocognitive domains and elicit distinct Event-Related Potential (ERP) components within a single, unified experimental session.

> **Primary Reference:**  
> Nair AK, Sasidharan A, John JP, Mehrotra S, Kutty BM (2016). *Assessing Neurocognition via Gamified Experimental Logic: A Novel Approach to Simultaneous Acquisition of Multiple ERPs.* **Frontiers in Neuroscience**, 10:1.  
> [https://doi.org/10.3389/fnins.2016.00001](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2016.00001/full)

### Multi-ERP Co-registration within a Single Protocol

Traditional ERP paradigms evaluate one cognitive process at a time (e.g., standard oddball for P300, flanker for ERN, or tone-pairs for MMN), requiring lengthy recording protocols that suffer from participant fatigue and non-stationarity. ANGEL multiplexes multiple cognitive challenges into a structured trial flow:

| Neural Component | Cognitive Domain | Paradigm Manipulation |
| :--- | :--- | :--- |
| **N170 / N1** | Early Visual Structural Encoding | Mooney Face vs. Kanizsa Illusory Shape vs. Distorted Stimuli |
| **Visual P300 (P3b)** | Visual Context Updating / Oddball Target Detection | Infrequent (20%) vs. Frequent (80%) visual targets |
| **Auditory MMN / P3a** | Preattentive Auditory Deviance Processing | Standard (80%) vs. Deviant (20%) auditory distractor tones |
| **LRP (Lateralized Readiness Potential)** | Motor Preparation & Execution | Left-hand vs. Right-hand motor responses |
| **ERN / Pe (Error-Related Negativity)** | Performance Monitoring & Error Processing | Speeded responses and rule-reversal conflicts |
| **Corollary Discharge (CD) Suppression** | Self-Monitoring & Agency Verification | Contingent auditory tones (immediate, delayed, or absent) |

---

## 🖼️ Stimulus Sets & Visual Features

ANGEL uses standardized, high-contrast visual stimuli presented with backward checkerboard masking to ensure precise perceptual onset and offset:

| Stimulus Type | Meaningful / Target (Face/Shape Present) | Distorted / Non-Target (Face/Shape Absent) | Mask / Fixation |
| :---: | :---: | :---: | :---: |
| **Mooney Faces** | <img src="docs/assets/face_meaningful.png" width="130" alt="Meaningful Mooney Face"><br>*(Meaningful Face)* | <img src="docs/assets/face_distorted.png" width="130" alt="Distorted Mooney Face"><br>*(Distorted Face)* | <img src="docs/assets/mask_checkerboard.png" width="130" alt="Checkerboard Mask"><br>*(Checkerboard Mask)* |
| **Kanizsa Triangles** | <img src="docs/assets/kanizsa_shape.png" width="130" alt="Kanizsa Triangle"><br>*(Illusory Shape)* | <img src="docs/assets/nonkanizsa_shape.png" width="130" alt="Control Shape"><br>*(Distorted Shape)* | <img src="docs/assets/fixation_cross.png" width="130" alt="Fixation Cross"><br>*(Central Fixation)* |

---

## 🎯 Paradigm Architecture & Levels

The experiment is structured into distinct, hierarchically complex cognitive levels:

```mermaid
flowchart TD
    subgraph L1["Level 1: Spatial Oddball & Motor Agency"]
        direction TB
        L1_Rule["Rule: Respond to Spatial Side of Stimulus (Left vs. Right)"] --> L1_Freq["Frequent Side (75-80%) vs. Rare Side (20-25%)"]
        L1_Freq --> L1_CD["Corollary Discharge (CD) Tone Feedback: Immediate (50ms), Delayed (250ms), or None"]
    end

    subgraph L2["Level 2: Semantic Categorization & Rule Reversal"]
        direction TB
        L2_Rule["Rule: Respond to Semantic Category (Face/Shape vs. Distorted)"] --> L2_Conflict["Side × Category Conflict: Rare stimuli alter side, category, or both"]
        L2_Conflict --> L2_Reversal["Midpoint Rule Reversal: Inverts target-to-key mapping midway through the session"]
    end

    L1 --> L2
```

### Level 1: Spatial Rule & Corollary Discharge
- **Primary Task**: Spatial response according to stimulus side (e.g., Left side stimulus $\rightarrow$ Left key, Right side stimulus $\rightarrow$ Right key) irrespective of image category.
- **Visual Oddball Balance**: 75–80% frequent side, 20–25% rare side.
- **Corollary Discharge Schedule**: Button presses trigger an auditory feedback tone under immediate (50 ms), delayed (250 ms), or absent conditions, evaluating motor efference copy attenuation.

### Level 2: Semantic Categorization & Executive Reversal
- **Primary Task**: Semantic categorization (Meaningful vs. Distorted) regardless of spatial presentation.
- **Conflict Engineering**: Rare trials feature incongruent spatial side, incongruent category, or both altered to generate robust response competition and cognitive conflict.
- **Midpoint Rule Reversal**: At block midpoint (e.g., block 8 of 16), the response mapping inverts (e.g., Meaningful switches from Left key to Right key), measuring behavioral flexibility, cognitive control, and eliciting ERN/Pe components upon commission errors.

---

## ⏱️ Trial Timing & Sequence

Each trial follows microsecond-precise display refresh synchronization:

```mermaid
sequenceDiagram
    autonumber
    participant Display as Visual Display
    participant Audio as Sound Output
    participant Participant as Participant
    participant Hardware as EEG / fMRI Trigger

    Note over Display: Fixation Cross (Pre-stimulus jitter: 350-500 ms)
    Display->>Hardware: Send Fixation Marker
    Note over Display,Audio: Target Stimulus Onset (100 ms)
    Display->>Hardware: Send Stimulus Marker (1-24)
    opt Auditory Distractor (80% Standard / 20% Deviant)
        Audio->>Hardware: Sound Onset Marker (Programmatic Continuous Offset)
    end
    Note over Display: Checkerboard Mask (Response Window: 1000 ms)
    Participant->>Hardware: Key Press / Button Box (Left or Right)
    Hardware->>Hardware: Send Response Marker (51 / 52)
    opt Corollary Discharge Active
        Audio->>Hardware: Contingent Tone (Immediate 50ms / Delayed 250ms)
    end
    Note over Display: Post-Trial Masked Baseline (Variable Jitter: 1100-1450 ms)
    Note over Display: Total Trial Duration: Fixed Epoch (e.g., 1500 ms target)
```

1. **Pre-stimulus Fixation**: Central cross (`plus.png`) for 350–500 ms.
2. **Target Display**: Mooney face or Kanizsa shape on Left or Right hemifield for 100 ms.
3. **Auditory Oddball Tone**: Concurrent or jittered auditory presentation (Standard 800 Hz vs. Deviant 500 Hz).
4. **Response Window & Mask**: High-contrast checkerboard mask (`cb.png`) presented for up to 1000 ms or until response.
5. **Corollary Tone**: Post-response auditory feedback tone (50 ms immediate or 250 ms delayed).
6. **Inter-Trial Baseline**: Dynamic jittered post-trial mask ensuring a consistent overall trial cycle with randomized event onsets.

---

## 🧲 Neuroimaging & Multi-Modal Synchronization

<p align="center">
  <img src="docs/assets/instruction_level1.png" width="550" alt="ANGEL Task Instructions">
</p>

### 1. fMRI Scanner Synchronization & Dynamic BOLD Volume Estimator
- **Scanner Trigger Wait**: A dedicated trigger-wait screen (`Waiting for scanner trigger 's'...`) pauses the task until the scanner trigger is received.
- **Practice Separation**: Comprehensive instructions and interactive practice blocks execute **before** scanner trigger wait, avoiding scan time waste.
- **Dynamic BOLD Volume Estimator**: Set Repetition Time (TR, default 2.0 s) and dummy scans in the startup GUI. The system instantly auto-calculates and displays:
  $$\text{Expected Volumes} = \left\lceil \frac{T_{\text{dummy}} + T_{\text{experiment}}}{TR} \right\rceil$$
  Displaying the minimum, maximum, and expected scan volumes so imaging technicians can set scanner protocols accurately.
- **Mirror Projection Inversion**: `--flip-horizontal` and `--flip-vertical` toggles instantly adjust visual output for fMRI head-coil mirror setups.
- **Passive Viewing Mode**: `--passive-mode` allows fMRI or patient paradigms where motor responses are omitted (auto-advancing without miss penalty).

### 2. BIDS-Compliant fMRI Event Export
Alongside detailed behavioral logs, ANGEL generates a BIDS-compliant event file (`*_fmri_events.csv` / `.tsv`):
```text
onset,duration,trial_type,stim_category,stim_side,response_time,accuracy
10.042,0.100,frequent_left,face_meaningful,left,0.342,1
11.584,0.100,rare_right,face_distorted,right,0.412,1
```
All onsets are accurately time-locked ($t = 0.000\,\text{s}$) to the initial scanner trigger.

### 3. EEG Hardware Triggers & Codes
Markers are sent simultaneously via **Lab Streaming Layer (LSL)**, **Parallel Port TTL**, or **Cedrus C-Pod USB Serial**:

| Trigger Code | Event Description |
| :---: | :--- |
| **99 / 107** | fMRI Scanner Trigger Received |
| **101** | Experiment Session Start |
| **102 / 103** | Instruction Slide Start / End |
| **104 / 105** | Practice Block Start / End |
| **106** | Waiting for Scanner Trigger |
| **108 / 109** | Main Block Start / End |
| **110** | Experiment End Slide |
| **1 – 8** | Level 1 Visual Stimuli (Side × Category combinations) |
| **9 – 16** | Level 2 Visual Stimuli (Rule Phase 1 & 2 combinations) |
| **25 / 26** | Visual Baseline / Rest Intervals |
| **31 – 46** | Practice Trial Stimuli |
| **51 / 52** | Participant Left / Right Button Press |
| **61 – 63** | Corollary Feedback Tones (Immediate, Delayed, Audio) |

Every session generates an exhaustive marker audit file (`*_markers.csv`) recording hardware marker codes, global timestamps, and trigger-relative timestamps.

---

## 🛠️ PsychoPy Studio / Builder Architecture

The paradigm provides full dual-mode support:

```
ANGEL_PsychoPy/
├── angel_paradigm.psyexp          # Visual Builder experiment file
├── angel_paradigm.py              # Compiled standalone execution script
├── angel_paradigm_coder.py        # Core object-oriented engine & GUI dialogs
├── angel_config.json              # Persistent user configuration
├── docs/assets/                   # Stimulus samples, diagrams, and CCS logo
└── EPrimeFiles/                   # Original E-Prime audio and visual stimulus assets
```

### Visual Builder Routine Flow
Researchers can open `angel_paradigm.psyexp` in **PsychoPy Builder** to visually inspect, reorder, or edit experimental routines:

```mermaid
flowchart LR
    InitRoutine["⚙️ InitRoutine<br>(Config & Engine)"] --> InstructionRoutine["📖 InstructionRoutine<br>(Slide Display)"]
    InstructionRoutine --> PracticeRoutine["🎯 PracticeRoutine<br>(Interactive Practice)"]
    PracticeRoutine --> TriggerWaitRoutine["🧲 TriggerWaitRoutine<br>(Scanner Sync)"]
    TriggerWaitRoutine --> TrialRoutine["⚡ TrialRoutine<br>(Core Stimulus Loop)"]
    TrialRoutine --> FeedbackRoutine["📊 FeedbackRoutine<br>(Block Performance)"]
    FeedbackRoutine --> EndRoutine["🏁 EndRoutine<br>(Summary & Teardown)"]
```

---

## 🚀 Quick Start & Usage

### 1. Launching via PsychoPy Builder (GUI)
1. Open **PsychoPy Studio**.
2. Open `angel_paradigm.psyexp`.
3. Click the green **Run Experiment** button (or press `Ctrl+R` / `Cmd+R`).
4. The interactive startup dialog appears, allowing visual selection of parameters.

### 2. Launching via Command Line
Run directly using Python in your PsychoPy environment:

```bash
# Standard 2-Level session with Mooney faces in English
python angel_paradigm.py --participant S001 --levels 1,2 --category-set face --language english

# fMRI Mode with TR=2.0s and 5 dummy scans
python angel_paradigm.py --participant SUB01 --levels 1 --fmri-mode --tr 2.0 --dummy-scans 5

# Passive viewing mode (no button responses required)
python angel_paradigm.py --participant SUB02 --levels 1 --passive-mode

# Fast testing run (1 block, 2 practice trials, windowed)
python angel_paradigm.py --participant test --levels 1 --blocks 1 --practice 2 --no-fullscreen
```

---

## ⚙️ Key Configuration Parameters (`angel_config.json`)

All runtime options can be configured either via the startup dialog, command-line arguments, or the persistent `angel_config.json` file:

```json
{
  "participant": "S001",
  "category_set": "face",
  "levels": "1,2",
  "language": "english",
  "blocks": 16,
  "trials_per_block": "25+3",
  "fmri_mode": false,
  "tr_s": 2.0,
  "dummy_scans": 5,
  "passive_mode": false,
  "marker_mode": "none",
  "left_keys": "left,z,1",
  "right_keys": "right,slash,2",
  "continue_keys": "any",
  "trigger_keys": "s",
  "slide_timeout_s": 5.0,
  "show_feedback": true,
  "show_performance": true,
  "feedback_frequency": 2
}
```

---

## 📊 Output Data Files

For every session, files are organized into the `data/` directory:

1. **`data/<participant>_<timestamp>.csv`**: Full behavioral dataset containing over 70 diagnostic columns including trial parameters, visual/auditory latencies, keypress reaction times, accuracies, and timing jitter audits.
2. **`data/<participant>_<timestamp>_markers.csv`**: Dedicated electrophysiology and trigger verification file recording exact sample timestamps and trigger-locked times for all stimulus, response, and slide events.
3. **`data/<participant>_<timestamp>_fmri_events.csv`**: BIDS-compliant event file for direct ingestion into fMRI analysis pipelines (SPM, FSL, AFNI, Nilearn).

---

## 👥 Authors & Acknowledgements

- **Centre for Consciousness Studies (CCS)**, Department of Neurophysiology, National Institute of Mental Health and Neurosciences (NIMHANS), Bengaluru, Karnataka, India.
- Adapted for PsychoPy from the original E-Prime paradigm developed by Nair et al. (2016).
