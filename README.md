# MBTI-Manual-Behavior-Tracking-Interface

MBTI makes manual behavior tracking on video fast and simple. 
Set a recording time limit and **the player stops automatically**. 
Count behaviors **with quick keystrokes**, map the exact keys you prefer, **and export CSV data** to review what happened and when it happened.

## Features

- Time-boxed recording: Specify a recording limit; playback pauses automatically at the end.

- Simple keyboard labeling: Count behaviors with simple keyboard clicks while you watch. It can record up to four actions simultaneously.

- Custom key mapping: Assign your own keys for each behavior—no hardcoded shortcuts.

- CSV export: Save per-frame labels and totals to CSV for analysis and auditing.



### **Basic UI**

<img width="1920" height="1032" alt="기본" src="https://github.com/user-attachments/assets/45b45a3a-a8a7-4ad5-bd52-5986a4c52a0a" />

### **Behavior Recording**

<img width="1920" height="1032" alt="측정" src="https://github.com/user-attachments/assets/36488f90-8f9c-4844-b11c-641bdabcdb4c" />

### **Data Preview**

<img width="1920" height="1032" alt="결과" src="https://github.com/user-attachments/assets/3e1ae140-39f7-4ce2-85a6-ae92581a67ca" />

### **Exported CSV**

<img width="734" height="708" alt="csv" src="https://github.com/user-attachments/assets/e4b403b5-f78a-4759-ac69-2811ab626f5f" />



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

1. Download MBTI.py, mbti.yaml from GitHub to any folder you like.

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

1. Download MBTI.zip from [drive](https://drive.google.com/file/d/1GYmbJBYuUgZxJvPzaPTN7LokJ2U0z5VZ/view?usp=sharing) to any folder you like.

2. Extract the ZIP in that folder.
Do not delete any files inside the extracted folder—the EXE needs the accompanying files to run.

3. Run MBTI.exe.

Window defender can work because it is a file created by an unknown publisher, but if you press the View Details button to run it once, the window will not appear afterwards and can work conveniently.

---

Developed by YJ 

MBTI is provided for research and academic purposes.

Copyright (c) 2024, coldlabkaist
