"""Carregamento e validação da configuração YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Configuração ausente ou inválida."""


@dataclass
class WhisperConfig:
    backend: str = "whisper_cpp"
    executable: Path = Path("bin/whisper/whisper-cli.exe")
    model: str = "large-v3"
    language: str = "pt"
    use_gpu: bool = True
    gpu_backend: str = "vulkan"
    threads: int = 0


@dataclass
class DiarizationConfig:
    enabled: bool = True
    model: str = "pyannote/speaker-diarization-community-1"
    local_model_path: Path | None = None
    device: str = "cpu"
    num_speakers: int | None = None
    min_speakers: int | None = 2
    max_speakers: int | None = 5


@dataclass
class OutputConfig:
    txt: bool = True
    json: bool = True
    srt: bool = True
    timestamps: bool = True


@dataclass
class ProcessingConfig:
    recursive: bool = False
    skip_existing: bool = True
    keep_temp_on_error: bool = True


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1


@dataclass
class PathsConfig:
    output: Path = Path("output")
    temp: Path = Path("temp")
    logs: Path = Path("logs")
    whisper_models: Path = Path("models/whisper")


@dataclass
class AppConfig:
    project_root: Path
    whisper: WhisperConfig
    diarization: DiarizationConfig
    output: OutputConfig
    processing: ProcessingConfig
    audio: AudioConfig
    paths: PathsConfig

    def apply_cli(self, args: Any) -> None:
        self.processing.recursive = self.processing.recursive or args.recursive
        if args.force:
            self.processing.skip_existing = False
        if args.no_diarization:
            self.diarization.enabled = False
        if args.model:
            self.whisper.model = args.model
        if args.speakers is not None:
            if args.speakers < 1:
                raise ConfigError("--speakers deve ser maior que zero")
            self.diarization.num_speakers = args.speakers
            self.diarization.min_speakers = args.speakers
            self.diarization.max_speakers = args.speakers
        else:
            if args.min_speakers is not None:
                self.diarization.min_speakers = args.min_speakers
            if args.max_speakers is not None:
                self.diarization.max_speakers = args.max_speakers
        _validate_speakers(self.diarization)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"A seção '{name}' deve ser um mapa YAML")
    return value


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (root / path).resolve()


def _validate_speakers(config: DiarizationConfig) -> None:
    for name in ("num_speakers", "min_speakers", "max_speakers"):
        value = getattr(config, name)
        if value is not None and value < 1:
            raise ConfigError(f"diarization.{name} deve ser maior que zero")
    if (
        config.min_speakers is not None
        and config.max_speakers is not None
        and config.min_speakers > config.max_speakers
    ):
        raise ConfigError("min_speakers não pode ser maior que max_speakers")


def load_config(path: Path) -> AppConfig:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ConfigError(f"Arquivo de configuração não encontrado: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Não foi possível ler {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("A raiz de config.yaml deve ser um mapa")

    root = path.parent
    w, d, o = _section(raw, "whisper"), _section(raw, "diarization"), _section(raw, "output")
    p, a, paths = _section(raw, "processing"), _section(raw, "audio"), _section(raw, "paths")
    whisper = WhisperConfig(
        backend=str(w.get("backend", "whisper_cpp")),
        executable=_resolve(root, w.get("executable", "bin/whisper/whisper-cli.exe")),
        model=str(w.get("model", "large-v3")), language=str(w.get("language", "pt")),
        use_gpu=bool(w.get("use_gpu", True)), gpu_backend=str(w.get("gpu_backend", "vulkan")),
        threads=int(w.get("threads", 0)),
    )
    local = d.get("local_model_path")
    diarization = DiarizationConfig(
        enabled=bool(d.get("enabled", True)),
        model=str(d.get("model", "pyannote/speaker-diarization-community-1")),
        local_model_path=_resolve(root, local) if local else None,
        device=str(d.get("device", "cpu")),
        min_speakers=d.get("min_speakers", 2), max_speakers=d.get("max_speakers", 5),
    )
    _validate_speakers(diarization)
    audio = AudioConfig(sample_rate=int(a.get("sample_rate", 16000)), channels=int(a.get("channels", 1)))
    if audio.sample_rate < 8000 or audio.channels < 1:
        raise ConfigError("Configuração de áudio inválida")
    config = AppConfig(
        project_root=root, whisper=whisper, diarization=diarization,
        output=OutputConfig(**{k: bool(o.get(k, True)) for k in ("txt", "json", "srt", "timestamps")}),
        processing=ProcessingConfig(
            recursive=bool(p.get("recursive", False)), skip_existing=bool(p.get("skip_existing", True)),
            keep_temp_on_error=bool(p.get("keep_temp_on_error", True)),
        ),
        audio=audio,
        paths=PathsConfig(
            output=_resolve(root, paths.get("output", "output")),
            temp=_resolve(root, paths.get("temp", "temp")),
            logs=_resolve(root, paths.get("logs", "logs")),
            whisper_models=_resolve(root, paths.get("whisper_models", "models/whisper")),
        ),
    )
    for directory in (config.paths.output, config.paths.temp, config.paths.logs, config.paths.whisper_models):
        directory.mkdir(parents=True, exist_ok=True)
    return config

