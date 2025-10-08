"""Legacy shim module.

All views and helpers were migrated to domain modules under
`api/service/views/`. This module remains as a minimal compatibility
layer during the transition and should not contain active logic.
"""

# Export commonly used helpers for potential direct imports from
# `service.views.legacy` (compat only).
from .helpers import (  # noqa: F401
    # DB
    q, exec_void, exec_returning, last_insert_id, money, _set_audit_user,
    # Text/encoding
    _fix_text_value, _fix_row, _norm_txt,
    # Motivo ENUM
    _get_motivo_enum_values, _get_motivo_enum_values_raw, _map_motivo_to_db_label, _fetchall_dicts,
    # Roles/auth
    require_roles, require_jefe, _rol, _is, _in,
    # Misc
    ensure_default_locations, _frontend_url, _load_email_footer_text, _email_append_footer_text, _email_append_footer_html, os_label,
    # Business-hours
    WORKDAY_START_HOUR, WORKDAY_END_HOUR, WORKDAYS,
    _tz_aware, _clamp_to_work_window_forward, _clamp_to_work_window_backward,
    _holidays_country, _parse_extra_holidays_env, _fetch_nager_year, _get_year_holidays,
    _holidays_between, business_minutes_between,
)

__all__ = []

