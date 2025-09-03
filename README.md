# MBTI-Manual-Behavior-Tracking-Interface

MBTI makes manual behavior tracking on video fast and simple. 
Set a recording time limit and **ㅅhe player stops automatically**. 
Count behaviors **with quick keystrokes**, map the exact keys you prefer, **and export CSV data** to review what happened and when it happened.

## Features

- Time-boxed recording: Specify a recording limit; playback pauses automatically at the end.

- Simple keyboard labeling: Count behaviors with simple keyboard clicks while you watch. It can record up to four actions simultaneously.

- Custom key mapping: Assign your own keys for each behavior—no hardcoded shortcuts.

- CSV export: Save per-frame labels and totals to CSV for analysis and auditing.



### **Basic UI**

<img width="1919" height="1019" alt="기본" src="https://github.com/user-attachments/assets/9dac7528-a2a7-4712-a1b9-3b31ed11f015" />

### **Behavior Recording**

<img width="1914" height="1032" alt="측정" src="https://github.com/user-attachments/assets/ec378029-ac01-4112-af27-6ff6474c6d7b" />

### **Data Preview**

<img width="1916" height="1016" alt="결과" src="https://github.com/user-attachments/assets/4e4d35e3-f1e4-4f50-95f0-e2da76151a11" />



## Update Log

### 25.09.03.
MBTI 2.0.0 released!

**Highlights**
* **Smooth, reliable playback** — Snappy scrubbing and stable frame-accurate stepping for stress-free review.
* **Easy key setup** — Map your preferred keys to behaviors in seconds; no hardcoded shortcuts.
* **Clean UI** — Focused layout with overlays that stay readable while you work.
* **Simple data export** — One click to export per-frame labels and totals to CSV.
* **Resume existing work** — Import prior datasets and continue labeling without losing progress.


### 24.08.21.
MBTI 1.1.1 released
- able to export behavior data in *.csv
 
### 24.08.02.
MBTI 1.0.0 released
- able to track two behaviors at the same time for a specified minutes.

## Requirement
Python based execution
- Compatable on Window/Linux/Mac
- Requires Python, Anaconda
- Fast Execution

EXE file based execution
- Compatible on Window
- Easy Installation

## Installation
### Option A — Run from source (Conda, Fast Execution)
Requirements: Anaconda / Miniconda installed.
1. Download MBTI.py from GitHub to any folder you like.

2. Open a terminal in that folder. Create the environment:

```
conda env create -f mbti.yaml
```

3. Activate & run:

```
conda activate mbti
python MBTI.py
```

### Option B — Run the prebuilt app (Windows, Easy Installation)

1. Download MBTI.zip from your Drive to any folder you like.

2. Extract the ZIP in that folder.
Do not delete any files inside the extracted folder—the EXE needs the accompanying files to run.

3. Run MBTI.exe.

---

Developed by YJ 

MBTI is provided for research and academic purposes.

Copyright (c) 2024, coldlabkaist
