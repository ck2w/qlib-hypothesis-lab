"""Check an existing freeze against current inputs without running research."""
import argparse
from pathlib import Path

from lab.config import load_config
from lab.artifacts import canonical_config_hash, verify_frozen_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = verify_frozen_run(args.run_dir, load_config(args.config))
    print("冻结检查通过；配置 SHA-256:", canonical_config_hash(config))


if __name__ == "__main__":
    main()
