from qlib.data import D

from .config import build_fields


def load_research_data(config, end_time):
    """Load continuous histories and historical membership separately."""
    periods = config["periods"]
    fields = build_fields(config)
    # Read continuous histories first; historical membership filtering comes next.
    panel = D.features(
        D.instruments("all"),
        list(fields.values()),
        start_time=config["data"]["warmup_start"],
        end_time=end_time,
    )
    panel.columns = list(fields)

    # Qlib supplies the historical intervals; interval endpoints are inclusive.
    membership = D.list_instruments(
        D.instruments(config["data"]["universe"]),
        start_time=periods["train_start"],
        end_time=end_time,
        as_list=False,
    )
    return panel, membership, D.calendar()
