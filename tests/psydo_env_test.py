"""env 覆盖 psydo_image provider 的契约测试。

不发起真实网络请求;只验证 Config.apply_env_overrides 与
Config.get_image_provider_config 在不同环境变量场景下的行为。
"""
import os

import pytest

from backend.config import Config


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """每个用例前后清空相关环境变量,避免进程级污染。"""
    keys = [
        "PSYDO_API_KEY", "PSYDO_BASE_URL", "PSYDO_MODEL",
        "TEXT_GEMINI_API_KEY", "TEXT_OPENAI_API_KEY",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    # 清掉 Config 缓存,避免 yaml 文件副作用
    Config._image_providers_config = None
    Config._text_providers_config = None
    yield


def _write_yaml(tmp_path, content):
    """把 yaml 内容写到仓库根的 image_providers.yaml,绕过 .gitignore。"""
    repo_root = tmp_path
    # 直接用 monkeypatch 风格的 Config._image_providers_config 注入,
    # 不必真写文件
    Config._image_providers_config = content


def test_apply_env_overrides_replaces_empty_yaml_key(monkeypatch):
    """YAML api_key 为空、env 有值时,env 必须填充到最终 dict。"""
    monkeypatch.setenv("PSYDO_API_KEY", "sk-from-env")
    cfg = {"api_key": "", "base_url": "https://yaml.example", "model": "yaml-model"}
    merged = Config.apply_env_overrides("psydo_image", cfg)

    assert merged["api_key"] == "sk-from-env"
    assert merged["base_url"] == "https://yaml.example"
    assert merged["model"] == "yaml-model"
    # 不污染原 dict
    assert cfg["api_key"] == ""


def test_apply_env_overrides_does_not_clobber_nonempty_yaml(monkeypatch):
    """YAML api_key 已填、env 也有值时,env 优先(覆盖)。"""
    monkeypatch.setenv("PSYDO_API_KEY", "sk-from-env")
    monkeypatch.setenv("PSYDO_BASE_URL", "https://env.example")
    cfg = {"api_key": "sk-from-yaml", "base_url": "https://yaml.example", "model": "m"}
    merged = Config.apply_env_overrides("psydo_image", cfg)

    assert merged["api_key"] == "sk-from-env"
    assert merged["base_url"] == "https://env.example"


def test_apply_env_overrides_no_env_map_leaves_dict_alone(monkeypatch):
    """未注册的 provider(如 openai_image)不受 env 影响。"""
    monkeypatch.setenv("PSYDO_API_KEY", "sk-from-env")
    cfg = {"api_key": "sk-yaml", "base_url": "https://x", "model": "m"}
    merged = Config.apply_env_overrides("openai_image", cfg)
    assert merged == cfg
    assert merged["api_key"] == "sk-yaml"


def test_env_or_yaml_fallback_when_env_missing():
    cfg_val = "value-from-yaml"
    assert Config.env_or_yaml("psydo_image", "api_key", cfg_val) == "value-from-yaml"


def test_env_or_yaml_uses_env_when_present(monkeypatch):
    monkeypatch.setenv("PSYDO_MODEL", "env-model")
    assert Config.env_or_yaml("psydo_image", "model", "yaml-model") == "env-model"


def test_get_image_provider_config_uses_env_when_yaml_empty(monkeypatch):
    """完整链路:YAML api_key 为空、env 有值时,get_image_provider_config
    必须返回带 env api_key 的 dict,不抛 ValueError。"""
    monkeypatch.setenv("PSYDO_API_KEY", "sk-from-env")
    _write_yaml(None, {
        "active_provider": "psydo_image",
        "providers": {
            "psydo_image": {
                "type": "image_api",
                "api_key": "",
                "base_url": "https://api.psydo.top",
                "model": "gpt-image-2-firefly",
            },
            "gemini": {  # 另一个 provider 用来证明只覆盖 psydo
                "type": "google_genai",
                "api_key": "AIza-yaml",
                "model": "gemini-3-pro-image-preview",
            },
        },
    })

    cfg = Config.get_image_provider_config("psydo_image")
    assert cfg["api_key"] == "sk-from-env"
    assert cfg["base_url"] == "https://api.psydo.top"
    assert cfg["model"] == "gpt-image-2-firefly"

    # 取 gemini 时不应被 psydo 的 env 污染
    gcfg = Config.get_image_provider_config("gemini")
    assert gcfg["api_key"] == "AIza-yaml"


def test_get_image_provider_config_still_raises_when_neither_yaml_nor_env():
    """YAML 空、env 也空时,仍按原契约抛 ValueError,但错误信息要提到 env 名。"""
    _write_yaml(None, {
        "active_provider": "psydo_image",
        "providers": {
            "psydo_image": {
                "type": "image_api",
                "api_key": "",
                "base_url": "https://api.psydo.top",
                "model": "gpt-image-2-firefly",
            },
        },
    })
    with pytest.raises(ValueError) as exc:
        Config.get_image_provider_config("psydo_image")
    # 错误信息应提示 env 变量名,帮用户自助
    assert "PSYDO_API_KEY" in str(exc.value)