"""Small, reproducible configuration for VFXAI's first trainable model."""

APP_VERSION = "0.3.0"
MODEL_VERSION = "structured-mlp-v1"
GENERATOR_VERSION = "synthetic-plan-v1"

# 512 hashed word/character features -> 64 tanh units -> 10 category,
# 4 component-presence, and 45 structured numeric outputs.
INPUT_SIZE = 512
DEFAULT_HIDDEN_SIZE = 64
MIN_HIDDEN_SIZE = 16
MAX_HIDDEN_SIZE = 128
DEFAULT_INIT_SEED = 2026
DEFAULT_TRAIN_SEED = 1337
DEFAULT_DATASET_SEED = 2026
DEFAULT_DATASET_COUNT = 1000
DEFAULT_EPOCHS = 20
DEFAULT_BATCH_SIZE = 16
DEFAULT_LEARNING_RATE = 0.003

CATEGORIES = (
    "lightning",
    "energy-beam",
    "explosion",
    "shockwave",
    "magical-aura",
    "particle-burst",
    "energy-trail",
    "charge-release",
    "orbiting-energy",
    "layered-effect",
)

COMPONENT_TYPES = ("core", "ring", "lightning", "particles")
DEFAULT_CONSTRAINTS = {"maxObjects": 64, "maxParticles": 128}
HARD_LIMITS = {"objects": 256, "particles": 512, "vertices": 8192}

LOSS_WEIGHTS = {"category": 1.0, "components": 1.0, "numeric": 2.0}
