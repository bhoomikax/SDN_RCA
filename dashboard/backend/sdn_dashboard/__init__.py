"""Research demo backend for the SDN fault-localisation project.

The package wraps the repository's existing runner, builders, evaluators and
saved results behind a small FastAPI service. It never reimplements the
experiment; live runs are executed by ``experiment_runner_recollection.py``
inside the Mininet VM over SSH, and inference reuses the repository modules.
"""
