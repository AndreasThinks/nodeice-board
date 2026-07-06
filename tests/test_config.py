"""Tests for nodeice_board.config."""

import pytest

from nodeice_board.config import (
    load_config,
    get_device_names,
    get_info_url,
    get_expiration_days,
)


def write_config(tmp_path, content):
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_load_config_valid(tmp_path):
    path = write_config(
        tmp_path,
        'Nodeice_board:\n  Long_Name: "Test Board"\n  Short_Name: "TB"\n  Expiration_Days: 14\n',
    )
    config = load_config(path)
    assert config["Nodeice_board"]["Long_Name"] == "Test Board"


def test_load_config_missing_file(tmp_path):
    assert load_config(str(tmp_path / "nope.yaml")) == {}


def test_load_config_invalid_format(tmp_path):
    path = write_config(tmp_path, "- just\n- a\n- list\n")
    assert load_config(path) == {}


def test_get_device_names():
    config = {"Nodeice_board": {"Long_Name": "Long", "Short_Name": "SH"}}
    assert get_device_names(config) == ("Long", "SH")


def test_get_device_names_missing():
    assert get_device_names({}) == (None, None)


def test_get_info_url_default():
    assert "github.com" in get_info_url({})


def test_get_info_url_from_config():
    config = {"Nodeice_board": {"Info_URL": "https://example.com"}}
    assert get_info_url(config) == "https://example.com"


def test_get_expiration_days_int():
    config = {"Nodeice_board": {"Expiration_Days": 14}}
    assert get_expiration_days(config) == 14


def test_get_expiration_days_float_coerced():
    config = {"Nodeice_board": {"Expiration_Days": 7.0}}
    assert get_expiration_days(config) == 7


def test_get_expiration_days_invalid_falls_back_to_default():
    for bad in [0, -3, "soon", None, True]:
        config = {"Nodeice_board": {"Expiration_Days": bad}}
        assert get_expiration_days(config) == 7


def test_get_expiration_days_missing():
    assert get_expiration_days({}) == 7


def test_repo_config_yaml_is_valid():
    """The config.yaml shipped in the repo must parse and produce valid values."""
    import os

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = load_config(os.path.join(repo_root, "config.yaml"))
    long_name, short_name = get_device_names(config)

    assert config, "config.yaml failed to load"
    assert get_expiration_days(config) >= 1
    assert long_name and len(long_name.encode("utf-8")) <= 40
    assert short_name and len(short_name.encode("utf-8")) <= 4
