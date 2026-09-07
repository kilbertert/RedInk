import logging
import os
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


class Config:
    DEBUG = True
    HOST = '0.0.0.0'
    PORT = 12398
    CORS_ORIGINS = ['http://localhost:5173', 'http://localhost:3000']
    OUTPUT_DIR = 'output'

    # 环境变量覆盖:provider_key 是 YAML 里的字段(如 "api_key"),
    # env_name 是环境变量名(如 "PSYDO_API_KEY")。YAML 非空时优先 yaml,
    # YAML 空/缺时回落 env。env 不解析设置失败,启动期会清空避免泄露。
    _ENV_OVERRIDES = {
        'psydo_image': {
            'api_key': 'PSYDO_API_KEY',
            'base_url': 'PSYDO_BASE_URL',
            'model': 'PSYDO_MODEL',
        },
        'claude_local': {
            'api_key': 'TEXT_CLAUDE_API_KEY',
            'base_url': 'TEXT_CLAUDE_BASE_URL',
            'model': 'TEXT_CLAUDE_MODEL',
        },
    }

    _image_providers_config = None
    _text_providers_config = None

    @classmethod
    def env_or_yaml(cls, provider_name: str, field: str, yaml_value):
        """对单字段:env 覆盖 yaml。env 缺失返回 yaml 原值。"""
        env_map = cls._ENV_OVERRIDES.get(provider_name, {})
        env_name = env_map.get(field)
        if env_name:
            env_val = os.environ.get(env_name)
            if env_val:
                logger.debug(
                    "使用环境变量覆盖配置: provider=%s field=%s env=%s",
                    provider_name, field, env_name,
                )
                return env_val
        return yaml_value

    @classmethod
    def apply_env_overrides(cls, provider_name: str, provider_config: dict) -> dict:
        """对一个 provider 字典应用 env 覆盖,返回新字典(不变更原 dict)。"""
        env_map = cls._ENV_OVERRIDES.get(provider_name, {})
        if not env_map:
            return provider_config
        merged = dict(provider_config)
        for field, env_name in env_map.items():
            env_val = os.environ.get(env_name)
            if env_val:
                merged[field] = env_val
                logger.debug(
                    "环境变量覆盖生效: provider=%s field=%s env=%s",
                    provider_name, field, env_name,
                )
        return merged

    @classmethod
    def load_image_providers_config(cls):
        if cls._image_providers_config is not None:
            return cls._image_providers_config

        config_path = Path(__file__).parent.parent / 'image_providers.yaml'
        logger.debug(f"加载图片服务商配置: {config_path}")

        if not config_path.exists():
            logger.warning(f"图片配置文件不存在: {config_path}，使用默认配置")
            cls._image_providers_config = {
                'active_provider': 'google_genai',
                'providers': {}
            }
            return cls._image_providers_config

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cls._image_providers_config = yaml.safe_load(f) or {}
            logger.debug(f"图片配置加载成功: {list(cls._image_providers_config.get('providers', {}).keys())}")
        except yaml.YAMLError as e:
            logger.error(f"图片配置文件 YAML 格式错误: {e}")
            raise ValueError(
                f"配置文件格式错误: image_providers.yaml\n"
                f"YAML 解析错误: {e}\n"
                "解决方案：\n"
                "1. 检查 YAML 缩进是否正确（使用空格，不要用Tab）\n"
                "2. 检查引号是否配对\n"
                "3. 使用在线 YAML 验证器检查格式"
            )

        return cls._image_providers_config

    @classmethod
    def load_text_providers_config(cls):
        """加载文本生成服务商配置"""
        if cls._text_providers_config is not None:
            return cls._text_providers_config

        config_path = Path(__file__).parent.parent / 'text_providers.yaml'
        logger.debug(f"加载文本服务商配置: {config_path}")

        if not config_path.exists():
            logger.warning(f"文本配置文件不存在: {config_path}，使用默认配置")
            cls._text_providers_config = {
                'active_provider': 'google_gemini',
                'providers': {}
            }
            return cls._text_providers_config

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cls._text_providers_config = yaml.safe_load(f) or {}
            logger.debug(f"文本配置加载成功: {list(cls._text_providers_config.get('providers', {}).keys())}")
        except yaml.YAMLError as e:
            logger.error(f"文本配置文件 YAML 格式错误: {e}")
            raise ValueError(
                f"配置文件格式错误: text_providers.yaml\n"
                f"YAML 解析错误: {e}\n"
                "解决方案：\n"
                "1. 检查 YAML 缩进是否正确（使用空格，不要用Tab）\n"
                "2. 检查引号是否配对\n"
                "3. 使用在线 YAML 验证器检查格式"
            )

        return cls._text_providers_config

    @classmethod
    def get_active_image_provider(cls):
        config = cls.load_image_providers_config()
        active = config.get('active_provider', 'google_genai')
        logger.debug(f"当前激活的图片服务商: {active}")
        return active

    @classmethod
    def get_image_provider_config(cls, provider_name: str = None):
        config = cls.load_image_providers_config()

        if provider_name is None:
            provider_name = cls.get_active_image_provider()

        logger.info(f"获取图片服务商配置: {provider_name}")

        providers = config.get('providers', {})
        if not providers:
            raise ValueError(
                "未找到任何图片生成服务商配置。\n"
                "解决方案：\n"
                "1. 在系统设置页面添加图片生成服务商\n"
                "2. 或手动编辑 image_providers.yaml 文件\n"
                "3. 确保文件中有 providers 字段"
            )

        if provider_name not in providers:
            available = ', '.join(providers.keys()) if providers else '无'
            logger.error(f"图片服务商 [{provider_name}] 不存在，可用服务商: {available}")
            raise ValueError(
                f"未找到图片生成服务商配置: {provider_name}\n"
                f"可用的服务商: {available}\n"
                "解决方案：\n"
                "1. 在系统设置页面添加该服务商\n"
                "2. 或修改 active_provider 为已存在的服务商\n"
                "3. 检查 image_providers.yaml 文件"
            )

        provider_config = providers[provider_name].copy()
        provider_config = cls.apply_env_overrides(provider_name, provider_config)

        # 验证必要字段
        if not provider_config.get('api_key'):
            logger.error(f"图片服务商 [{provider_name}] 未配置 API Key")
            raise ValueError(
                f"服务商 {provider_name} 未配置 API Key\n"
                "解决方案：\n"
                "1. 在系统设置页面编辑该服务商，填写 API Key\n"
                "2. 或手动在 image_providers.yaml 中添加 api_key 字段\n"
                f"3. 或设置环境变量 {cls._ENV_OVERRIDES.get(provider_name, {}).get('api_key', '')}".strip()
            )

        provider_type = provider_config.get('type', provider_name)
        if provider_type in ['openai', 'openai_compatible', 'image_api']:
            if not provider_config.get('base_url'):
                logger.error(f"服务商 [{provider_name}] 类型为 {provider_type}，但未配置 base_url")
                raise ValueError(
                    f"服务商 {provider_name} 未配置 Base URL\n"
                    f"服务商类型 {provider_type} 需要配置 base_url\n"
                    "解决方案：在系统设置页面编辑该服务商，填写 Base URL"
                )

        logger.info(f"图片服务商配置验证通过: {provider_name} (type={provider_type})")
        return provider_config

    @classmethod
    def reload_config(cls):
        """重新加载配置（清除缓存）"""
        logger.info("重新加载所有配置...")
        cls._image_providers_config = None
        cls._text_providers_config = None

    @classmethod
    def get_active_text_provider(cls):
        config = cls.load_text_providers_config()
        active = config.get('active_provider', 'google_gemini')
        logger.debug(f"当前激活的文本服务商: {active}")
        return active

    @classmethod
    def get_text_provider_config(cls, provider_name: str = None):
        """镜像 get_image_provider_config:env 覆盖 + 必要字段校验。"""
        config = cls.load_text_providers_config()

        if provider_name is None:
            provider_name = cls.get_active_text_provider()

        logger.info(f"获取文本服务商配置: {provider_name}")

        providers = config.get('providers', {})
        if not providers:
            raise ValueError(
                "未找到任何文本生成服务商配置。\n"
                "解决方案：\n"
                "1. 在系统设置页面添加文本生成服务商\n"
                "2. 或手动编辑 text_providers.yaml 文件\n"
                "3. 确保文件中有 providers 字段"
            )

        if provider_name not in providers:
            available = ', '.join(providers.keys()) if providers else '无'
            logger.error(f"文本服务商 [{provider_name}] 不存在，可用服务商: {available}")
            raise ValueError(
                f"未找到文本生成服务商配置: {provider_name}\n"
                f"可用的服务商: {available}\n"
                "解决方案：\n"
                "1. 在系统设置页面添加该服务商\n"
                "2. 或修改 active_provider 为已存在的服务商\n"
                "3. 检查 text_providers.yaml 文件"
            )

        provider_config = providers[provider_name].copy()
        provider_config = cls.apply_env_overrides(provider_name, provider_config)

        if not provider_config.get('api_key'):
            logger.error(f"文本服务商 [{provider_name}] 未配置 API Key")
            raise ValueError(
                f"服务商 {provider_name} 未配置 API Key\n"
                "解决方案：\n"
                "1. 在系统设置页面编辑该服务商，填写 API Key\n"
                "2. 或手动在 text_providers.yaml 中添加 api_key 字段\n"
                f"3. 或设置环境变量 {cls._ENV_OVERRIDES.get(provider_name, {}).get('api_key', '')}".strip()
            )

        provider_type = provider_config.get('type', provider_name)
        if provider_type in ['openai', 'openai_compatible', 'google_gemini']:
            if not provider_config.get('base_url'):
                logger.error(f"服务商 [{provider_name}] 类型为 {provider_type}，但未配置 base_url")
                raise ValueError(
                    f"服务商 {provider_name} 未配置 Base URL\n"
                    f"服务商类型 {provider_type} 需要配置 base_url\n"
                    "解决方案：在系统设置页面编辑该服务商，填写 Base URL"
                )

        logger.info(f"文本服务商配置验证通过: {provider_name} (type={provider_type})")
        return provider_config
