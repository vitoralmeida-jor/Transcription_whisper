from argparse import Namespace
from pathlib import Path

from src.config import load_config


def test_config_paths_are_relative_to_yaml(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("paths:\n  output: resultados\n", encoding="utf-8")
    config = load_config(config_file)
    assert config.paths.output == (tmp_path / "resultados").resolve()


def test_speakers_cli_overrides_bounds(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("{}", encoding="utf-8")
    config = load_config(config_file)
    config.apply_cli(
        Namespace(
            recursive=False, force=False, no_diarization=False, model=None,
            speakers=2, min_speakers=None, max_speakers=None,
        )
    )
    assert config.diarization.num_speakers == 2
    assert config.diarization.min_speakers == config.diarization.max_speakers == 2

