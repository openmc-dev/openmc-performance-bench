"""Utilities for running OpenMC benchmarks under ``/usr/bin/time -v``.

These helpers focus on reproducible collection of CPU and memory metrics when
executing OpenMC jobs from ASV benchmarks. They assume that ``openmc`` is
available on ``PATH`` and that the GNU ``time`` executable lives at
``/usr/bin/time`` by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Dict, Mapping, MutableMapping, Optional, Pattern, Sequence


@dataclass
class TimeUsage:
    """Parsed output from ``time -v`` describing resource usage."""

    elapsed_seconds: Optional[float] = None
    user_seconds: Optional[float] = None
    system_seconds: Optional[float] = None
    max_rss_kb: Optional[int] = None
    cpu_percent: Optional[float] = None
    raw: Dict[str, str] = field(default_factory=dict)


@dataclass
class OpenMCBuildInfo:
    """Metadata extracted from ``openmc -v``."""

    version: Optional[str] = None
    commit_hash: Optional[str] = None
    raw: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, str]:
        return dict(self.raw)

@dataclass
class OpenMCTimingStats:
    """Selected timing metrics parsed from OpenMC stdout."""

    total_elapsed: Optional[float] = None
    initialization: Optional[float] = None
    transport: Optional[float] = None
    calc_rate_inactive: Optional[float] = None
    calc_rate_active: Optional[float] = None
    raw: Dict[str, float] = field(default_factory=dict)


@dataclass
class OpenMCRunResult:
    """Structured details about a finished OpenMC invocation."""

    returncode: int
    stdout: str
    stderr: str
    command: Sequence[str]
    workdir: Path
    threads: Optional[int]
    mpi_procs: Optional[int]
    time_usage: TimeUsage
    build_info: Optional[OpenMCBuildInfo] = None
    timing_stats: Optional[OpenMCTimingStats] = None
    requested_mpi_procs: Optional[int] = None


_TIMING_REGEX: Dict[str, Pattern[str]] = {
    "initialization": re.compile(r"^Total time for initialization\s*=\s*([0-9.eE+-]+)\s*seconds$"),
    "transport": re.compile(r"^Time in transport only\s*=\s*([0-9.eE+-]+)\s*seconds$"),
    "total_elapsed": re.compile(r"^Total time elapsed\s*=\s*([0-9.eE+-]+)\s*seconds$"),
    "calc_rate_inactive": re.compile(r"^Calculation Rate \(inactive\)\s*=\s*([0-9.eE+-]+)\s*particles/second$"),
    "calc_rate_active": re.compile(r"^Calculation Rate \(active\)\s*=\s*([0-9.eE+-]+)\s*particles/second$"),
}


class OpenMCRunner:
    """Run OpenMC models while capturing timing information."""

    def __init__(
        self,
        *,
        openmc_exec: str = "openmc",
        time_executable: str = "/usr/bin/time",
        default_mpi_runner: Optional[Sequence[str]] = ("mpirun",),
    ) -> None:
        self.openmc_exec = openmc_exec
        self.time_executable = time_executable
        self.default_mpi_runner = tuple(default_mpi_runner) if default_mpi_runner else None
        self._cached_build_info: Optional[OpenMCBuildInfo] = None

    def run_model(
        self,
        model: object,
        *,
        threads: Optional[int] = None,
        mpi_procs: Optional[int] = None,
        mpi_command: Optional[Sequence[str]] = None,
        openmc_args: Optional[Sequence[str]] = None,
        extra_env: Optional[Mapping[str, str]] = None,
        working_dir: Optional[Path] = None,
        keep_workdir: bool = False,
        openmc_exec: Optional[str] = None,
        time_executable: Optional[str] = None,
        capture_output: bool = True,
    ) -> OpenMCRunResult:
        """
        Export *model* to XML and execute it under ``time -v``.

        Parameters
        ----------
        model:
            An ``openmc.Model`` instance or any object exposing ``export_to_xml``.
        threads:
            Number of OpenMP threads to request. Sets both ``OMP_NUM_THREADS`` and
            ``OPENMC_THREADS`` in the child environment when provided.
        mpi_procs:
            Number of MPI ranks to request. Values <= 1 skip MPI entirely.
        mpi_command:
            Custom MPI launcher command. Placeholders ``{procs}`` in any item are
            formatted with *mpi_procs*.
        openmc_args:
            Extra CLI arguments forwarded to the ``openmc`` executable.
        extra_env:
            Mapping of additional environment variables for the subprocess.
        working_dir:
            Directory to reuse for the run. If omitted, a temporary directory is
            created and trimmed afterwards unless *keep_workdir* is ``True``.
        keep_workdir:
            Preserve the temporary directory created for the run. Has no effect
            when *working_dir* is supplied.
        openmc_exec:
            Override the executable name/path for OpenMC.
        time_executable:
            Override path to GNU ``time``. Must support ``-v`` and ``-o``.
        capture_output:
            When ``True`` (default), capture stdout/stderr; otherwise inherit the
            parent's streams.
        """

        run_openmc_exec = openmc_exec or self.openmc_exec
        run_time_exec = time_executable or self.time_executable

        workdir_path, cleanup = self._prepare_workdir(working_dir)

        try:
            self._export_model(model, workdir_path)

            time_output = workdir_path / "time-usage.txt"

            env = self._build_environment(os.environ, threads=threads, extra_env=extra_env)
            build_info = self._get_build_info(run_openmc_exec, env)
            effective_mpi_procs = self._select_mpi_procs(mpi_procs, build_info)

            command = self._build_command(
                run_openmc_exec,
                openmc_args=openmc_args,
                mpi_procs=effective_mpi_procs,
                mpi_command=mpi_command,
                time_exec=run_time_exec,
                time_output=time_output,
            )

            completed = subprocess.run(
                command,
                cwd=str(workdir_path),
                capture_output=capture_output,
                text=True,
                env=env,
                check=False,
            )

            time_usage = self._parse_time_output(time_output)
            timing_stats = (
                _parse_openmc_timing(completed.stdout, completed.stderr)
                if capture_output
                else None
            )

            return OpenMCRunResult(
                returncode=completed.returncode,
                stdout=completed.stdout if capture_output else "",
                stderr=completed.stderr if capture_output else "",
                command=command,
                workdir=workdir_path,
                threads=threads,
                mpi_procs=effective_mpi_procs,
                time_usage=time_usage,
                build_info=build_info,
                timing_stats=timing_stats,
                requested_mpi_procs=mpi_procs,
            )
        finally:
            if cleanup and not keep_workdir:
                shutil.rmtree(workdir_path, ignore_errors=True)

    @staticmethod
    def _prepare_workdir(working_dir: Optional[Path]) -> tuple[Path, bool]:
        if working_dir is not None:
            return Path(working_dir), False
        temp_path = Path(tempfile.mkdtemp(prefix="openmc-bench-"))
        return temp_path, True

    @staticmethod
    def _export_model(model: object, destination: Path) -> None:
        if model is None:
            raise ValueError("model must be provided")
        exporter = getattr(model, "export_to_xml", None)
        if exporter is None or not callable(exporter):
            raise TypeError("model must provide an export_to_xml() method")
        exporter(str(destination))

    def _select_mpi_procs(
        self, requested: Optional[int], build_info: Optional[OpenMCBuildInfo]
    ) -> Optional[int]:
        if not requested or requested <= 1:
            return None
        if not self._build_supports_mpi(build_info):
            return None
        return requested

    @staticmethod
    def _build_supports_mpi(build_info: Optional[OpenMCBuildInfo]) -> bool:
        if build_info is None:
            return True
        raw_value = build_info.raw.get("MPI enabled") or build_info.raw.get("MPI Enabled")
        if raw_value is None:
            return True
        return raw_value.strip().lower() in {"yes", "true", "1"}

    def _build_command(
        self,
        openmc_exec: str,
        *,
        openmc_args: Optional[Sequence[str]],
        mpi_procs: Optional[int],
        mpi_command: Optional[Sequence[str]],
        time_exec: str,
        time_output: Path,
    ) -> Sequence[str]:
        base_cmd: list[str] = []
        launcher = self._resolve_mpi_launcher(mpi_procs, mpi_command)
        if launcher:
            base_cmd.extend(launcher)
        base_cmd.append(openmc_exec)
        if openmc_args:
            base_cmd.extend(openmc_args)

        full_cmd = [time_exec, "-v", "-o", str(time_output), *base_cmd]
        return full_cmd

    def _resolve_mpi_launcher(
        self,
        mpi_procs: Optional[int],
        mpi_command: Optional[Sequence[str]],
    ) -> Sequence[str]:
        if not mpi_procs or mpi_procs <= 1:
            return []

        if mpi_command:
            return [part.format(procs=mpi_procs) for part in mpi_command]

        if self.default_mpi_runner:
            return [
                *self.default_mpi_runner,
                "-np",
                str(mpi_procs),
            ]

        raise ValueError("MPI requested but no launcher available")

    @staticmethod
    def _build_environment(
        parent_env: MutableMapping[str, str],
        *,
        threads: Optional[int],
        extra_env: Optional[Mapping[str, str]],
    ) -> Dict[str, str]:
        env: Dict[str, str] = dict(parent_env)
        if threads is not None:
            env["OMP_NUM_THREADS"] = str(threads)
            env["OPENMC_THREADS"] = str(threads)
        if extra_env:
            env.update(extra_env)
        return env

    def _get_build_info(
        self, openmc_exec: str, env: Mapping[str, str]
    ) -> Optional[OpenMCBuildInfo]:
        if self._cached_build_info and openmc_exec == self.openmc_exec:
            return self._cached_build_info

        info = self._fetch_build_info(openmc_exec, env)
        if openmc_exec == self.openmc_exec:
            self._cached_build_info = info
        return info

    def _fetch_build_info(
        self, openmc_exec: str, env: Mapping[str, str]
    ) -> Optional[OpenMCBuildInfo]:
        try:
            completed = subprocess.run(
                [openmc_exec, '-v'],
                capture_output=True,
                text=True,
                env=dict(env),
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None

        lines = completed.stdout.splitlines()
        if not lines:
            return None

        raw = _parse_openmc_version_output(lines)
        return OpenMCBuildInfo(
            version=raw.get('OpenMC version'),
            commit_hash=raw.get('Commit hash'),
            raw=raw,
        )

    @staticmethod
    def _parse_time_output(time_output: Path) -> TimeUsage:
        if not time_output.exists():
            return TimeUsage()

        raw: Dict[str, str] = {}
        with time_output.open("r", encoding="utf-8") as handle:
            for line in handle:
                if ': ' not in line:
                    continue
                key, value = line.split(': ', 1)
                raw[key.strip()] = value.strip()

        return TimeUsage(
            elapsed_seconds=_parse_elapsed(_lookup_stat(raw, "Elapsed (wall clock) time")),
            user_seconds=_parse_float(_lookup_stat(raw, "User time (seconds)")),
            system_seconds=_parse_float(_lookup_stat(raw, "System time (seconds)")),
            max_rss_kb=_parse_int(_lookup_stat(raw, "Maximum resident set size")),
            cpu_percent=_parse_percent(_lookup_stat(raw, "Percent of CPU this job got")),
            raw=raw,
        )


def _lookup_stat(values: Mapping[str, str], key_prefix: str) -> Optional[str]:
    for key, value in values.items():
        if key.startswith(key_prefix):
            return value
    return None


def _parse_openmc_timing(*streams: str) -> Optional[OpenMCTimingStats]:
    values: Dict[str, float] = {}
    for stream in streams:
        if not stream:
            continue
        for line in stream.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            for key, pattern in _TIMING_REGEX.items():
                match = pattern.match(stripped)
                if match:
                    try:
                        values[key] = float(match.group(1))
                    except ValueError:
                        continue
    if not values:
        return None

    return OpenMCTimingStats(
        total_elapsed=values.get('total_elapsed'),
        initialization=values.get('initialization'),
        transport=values.get('transport'),
        calc_rate_inactive=values.get('calc_rate_inactive'),
        calc_rate_active=values.get('calc_rate_active'),
        raw=values,
    )


def _parse_openmc_version_output(lines: Sequence[str]) -> Dict[str, str]:
    info: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('OpenMC version'):
            info['OpenMC version'] = stripped.partition('OpenMC version')[2].strip()
            continue
        if ':' in stripped:
            key, value = stripped.split(':', 1)
            info[key.strip()] = value.strip()
    return info


def _parse_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_percent(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    value = value.rstrip("%")
    return _parse_float(value)


def _parse_elapsed(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    parts = value.split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return None
    return None


def run_model_with_time(
    model: object,
    *,
    runner: Optional[OpenMCRunner] = None,
    **kwargs: object,
) -> OpenMCRunResult:
    """Convenience wrapper around :class:`OpenMCRunner`."""

    active_runner = runner or OpenMCRunner()
    return active_runner.run_model(model, **kwargs)
