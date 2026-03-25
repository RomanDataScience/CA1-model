import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BATCH_RUNS_DIR = REPO_ROOT / "batch_runs"
DEFAULT_BEST_TRIALS_FILE = BATCH_RUNS_DIR / "BestTrials.txt"
SCRIPT_DIR = Path(__file__).resolve().parent


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Read batch_runs/BestTrials.txt and run the condition replay scripts "
            "for each listed Optuna trial."
        )
    )
    parser.add_argument(
        "--best-trials-file",
        default=str(DEFAULT_BEST_TRIALS_FILE),
        help="Path to a text file containing one trial number per line.",
    )
    parser.add_argument(
        "--study-label",
        default=None,
        help="Optuna study label. If omitted, infer it from the batch_runs folder.",
    )
    parser.add_argument(
        "--batch-dir",
        default=None,
        help="Override the study output folder. Defaults to <repo>/batch_runs/<study-label>.",
    )
    parser.add_argument(
        "--output-root",
        default=str((REPO_ROOT / "output_best_batch").resolve()),
        help="Root folder where per-trial rerun outputs will be stored.",
    )
    parser.add_argument(
        "--skip-conditions",
        action="store_true",
        help="Skip run_best_vip_conditions.py.",
    )
    parser.add_argument(
        "--skip-currentscape",
        action="store_true",
        help="Skip run_best_vip_conditions_currentscape.py.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with later trials if one script invocation fails.",
    )
    return parser.parse_args()


def _load_trial_numbers(best_trials_file):
    trial_numbers = []
    with Path(best_trials_file).expanduser().open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped = raw_line.split("#", 1)[0].strip()
            if not stripped:
                continue
            try:
                trial_numbers.append(int(stripped))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid trial number on line {line_number} of {best_trials_file}: {raw_line.rstrip()}"
                ) from exc

    if not trial_numbers:
        raise ValueError(f"No trial numbers found in {best_trials_file}.")

    return trial_numbers


def _infer_study_label(batch_dir, study_label):
    if study_label is not None:
        return study_label

    if batch_dir is not None:
        return Path(batch_dir).expanduser().resolve().name

    study_dirs = sorted(path for path in BATCH_RUNS_DIR.iterdir() if path.is_dir())
    if len(study_dirs) == 1:
        return study_dirs[0].name

    if not study_dirs:
        raise ValueError(
            "Could not infer a study label because batch_runs/ contains no study directories. "
            "Pass --study-label or --batch-dir explicitly."
        )

    labels = ", ".join(path.name for path in study_dirs)
    raise ValueError(
        "Could not infer a unique study label because batch_runs/ contains multiple study directories: "
        f"{labels}. Pass --study-label or --batch-dir explicitly."
    )


def _build_commands(trial_number, study_label, batch_dir, output_root, skip_conditions, skip_currentscape):
    if skip_conditions and skip_currentscape:
        raise ValueError("Nothing to run: both --skip-conditions and --skip-currentscape were provided.")

    commands = []
    trial_root = output_root / f"trial_{trial_number}"
    common_args = ["--trial", str(trial_number), "--study-label", study_label]
    if batch_dir is not None:
        common_args.extend(["--batch-dir", str(Path(batch_dir).expanduser().resolve())])

    if not skip_conditions:
        commands.append(
            (
                "conditions",
                [
                    sys.executable,
                    str(SCRIPT_DIR / "run_best_vip_conditions.py"),
                    *common_args,
                    "--output-dir",
                    str((trial_root / "conditions").resolve()),
                ],
            )
        )

    if not skip_currentscape:
        commands.append(
            (
                "currentscape",
                [
                    sys.executable,
                    str(SCRIPT_DIR / "run_best_vip_conditions_currentscape.py"),
                    *common_args,
                    "--output-dir",
                    str((trial_root / "currentscape").resolve()),
                ],
            )
        )

    return commands


def main():
    args = _parse_args()
    best_trials_file = Path(args.best_trials_file).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    trial_numbers = _load_trial_numbers(best_trials_file)
    study_label = _infer_study_label(args.batch_dir, args.study_label)
    failures = []

    print(f"Using study label: {study_label}")
    print(f"Reading trial numbers from: {best_trials_file}")
    print(f"Writing rerun outputs under: {output_root}")

    for trial_number in trial_numbers:
        print(f"=== Trial {trial_number} ===")
        commands = _build_commands(
            trial_number=trial_number,
            study_label=study_label,
            batch_dir=args.batch_dir,
            output_root=output_root,
            skip_conditions=args.skip_conditions,
            skip_currentscape=args.skip_currentscape,
        )

        for command_name, command in commands:
            print(f"Running {command_name}: {' '.join(command)}")
            completed = subprocess.run(command, cwd=REPO_ROOT)
            if completed.returncode != 0:
                failures.append((trial_number, command_name, completed.returncode))
                print(
                    f"{command_name} failed for trial {trial_number} with exit code {completed.returncode}.",
                    file=sys.stderr,
                )
                if not args.continue_on_error:
                    return completed.returncode

    if failures:
        print("\nFailures:", file=sys.stderr)
        for trial_number, command_name, return_code in failures:
            print(
                f"  trial {trial_number}: {command_name} exited with {return_code}",
                file=sys.stderr,
            )
        return 1

    print("\nCompleted all requested trial reruns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
