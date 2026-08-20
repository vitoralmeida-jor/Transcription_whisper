# Journalism Transcriber

**English** | [Português (Brasil)](README.md)

A local tool for transcribing audio and video files with
[whisper.cpp](https://github.com/ggml-org/whisper.cpp), accelerating transcription on AMD
GPUs through Vulkan, separating speakers with
[pyannote.audio Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1),
and producing TXT, JSON, and SRT output. Media files are never sent to a transcription API.

> This V1 separates voices as `SPEAKER_00`, `SPEAKER_01`, and so on. It does not identify
> the real names of speakers.

## Architecture

```text
original media (never modified)
  -> FFprobe + FFmpeg (16-bit PCM WAV, mono, 16 kHz)
  -> whisper-cli built with Vulkan (text and timestamps)
  -> pyannote.audio on CPU (speaker intervals)
  -> alignment by greatest temporal overlap
  -> TXT + JSON + SRT, written atomically
```

Python only orchestrates local tools. Transcription and diarization are independent
modules, allowing either backend to be replaced without rewriting the exporters.

## Requirements

- 64-bit Windows 10 or 11;
- 64-bit Python 3.11 or 3.12 (3.11 is the conservative recommendation);
- Git;
- FFmpeg and FFprobe available on `PATH`;
- an up-to-date AMD driver with Vulkan support;
- to build whisper.cpp: Visual Studio 2022 Build Tools with “Desktop development with
  C++”, CMake, and the Vulkan SDK;
- enough disk space for the models — `large-v3` requires several gigabytes;
- internet access for the initial dependency and model downloads only.

FFmpeg, whisper.cpp, CMake, and the Vulkan SDK are not Python packages and are therefore
not listed in `requirements.txt`.

## Preparing Python and the virtual environment

Install Python from the [official Windows downloads page](https://www.python.org/downloads/windows/)
and select the option that adds it to `PATH`. In a new PowerShell window, from the project
root:

```powershell
python --version
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

For development and tests:

```powershell
pip install -r requirements-dev.txt
pytest -q
```

## Installing FFmpeg

Install a Windows FFmpeg distribution and add its `bin` directory to `PATH`. Close and
reopen PowerShell, then verify:

```powershell
ffmpeg -version
ffprobe -version
```

You may also use `winget` when the package is available:

```powershell
winget search ffmpeg
winget install --id Gyan.FFmpeg.Shared
```

Package identifiers may change, so check the search result before installing.

## Building whisper.cpp with Vulkan

The official project exposes the CMake option `GGML_VULKAN`. Common Windows release
binaries may not include Vulkan, so a local build is the most predictable route for an
AMD RX 6600.

### 1. Build prerequisites

Install:

1. [Git](https://git-scm.com/download/win);
2. [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/),
   including MSVC and the Windows SDK;
3. [CMake](https://cmake.org/download/) and add it to `PATH`;
4. [LunarG Vulkan SDK](https://vulkan.lunarg.com/sdk/home#windows).

Restart the terminal and verify:

```powershell
git --version
cmake --version
vulkaninfo --summary
```

### 2. Build

Open “Developer PowerShell for VS 2022”:

```powershell
Set-Location $env:USERPROFILE\Documents
git clone https://github.com/ggml-org/whisper.cpp.git
Set-Location .\whisper.cpp

cmake -B build -DGGML_VULKAN=ON -DGGML_CUDA=OFF -DGGML_HIP=OFF
cmake --build build --config Release --parallel
```

Copy the executable and generated DLLs into this project. Adjust the destination to the
actual repository location:

```powershell
$WhisperDestination = "C:\path\to\Transcrição_whisper\bin\whisper"
New-Item -ItemType Directory -Force $WhisperDestination
Copy-Item .\build\bin\Release\* $WhisperDestination
```

The default configuration expects:

```text
bin/whisper/whisper-cli.exe
```

If the executable is elsewhere, update `whisper.executable` in `config.yaml`. Vulkan is a
property of the compiled binary, so no Vulkan flag is needed for each transcription. The
application passes `-ng` only when `use_gpu: false`.

### 3. Confirm Vulkan usage

Run the binary directly. Its startup output should identify the Vulkan backend and AMD
device; a CPU-only build will not do so.

```powershell
.\bin\whisper\whisper-cli.exe --help
.\bin\whisper\whisper-cli.exe `
  -m .\models\whisper\ggml-small.bin `
  -f .\example.wav `
  -l pt
```

If required DLLs cannot be loaded, copy every generated DLL beside the executable and
confirm that the AMD driver's Vulkan Runtime is installed.

## Downloading a Whisper model

The application never downloads models automatically. Models must use the GGML format
supported by whisper.cpp:

```powershell
New-Item -ItemType Directory -Force .\models\whisper

# Lighter test model
Invoke-WebRequest `
  -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin" `
  -OutFile ".\models\whisper\ggml-small.bin"

# Higher quality; very large file
Invoke-WebRequest `
  -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin" `
  -OutFile ".\models\whisper\ggml-large-v3.bin"
```

Set `model: small`, `model: medium`, or `model: large-v3` in YAML. A name resolves to
`models/whisper/ggml-NAME.bin`; an explicit `.bin` path is also accepted. `small` is useful
for setup tests. For final Portuguese interviews, `large-v3` prioritizes quality at the
cost of memory and processing time.

## Configuring pyannote

The open `pyannote/speaker-diarization-community-1` model runs locally. Initial access
requires a Hugging Face account, acceptance of the model's conditions, and a read token.

1. Accept the terms on the [Community-1 model page](https://huggingface.co/pyannote/speaker-diarization-community-1);
2. create a read token at `https://huggingface.co/settings/tokens`;
3. copy `.env.example` to `.env` and enter the token:

```powershell
Copy-Item .env.example .env
notepad .env
```

```dotenv
HF_TOKEN=hf_your_real_token
```

`.env` is ignored by Git. Never put the token in `config.yaml` or commit it. The pyannote
pipeline is loaded once and reused for the entire batch.

### Offline use after download

On first use, pyannote downloads its files to the Hugging Face cache. To keep an explicit,
portable copy under `models/`:

```powershell
.\.venv\Scripts\Activate.ps1
hf auth login
hf download pyannote/speaker-diarization-community-1 `
  --local-dir .\models\diarization\community-1
```

Then update:

```yaml
diarization:
  local_model_path: models/diarization/community-1
  device: cpu
```

To test offline and explicitly prevent Hugging Face network access for the session:

```powershell
$env:HF_HUB_OFFLINE = "1"
python main.py .\example.mp4 --speakers 2
Remove-Item Env:HF_HUB_OFFLINE
```

Community-1, whisper.cpp, and FFmpeg all run locally after installation. Initial package
and model downloads naturally require network access.

## Configuration

Relative paths in `config.yaml` are resolved from the YAML file's location, not the
terminal's current directory. Personal absolute paths are not hardcoded.

Important settings:

```yaml
whisper:
  executable: bin/whisper/whisper-cli.exe
  model: large-v3
  language: pt
  use_gpu: true
  gpu_backend: vulkan

diarization:
  enabled: true
  device: cpu
  min_speakers: 2
  max_speakers: 5

processing:
  recursive: false
  skip_existing: true
  keep_temp_on_error: true
```

Validate the environment before the first transcription:

```powershell
python main.py --check
```

## Usage

### One file

```powershell
python main.py "C:\Videos\interview.mp4"
```

### One folder

```powershell
python main.py "C:\Videos\Interviews"
```

### Include subfolders

```powershell
python main.py "C:\Videos\Interviews" --recursive
```

### Known number of speakers

`--speakers` temporarily overrides both speaker bounds:

```powershell
python main.py "C:\Videos\interview.mp4" --speakers 2
```

Or provide bounds:

```powershell
python main.py "C:\Videos\interview.mp4" --min-speakers 2 --max-speakers 4
```

### No diarization, another model, or forced reprocessing

```powershell
python main.py ".\interview.mp4" --no-diarization
python main.py ".\interview.mp4" --model medium
python main.py ".\interview.mp4" --force
```

Run `python main.py --help` for every option.

## Output structure

```text
output/
  txt/interview.txt
  json/interview.json
  srt/interview.srt
  manifest.json
```

Unique media names remain readable. Only colliding base names receive a deterministic hash
of their relative path. The manifest stores status, size, and modification time. With
`skip_existing: true`, complete outputs for an unchanged source are skipped; changed media
is processed again.

Results are first written to hidden temporary files and then atomically moved to their
final names, preventing interrupted output from appearing complete.

### TXT

TXT groups adjacent segments from the same speaker for comfortable reading:

```text
[00:00:03] SPEAKER_00
How do you assess the data published yesterday?

[00:00:09] SPEAKER_01
We identified a difference between the two databases.
```

### JSON

JSON preserves source path, language, duration, model, full text, seconds, timestamps, and
speaker labels. It is suitable for `pandas` and future renaming tools. Editing `speaker`
allows `SPEAKER_00` to become `INTERVIEWER` without running either model again.

### SRT

SRT uses millisecond timestamps and prefixes each subtitle with its speaker identifier.
The prefix is omitted when diarization is disabled.

## Alignment strategy

For each Whisper segment, the aligner sums the overlap duration for every speaker and
selects the greatest. If `SPEAKER_00` covers 0.8 seconds and `SPEAKER_01` covers 4.2
seconds, the block is assigned to `SPEAKER_01`.

Community-1 provides “exclusive” diarization without simultaneous turns, which is useful
for reconciling transcription and speaker timestamps. V1 does not split text
proportionally inside a segment: block timestamps do not reliably reveal each word's
boundary, and such a split would invent information. The internal structures can support
word timestamps in a future backend.

## Batches, errors, and temporary files

- Files are sorted alphabetically by path.
- A media error is logged and the batch continues.
- Full tracebacks go to `logs/transcritor-YYYY-MM-DD.log`, not the terminal.
- 16-bit PCM, mono, 16 kHz WAV files are used directly.
- Other media creates a WAV under `temp/`; the source is never modified.
- Temporary files are deleted after success.
- With `keep_temp_on_error: true`, diagnostic WAV files remain after errors.
- `Ctrl+C` cleans the current temporary file when possible, preserves finished output,
  and exits with code 130.

## Opening in VS Code

1. Open this project folder using **File > Open Folder**.
2. Run **Python: Select Interpreter** and select `.venv`.
3. Open an integrated PowerShell terminal.
4. Activate it with `.\.venv\Scripts\Activate.ps1`.
5. Run `python main.py --check`, then start a transcription.

## First test

After testing `whisper-cli` directly and configuring pyannote:

```powershell
python main.py ".\example.mp4" --speakers 2
```

Expected output (a hash is added only if another media item has the same base name):

```text
output/txt/example.txt
output/json/example.json
output/srt/example.srt
```

To isolate setup issues, start without diarization:

```powershell
python main.py ".\example.mp4" --no-diarization --model small
```

## Troubleshooting

### `python` is not recognized

Install 64-bit Python 3.11 or 3.12, select “Add Python to PATH”, and open a new terminal.

### FFmpeg or FFprobe is missing

Confirm both are in the same `bin` directory, add it to `PATH`, and restart VS Code. Run
`Get-Command ffmpeg` and `Get-Command ffprobe`.

### whisper.cpp or its model is missing

Check `whisper.executable` and `paths.whisper_models`. The name `large-v3` requires a file
named exactly `ggml-large-v3.bin` in the configured directory.

### Vulkan is not shown

Update the AMD driver, run `vulkaninfo --summary`, remove whisper.cpp's `build` directory,
and rebuild with `-DGGML_VULKAN=ON`. Make sure you did not copy a CPU-only release.

### Pyannote returns 401/403 or cannot access the model

Accept the Community-1 terms using the same account that owns the token, verify `HF_TOKEN`
in `.env`, and perform the first run while online. Never publish `.env`.

### Diarization is slow

It runs on CPU for compatibility with the AMD GPU. `--no-diarization` isolates the
transcription stage. The model remains loaded between files in the same batch.

### Did one bad file stop the batch?

Normal FFmpeg, whisper.cpp, pyannote, and export errors are caught per file. A batch exits
early only on `Ctrl+C` or a global preflight failure such as a missing executable/model.

## Privacy and version control

Media, transcripts, and models stay local. `models/`, `bin/`, `temp/`, `output/`, `logs/`,
`.env`, and `.venv/` are ignored by Git; `.gitkeep` files preserve the directory layout.
Review JSON before sharing it because `metadata.source_path` contains the local media path.

## License and attribution

Copyright 2026 Vitor Almeida.

Licensed under the [Apache License 2.0](LICENSE). You may use, modify, and distribute this
project, including commercially, provided that copyright, license, and attribution notices
are preserved and modified files are identified. See [NOTICE](NOTICE).

