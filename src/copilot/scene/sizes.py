"""A thing's typical size (F-016 §4, test32): how big the canvas draws things next to each other. A boy holding a book:
the book is clearly smaller than the boy, yet both are readable.

    typical(noun, size word) -> metres: the noun's typical height (a short table of common nouns), times the size
                                word's factor when the teacher said one ("a giant apple"); a noun not in the table: the
                                size word (tiny .. huge), else medium

The metres only order and compress the pictures' heights (scene.worlds.canvas): drawn, never printed. Things in the
sky (sun, moon, planets) get the size they look, not their true size."""
from __future__ import annotations

from copilot.scene import assets

BY_WORD = {"tiny": 0.05, "small": 0.3, "medium": 1.2, "large": 6.0, "huge": 300.0}
DEFAULT_M = 1.2
FACTOR = {"tiny": 0.3, "small": 0.6, "medium": 1.0, "large": 2.0, "huge": 4.0}  # a said size on a known noun

# typical height (or the longest side) in metres; one word per row of a kind
_TABLE: dict[float, tuple[str, ...]] = {
    0.01: ("ant", "bee", "fly", "coin", "seed", "ladybug", "ladybird", "bug", "insect", "marble", "button", "ring",
           "key", "dice", "die"),
    0.05: ("butterfly", "egg", "strawberry", "cherry", "grape", "nut", "candy", "battery", "chalk", "eraser", "mouse",
           "snail", "frog", "spider", "lemon", "lime", "tomato"),
    0.08: ("apple", "orange", "ball", "potato", "onion", "peach", "pear", "cookie", "watch", "bulb", "cupcake"),
    0.12: ("rat", "cup", "mug", "glass", "phone", "banana", "pen", "pencil", "spoon", "fork", "knife", "brush",
           "hamster", "chick", "fish", "can", "candle", "flower", "rose", "magnet", "compass"),
    0.22: ("book", "notebook", "football", "basketball", "bottle", "bird", "parrot", "pigeon", "crow", "sparrow",
           "owl", "hen", "chicken", "rabbit", "squirrel", "plate", "bowl", "shoe", "hat", "cap", "pineapple", "camera",
           "clock", "teapot", "kettle", "toy", "doll", "trophy", "tablet", "keyboard", "laptop", "lamp", "vase"),
    0.35: ("cat", "kitten", "duck", "turtle", "tortoise", "bag", "backpack", "box", "basket", "helmet", "pumpkin",
           "watermelon", "monitor", "computer", "drum", "guitar", "violin", "pot", "bucket", "snake", "plant"),
    0.6: ("dog", "puppy", "goat", "sheep", "pig", "fox", "monkey", "penguin", "baby", "suitcase", "chair", "stool",
          "bench", "tyre", "tire", "wheel", "bed", "sofa", "couch", "fire"),
    0.8: ("table", "desk", "wolf", "deer", "kangaroo", "television", "tv", "fridge", "refrigerator", "bush"),
    1.0: ("bicycle", "bike", "cycle", "lion", "tiger", "leopard", "cheetah", "bear", "umbrella", "scooter", "child",
          "kid", "skateboard", "robot"),
    1.4: ("boy", "girl", "student", "cow", "buffalo", "motorcycle", "motorbike", "car", "automobile", "taxi", "door",
          "boat", "canoe", "stick", "ladder"),
    1.7: ("you", "yourself", "me", "myself", "person", "man", "woman", "teacher", "people", "human", "farmer",
          "doctor", "astronaut", "player", "driver", "pilot", "soldier", "king", "queen", "horse", "camel", "zebra",
          "gorilla", "spear", "statue"),
    3.0: ("elephant", "bus", "truck", "lorry", "van", "tractor", "train", "locomotive", "tram", "helicopter",
          "dinosaur", "wall", "gate", "car park"),
    5.0: ("giraffe", "whale", "shark", "submarine", "tent", "hut", "cloud", "rainbow"),
    8.0: ("tree", "house", "home", "cottage", "palm", "lighthouse", "windmill", "airplane", "plane", "aeroplane",
          "jet", "ship", "yacht", "pole", "lamppost"),
    20.0: ("building", "school", "temple", "church", "mosque", "castle", "bridge", "dam", "stadium"),
    50.0: ("rocket", "tower", "skyscraper", "pyramid", "hill", "spaceship", "satellite"),
    # in the sky: the size they look next to a rocket or a person, not their true size
    12.0: ("sun", "moon", "earth", "globe", "planet", "mars", "jupiter", "saturn", "venus", "mercury", "star",
           "comet", "asteroid"),
    1000.0: ("mountain", "volcano", "cliff", "glacier", "iceberg", "island", "valley"),
}
TYPICAL: dict[str, float] = {w: m for m, ws in _TABLE.items() for w in ws}


def typical(noun: str, size: str = "") -> float:
    """The noun's typical size in metres (its head word in the table, times a said size's factor), else the size
    word's, else medium."""
    low = " ".join(noun.lower().split())
    h = assets.head(noun)
    for w in (low, h, assets.singular(h)):
        if w in TYPICAL:
            return TYPICAL[w] * FACTOR.get(size, 1.0)
    return BY_WORD.get(size, DEFAULT_M)
