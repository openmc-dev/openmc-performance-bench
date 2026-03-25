"""Benchmark for Evaluation And Validation of Reactor Simulations."""

from pathlib import Path
import openmc

BENCHMARK_NAME = "BEAVRS"


def build_model() -> openmc.Model:
    return openmc.Model.from_model_xml(Path(__file__).resolve().parent / "beavrs.xml")
