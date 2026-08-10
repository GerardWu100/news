"""Password hashing rules that the sign-in check depends on."""

from __future__ import annotations

import unittest

from news.web.passwords import (
    MINIMUM_PBKDF2_ITERATIONS,
    PASSWORD_HASH_SCHEME,
    PBKDF2_ITERATIONS,
    hash_password,
    is_password_hash,
    verify_password,
)


class PasswordHashingTests(unittest.TestCase):
    """Verify the stored format and the checks applied when reading it."""

    def test_hash_verifies_against_its_own_password(self) -> None:
        """A freshly written hash accepts the password it was built from."""
        stored_hash = hash_password("a-real-password")

        self.assertTrue(verify_password("a-real-password", stored_hash))
        self.assertFalse(verify_password("a-real-passwore", stored_hash))

    def test_hash_records_scheme_and_iteration_count(self) -> None:
        """The stored value names its scheme and cost so it can be read back."""
        stored_hash = hash_password("a-real-password")
        scheme, iterations, salt, derived_key = stored_hash.split("$")

        self.assertEqual(scheme, PASSWORD_HASH_SCHEME)
        self.assertEqual(int(iterations), PBKDF2_ITERATIONS)
        self.assertTrue(salt)
        self.assertTrue(derived_key)
        self.assertTrue(is_password_hash(stored_hash))

    def test_same_password_hashes_differently_each_time(self) -> None:
        """A fresh random salt makes two hashes of one password differ."""
        self.assertNotEqual(
            hash_password("a-real-password"),
            hash_password("a-real-password"),
        )

    def test_blank_password_is_refused(self) -> None:
        """A password of only whitespace is an operator mistake, not a secret."""
        with self.assertRaises(ValueError):
            hash_password("   ")

    def test_damaged_stored_values_fail_instead_of_raising(self) -> None:
        """Anything that is not a well-formed hash is simply rejected."""
        for damaged_value in (
            "",
            "plain-text-password",
            "pbkdf2_sha256$notanumber$c2FsdA$aGFzaA",
            "sha1$600000$c2FsdA$aGFzaA",
            "pbkdf2_sha256$600000$!!!$aGFzaA",
        ):
            with self.subTest(stored_value=damaged_value):
                self.assertFalse(verify_password("a-real-password", damaged_value))

    def test_iteration_count_below_the_floor_is_refused(self) -> None:
        """A weakened cost is rejected even when the password matches it."""
        weak_iterations = MINIMUM_PBKDF2_ITERATIONS - 1
        strong_hash = hash_password("a-real-password")
        _, _, salt, derived_key = strong_hash.split("$")
        weakened_hash = f"{PASSWORD_HASH_SCHEME}${weak_iterations}${salt}${derived_key}"

        self.assertFalse(verify_password("a-real-password", weakened_hash))


if __name__ == "__main__":
    unittest.main()
