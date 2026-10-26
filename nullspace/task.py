"""Staggered cohorts over identical hidden sequences (an analogue of the
timed question chains the German Wiki Incident archive shows)."""
import random
from dataclasses import dataclass, field

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    "Wisconsin", "Wyoming",
]
TOPICS = [
    ("Sector61", "workforce state sequence for industry sector 61-62"),
    ("Grocery", "grocery employment state sequence"),
    ("Clothing", "clothing stores state sequence"),
    ("Construction", "construction workforce state sequence"),
    ("Transport", "transport workforce state sequence"),
]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DATA_SOURCE = "DataUSA"

ROUND_LEN = 900       # seconds between a cohort's rounds
STAGGER = 1400        # > ROUND_LEN, so an earlier cohort is a full round ahead
JITTER = 200          # < STAGGER - ROUND_LEN


@dataclass
class Family:
    token: str
    topic: str
    sequence: list


@dataclass
class Slot:
    family: str
    topic: str
    data_source: str
    cohort: int
    cohort_date: str
    round: int
    arrival: float
    known_items: list
    target_item: str
    slot_id: int = 0

    def as_dict(self):
        return {
            "slot_id": self.slot_id, "family": self.family, "topic": self.topic,
            "data_source": self.data_source, "cohort": self.cohort,
            "cohort_date": self.cohort_date, "round": self.round, "arrival": self.arrival,
            "known_items": list(self.known_items), "target_item": self.target_item,
        }


@dataclass
class World:
    families: list
    slots: list = field(default_factory=list)

    def schedule(self):
        return list(self.slots)


def make_world(seed, families=3, cohorts=4, rounds=3):
    rng = random.Random(seed)
    fams = []
    for token, topic in rng.sample(TOPICS, families):
        fams.append(Family(token, topic, rng.sample(US_STATES, rounds + 1)))
    slots = []
    for fam in fams:
        dates = set()
        while len(dates) < cohorts:
            dates.add(f"{rng.choice(MONTHS)}{rng.randint(1, 28)}")
        dates = sorted(dates)          # sets iterate in hash order; sort first (review F1)
        rng.shuffle(dates)
        for c in range(cohorts):
            start = c * STAGGER + rng.uniform(0, JITTER)
            for r in range(1, rounds + 1):
                slots.append(Slot(
                    family=fam.token, topic=fam.topic, data_source=DATA_SOURCE,
                    cohort=c, cohort_date=dates[c], round=r,
                    arrival=start + (r - 1) * ROUND_LEN,
                    known_items=fam.sequence[:r], target_item=fam.sequence[r]))
    slots.sort(key=lambda s: (s.arrival, s.family, s.cohort))
    for i, s in enumerate(slots):
        s.slot_id = i
    return World(families=fams, slots=slots)
