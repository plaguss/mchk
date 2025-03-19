"""
Usage:
$ uv run first_batch.py \
    --input "/home/agustin/github_repos/mchk/raw_wods" \
    --output "/home/agustin/github_repos/mchk/site/content/wods"
"""

from pathlib import Path
import subprocess
import datetime as dt


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--input", type=Path, required=True, help="Input folder to grab the files.")
    parser.add_argument("--output", type=Path, required=True, help="Folder where the results should be placed.")
    args = parser.parse_args()

    folder: Path = args.input

    for file in folder.iterdir():
        print("Run with: ", file)
        datestr = file.stem.replace("wod-", "")
        date = dt.datetime.strptime(datestr, "%d-%m-%y").date()
        new_filename = f"wod-{date.strftime("%d-%m-%y")}.md"
        # print(file, new_filename)
        new_filename = str(args.output / new_filename)
        cmd = ["wod", new_filename, "--wodfile", str(file)]
        result = subprocess.run(cmd, capture_output=True, check=False)
        if err := result.stderr.decode("utf-8"):
            print("ERR", err)
        else:
            pass
