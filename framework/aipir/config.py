"""Single source of configuration for the AIPIR pipeline and the runtime service.

Design choices were made on the DEVELOPMENT file (HAI 21.03 test1) only, before any
held-out test file (test2-test5) or HAI 20.07 was scored. See docs/LIMITATIONS.md.
"""
from .detectors import AIPIRPredictive, IForest, PCAResidual, StaticLimits

# Alarm logic shared by all detectors [VERIFY V3: grace window and debounce]
MERGE_GAP_S = 30      # alarm runs closer than this are one episode
MIN_DUR_S = 5         # an episode must persist this long to be raised (debounce)
GRACE_S = 60          # an alarm up to 60 s after an attack ends still counts as detecting it

# Threshold calibration target on held-out normal data [VERIFY V2]
FA_BUDGET_PER_DAY = 1.0
TRAIN_EXCLUDE_PAD_S = 600  # seconds after any labelled training second also excluded
FIT_FRACTION = 0.8    # first 80 % of each normal file fits models; last 20 % calibrates thresholds

DEV_FILES = {"hai-21.03": ["test1"]}
TEST_FILES = {"hai-21.03": ["test2", "test3", "test4", "test5"], "hai-20.07": ["test1", "test2"]}
TRAIN_FILES = {"hai-21.03": ["train1", "train2", "train3"], "hai-20.07": ["train1", "train2"]}


def make_detectors():
    """Detector set with the configurations selected on the development file."""
    return {
        "D0": StaticLimits(),
        "D1": PCAResidual(var=0.95, mode="spe", smooth=60),
        "D2": IForest(n=100, smooth=10),
        "D3": AIPIRPredictive(channels=("forecast",), q=99.9, clip=5.0, smooth=10, topk=5),
    }


def make_ablations():
    return {
        "D3+C": AIPIRPredictive(channels=("forecast", "consistency"), q=99.9, clip=5.0, smooth=10, topk=5),
        "D3-noclip": AIPIRPredictive(channels=("forecast",), q=95.0, clip=None, smooth=10, topk=5),
    }


LABELS = {
    "D0": "Static alarm limits",
    "D1": "PCA residual",
    "D2": "Isolation Forest",
    "D3": "AIPIR predictive",
    "D3+C": "AIPIR + consistency channel",
    "D3-noclip": "AIPIR without robust normalization",
}
