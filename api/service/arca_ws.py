import base64
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7
from django.core.cache import cache


WSAA_URLS = {
    'homologacion': 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms',
    'produccion': 'https://wsaa.afip.gov.ar/ws/services/LoginCms',
}

WSFE_URLS = {
    'homologacion': 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx',
    'produccion': 'https://servicios1.afip.gov.ar/wsfev1/service.asmx',
}

WSFE_SOAP_NS = 'http://ar.gov.afip.dif.FEV1/'
WSAA_SOAP_NS = 'http://wsaa.view.sua.dvadac.desein.afip.gov'
SOAP_ENV_NS = 'http://schemas.xmlsoap.org/soap/envelope/'


class ArcaError(Exception):
    def __init__(self, message: str, code: str | None = None, retryable: bool = False, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.payload = payload or {}


class ArcaRetryableError(ArcaError):
    def __init__(self, message: str, code: str | None = None, payload: dict[str, Any] | None = None):
        super().__init__(message, code=code, retryable=True, payload=payload)


class ArcaConfigError(ArcaError):
    def __init__(self, message: str, code: str | None = None, payload: dict[str, Any] | None = None):
        super().__init__(message, code=code, retryable=False, payload=payload)


@dataclass(frozen=True)
class ArcaRuntimeConfig:
    env: str
    cuit: str
    cert_path: str
    key_path: str
    wsaa_service: str = 'wsfe'
    wsaa_url: str = ''
    wsfe_url: str = ''
    timeout_secs: int = 25
    ta_cache_skew_secs: int = 180

    def with_defaults(self) -> 'ArcaRuntimeConfig':
        env = normalize_env(self.env)
        wsaa_url = (self.wsaa_url or '').strip() or WSAA_URLS[env]
        wsfe_url = (self.wsfe_url or '').strip() or WSFE_URLS[env]
        return ArcaRuntimeConfig(
            env=env,
            cuit=_clean_digits(self.cuit),
            cert_path=(self.cert_path or '').strip(),
            key_path=(self.key_path or '').strip(),
            wsaa_service=(self.wsaa_service or 'wsfe').strip() or 'wsfe',
            wsaa_url=wsaa_url,
            wsfe_url=wsfe_url,
            timeout_secs=max(5, int(self.timeout_secs or 25)),
            ta_cache_skew_secs=max(0, int(self.ta_cache_skew_secs or 180)),
        )


def normalize_env(raw: str | None) -> str:
    value = (raw or '').strip().lower()
    if value in ('prod', 'produccion', 'production'):
        return 'produccion'
    if value in ('homolog', 'homo', 'homologacion', 'test'):
        return 'homologacion'
    return 'homologacion'


def _clean_digits(raw: Any) -> str:
    return ''.join(ch for ch in str(raw or '') if ch.isdigit())


def _validate_runtime_config(cfg: ArcaRuntimeConfig) -> None:
    if len(_clean_digits(cfg.cuit)) != 11:
        raise ArcaConfigError('ARCA CUIT invalido o ausente')
    if not (cfg.cert_path or '').strip():
        raise ArcaConfigError('ARCA cert path ausente')
    if not (cfg.key_path or '').strip():
        raise ArcaConfigError('ARCA key path ausente')
    if not Path(cfg.cert_path).exists():
        raise ArcaConfigError('ARCA cert path no existe')
    if not Path(cfg.key_path).exists():
        raise ArcaConfigError('ARCA key path no existe')
    if not (cfg.wsaa_url or '').strip():
        raise ArcaConfigError('ARCA WSAA URL ausente')
    if not (cfg.wsfe_url or '').strip():
        raise ArcaConfigError('ARCA WSFE URL ausente')


def _load_cert(cert_path: str):
    data = Path(cert_path).read_bytes()
    try:
        return x509.load_pem_x509_certificate(data)
    except ValueError:
        return x509.load_der_x509_certificate(data)


def _load_private_key(key_path: str):
    data = Path(key_path).read_bytes()
    try:
        return serialization.load_pem_private_key(data, password=None)
    except ValueError:
        return serialization.load_der_private_key(data, password=None)


def _build_tra_xml(service: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    gen = (now - dt.timedelta(minutes=5)).isoformat(timespec='seconds')
    exp = (now + dt.timedelta(hours=12)).isoformat(timespec='seconds')
    uid = int(now.timestamp())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<loginTicketRequest version="1.0">'
        '<header>'
        f'<uniqueId>{uid}</uniqueId>'
        f'<generationTime>{escape(gen)}</generationTime>'
        f'<expirationTime>{escape(exp)}</expirationTime>'
        '</header>'
        f'<service>{escape(service)}</service>'
        '</loginTicketRequest>'
    )


def _sign_tra_cms_b64(tra_xml: str, cert_path: str, key_path: str) -> str:
    cert = _load_cert(cert_path)
    key = _load_private_key(key_path)
    builder = pkcs7.PKCS7SignatureBuilder().set_data(tra_xml.encode('utf-8')).add_signer(cert, key, hashes.SHA256())
    cms_der = builder.sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    return base64.b64encode(cms_der).decode('ascii')


def _local_name(tag: str) -> str:
    if not isinstance(tag, str):
        return ''
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def _find_first(root: ET.Element, name: str) -> ET.Element | None:
    for elem in root.iter():
        if _local_name(elem.tag) == name:
            return elem
    return None


def _find_children(elem: ET.Element | None, name: str) -> list[ET.Element]:
    if elem is None:
        return []
    out = []
    for child in list(elem):
        if _local_name(child.tag) == name:
            out.append(child)
    return out


def _child_text(elem: ET.Element | None, *names: str) -> str | None:
    if elem is None:
        return None
    expected = set(names)
    for child in list(elem):
        if _local_name(child.tag) in expected:
            text = (child.text or '').strip()
            if text:
                return text
    return None


def _to_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        if isinstance(value, str) and value.strip() == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _fmt_decimal(value: Any, places: int = 2) -> str:
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raw = Decimal('0')
    quant = Decimal('1').scaleb(-places)
    return str(raw.quantize(quant, rounding=ROUND_HALF_UP))


def _parse_iso_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace('Z', '+00:00')
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _parse_soap_root(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ArcaRetryableError(f'XML invalido desde ARCA: {exc}')


def _extract_soap_fault(root: ET.Element) -> tuple[str | None, str | None]:
    fault = _find_first(root, 'Fault')
    if fault is None:
        return None, None
    code = _child_text(fault, 'faultcode', 'Code')
    message = _child_text(fault, 'faultstring', 'Reason', 'faultstring')
    if not message:
        message = (fault.text or '').strip() or None
    return code, message


def _collect_messages(node: ET.Element | None) -> list[dict[str, str | None]]:
    if node is None:
        return []
    out: list[dict[str, str | None]] = []
    for elem in node.iter():
        lname = _local_name(elem.tag)
        if lname not in ('Err', 'Obs', 'Eve'):
            continue
        code = _child_text(elem, 'Code', 'CodObs', 'EvtCode')
        msg = _child_text(elem, 'Msg', 'Obs', 'EvtMsg')
        if code or msg:
            out.append(
                {
                    'type': lname.lower(),
                    'code': code,
                    'message': msg,
                }
            )
    return out


def _soap_post(url: str, envelope: str, timeout_secs: int, soap_action: str | None = None) -> tuple[ET.Element, str]:
    headers = {'Content-Type': 'text/xml; charset=utf-8'}
    if soap_action:
        headers['SOAPAction'] = soap_action
    try:
        resp = requests.post(url, data=envelope.encode('utf-8'), headers=headers, timeout=timeout_secs)
        xml_text = resp.text or ''
    except requests.Timeout as exc:
        raise ArcaRetryableError(f'Timeout ARCA: {exc}')
    except requests.ConnectionError as exc:
        raise ArcaRetryableError(f'Conexion ARCA fallida: {exc}')
    except requests.RequestException as exc:
        raise ArcaRetryableError(f'Error HTTP ARCA: {exc}')

    root = _parse_soap_root(xml_text)
    fault_code, fault_msg = _extract_soap_fault(root)
    if fault_code or fault_msg:
        msg = fault_msg or 'SOAP Fault ARCA'
        code = fault_code or None
        low = f'{code or ""} {msg}'.lower()
        if 'notauthorized' in low or 'not authorized' in low or 'coe.notauthorized' in low:
            raise ArcaConfigError(msg, code=code, payload={'raw': xml_text[:2000]})
        raise ArcaError(msg, code=code, retryable=False, payload={'raw': xml_text[:2000]})

    if int(resp.status_code) >= 500:
        raise ArcaRetryableError(f'ARCA HTTP {resp.status_code}', payload={'raw': xml_text[:2000]})
    if int(resp.status_code) >= 400:
        raise ArcaError(f'ARCA HTTP {resp.status_code}', code=str(resp.status_code), retryable=False, payload={'raw': xml_text[:2000]})

    return root, xml_text


def _wsaa_login_cms(cfg: ArcaRuntimeConfig, cms_b64: str) -> tuple[dict[str, Any], str]:
    envelope = (
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:wsaa="{WSAA_SOAP_NS}">'
        '<soapenv:Header/>'
        '<soapenv:Body>'
        '<wsaa:loginCms>'
        f'<wsaa:in0>{escape(cms_b64)}</wsaa:in0>'
        '</wsaa:loginCms>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )
    root, raw_xml = _soap_post(cfg.wsaa_url, envelope, cfg.timeout_secs)
    ret_node = _find_first(root, 'loginCmsReturn')
    if ret_node is None:
        raise ArcaRetryableError('WSAA sin loginCmsReturn', payload={'raw': raw_xml[:2000]})
    inner = (ret_node.text or '').strip()
    if not inner:
        raise ArcaRetryableError('WSAA loginCmsReturn vacio', payload={'raw': raw_xml[:2000]})

    try:
        ticket = ET.fromstring(inner)
    except ET.ParseError:
        ticket = _parse_soap_root(inner)

    token = _child_text(_find_first(ticket, 'credentials'), 'token')
    sign = _child_text(_find_first(ticket, 'credentials'), 'sign')
    expiration_time = _child_text(_find_first(ticket, 'header'), 'expirationTime')
    generation_time = _child_text(_find_first(ticket, 'header'), 'generationTime')
    if not token or not sign or not expiration_time:
        raise ArcaRetryableError('WSAA response incompleta', payload={'raw': inner[:2000]})

    return (
        {
            'token': token,
            'sign': sign,
            'expiration_time': expiration_time,
            'generation_time': generation_time,
        },
        raw_xml,
    )


def _ta_cache_key(cfg: ArcaRuntimeConfig) -> str:
    return f'arca:ta:{cfg.env}:{_clean_digits(cfg.cuit)}:{cfg.wsaa_service}'


def _is_ta_valid(value: dict[str, Any] | None, skew_secs: int) -> bool:
    if not isinstance(value, dict):
        return False
    exp = _parse_iso_dt(value.get('expiration_time'))
    if not exp:
        return False
    now = dt.datetime.now(dt.timezone.utc)
    return exp > (now + dt.timedelta(seconds=max(0, skew_secs)))


def wsaa_get_ta(cfg: ArcaRuntimeConfig, force_refresh: bool = False) -> dict[str, Any]:
    full_cfg = cfg.with_defaults()
    _validate_runtime_config(full_cfg)
    cache_key = _ta_cache_key(full_cfg)

    if not force_refresh:
        cached = cache.get(cache_key)
        if _is_ta_valid(cached, full_cfg.ta_cache_skew_secs):
            out = dict(cached)
            out['source'] = 'cache'
            return out

    tra_xml = _build_tra_xml(full_cfg.wsaa_service)
    cms_b64 = _sign_tra_cms_b64(tra_xml, full_cfg.cert_path, full_cfg.key_path)
    ta, raw_xml = _wsaa_login_cms(full_cfg, cms_b64)
    exp = _parse_iso_dt(ta.get('expiration_time'))
    now = dt.datetime.now(dt.timezone.utc)
    ttl = 60
    if exp:
        ttl = max(60, int((exp - now).total_seconds()) - max(0, full_cfg.ta_cache_skew_secs))
    cache_value = dict(ta)
    cache_value['acquired_at'] = now.isoformat(timespec='seconds')
    cache.set(cache_key, cache_value, ttl)

    out = dict(cache_value)
    out['source'] = 'fresh'
    out['raw_response'] = raw_xml[:4000]
    return out


def _wsfe_auth_block(auth: dict[str, Any]) -> str:
    token = escape(str(auth.get('token') or ''))
    sign = escape(str(auth.get('sign') or ''))
    cuit = escape(str(_clean_digits(auth.get('cuit') or '')))
    return (
        '<ar:Auth>'
        f'<ar:Token>{token}</ar:Token>'
        f'<ar:Sign>{sign}</ar:Sign>'
        f'<ar:Cuit>{cuit}</ar:Cuit>'
        '</ar:Auth>'
    )


def _wsfe_call(cfg: ArcaRuntimeConfig, operation_name: str, body_xml: str) -> tuple[ET.Element, str]:
    envelope = (
        f'<soap:Envelope xmlns:soap="{SOAP_ENV_NS}" xmlns:ar="{WSFE_SOAP_NS}">'
        '<soap:Header/>'
        f'<soap:Body>{body_xml}</soap:Body>'
        '</soap:Envelope>'
    )
    action = f'{WSFE_SOAP_NS}{operation_name}'
    return _soap_post(cfg.wsfe_url, envelope, cfg.timeout_secs, soap_action=action)


def wsfe_fedummy(cfg: ArcaRuntimeConfig) -> dict[str, Any]:
    full_cfg = cfg.with_defaults()
    _validate_runtime_config(full_cfg)
    body = '<ar:FEDummy/>'
    root, raw = _wsfe_call(full_cfg, 'FEDummy', body)
    result = _find_first(root, 'FEDummyResult')
    return {
        'appserver': _child_text(result, 'AppServer'),
        'dbserver': _child_text(result, 'DbServer'),
        'authserver': _child_text(result, 'AuthServer'),
        'raw_response': raw[:4000],
    }


def wsfe_comp_ultimo_autorizado(cfg: ArcaRuntimeConfig, auth: dict[str, Any], pto_vta: int, cbte_tipo: int) -> dict[str, Any]:
    full_cfg = cfg.with_defaults()
    _validate_runtime_config(full_cfg)
    payload_auth = dict(auth or {})
    payload_auth['cuit'] = _clean_digits(payload_auth.get('cuit') or full_cfg.cuit)
    body = (
        '<ar:FECompUltimoAutorizado>'
        f'{_wsfe_auth_block(payload_auth)}'
        f'<ar:PtoVta>{int(pto_vta)}</ar:PtoVta>'
        f'<ar:CbteTipo>{int(cbte_tipo)}</ar:CbteTipo>'
        '</ar:FECompUltimoAutorizado>'
    )
    root, raw = _wsfe_call(full_cfg, 'FECompUltimoAutorizado', body)
    result = _find_first(root, 'FECompUltimoAutorizadoResult')
    errors = _collect_messages(result)
    cbte_nro = _to_int(_child_text(result, 'CbteNro'), default=0) or 0
    return {
        'cbte_nro': cbte_nro,
        'errors': errors,
        'raw_response': raw[:4000],
    }


def wsfe_comp_consultar(cfg: ArcaRuntimeConfig, auth: dict[str, Any], pto_vta: int, cbte_tipo: int, cbte_nro: int) -> dict[str, Any]:
    full_cfg = cfg.with_defaults()
    _validate_runtime_config(full_cfg)
    payload_auth = dict(auth or {})
    payload_auth['cuit'] = _clean_digits(payload_auth.get('cuit') or full_cfg.cuit)
    body = (
        '<ar:FECompConsultar>'
        f'{_wsfe_auth_block(payload_auth)}'
        '<ar:FeCompConsReq>'
        f'<ar:CbteTipo>{int(cbte_tipo)}</ar:CbteTipo>'
        f'<ar:CbteNro>{int(cbte_nro)}</ar:CbteNro>'
        f'<ar:PtoVta>{int(pto_vta)}</ar:PtoVta>'
        '</ar:FeCompConsReq>'
        '</ar:FECompConsultar>'
    )
    root, raw = _wsfe_call(full_cfg, 'FECompConsultar', body)
    result = _find_first(root, 'FECompConsultarResult')
    errors = _collect_messages(result)
    result_get = _find_first(result, 'ResultGet')
    if result_get is None:
        return {
            'found': False,
            'errors': errors,
            'raw_response': raw[:4000],
        }
    cae = _child_text(result_get, 'CodAutorizacion', 'CAE')
    cae_due = _child_text(result_get, 'FchVto', 'CAEFchVto')
    resultado = _child_text(result_get, 'Resultado')
    out_cbte = _to_int(_child_text(result_get, 'CbteDesde', 'CbteHasta', 'CbteNro'), default=cbte_nro) or cbte_nro
    return {
        'found': True,
        'cbte_nro': out_cbte,
        'resultado': resultado,
        'cae': cae,
        'cae_due_date': cae_due,
        'errors': errors,
        'raw_response': raw[:4000],
    }


def _render_cbtes_asoc_xml(items: list[dict[str, Any]] | None) -> str:
    rows = items or []
    if not rows:
        return ''
    chunks = []
    for row in rows:
        tipo = _to_int(row.get('tipo') or row.get('Tipo'))
        pto = _to_int(row.get('pto_vta') or row.get('PtoVta'))
        nro = _to_int(row.get('nro') or row.get('Nro'))
        if not (tipo and pto is not None and nro):
            continue
        chunks.append(
            '<ar:CbteAsoc>'
            f'<ar:Tipo>{tipo}</ar:Tipo>'
            f'<ar:PtoVta>{pto}</ar:PtoVta>'
            f'<ar:Nro>{nro}</ar:Nro>'
            '</ar:CbteAsoc>'
        )
    if not chunks:
        return ''
    return f"<ar:CbtesAsoc>{''.join(chunks)}</ar:CbtesAsoc>"


def wsfe_cae_solicitar(cfg: ArcaRuntimeConfig, auth: dict[str, Any], request_data: dict[str, Any]) -> dict[str, Any]:
    full_cfg = cfg.with_defaults()
    _validate_runtime_config(full_cfg)
    payload_auth = dict(auth or {})
    payload_auth['cuit'] = _clean_digits(payload_auth.get('cuit') or full_cfg.cuit)

    pto_vta = int(request_data.get('pto_vta'))
    cbte_tipo = int(request_data.get('cbte_tipo'))
    cbte_nro = int(request_data.get('cbte_nro'))
    doc_tipo = int(request_data.get('doc_tipo'))
    doc_nro = int(request_data.get('doc_nro'))
    concepto = int(request_data.get('concepto') or 1)
    cbte_fch = str(request_data.get('cbte_fch') or '').strip()
    if not cbte_fch:
        cbte_fch = dt.date.today().strftime('%Y%m%d')

    imp_total = _fmt_decimal(request_data.get('imp_total') or '0', 2)
    imp_tot_conc = _fmt_decimal(request_data.get('imp_tot_conc') or '0', 2)
    imp_neto = _fmt_decimal(request_data.get('imp_neto') or imp_total, 2)
    imp_op_ex = _fmt_decimal(request_data.get('imp_op_ex') or '0', 2)
    imp_iva = _fmt_decimal(request_data.get('imp_iva') or '0', 2)
    imp_trib = _fmt_decimal(request_data.get('imp_trib') or '0', 2)
    mon_id = escape(str(request_data.get('mon_id') or 'PES'))
    mon_cotiz = _fmt_decimal(request_data.get('mon_cotiz') or '1', 6)
    cond_iva_receptor = _to_int(request_data.get('condicion_iva_receptor_id'))

    cbtes_asoc_xml = _render_cbtes_asoc_xml(request_data.get('cbtes_asoc'))
    cond_iva_xml = ''
    if cond_iva_receptor:
        cond_iva_xml = f'<ar:CondicionIVAReceptorId>{int(cond_iva_receptor)}</ar:CondicionIVAReceptorId>'

    body = (
        '<ar:FECAESolicitar>'
        f'{_wsfe_auth_block(payload_auth)}'
        '<ar:FeCAEReq>'
        '<ar:FeCabReq>'
        '<ar:CantReg>1</ar:CantReg>'
        f'<ar:PtoVta>{pto_vta}</ar:PtoVta>'
        f'<ar:CbteTipo>{cbte_tipo}</ar:CbteTipo>'
        '</ar:FeCabReq>'
        '<ar:FeDetReq>'
        '<ar:FECAEDetRequest>'
        f'<ar:Concepto>{concepto}</ar:Concepto>'
        f'<ar:DocTipo>{doc_tipo}</ar:DocTipo>'
        f'<ar:DocNro>{doc_nro}</ar:DocNro>'
        f'<ar:CbteDesde>{cbte_nro}</ar:CbteDesde>'
        f'<ar:CbteHasta>{cbte_nro}</ar:CbteHasta>'
        f'<ar:CbteFch>{escape(cbte_fch)}</ar:CbteFch>'
        f'<ar:ImpTotal>{imp_total}</ar:ImpTotal>'
        f'<ar:ImpTotConc>{imp_tot_conc}</ar:ImpTotConc>'
        f'<ar:ImpNeto>{imp_neto}</ar:ImpNeto>'
        f'<ar:ImpOpEx>{imp_op_ex}</ar:ImpOpEx>'
        f'<ar:ImpIVA>{imp_iva}</ar:ImpIVA>'
        f'<ar:ImpTrib>{imp_trib}</ar:ImpTrib>'
        f'<ar:MonId>{mon_id}</ar:MonId>'
        f'<ar:MonCotiz>{mon_cotiz}</ar:MonCotiz>'
        f'{cbtes_asoc_xml}'
        f'{cond_iva_xml}'
        '</ar:FECAEDetRequest>'
        '</ar:FeDetReq>'
        '</ar:FeCAEReq>'
        '</ar:FECAESolicitar>'
    )

    root, raw = _wsfe_call(full_cfg, 'FECAESolicitar', body)
    result = _find_first(root, 'FECAESolicitarResult')
    messages = _collect_messages(result)
    detail = _find_first(result, 'FECAEDetResponse')
    detail_messages = _collect_messages(detail)
    resultado = _child_text(detail, 'Resultado') or _child_text(result, 'Resultado')
    cae = _child_text(detail, 'CAE') or _child_text(detail, 'CodAutorizacion')
    cae_due = _child_text(detail, 'CAEFchVto', 'FchVto')
    out_cbte = _to_int(_child_text(detail, 'CbteDesde', 'CbteHasta'), default=cbte_nro) or cbte_nro

    return {
        'resultado': resultado,
        'cbte_nro': out_cbte,
        'cae': cae,
        'cae_due_date': cae_due,
        'messages': messages + detail_messages,
        'raw_response': raw[:4000],
    }
