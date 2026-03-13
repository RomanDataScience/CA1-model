import os
from pathlib import Path

try:
    from batchtk.algos import optuna_search
except ImportError:
    from netpyne.batchtools.search import search as _search

    def optuna_search(
        study_label,
        param_space,
        metrics,
        num_trials,
        num_workers,
        dispatcher_constructor,
        submit_constructor,
        submit_kwargs,
        param_space_samplers=None,
        interval=10,
        project_path=".",
        output_path="./optimization/optuna",
        checkpoint_path=None,
        algorithm_config=None,
        ray_config=None,
        **kwargs,
    ):
        metric_name, objective = next(iter(metrics.items()))
        mode = {"minimize": "min", "maximize": "max", "min": "min", "max": "max"}[objective]
        current_dir = Path.cwd()
        try:
            os.chdir(Path(project_path).resolve())
            return _search(
                dispatcher_constructor=dispatcher_constructor,
                submit_constructor=submit_constructor,
                run_config=submit_kwargs,
                params=param_space,
                algorithm="optuna",
                label=study_label,
                output_path=output_path,
                checkpoint_path=checkpoint_path or f"{output_path}_checkpoint",
                max_concurrent=num_workers,
                num_samples=num_trials,
                metric=metric_name,
                mode=mode,
                sample_interval=interval,
                algorithm_config=algorithm_config,
                ray_config=ray_config,
                clean_checkpoint=False,
            )
        finally:
            os.chdir(current_dir)

try:
    from batchtk.utils import expand_path
except ImportError:
    def expand_path(path, create_dirs=False):
        expanded = Path(path).expanduser().resolve()
        if create_dirs:
            expanded.mkdir(parents=True, exist_ok=True)
        return str(expanded)

from netpyne.batchtools.search import generate_constructors


REPO_ROOT = Path(__file__).resolve().parents[1]
cwd = str(REPO_ROOT)
env_bin = Path("/Users/romanbaravalle/miniconda3/envs/M1_CEBRA/bin")
study_label = "vip_optuna_theta_gate_v3"

# Option for local run.
dispatcher, submit = generate_constructors("sh", "sfs")

num_individuals = 1
num_iterations = 200

percentage_change = 0.5
min_chg = 1.0 - percentage_change
max_chg = 1.0 + percentage_change

params = {
    "factorSynVIP": (0.1, 10.),
    "nMSweight": (1e-5, 1e-2),
    "synMechParams.nACh_IS3.tau2": (150, 300),
    "nMSinputs": (1, 10),
    "nVipScInputs": (1, 10),
    "nVipPpInputs": (1, 10),
    "vipInputResistanceScale": (0.1, 5.0),
}

param_space_samplers = [
    "float",
    "float",
    "float",
    "int",
    "int",
    "int",
    "float",
]

submit_kwargs = {
    "command": f"{env_bin / 'python'} -u src_reformated/init_vip_batch.py",
}


def main():
    results = optuna_search(
        study_label=study_label,
        param_space=params,
        metrics={"loss": "minimize"},
        param_space_samplers=param_space_samplers,
        num_trials=num_iterations * num_individuals,
        num_workers=num_individuals,
        dispatcher_constructor=dispatcher,
        submit_constructor=submit,
        submit_kwargs=submit_kwargs,
        interval=10,
        project_path=cwd,
        output_path=expand_path(f"./src_reformated/batch_runs/{study_label}", create_dirs=True),
    )
    return results


if __name__ == "__main__":
    main()
