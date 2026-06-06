from __future__ import annotations

import unittest

from trwm.reversible import AdditiveCoupling, BlockToken, DeltaToken


class ReversibleTests(unittest.TestCase):
    def test_additive_coupling_exact_roundtrip(self) -> None:
        def f(v, context):
            return (v[0] + context["bias"], v[1] - 2)

        def g(u, context):
            return (u[0] - context["bias"], u[1] + 3)

        coupling = AdditiveCoupling(f=f, g=g, split=2)
        for z in [(-4, 2, 9, 1), (0, 0, 0, 0), (7, -3, 4, -8)]:
            self.assertTrue(coupling.cycle_ok(z, {"bias": 5}))
            self.assertEqual(coupling.inverse(coupling.forward(z, {"bias": 5}), {"bias": 5}), z)

    def test_delta_and_block_inverse(self) -> None:
        block = BlockToken.of(
            [
                DeltaToken("x", before=1, after=3),
                DeltaToken("y", before=2, after=5),
            ]
        )
        state = {"x": 1, "y": 2, "z": 9}
        updated = block.apply(state)
        restored = block.inverse().apply(updated)

        self.assertEqual(updated, {"x": 3, "y": 5, "z": 9})
        self.assertEqual(restored, state)

    def test_delta_token_rejects_missing_read_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "read mismatch"):
            DeltaToken("x", before=None, after=1).apply({})

    def test_commutativity_uses_read_write_sets(self) -> None:
        x = BlockToken.of([DeltaToken("x", 1, 2)])
        y = BlockToken.of([DeltaToken("y", 1, 2)])
        x2 = BlockToken.of([DeltaToken("x", 2, 3)])

        self.assertTrue(x.commutes_with(y))
        self.assertFalse(x.commutes_with(x2))


if __name__ == "__main__":
    unittest.main()
