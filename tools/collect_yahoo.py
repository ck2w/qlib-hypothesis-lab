import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QLIB_SCRIPTS = PROJECT_ROOT / "upstream" / "qlib" / "scripts"
sys.path.insert(0, str(QLIB_SCRIPTS))

from data_collector.yahoo.collector import YahooCollectorUS1d


class PilotCollector(YahooCollectorUS1d):
    def __init__(self, *args, symbols_file=None, **kwargs):
        self.symbols_file = symbols_file
        super().__init__(*args, **kwargs)

    def get_instrument_list(self):
        if self.symbols_file is None:
            return ["AAPL", "MSFT", "JPM"]
        symbols = [
            line.strip().upper().replace(".", "-")
            for line in Path(self.symbols_file).read_text().splitlines()
            if line.strip()
        ]
        if not symbols:
            raise ValueError("股票名单为空，请检查 --symbols-file。")
        return sorted(set(symbols))


def main():
    parser = argparse.ArgumentParser(
        description="Download a symbol list (or the three-stock pilot) using Qlib's Yahoo collector."
    )
    parser.add_argument("--symbols-file", type=Path, help="One ticker per line; default: AAPL, MSFT, JPM")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--start", required=True, help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Exclusive end date (YYYY-MM-DD)")
    args = parser.parse_args()

    source_dir = args.source_dir.expanduser().resolve()
    if source_dir.exists() and not source_dir.is_dir():
        raise SystemExit("目标路径不是目录，请换一个新目录。")
    if source_dir.exists() and any(source_dir.iterdir()):
        raise SystemExit("目标目录非空，请换一个新目录，避免重复追加数据。")

    collector = PilotCollector(
        symbols_file=args.symbols_file,
        save_dir=source_dir,
        start=args.start,
        end=args.end,
        interval="1d",
        max_workers=1,
        max_collector_count=2,
        delay=1,
    )
    collector.retry = 2

    print("采集数量:", len(collector.instrument_list))
    print("采集名单:", collector.instrument_list)
    print("日期范围:", args.start, "至", args.end, "（结束日不含）")
    print("保存位置:", source_dir)
    collector.collector_data()


if __name__ == "__main__":
    main()
