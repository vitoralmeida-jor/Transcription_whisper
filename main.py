"""Ponto de entrada do Transcritor Jornalístico."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.batch import BatchProcessor
from src.config import ConfigError, load_config
from src.logger import setup_logging


def configure_console() -> None:
    """Evita falhas de encoding com símbolos e acentos no PowerShell antigo."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcreve arquivos locais com whisper.cpp e diarização pyannote."
    )
    parser.add_argument("input", type=Path, nargs="?", default=Path("."), help="Arquivo de mídia ou pasta")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--recursive", action="store_true", help="Busca em subpastas")
    parser.add_argument("--speakers", type=int, help="Número exato de falantes")
    parser.add_argument("--min-speakers", type=int, help="Número mínimo de falantes")
    parser.add_argument("--max-speakers", type=int, help="Número máximo de falantes")
    parser.add_argument("--force", action="store_true", help="Reprocessa saídas existentes")
    parser.add_argument("--no-diarization", action="store_true", help="Desativa diarização")
    parser.add_argument("--model", help="Modelo whisper.cpp (nome ou caminho .bin)")
    parser.add_argument(
        "--check", action="store_true", help="Somente verifica o ambiente e encerra"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        config.apply_cli(args)
        setup_logging(config.paths.logs)
        processor = BatchProcessor(config)
        if args.check:
            return 0 if processor.print_environment_check() else 2
        result = processor.run(args.input)
        return 1 if result.failed else 0
    except (ConfigError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning("Processamento interrompido pelo usuário")
        print("\nProcessamento interrompido. Resultados já concluídos foram preservados.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
