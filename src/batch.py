"""Orquestração resiliente do pipeline e do processamento em lote."""

from __future__ import annotations

import importlib.util
import json
import logging
import platform
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .aligner import align_segments, without_diarization
from .config import AppConfig, ConfigError
from .diarizer import PyannoteDiarizer
from .exporter import export_all, outputs_complete
from .media import MediaPreparer, PreparedAudio, discover_media
from .transcriber import WhisperCppTranscriber
from .utils import atomic_write_text, seconds_to_timestamp, stable_output_key


@dataclass
class BatchResult:
    found: int = 0
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    elapsed: float = 0.0


class Manifest:
    def __init__(self, path: Path):
        self.path = path
        try:
            loaded = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            self.data: dict = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            self.data = {}

    @staticmethod
    def fingerprint(path: Path) -> dict[str, int]:
        stat = path.stat()
        return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

    def is_current(self, source: Path, key: str) -> bool:
        item = self.data.get(str(source.resolve()))
        return bool(
            item and item.get("status") == "completed" and item.get("output_key") == key
            and item.get("fingerprint") == self.fingerprint(source)
        )

    def update(self, source: Path, key: str, status: str, error: str | None = None) -> None:
        self.data[str(source.resolve())] = {
            "status": status,
            "output_key": key,
            "fingerprint": self.fingerprint(source),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            **({"error": error} if error else {}),
        }
        atomic_write_text(self.path, json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")


class BatchProcessor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.media = MediaPreparer(config.paths.temp, config.audio.sample_rate, config.audio.channels)
        self.transcriber = WhisperCppTranscriber(
            config.whisper, config.paths.whisper_models, config.paths.temp
        )
        self.diarizer = PyannoteDiarizer(config.diarization) if config.diarization.enabled else None
        self.manifest = Manifest(config.paths.output / "manifest.json")

    def environment_status(self) -> list[tuple[str, bool, str]]:
        pyannote_ready = (
            importlib.util.find_spec("pyannote") is not None
            and importlib.util.find_spec("pyannote.audio") is not None
        )
        checks = [
            ("Python", True, platform.python_version()),
            ("FFmpeg/FFprobe", self.media.available, "encontrado" if self.media.available else "não encontrado no PATH"),
            ("whisper.cpp", self.transcriber.executable.is_file(), str(self.transcriber.executable)),
            ("Modelo Whisper", self.transcriber.model_path.is_file(), str(self.transcriber.model_path)),
            ("Configuração", True, str(self.config.project_root / "config.yaml")),
            ("Diretório de saída", self.config.paths.output.is_dir(), str(self.config.paths.output)),
        ]
        if self.config.diarization.enabled:
            checks.append(("pyannote.audio", pyannote_ready, "instalado" if pyannote_ready else "não instalado"))
        return checks

    def print_environment_check(self) -> bool:
        print("Verificando ambiente...\n")
        checks = self.environment_status()
        for name, ok, detail in checks:
            print(f"[{'✓' if ok else '✗'}] {name}: {detail}")
        ready = all(item[1] for item in checks)
        print("\nAmbiente pronto." if ready else "\nAmbiente incompleto. Consulte o README.md.")
        return ready

    def _validate_global_environment(self) -> None:
        failures = [f"{name}: {detail}" for name, ok, detail in self.environment_status() if not ok]
        if failures:
            raise ConfigError("Ambiente incompleto:\n- " + "\n- ".join(failures))
        if not any((self.config.output.txt, self.config.output.json, self.config.output.srt)):
            raise ConfigError("Ative ao menos um formato em output")

    def run(self, input_path: Path) -> BatchResult:
        self._validate_global_environment()
        root = input_path.expanduser().resolve()
        files = discover_media(root, self.config.processing.recursive)
        result = BatchResult(found=len(files))
        started = time.monotonic()
        print(f"Arquivos encontrados: {len(files)}")
        if not files:
            print("Nenhum arquivo de áudio ou vídeo suportado foi encontrado.")
            return result
        stem_counts = Counter(source.stem.casefold() for source in files)
        for index, source in enumerate(files, 1):
            print(f"\n[{index:02d}/{len(files):02d}] {source.name}")
            key = (
                stable_output_key(source, root)
                if root.is_dir() and stem_counts[source.stem.casefold()] > 1
                else source.stem
            )
            complete = outputs_complete(self.config.paths.output, key, self.config.output)
            manifest_current = self.manifest.is_current(source, key)
            known_to_manifest = str(source.resolve()) in self.manifest.data
            if self.config.processing.skip_existing and complete and (manifest_current or not known_to_manifest):
                print("↪ já processado — ignorando")
                result.skipped += 1
                continue
            try:
                self._process_one(source, key)
                result.completed += 1
                print("✓ concluído")
            except KeyboardInterrupt:
                self.manifest.update(source, key, "interrupted", "Interrompido pelo usuário")
                raise
            except Exception as exc:
                result.failed += 1
                message = str(exc) or exc.__class__.__name__
                self.manifest.update(source, key, "failed", message)
                self.logger.error(
                    "arquivo=%s | status=erro | erro=%s\n%s", source, message, traceback.format_exc()
                )
                print(f"ERRO: {message}\nArquivo ignorado. Prosseguindo para o próximo.")
        result.elapsed = time.monotonic() - started
        self._print_summary(result)
        return result

    def _process_one(self, source: Path, key: str) -> None:
        started = time.monotonic()
        prepared: PreparedAudio | None = None
        self.logger.info("arquivo=%s | status=iniciado | modelo=%s", source, self.config.whisper.model)
        try:
            print("Extraindo/preparando áudio...")
            prepared = self.media.prepare(source, key)
            duration = self.media.duration(prepared.path)
            print("✓ áudio preparado\nTranscrevendo...")
            transcripts = self.transcriber.transcribe(prepared.path, key)
            print("✓ transcrição concluída")
            if self.diarizer:
                print("Identificando falantes...")
                turns = self.diarizer.diarize(prepared.path)
                print("✓ diarização concluída\nAssociando falantes...")
                aligned = align_segments(transcripts, turns)
                print("✓ alinhamento concluído")
            else:
                aligned = without_diarization(transcripts)
            print("Salvando resultados...")
            export_all(
                self.config.paths.output, key, source, self.config.whisper.language,
                duration, self.config.whisper.model, bool(self.diarizer), aligned, self.config.output,
            )
            self.manifest.update(source, key, "completed")
            self.logger.info(
                "arquivo=%s | status=concluído | duração_mídia=%.3f | tempo=%.3f",
                source, duration, time.monotonic() - started,
            )
            prepared.cleanup()
        except KeyboardInterrupt:
            if prepared:
                prepared.cleanup()
            raise
        except Exception:
            if prepared and not self.config.processing.keep_temp_on_error:
                prepared.cleanup()
            raise

    @staticmethod
    def _print_summary(result: BatchResult) -> None:
        print(
            "\n" + "=" * 40 + "\n\nPROCESSAMENTO CONCLUÍDO\n\n"
            f"Arquivos encontrados: {result.found:6d}\n"
            f"Concluídos:            {result.completed:6d}\n"
            f"Ignorados:             {result.skipped:6d}\n"
            f"Com erro:              {result.failed:6d}\n\n"
            f"Tempo total: {seconds_to_timestamp(result.elapsed)}\n\n" + "=" * 40
        )
