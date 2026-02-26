from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any


RESULT_OPTIONS = [
    {"value": "ok", "label": "OK"},
    {"value": "observado", "label": "Observado"},
    {"value": "no_ok", "label": "No OK"},
    {"value": "na", "label": "N/A"},
]

GLOBAL_RESULT_OPTIONS = [
    {"value": "pendiente", "label": "Pendiente"},
    {"value": "apto", "label": "Apto"},
    {"value": "apto_condicional", "label": "Apto condicional"},
    {"value": "no_apto", "label": "No apto"},
]


BASE_TEMPLATES: dict[str, dict[str, Any]] = {
    "aspirador": {
        "type_key": "aspirador",
        "template_key": "aspirador_v1",
        "template_version": "1.0.0",
        "display_name": "Aspirador",
        "references": [
            {
                "ref_id": "REF-01",
                "tipo": "norma",
                "titulo": "ISO 10079-1:2022",
                "edicion": "2022",
                "anio": 2022,
                "organismo_o_fabricante": "ISO",
                "url": "https://www.iso.org/standard/81532.html",
                "aplica_a": "Aspiradores médicos eléctricos",
            },
        ],
        "sections": [
            {
                "id": "seguridad",
                "title": "Seguridad y verificación inicial",
                "items": [
                    {
                        "key": "asp_inspeccion_visual",
                        "label": "Inspección visual y estado general",
                        "target": "Sin daño estructural, cables y conexiones seguros",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "asp_alarma_obstruccion",
                        "label": "Alarma/indicador de obstrucción",
                        "target": "Activa según diseño del fabricante",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
            {
                "id": "performance",
                "title": "Rendimiento",
                "items": [
                    {
                        "key": "asp_vacio_max",
                        "label": "Vacío máximo",
                        "target": "Dentro de especificación del fabricante",
                        "unit": "mmHg",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "asp_caudal_libre",
                        "label": "Caudal libre",
                        "target": "Dentro de especificación del fabricante",
                        "unit": "L/min",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
        ],
    },
    "concentrador_oxigeno": {
        "type_key": "concentrador_oxigeno",
        "template_key": "concentrador_oxigeno_v1",
        "template_version": "1.0.0",
        "display_name": "Concentrador de oxígeno",
        "references": [
            {
                "ref_id": "REF-01",
                "tipo": "norma",
                "titulo": "ISO 80601-2-69:2020",
                "edicion": "2020",
                "anio": 2020,
                "organismo_o_fabricante": "ISO",
                "url": "https://www.iso.org/standard/75946.html",
                "aplica_a": "Concentradores de oxígeno para uso médico",
            },
        ],
        "sections": [
            {
                "id": "salida_o2",
                "title": "Salida de oxígeno",
                "items": [
                    {
                        "key": "co2_concentracion",
                        "label": "Concentración de O2",
                        "target": "Dentro de especificación del fabricante por flujo",
                        "unit": "%",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "co2_flujo_setpoint",
                        "label": "Flujo real vs setpoint",
                        "target": "Desviación dentro de tolerancia del fabricante",
                        "unit": "L/min",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
            {
                "id": "alarmas",
                "title": "Alarmas y seguridad",
                "items": [
                    {
                        "key": "co2_alarma_baja_concentracion",
                        "label": "Alarma baja concentración de O2",
                        "target": "Activa según especificación",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "co2_alarma_falla_energia",
                        "label": "Alarma por falla de energía",
                        "target": "Activa y audible/visible según especificación",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
        ],
    },
    "concentrador_portatil_oxigeno": {
        "type_key": "concentrador_portatil_oxigeno",
        "template_key": "concentrador_portatil_oxigeno_v1",
        "template_version": "1.0.0",
        "display_name": "Concentrador portátil de oxígeno",
        "references": [
            {
                "ref_id": "REF-01",
                "tipo": "norma",
                "titulo": "ISO 80601-2-69:2020",
                "edicion": "2020",
                "anio": 2020,
                "organismo_o_fabricante": "ISO",
                "url": "https://www.iso.org/standard/75946.html",
                "aplica_a": "Concentradores de oxígeno para uso médico",
            },
        ],
        "sections": [
            {
                "id": "modo_pulso",
                "title": "Modo pulso y entrega de O2",
                "items": [
                    {
                        "key": "cpo2_deteccion_inspiracion",
                        "label": "Detección de inspiración",
                        "target": "Detecta ciclo inspiratorio y entrega bolo",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "cpo2_entrega_bolo",
                        "label": "Entrega de bolo por nivel",
                        "target": "Dentro de especificación del fabricante",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
            {
                "id": "energia",
                "title": "Energía y alarmas",
                "items": [
                    {
                        "key": "cpo2_bateria_autonomia",
                        "label": "Autonomía de batería",
                        "target": "Dentro de especificación del fabricante",
                        "unit": "min",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "cpo2_alarmas",
                        "label": "Alarmas (batería baja / fallo)",
                        "target": "Operativas y audibles/visibles",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
        ],
    },
    "respirador": {
        "type_key": "respirador",
        "template_key": "respirador_v1",
        "template_version": "1.0.0",
        "display_name": "Respirador",
        "references": [
            {
                "ref_id": "REF-01",
                "tipo": "norma",
                "titulo": "ISO 80601-2-12:2020",
                "edicion": "2020",
                "anio": 2020,
                "organismo_o_fabricante": "ISO",
                "url": "https://www.iso.org/cms/render/live/en/sites/isoorg/contents/data/standard/07/20/72069.html",
                "aplica_a": "Ventiladores de cuidados críticos",
            },
        ],
        "sections": [
            {
                "id": "ventilacion",
                "title": "Variables ventilatorias",
                "items": [
                    {
                        "key": "resp_presion_via_aerea",
                        "label": "Presión en vía aérea (PIP/IPAP/EPAP/PEEP)",
                        "target": "Dentro de tolerancia del fabricante",
                        "unit": "cmH2O",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "resp_volumen_tidal",
                        "label": "Volumen tidal entregado",
                        "target": "Dentro de tolerancia del fabricante",
                        "unit": "mL",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
            {
                "id": "alarmas",
                "title": "Alarmas de seguridad",
                "items": [
                    {
                        "key": "resp_alarma_apnea",
                        "label": "Alarma de apnea",
                        "target": "Activa conforme configuración",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "resp_alarma_alta_presion",
                        "label": "Alarma de alta presión",
                        "target": "Activa conforme umbral configurado",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
        ],
    },
    "cpap_autocpap": {
        "type_key": "cpap_autocpap",
        "template_key": "cpap_autocpap_v1",
        "template_version": "1.0.0",
        "display_name": "CPAP / AutoCPAP",
        "references": [
            {
                "ref_id": "REF-01",
                "tipo": "norma",
                "titulo": "ISO 80601-2-70:2025",
                "edicion": "2025",
                "anio": 2025,
                "organismo_o_fabricante": "ISO",
                "url": "https://www.iso.org/standard/87160.html",
                "aplica_a": "Equipos de terapia de apnea del sueño",
            },
        ],
        "sections": [
            {
                "id": "presion",
                "title": "Presión terapéutica",
                "items": [
                    {
                        "key": "cpap_presion_setpoint",
                        "label": "Presión real vs setpoint",
                        "target": "Dentro de tolerancia del fabricante",
                        "unit": "cmH2O",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "cpap_rampa",
                        "label": "Función rampa",
                        "target": "Transición progresiva según configuración",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
            {
                "id": "eventos",
                "title": "Algoritmo y compensaciones",
                "items": [
                    {
                        "key": "cpap_compensacion_fuga",
                        "label": "Compensación de fuga",
                        "target": "Respuesta acorde al diseño del fabricante",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "cpap_respuesta_auto",
                        "label": "Respuesta en modo Auto",
                        "target": "Ajuste de presión según evento detectado",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
        ],
    },
    "bpap": {
        "type_key": "bpap",
        "template_key": "bpap_v1",
        "template_version": "1.0.0",
        "display_name": "BPAP",
        "references": [
            {
                "ref_id": "REF-01",
                "tipo": "norma",
                "titulo": "ISO 80601-2-80:2024",
                "edicion": "2024",
                "anio": 2024,
                "organismo_o_fabricante": "ISO",
                "url": "https://www.iso.org/standard/83466.html",
                "aplica_a": "Equipos de soporte ventilatorio para insuficiencia respiratoria",
            },
        ],
        "sections": [
            {
                "id": "bilevel",
                "title": "Parámetros bi-nivel",
                "items": [
                    {
                        "key": "bpap_ipap_epap",
                        "label": "IPAP/EPAP reales vs configuradas",
                        "target": "Dentro de tolerancia del fabricante",
                        "unit": "cmH2O",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "bpap_ps",
                        "label": "Soporte de presión (PS)",
                        "target": "Consistente con configuración",
                        "unit": "cmH2O",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
            {
                "id": "temporizacion",
                "title": "Trigger/cycle y respaldo",
                "items": [
                    {
                        "key": "bpap_trigger_cycle",
                        "label": "Sensibilidad trigger y cycle",
                        "target": "Respuesta estable y sin auto-disparo",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "bpap_backup_rate",
                        "label": "Frecuencia de respaldo",
                        "target": "Dentro de tolerancia del fabricante",
                        "unit": "rpm",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
        ],
    },
    "calentador_humidificador": {
        "type_key": "calentador_humidificador",
        "template_key": "calentador_humidificador_v1",
        "template_version": "1.0.0",
        "display_name": "Calentador humidificador",
        "references": [
            {
                "ref_id": "REF-01",
                "tipo": "norma",
                "titulo": "ISO 80601-2-74:2021",
                "edicion": "2021",
                "anio": 2021,
                "organismo_o_fabricante": "ISO",
                "url": "https://www.iso.org/standard/81613.html",
                "aplica_a": "Equipos de humidificación respiratoria",
            }
        ],
        "sections": [
            {
                "id": "termico",
                "title": "Control térmico",
                "items": [
                    {
                        "key": "hum_temp_salida",
                        "label": "Temperatura de salida",
                        "target": "Dentro de rango configurable y tolerancia del fabricante",
                        "unit": "C",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "hum_temp_placa",
                        "label": "Temperatura de placa/calefactor",
                        "target": "Estable según setpoint",
                        "unit": "C",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
            {
                "id": "alarmas",
                "title": "Alarmas y protecciones",
                "items": [
                    {
                        "key": "hum_alarma_sobretemp",
                        "label": "Alarma de sobretemperatura",
                        "target": "Activa según diseño del fabricante",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                    {
                        "key": "hum_alarma_falta_agua",
                        "label": "Alarma de nivel/cámara",
                        "target": "Activa según diseño del fabricante",
                        "unit": "",
                        "ref_ids": ["REF-01"],
                    },
                ],
            },
        ],
    },
}


TYPE_ALIASES: dict[str, list[str]] = {
    "aspirador": [
        "aspirador",
        "aspirador quirúrgico",
        "bomba de aspiración",
        "suctor",
    ],
    "concentrador_oxigeno": [
        "concentrador de oxígeno",
        "concentrador oxígeno",
        "concentrador fijo",
    ],
    "concentrador_portatil_oxigeno": [
        "concentrador portátil de oxígeno",
        "concentrador portátil",
        "concentrador portable",
        "poc",
    ],
    "respirador": [
        "respirador",
        "ventilador",
        "ventilador mecánico",
    ],
    "cpap_autocpap": [
        "cpap",
        "autocpap",
        "auto cpap",
        "cpap/autocpap",
    ],
    "bpap": [
        "bpap",
        "bi-level",
        "bilevel",
        "bipap",
    ],
    "calentador_humidificador": [
        "calentador humidificador",
        "humidificador",
        "humidificador calentado",
    ],
}


MODEL_OVERRIDES: list[dict[str, Any]] = []


def _norm(value: str) -> str:
    s = (value or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s/+-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def resolve_type_key(tipo_equipo: str) -> str:
    raw = _norm(tipo_equipo)
    if not raw:
        return ""
    # Prefer exact alias match first.
    for key, aliases in TYPE_ALIASES.items():
        for alias in aliases:
            if raw == _norm(alias):
                return key
    # Then fallback to "contains" matching, longest aliases first.
    contains_candidates: list[tuple[int, str, str]] = []
    for key, aliases in TYPE_ALIASES.items():
        for alias in aliases:
            a = _norm(alias)
            if not a:
                continue
            if a in raw:
                contains_candidates.append((len(a), key, a))
    if contains_candidates:
        contains_candidates.sort(reverse=True)
        return contains_candidates[0][1]
    return ""


def _add_reference(protocol: dict[str, Any], ref: dict[str, Any]) -> None:
    ref_id = (ref or {}).get("ref_id")
    if not ref_id:
        return
    refs = protocol.setdefault("references", [])
    exists = any((r.get("ref_id") == ref_id) for r in refs)
    if not exists:
        refs.append(copy.deepcopy(ref))


def _append_ref_to_all_items(protocol: dict[str, Any], ref_id: str) -> None:
    if not ref_id:
        return
    for section in protocol.get("sections", []) or []:
        for item in section.get("items", []) or []:
            refs = item.setdefault("ref_ids", [])
            if ref_id not in refs:
                refs.append(ref_id)


def _append_item_refs(protocol: dict[str, Any], item_ref_ids: dict[str, list[str]]) -> None:
    if not item_ref_ids:
        return
    for section in protocol.get("sections", []) or []:
        for item in section.get("items", []) or []:
            key = item.get("key")
            if not key:
                continue
            extra = item_ref_ids.get(key) or []
            refs = item.setdefault("ref_ids", [])
            for ref_id in extra:
                if ref_id and ref_id not in refs:
                    refs.append(ref_id)


def _match_override(override: dict[str, Any], marca: str, modelo: str) -> bool:
    match = override.get("match") or {}
    marca_contains = _norm(match.get("marca_contains") or "")
    modelo_contains = _norm(match.get("modelo_contains") or "")
    marca_n = _norm(marca)
    modelo_n = _norm(modelo)
    if marca_contains and marca_contains not in marca_n:
        return False
    if modelo_contains and modelo_contains not in modelo_n:
        return False
    return True


def _apply_overrides(protocol: dict[str, Any], marca: str, modelo: str) -> None:
    type_key = protocol.get("type_key")
    applied = []
    for override in MODEL_OVERRIDES:
        if override.get("type_key") != type_key:
            continue
        if not _match_override(override, marca, modelo):
            continue
        for ref in override.get("references") or []:
            _add_reference(protocol, ref)
        _append_ref_to_all_items(protocol, (override.get("append_ref_to_all_items") or "").strip())
        _append_item_refs(protocol, override.get("item_ref_ids") or {})
        applied.append(override.get("name"))
    protocol["applied_overrides"] = [x for x in applied if x]


def get_protocol_by_type_key(type_key: str, marca: str = "", modelo: str = "") -> dict[str, Any] | None:
    base = BASE_TEMPLATES.get(type_key)
    if not base:
        return None
    protocol = copy.deepcopy(base)
    _apply_overrides(protocol, marca=marca, modelo=modelo)
    protocol["result_options"] = copy.deepcopy(RESULT_OPTIONS)
    protocol["global_result_options"] = copy.deepcopy(GLOBAL_RESULT_OPTIONS)
    return protocol


def get_protocol_by_template_key(template_key: str, marca: str = "", modelo: str = "") -> dict[str, Any] | None:
    needle = (template_key or "").strip().lower()
    if not needle:
        return None
    for key, tpl in BASE_TEMPLATES.items():
        if (tpl.get("template_key") or "").strip().lower() == needle:
            return get_protocol_by_type_key(key, marca=marca, modelo=modelo)
    return None


def resolve_protocol_for_equipo(tipo_equipo: str, marca: str = "", modelo: str = "") -> dict[str, Any] | None:
    type_key = resolve_type_key(tipo_equipo)
    if not type_key:
        return None
    return get_protocol_by_type_key(type_key, marca=marca, modelo=modelo)


def flatten_items(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for section in (protocol or {}).get("sections", []) or []:
        for item in section.get("items", []) or []:
            out.append(item)
    return out


def default_values_for_protocol(protocol: dict[str, Any]) -> dict[str, dict[str, str]]:
    defaults: dict[str, dict[str, str]] = {}
    for item in flatten_items(protocol):
        key = (item.get("key") or "").strip()
        if not key:
            continue
        defaults[key] = {
            "measured": "",
            "result": "",
            "observaciones": "",
        }
    return defaults


