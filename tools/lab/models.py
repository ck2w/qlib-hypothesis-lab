import pandas as pd
from sklearn.linear_model import Ridge


MODEL_FEATURES = {
    "baseline": ["z_rev", "z_rv", "z_vol20"],
    "with_candidate": ["z_rev", "z_rv", "z_vol20", "candidate"],
}


def fit_models(train, config):
    """Both models receive identical training rows and the same target."""
    if train.empty:
        raise ValueError("没有可用于拟合的训练样本。")
    models = {}
    for name, columns in MODEL_FEATURES.items():
        model = Ridge(**config["model"])
        model.fit(train[columns], train["label"])
        models[name] = model
    return models


def predict_models(models, samples):
    """Predict using features only; keep the original stock-date index."""
    predictions = pd.DataFrame(index=samples.index)
    for name, columns in MODEL_FEATURES.items():
        predictions[name] = (
            models[name].predict(samples[columns]) if len(samples) else
            pd.Series(index=samples.index, dtype="float64")
        )
    return predictions
