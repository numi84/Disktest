"""
Bitmuster-Generierung für DiskTest
Erzeugt die 5 verschiedenen Testmuster: 0x00, 0xFF, 0xAA, 0x55, Random
"""
from enum import Enum
import random


class PatternType(Enum):
    """Verfügbare Testmuster"""
    ZERO = "00"      # 0x00 - Alle Bits 0
    ONE = "FF"       # 0xFF - Alle Bits 1
    ALT_AA = "AA"    # 0xAA - Alternierende Bits (10101010)
    ALT_55 = "55"    # 0x55 - Alternierende Bits (01010101)
    RANDOM = "RND"   # Zufallsdaten (mit Seed für Reproduzierbarkeit)

    def __str__(self):
        return self.value

    @property
    def display_name(self):
        """Anzeigename für GUI"""
        names = {
            PatternType.ZERO: "0x00 (Null)",
            PatternType.ONE: "0xFF (Eins)",
            PatternType.ALT_AA: "0xAA (Alt-1)",
            PatternType.ALT_55: "0x55 (Alt-2)",
            PatternType.RANDOM: "Random"
        }
        return names[self]


# Standard-Reihenfolge der Muster (wie in Spezifikation)
PATTERN_SEQUENCE = [
    PatternType.ZERO,
    PatternType.ONE,
    PatternType.ALT_AA,
    PatternType.ALT_55,
    PatternType.RANDOM
]


class PatternGenerator:
    """
    Generator für Testmuster

    Erzeugt Chunks mit definierten Bitmustern.
    Für Random-Muster: Seed wird gespeichert für Reproduzierbarkeit.
    """

    def __init__(self, pattern_type: PatternType, seed: int = None):
        """
        Initialisiert den Pattern-Generator

        Args:
            pattern_type: Typ des zu generierenden Musters
            seed: Seed für Random-Generator (optional, wird automatisch erzeugt wenn None)
        """
        self.pattern_type = pattern_type

        # Für Random: Seed speichern oder generieren
        if pattern_type == PatternType.RANDOM:
            self.seed = seed if seed is not None else random.randint(0, 2**31 - 1)
            self._random = random.Random(self.seed)
        else:
            self.seed = None
            self._random = None

    def generate_chunk(self, size: int) -> bytes:
        """
        Generiert einen Chunk mit dem definierten Muster

        Args:
            size: Größe des Chunks in Bytes

        Returns:
            bytes: Chunk mit Testmuster
        """
        if self.pattern_type == PatternType.ZERO:
            return bytes(size)  # Alle Bytes 0x00

        elif self.pattern_type == PatternType.ONE:
            return bytes([0xFF] * size)

        elif self.pattern_type == PatternType.ALT_AA:
            return bytes([0xAA] * size)

        elif self.pattern_type == PatternType.ALT_55:
            return bytes([0x55] * size)

        elif self.pattern_type == PatternType.RANDOM:
            # Zufallsdaten mit gespeichertem Seed
            # Optimiert: Bulk-Generierung statt Byte-für-Byte (~15x schneller)
            return self._random.randbytes(size)

        else:
            raise ValueError(f"Unbekannter Pattern-Typ: {self.pattern_type}")

    def reset(self):
        """
        Setzt den Generator zurück

        WICHTIG für Verifikation: Random-Generator wird mit gleichem Seed neu initialisiert,
        damit die gleichen Zufallsdaten reproduziert werden können.
        """
        if self.pattern_type == PatternType.RANDOM and self.seed is not None:
            self._random = random.Random(self.seed)

    def __repr__(self):
        if self.pattern_type == PatternType.RANDOM:
            return f"PatternGenerator({self.pattern_type}, seed={self.seed})"
        return f"PatternGenerator({self.pattern_type})"
