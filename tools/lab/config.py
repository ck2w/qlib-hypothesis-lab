"""Configuration for the first research workflow, not an arbitrary factor DSL."""
import ast
import math
import re
from pathlib import Path

import pandas as pd
import yaml


FIELDS = {"open", "high", "low", "close", "volume", "factor"}
ROLLING = {"Mean", "Std", "Count", "Sum", "Max", "Min"}
UNARY_FUNCTIONS = {"Abs", "Log"}


def parse_feature_expression(expression):
    """Parse a restricted Qlib expression and infer each field's lag interval."""
    if not isinstance(expression, str) or "FIELD_" in expression:
        raise ValueError("表达式必须使用明确的 $字段。")
    transformed = re.sub(r"\$([A-Za-z_][A-Za-z_0-9]*)", r"FIELD_\1", expression)
    try:
        tree = ast.parse(transformed, mode="eval").body
    except SyntaxError as error:
        raise ValueError("表达式语法无效。") from error

    def merge(left, right):
        result = dict(left)
        for field, (low, high) in right.items():
            if field in result:
                low, high = min(low, result[field][0]), max(high, result[field][1])
            result[field] = (low, high)
        return result

    def walk(node):
        if isinstance(node, ast.Constant):
            if type(node.value) not in [int, float] or not math.isfinite(node.value):
                raise ValueError("只允许有限数值常量。")
            return {}
        if isinstance(node, ast.Name):
            if node.id.startswith("FIELD_") and node.id[6:] in FIELDS:
                return {node.id[6:]: (0, 0)}
            raise ValueError("未知字段或缺少 $ 前缀。")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            if not isinstance(node.operand, ast.Constant):
                raise ValueError("Qlib 不支持对表达式使用一元正负号，请使用二元运算。")
            return walk(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            return merge(walk(node.left), walk(node.right))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name in UNARY_FUNCTIONS and len(node.args) == 1:
                return walk(node.args[0])
            if name in ROLLING | {"Ref"} and len(node.args) == 2:
                try:
                    window = ast.literal_eval(node.args[1])
                except (TypeError, ValueError):
                    raise ValueError("窗口或偏移必须是明确的整数。") from None
                if type(window) is not int:
                    raise ValueError("窗口或偏移必须是整数。")
                if name == "Ref" and window < 0:
                    raise ValueError("特征不能包含未来 Ref。")
                if name != "Ref" and window < 1:
                    raise ValueError("滚动窗口必须为正整数。")
                history = walk(node.args[0])
                if name == "Ref":
                    return {field: (low + window, high + window) for field, (low, high) in history.items()}
                return {field: (low, high + window - 1) for field, (low, high) in history.items()}
        raise ValueError("表达式包含未允许的语法或算子。")

    history = walk(tree)
    if not history:
        raise ValueError("特征表达式必须引用行情字段。")
    return tree, history


def validate_feature_expression(expression):
    return parse_feature_expression(expression)[1]


def validate_window(feature):
    expression, history = parse_feature_expression(feature["expression"])
    count, count_history = parse_feature_expression(feature["count_expression"])
    required = feature["required_count"]
    if type(required) is not int or required < 1:
        raise ValueError("完整窗口计数必须为正整数。")
    if not isinstance(count, ast.Call) or count.func.id != "Count":
        raise ValueError("窗口检查必须使用 Count。")
    if ast.literal_eval(count.args[1]) != required:
        raise ValueError("required_count 与 Count 窗口不一致。")
    for node in ast.walk(count.args[0]):
        if isinstance(node, ast.Call) and node.func.id in ROLLING:
            raise ValueError("Count 内不能嵌套会在不足窗口时返回值的滚动算子。")
    for field, (low, high) in history.items():
        if field not in count_history:
            raise ValueError("窗口计数没有覆盖特征依赖的字段。")
        count_low, count_high = count_history[field]
        if count_low > low or count_high < high:
            raise ValueError("窗口计数不足以覆盖特征历史。")
    if "positive_denominator" in feature:
        denominator, _ = parse_feature_expression(feature["positive_denominator"])
        divisors = [node.right for node in ast.walk(expression)
                    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)]
        if not any(ast.dump(denominator) == ast.dump(node) for node in divisors):
            raise ValueError("positive_denominator 必须对应实际公式分母。")


def parse_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期必须为 YYYY-MM-DD。")
    result = pd.Timestamp(value)
    if pd.isna(result):
        raise ValueError("日期不能为 NaT。")
    return result


def load_config(path):
    config = yaml.safe_load(Path(path).read_text())
    try:
        if config["schema_version"] != 1:
            raise ValueError("不支持的配置版本。")
        periods = config["periods"]
        start, train_end, oos_start, oos_end = [
            parse_date(periods[key]) for key in
            ["train_start", "train_end_exclusive", "oos_start", "oos_end_exclusive"]
        ]
        if not start < train_end <= oos_start < oos_end:
            raise ValueError("训练和样本外区间必须有序且不重叠。")
        if not start <= parse_date(periods["development_end"]) < train_end:
            raise ValueError("开发片段必须位于训练期间。")
        if not parse_date(config["data"]["warmup_start"]) < start:
            raise ValueError("预热起点必须早于训练起点。")
        if config["data"]["region"] != "us":
            raise ValueError("当前工具仅支持 US 数据。")
        if config["standardization"]["ddof"] != 0:
            raise ValueError("当前截面标准化固定 ddof=0。")
        features = config["features"]
        if set(features) != {"rev", "rv", "vol20"}:
            raise ValueError("第一版配置需要 rev、rv、vol20 三个特征角色。")
        for feature in features.values():
            validate_window(feature)
        candidate = config["candidate"]
        if (candidate["kind"] != "standardized_product"
                or candidate["left"] not in features or candidate["right"] not in features
                or candidate["right_sign"] not in [-1, 1]):
            raise ValueError("当前候选必须是指定特征的标准化乘积。")
        entry, exit_ = config["label"]["entry_offset"], config["label"]["exit_offset"]
        if type(entry) is not int or type(exit_) is not int or not 0 < entry < exit_:
            raise ValueError("标签偏移必须满足 0 < entry_offset < exit_offset。")
        alpha = config["model"]["alpha"]
        if not math.isfinite(alpha) or alpha < 0:
            raise ValueError("Ridge alpha 必须是有限非负数。")
        if type(config["model"]["fit_intercept"]) is not bool:
            raise ValueError("fit_intercept 必须为布尔值。")
        bootstrap = config["bootstrap"]
        for key in ["block_length", "n_resamples"]:
            if type(bootstrap[key]) is not int or bootstrap[key] < 1:
                raise ValueError("bootstrap 块长和次数必须为正整数。")
        if bootstrap["block_length"] < exit_ - entry:
            raise ValueError("bootstrap 块长不能短于标签持有期。")
        if type(bootstrap["seed"]) is not int or bootstrap["seed"] < 0:
            raise ValueError("seed 必须为非负整数。")
        if not 0 < bootstrap["confidence"] < 1:
            raise ValueError("confidence 必须介于 0 与 1。")
        if type(config["research"]["oos_previously_seen"]) is not bool:
            raise ValueError("必须记录样本外是否已经看过。")
    except (KeyError, TypeError) as error:
        raise ValueError(f"研究配置缺字段或类型错误：{error}") from error
    return config


def build_fields(config):
    fields = {"close": "$close", "volume": "$volume"}
    for name, feature in config["features"].items():
        fields[name] = feature["expression"]
        fields[f"count_{name}"] = feature["count_expression"]
        if "positive_denominator" in feature:
            fields[f"denominator_{name}"] = feature["positive_denominator"]
    entry, exit_ = config["label"]["entry_offset"], config["label"]["exit_offset"]
    fields.update(
        label=f"Ref($open, -{exit_}) / Ref($open, -{entry}) - 1",
        entry_open=f"Ref($open, -{entry})", exit_open=f"Ref($open, -{exit_})",
    )
    return fields
