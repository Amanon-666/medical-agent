"""
MCP 服务配置加载模块。

该模块集中读取数据库路径、平台地址、可视化入口和任务运行参数。
"""

import os, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = {}
_cfg_path = ROOT / 'config.yaml'
if _cfg_path.exists():
    with open(_cfg_path, 'r', encoding='utf-8') as fh:
        CONFIG = yaml.safe_load(fh) or {}

def _load_runtime_env() -> None:
    env_path = ROOT / '.env.runtime'
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")

_load_runtime_env()

def _secret_value(env_name: str, file_env_name: str) -> str:
    v = os.environ.get(env_name, '').strip()
    if v: return v
    key_file = os.environ.get(file_env_name, '').strip()
    if key_file:
        try: return Path(key_file).read_text(encoding='utf-8').strip()
        except OSError: pass
    return ''

def _project_db_path(config_value, fallback: str) -> str:
    v = (config_value or '').strip()
    return str(ROOT / v) if v else str(ROOT / fallback)

# 大模型配置
LLM_API_KEY = _secret_value('CCF_LLM_API_KEY', 'CCF_LLM_API_KEY_FILE')
LLM_BASE_URL = os.environ.get('CCF_LLM_BASE_URL', CONFIG.get('ollama', {}).get('base_url', 'https://api.deepseek.com/v1/chat/completions'))
LLM_MODEL = os.environ.get('CCF_LLM_MODEL', CONFIG.get('ollama', {}).get('model', 'deepseek-chat'))

# DataMate 服务地址
DATAMATE_BASE = os.environ.get('CCF_DATAMATE_BASE', CONFIG.get('datamate', {}).get('api_base', 'http://localhost:18000'))
DATAMATE_GATEWAY = os.environ.get('CCF_DATAMATE_GATEWAY', CONFIG.get('datamate', {}).get('gateway_base', 'http://localhost:8080'))
DATASET_VOLUME = os.environ.get('CCF_DATASET_VOLUME', CONFIG.get('datamate', {}).get('dataset_volume', ''))
SUDO_PW = os.environ.get('CCF_SUDO_PW', '')

# 知识图谱与分析库路径
KG_DB = _project_db_path(CONFIG.get('kg', {}).get('sqlite_path'), 'data/task2_medical_kg.db')
ANALYTICS_DB = _project_db_path(CONFIG.get('kg', {}).get('analytics_db_path'), 'data/task3_analytics.db')
SQL_DB = _project_db_path(CONFIG.get('kg', {}).get('sql_db_path'), 'data/medical_analytics.db')
