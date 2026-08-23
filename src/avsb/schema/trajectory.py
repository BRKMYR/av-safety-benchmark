"""Trajectory log format: the system-agnostic evaluation contract (spec 5.2).

One JSONL file per (scenario, planner) run:
    runs/{suite}/{planner}/{scenario_id}.jsonl

Line 1 is a header record. Each subsequent line is one actor-state record
(ego first at every step, then actors in header.actor_ids order). The metrics
layer consumes only this format, so any external stack that emits conforming
JSONL can be scored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from avsb.schema.io import round_floats


class TrajectoryHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: Literal["header"] = "header"
    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str
    planner: str
    dt_s: float = 0.1
    n_steps: int = Field(ge=1)
    actor_ids: list[str]
    created: str  # ISO-8601 UTC


class TrajectoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: Literal["state"] = "state"
    t: float
    actor_id: str
    x: float
    y: float
    yaw: float
    vx: float
    vy: float
    accel_cmd: float | None = None  # ego only; scripted actors log null
    steer_cmd: float | None = None  # ego only; scripted actors log null


@dataclass
class TrajectoryLog:
    """In-memory representation of one JSONL trajectory log."""

    header: TrajectoryHeader
    # Per-actor numpy state array of shape (n_steps, 5): columns (t, x, y, vx, vy).
    _states: dict[str, np.ndarray]
    _yaw: dict[str, np.ndarray]
    _accel_cmd: np.ndarray | None
    _steer_cmd: np.ndarray | None

    @property
    def actor_ids(self) -> list[str]:
        return list(self.header.actor_ids)

    @property
    def dt_s(self) -> float:
        return float(self.header.dt_s)

    @property
    def n_steps(self) -> int:
        return int(self.header.n_steps)

    def states(self, actor_id: str) -> np.ndarray:
        """Return (n_steps, 5) array: columns (t, x, y, vx, vy)."""
        return self._states[actor_id]

    def yaw(self, actor_id: str) -> np.ndarray:
        return self._yaw[actor_id]

    def accel_cmd(self) -> np.ndarray:
        """Ego post-clamp acceleration command per step, or zeros if absent."""
        if self._accel_cmd is None:
            return np.zeros(self.n_steps, dtype=float)
        return self._accel_cmd

    def steer_cmd(self) -> np.ndarray:
        if self._steer_cmd is None:
            return np.zeros(self.n_steps, dtype=float)
        return self._steer_cmd

    # ---- I/O ----

    @classmethod
    def read(cls, path: str | Path) -> "TrajectoryLog":
        p = Path(path)
        with p.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if not lines:
            raise ValueError(f"empty trajectory file: {p}")
        header = TrajectoryHeader.model_validate_json(lines[0])
        n = header.n_steps
        actor_ids = list(header.actor_ids)
        states: dict[str, np.ndarray] = {
            aid: np.zeros((n, 5), dtype=float) for aid in actor_ids
        }
        yaws: dict[str, np.ndarray] = {
            aid: np.zeros(n, dtype=float) for aid in actor_ids
        }
        # Track write cursors per actor.
        idx: dict[str, int] = {aid: 0 for aid in actor_ids}
        ego_accel = np.zeros(n, dtype=float)
        ego_steer = np.zeros(n, dtype=float)
        ego_seen = False
        for raw in lines[1:]:
            raw = raw.strip()
            if not raw:
                continue
            rec = TrajectoryRecord.model_validate_json(raw)
            aid = rec.actor_id
            if aid not in states:
                raise ValueError(
                    f"actor_id {aid!r} in state record not in header.actor_ids"
                )
            k = idx[aid]
            if k >= n:
                raise ValueError(
                    f"more state records than header.n_steps for actor {aid!r}"
                )
            states[aid][k, 0] = rec.t
            states[aid][k, 1] = rec.x
            states[aid][k, 2] = rec.y
            states[aid][k, 3] = rec.vx
            states[aid][k, 4] = rec.vy
            yaws[aid][k] = rec.yaw
            if aid == "ego":
                ego_seen = True
                ego_accel[k] = 0.0 if rec.accel_cmd is None else rec.accel_cmd
                ego_steer[k] = 0.0 if rec.steer_cmd is None else rec.steer_cmd
            idx[aid] += 1
        for aid, count in idx.items():
            if count != n:
                raise ValueError(
                    f"actor {aid!r} has {count} state records but header.n_steps={n}"
                )
        return cls(
            header=header,
            _states=states,
            _yaw=yaws,
            _accel_cmd=ego_accel if ego_seen else None,
            _steer_cmd=ego_steer if ego_seen else None,
        )

    def write(self, path: str | Path) -> Path:
        """Serialize this log to canonical JSONL."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            header_payload = round_floats(self.header.model_dump(mode="json"), 4)
            fh.write(json.dumps(header_payload, sort_keys=True))
            fh.write("\n")
            n = self.n_steps
            for k in range(n):
                for aid in self.header.actor_ids:
                    s = self._states[aid][k]
                    yaw = self._yaw[aid][k]
                    if aid == "ego":
                        accel = (
                            None if self._accel_cmd is None else self._accel_cmd[k]
                        )
                        steer = (
                            None if self._steer_cmd is None else self._steer_cmd[k]
                        )
                    else:
                        accel = None
                        steer = None
                    payload = {
                        "record": "state",
                        "t": float(s[0]),
                        "actor_id": aid,
                        "x": float(s[1]),
                        "y": float(s[2]),
                        "yaw": float(yaw),
                        "vx": float(s[3]),
                        "vy": float(s[4]),
                        "accel_cmd": None if accel is None else float(accel),
                        "steer_cmd": None if steer is None else float(steer),
                    }
                    payload = round_floats(payload, 4)
                    fh.write(json.dumps(payload, sort_keys=True))
                    fh.write("\n")
        return p

    # ---- Construction from raw arrays (used by the engine) ----

    @classmethod
    def from_arrays(
        cls,
        *,
        header: TrajectoryHeader,
        states: dict[str, np.ndarray],
        yaws: dict[str, np.ndarray],
        ego_accel_cmd: np.ndarray | None,
        ego_steer_cmd: np.ndarray | None,
    ) -> "TrajectoryLog":
        return cls(
            header=header,
            _states=states,
            _yaw=yaws,
            _accel_cmd=ego_accel_cmd,
            _steer_cmd=ego_steer_cmd,
        )


def iter_state_records(log: TrajectoryLog) -> Iterable[TrajectoryRecord]:
    """Convenience iterator: yields TrajectoryRecord objects step-major, ego-first."""
    n = log.n_steps
    for k in range(n):
        for aid in log.actor_ids:
            s = log.states(aid)[k]
            yaw = log.yaw(aid)[k]
            yield TrajectoryRecord(
                t=float(s[0]),
                actor_id=aid,
                x=float(s[1]),
                y=float(s[2]),
                yaw=float(yaw),
                vx=float(s[3]),
                vy=float(s[4]),
                accel_cmd=(
                    float(log.accel_cmd()[k]) if aid == "ego" else None
                ),
                steer_cmd=(
                    float(log.steer_cmd()[k]) if aid == "ego" else None
                ),
            )
