"""
Drift and Divergence Detection Engine.

Evaluates discrepancies between forecast models and ground-truth observations,
computes scalar and vector innovations, queries regional memory, and generates
calibrated, debounced alerts for the VARUNA alert stream.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .config import classify_sub_basin, settings
from .memory import RegionalDriftMemory
from .schemas import (
    Alert,
    AlertSeverity,
    FusedPoint,
    FusedResponse,
    ModelGridPoint,
    ModelSnapshot,
    ObservationPoint,
    ObservationSnapshot,
)


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class DriftDetector:
    """
    Evaluates ocean observations against model forecasts and determines
    divergence alerts with temporal debouncing.
    """

    def __init__(self, memory: RegionalDriftMemory | None = None) -> None:
        self.memory = memory or RegionalDriftMemory()
        # Track last alert timestamp per (sub_basin, variable) to prevent alert flooding
        self._last_alert_time: Dict[Tuple[str, str], datetime] = {}

    def _should_suppress_alert(self, sub_basin: str, variable: str, now: datetime) -> bool:
        key = (sub_basin, variable)
        if key in self._last_alert_time:
            delta = (now - self._last_alert_time[key]).total_seconds()
            if delta < settings.alert_debounce_seconds:
                return True
        return False

    def _record_alert_fired(self, sub_basin: str, variable: str, now: datetime) -> None:
        self._last_alert_time[(sub_basin, variable)] = now

    def evaluate_fused_response(self, fused: FusedResponse) -> list[Alert]:
        """
        Evaluate drift directly from Person 1's /fused output.
        
        FusedPoint contains both the baseline field and the correction delta
        derived from sensor fusion (e.g. correction_sst_c).
        """
        alerts: list[Alert] = []
        now = fused.time or datetime.now(timezone.utc)

        for pt in fused.points:
            sub_basin = classify_sub_basin(pt.lat, pt.lon)

            # 1. Evaluate SST Divergence
            if pt.sst_c is not None and pt.correction_sst_c is not None and abs(pt.correction_sst_c) > 0.01:
                model_sst = pt.sst_c
                observed_sst = model_sst + pt.correction_sst_c
                delta_sst = pt.correction_sst_c
                abs_delta = abs(delta_sst)
                surprise = abs_delta / settings.sigma_sst_c

                self.memory.record_update(sub_basin, "sst", delta_sst, surprise, now)

                if abs_delta >= settings.sst_info_delta and not self._should_suppress_alert(sub_basin, "sst", now):
                    if abs_delta >= settings.sst_critical_delta:
                        severity = AlertSeverity.critical
                        qualifier = "CRITICAL (Possible Marine Heatwave / Upwelling Disruption)"
                    elif abs_delta >= settings.sst_warning_delta:
                        severity = AlertSeverity.warning
                        qualifier = "WARNING (Substantial Thermal Divergence)"
                    else:
                        severity = AlertSeverity.info
                        qualifier = "INFO (Localized Forecast Drift)"

                    msg = (
                        f"Drift detected in {sub_basin.replace('_', ' ').title()} "
                        f"({pt.lat:.2f}°N, {pt.lon:.2f}°E): SST diverging {delta_sst:+.2f}°C from forecast "
                        f"(Model: {model_sst:.2f}°C, Obs: {observed_sst:.2f}°C). Severity: {qualifier}"
                    )

                    alert = Alert(
                        id=f"alt-{sub_basin}-sst-{uuid.uuid4().hex[:8]}",
                        region=fused.region,
                        variable="sst",
                        severity=severity,
                        message=msg,
                        timestamp=now,
                        lat=pt.lat,
                        lon=pt.lon,
                        model_value=round(model_sst, 2),
                        observed_value=round(observed_sst, 2),
                        divergence=round(delta_sst, 2),
                    )
                    alerts.append(alert)
                    self._record_alert_fired(sub_basin, "sst", now)

            # 2. Evaluate Current Vector Divergence
            if (
                pt.current_u_ms is not None
                and pt.current_v_ms is not None
                and (pt.correction_current_u_ms is not None or pt.correction_current_v_ms is not None)
            ):
                corr_u = pt.correction_current_u_ms or 0.0
                corr_v = pt.correction_current_v_ms or 0.0
                if abs(corr_u) > 0.01 or abs(corr_v) > 0.01:
                    u_mod, v_mod = pt.current_u_ms, pt.current_v_ms
                    u_obs, v_obs = u_mod + corr_u, v_mod + corr_v

                    spd_mod = math.hypot(u_mod, v_mod)
                    spd_obs = math.hypot(u_obs, v_obs)
                    delta_spd = spd_obs - spd_mod
                    abs_delta_spd = abs(delta_spd)

                    # Directional angle deviation
                    dot = u_mod * u_obs + v_mod * v_obs
                    denom = (spd_mod * spd_obs) + 1e-6
                    cos_theta = max(-1.0, min(1.0, dot / denom))
                    dir_diff_deg = math.degrees(math.acos(cos_theta))

                    surprise = abs_delta_spd / settings.sigma_current_ms
                    self.memory.record_update(sub_basin, "currents", delta_spd, surprise, now)

                    if (
                        abs_delta_spd >= settings.current_info_delta or dir_diff_deg >= settings.current_dir_warning_deg
                    ) and not self._should_suppress_alert(sub_basin, "currents", now):
                        if abs_delta_spd >= settings.current_critical_delta or dir_diff_deg >= settings.current_dir_critical_deg:
                            severity = AlertSeverity.critical
                            qualifier = "CRITICAL (Severe Velocity Disparity / Vector Reversal)"
                        elif abs_delta_spd >= settings.current_warning_delta or dir_diff_deg >= settings.current_dir_warning_deg:
                            severity = AlertSeverity.warning
                            qualifier = "WARNING (Current Shear / Boundary Offset)"
                        else:
                            severity = AlertSeverity.info
                            qualifier = "INFO (Minor Current Vector Drift)"

                        msg = (
                            f"Current drift in {sub_basin.replace('_', ' ').title()} "
                            f"({pt.lat:.2f}°N, {pt.lon:.2f}°E): speed delta {delta_spd:+.2f} m/s "
                            f"(Model: {spd_mod:.2f} m/s, Obs: {spd_obs:.2f} m/s), shear {dir_diff_deg:.1f}°. "
                            f"Severity: {qualifier}"
                        )

                        alert = Alert(
                            id=f"alt-{sub_basin}-curr-{uuid.uuid4().hex[:8]}",
                            region=fused.region,
                            variable="currents",
                            severity=severity,
                            message=msg,
                            timestamp=now,
                            lat=pt.lat,
                            lon=pt.lon,
                            model_value=round(spd_mod, 2),
                            observed_value=round(spd_obs, 2),
                            divergence=round(delta_spd, 2),
                        )
                        alerts.append(alert)
                        self._record_alert_fired(sub_basin, "currents", now)

            # 3. Evaluate Wave Height Divergence
            if (
                pt.wave_height_m is not None
                and pt.correction_wave_height_m is not None
                and abs(pt.correction_wave_height_m) > 0.05
            ):
                mod_wave = pt.wave_height_m
                obs_wave = mod_wave + pt.correction_wave_height_m
                delta_wave = pt.correction_wave_height_m
                abs_delta_wave = abs(delta_wave)
                surprise = abs_delta_wave / settings.sigma_wave_height_m

                self.memory.record_update(sub_basin, "wave_height", delta_wave, surprise, now)

                if abs_delta_wave >= settings.wave_info_delta and not self._should_suppress_alert(sub_basin, "wave_height", now):
                    if abs_delta_wave >= settings.wave_critical_delta:
                        severity = AlertSeverity.critical
                        qualifier = "CRITICAL (Severe Sea State Underprediction)"
                    elif abs_delta_wave >= settings.wave_warning_delta:
                        severity = AlertSeverity.warning
                        qualifier = "WARNING (Moderate Wave Drift)"
                    else:
                        severity = AlertSeverity.info
                        qualifier = "INFO (Minor Sea State Deviation)"

                    msg = (
                        f"Wave height drift in {sub_basin.replace('_', ' ').title()} "
                        f"({pt.lat:.2f}°N, {pt.lon:.2f}°E): wave delta {delta_wave:+.2f} m "
                        f"(Model: {mod_wave:.2f} m, Obs: {obs_wave:.2f} m). Severity: {qualifier}"
                    )

                    alert = Alert(
                        id=f"alt-{sub_basin}-wave-{uuid.uuid4().hex[:8]}",
                        region=fused.region,
                        variable="wave_height",
                        severity=severity,
                        message=msg,
                        timestamp=now,
                        lat=pt.lat,
                        lon=pt.lon,
                        model_value=round(mod_wave, 2),
                        observed_value=round(obs_wave, 2),
                        divergence=round(delta_wave, 2),
                    )
                    alerts.append(alert)
                    self._record_alert_fired(sub_basin, "wave_height", now)

        return alerts

    def evaluate_model_and_observations(
        self,
        model: ModelSnapshot,
        observations: ObservationSnapshot,
        max_match_distance_km: float = 120.0,
    ) -> list[Alert]:
        """
        Evaluate drift directly from raw ModelSnapshot and ObservationSnapshot
        (e.g., when running independently before Graph Fusion).
        Matches each observation to nearest model grid point.
        """
        alerts: list[Alert] = []
        now = observations.time or datetime.now(timezone.utc)

        if not model.points or not observations.points:
            return alerts

        for obs in observations.points:
            # Find nearest model grid point
            best_pt: ModelGridPoint | None = None
            min_dist = float("inf")

            for m_pt in model.points:
                dist = _haversine_distance_km(obs.lat, obs.lon, m_pt.lat, m_pt.lon)
                if dist < min_dist:
                    min_dist = dist
                    best_pt = m_pt

            if not best_pt or min_dist > max_match_distance_km:
                continue

            sub_basin = classify_sub_basin(obs.lat, obs.lon)

            # Evaluate SST
            if obs.sst_c is not None and best_pt.sst_c is not None:
                delta_sst = obs.sst_c - best_pt.sst_c
                abs_delta = abs(delta_sst)
                surprise = abs_delta / settings.sigma_sst_c

                self.memory.record_update(sub_basin, "sst", delta_sst, surprise, now)

                if abs_delta >= settings.sst_info_delta and not self._should_suppress_alert(sub_basin, "sst", now):
                    if abs_delta >= settings.sst_critical_delta:
                        severity = AlertSeverity.critical
                        qualifier = "CRITICAL (Marine Heatwave Signal)"
                    elif abs_delta >= settings.sst_warning_delta:
                        severity = AlertSeverity.warning
                        qualifier = "WARNING (Moderate SST Divergence)"
                    else:
                        severity = AlertSeverity.info
                        qualifier = "INFO (Localized Model Bias)"

                    msg = (
                        f"Drift detected in {sub_basin.replace('_', ' ').title()} "
                        f"via {obs.sensor_type.value.upper()} ({obs.sensor_id}) at {obs.lat:.2f}°N, {obs.lon:.2f}°E: "
                        f"SST diverging {delta_sst:+.2f}°C from model forecast (Model: {best_pt.sst_c:.2f}°C, "
                        f"Obs: {obs.sst_c:.2f}°C). Severity: {qualifier}"
                    )

                    alert = Alert(
                        id=f"alt-{sub_basin}-sst-{uuid.uuid4().hex[:8]}",
                        region=model.region,
                        variable="sst",
                        severity=severity,
                        message=msg,
                        timestamp=now,
                        lat=obs.lat,
                        lon=obs.lon,
                        model_value=round(best_pt.sst_c, 2),
                        observed_value=round(obs.sst_c, 2),
                        divergence=round(delta_sst, 2),
                    )
                    alerts.append(alert)
                    self._record_alert_fired(sub_basin, "sst", now)

            # Evaluate Currents
            if (
                obs.current_u_ms is not None
                and obs.current_v_ms is not None
                and best_pt.current_u_ms is not None
                and best_pt.current_v_ms is not None
            ):
                spd_obs = math.hypot(obs.current_u_ms, obs.current_v_ms)
                spd_mod = math.hypot(best_pt.current_u_ms, best_pt.current_v_ms)
                delta_spd = spd_obs - spd_mod
                abs_delta_spd = abs(delta_spd)
                surprise = abs_delta_spd / settings.sigma_current_ms

                self.memory.record_update(sub_basin, "currents", delta_spd, surprise, now)

                if abs_delta_spd >= settings.current_info_delta and not self._should_suppress_alert(sub_basin, "currents", now):
                    severity = AlertSeverity.critical if abs_delta_spd >= settings.current_critical_delta else (
                        AlertSeverity.warning if abs_delta_spd >= settings.current_warning_delta else AlertSeverity.info
                    )
                    msg = (
                        f"Current drift in {sub_basin.replace('_', ' ').title()} "
                        f"via {obs.sensor_type.value.upper()} ({obs.sensor_id}): speed delta {delta_spd:+.2f} m/s "
                        f"(Model: {spd_mod:.2f} m/s, Obs: {spd_obs:.2f} m/s). Severity: {severity.value.upper()}"
                    )
                    alert = Alert(
                        id=f"alt-{sub_basin}-curr-{uuid.uuid4().hex[:8]}",
                        region=model.region,
                        variable="currents",
                        severity=severity,
                        message=msg,
                        timestamp=now,
                        lat=obs.lat,
                        lon=obs.lon,
                        model_value=round(spd_mod, 2),
                        observed_value=round(spd_obs, 2),
                        divergence=round(delta_spd, 2),
                    )
                    alerts.append(alert)
                    self._record_alert_fired(sub_basin, "currents", now)

        return alerts

    def clear_debounce_cache(self) -> None:
        """Reset debounce timer to allow immediate alert triggering."""
        self._last_alert_time.clear()
