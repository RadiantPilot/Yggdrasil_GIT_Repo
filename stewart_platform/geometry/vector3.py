# vector3.py
# ==========
# 3D-vektorklasse for bruk i geometri- og kinematikkberegninger.
# Brukes til å representere posisjoner, krefter, akselerasjon,
# vinkelhastighet og andre tredimensjonale størrelser.

from __future__ import annotations

import numpy as np


class Vector3:
    """Tredimensjonal vektor med aritmetiske operasjoner.

    Brukes gjennomgående i systemet for å representere 3D-størrelser
    som posisjoner (mm), akselerasjon (m/s²), vinkelhastighet (grader/s)
    og retningsvektorer. Gir et typsikkert alternativ til rå numpy-arrays.
    """

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        """Opprett en ny 3D-vektor.

        Args:
            x: X-komponent.
            y: Y-komponent.
            z: Z-komponent.
        """
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other: Vector3) -> Vector3:
        """Addér to vektorer komponentvis.

        Args:
            other: Vektoren som skal adderes.

        Returns:
            Ny vektor som er summen av de to.
        """
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3) -> Vector3:
        """Subtraher en vektor fra denne.

        Args:
            other: Vektoren som skal subtraheres.

        Returns:
            Ny vektor som er differansen.
        """
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vector3:
        """Multipliser vektoren med en skalar.

        Args:
            scalar: Skalarverdien å multiplisere med.

        Returns:
            Ny vektor skalert med den gitte verdien.
        """
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __neg__(self) -> Vector3:
        """Neger alle komponenter i vektoren.

        Returns:
            Ny vektor med inverterte fortegn.
        """
        return Vector3(-self.x, -self.y, -self.z)

    def magnitude(self) -> float:
        """Beregn vektorens lengde (euklidsk norm).

        Returns:
            Lengden av vektoren: sqrt(x² + y² + z²).
        """
        return float(np.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2))

    def normalized(self) -> Vector3:
        """Returner en normalisert kopi av vektoren (lengde 1).

        Returns:
            Enhetsvektor med samme retning.

        Raises:
            ValueError: Hvis vektoren har lengde 0.
        """
        mag = self.magnitude()
        if mag == 0.0:
            raise ValueError("Kan ikke normalisere en nullvektor.")
        return Vector3(self.x / mag, self.y / mag, self.z / mag)

    def dot(self, other: Vector3) -> float:
        """Beregn prikkproduktet mellom to vektorer.

        Args:
            other: Den andre vektoren.

        Returns:
            Skalarverdi: x1*x2 + y1*y2 + z1*z2.
        """
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector3) -> Vector3:
        """Beregn kryssproduktet mellom to vektorer.

        Resultatet er en vektor vinkelrett på begge inputvektorer.

        Args:
            other: Den andre vektoren.

        Returns:
            Ny vektor som er kryssproduktet.
        """
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def to_array(self) -> np.ndarray:
        """Konverter til numpy array [x, y, z].

        Returns:
            numpy.ndarray med 3 elementer.
        """
        return np.array([self.x, self.y, self.z])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> Vector3:
        """Opprett en Vector3 fra et numpy array.

        Args:
            arr: numpy array med minst 3 elementer.

        Returns:
            Ny Vector3 med verdiene fra arrayet.
        """
        return cls(float(arr[0]), float(arr[1]), float(arr[2]))

    def __repr__(self) -> str:
        """Tekstrepresentasjon for feilsøking."""
        return f"Vector3(x={self.x:.4f}, y={self.y:.4f}, z={self.z:.4f})"
