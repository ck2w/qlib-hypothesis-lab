from collect_yahoo import PilotCollector


def test_explicit_symbols_only(tmp_path):
    collector = PilotCollector(
        save_dir=tmp_path,
        start="2018-01-01",
        end="2026-10-12",
        interval="1d",
        max_workers=1,
        delay=1,
    )

    assert set(collector.instrument_list) == {"AAPL", "MSFT", "JPM"}
    assert len(collector.instrument_list) == 3
