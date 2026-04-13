import json
import subprocess
from pathlib import Path


CHANNEL = 'main'
REPO_DIR = Path(__file__).resolve().parents[2]
RETAILHUB_ROOT = REPO_DIR.parent
STATE_FILE = RETAILHUB_ROOT / 'state' / 'update_state.json'
UPDATE_SCRIPT = REPO_DIR / 'deploy' / 'retailhub_update_manager.ps1'


def _git_head():
    try:
        out = subprocess.check_output(
            ['git', '-C', str(REPO_DIR), 'rev-parse', 'HEAD'],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return out.strip()
    except Exception:
        return ''


def _normalize(payload):
    payload = payload if isinstance(payload, dict) else {}
    installed = str(payload.get('installed_commit') or '').strip()
    remote = str(payload.get('remote_commit') or '').strip() or installed
    pending = bool(payload.get('pending'))
    if installed and remote:
        pending = installed != remote
    return {
        'ok': bool(payload.get('ok', True)),
        'channel': str(payload.get('channel') or CHANNEL),
        'pending': pending,
        'installed_commit': installed,
        'remote_commit': remote,
        'last_check_at': payload.get('last_check_at'),
        'last_update_at': payload.get('last_update_at'),
        'last_error': payload.get('last_error'),
    }


def get_update_status():
    head = _git_head()
    default = {
        'ok': True,
        'channel': CHANNEL,
        'pending': False,
        'installed_commit': head,
        'remote_commit': head,
        'last_check_at': None,
        'last_update_at': None,
        'last_error': None,
    }
    if not STATE_FILE.exists():
        return default

    try:
        raw = STATE_FILE.read_text(encoding='utf-8-sig').strip()
        if not raw:
            return default
        data = json.loads(raw)
    except Exception:
        out = dict(default)
        out['ok'] = False
        out['last_error'] = 'No se pudo leer state/update_state.json'
        return out

    merged = dict(default)
    merged.update(_normalize(data))
    return merged


def _extract_json_line(text):
    lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith('{') and line.endswith('}'):
            return line
    return ''


def run_update_check(*, force=False):
    if not UPDATE_SCRIPT.exists():
        out = get_update_status()
        out['ok'] = False
        out['last_error'] = f'No se encontro script de actualizacion: {UPDATE_SCRIPT}'
        return out

    cmd = [
        'powershell.exe',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        str(UPDATE_SCRIPT),
        '-Mode',
        'check',
        '-Channel',
        CHANNEL,
        '-RetailHubRoot',
        str(RETAILHUB_ROOT),
        '-Json',
    ]
    if force:
        cmd.append('-Force')

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception as exc:
        out = get_update_status()
        out['ok'] = False
        out['last_error'] = f'No se pudo ejecutar chequeo de actualizaciones: {exc}'
        return out

    raw_json = _extract_json_line(proc.stdout)
    if not raw_json:
        out = get_update_status()
        out['ok'] = False
        stderr_text = (proc.stderr or '').strip()
        out['last_error'] = stderr_text or 'El script de actualizacion no devolvio JSON valido.'
        return out

    try:
        data = json.loads(raw_json)
    except Exception:
        out = get_update_status()
        out['ok'] = False
        out['last_error'] = 'Respuesta invalida del script de actualizacion.'
        return out

    normalized = _normalize(data)
    normalized['ok'] = bool(data.get('ok'))
    if 'checked' in data:
        normalized['checked'] = bool(data.get('checked'))
    if 'applied' in data:
        normalized['applied'] = bool(data.get('applied'))
    if 'mode' in data:
        normalized['mode'] = data.get('mode')
    return normalized
