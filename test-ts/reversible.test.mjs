import assert from "node:assert/strict";
import test from "node:test";

import {
  AdditiveCoupling,
  BlockToken,
  DeltaToken,
  affineCouplingWgsl,
  affineForward,
  affineInverse,
  assertAffineI32Safe,
  assertI32Ticks,
  equalTicks,
  runAffineCouplingCpu,
  toTicks,
  fromTicks,
} from "../dist/index.js";

test("dyadic tick conversion is exact for binary fractions", () => {
  const tick = toTicks(1.25, 4);
  assert.equal(tick, 20n);
  assert.equal(fromTicks(tick, 4), 1.25);
});

test("additive coupling round trips exactly over bigint ticks", () => {
  const coupling = new AdditiveCoupling(
    (v, context) => v.map((tick) => tick + BigInt(context.bias)),
    (uNext) => uNext.map((tick) => -2n * tick + 3n),
    2,
  );
  const z = [4n, -2n, 7n, 1n];
  const forward = coupling.forward(z, { bias: 5 });
  const inverse = coupling.inverse(forward, { bias: 5 });

  assert.deepEqual(inverse, z);
  assert.equal(coupling.cycleOk(z, { bias: 5 }), true);
});

test("affine CPU fallback matches forward inverse cycle", () => {
  const params = { split: 2, gainF: 1n, biasF: 2n, gainG: -1n, biasG: 3n };
  const z = [1n, 2n, 5n, -1n];
  const forward = affineForward(z, params);
  const inverse = affineInverse(forward, params);
  const viaRunner = runAffineCouplingCpu(z, params, "forward");

  assert.deepEqual(inverse, z);
  assert.deepEqual(viaRunner, forward);
  assert.equal(equalTicks(runAffineCouplingCpu(forward, params, "inverse"), z), true);
});

test("delta and block tokens round trip and reject missing read keys", () => {
  const block = BlockToken.of([
    new DeltaToken("x", 1, 3),
    new DeltaToken("y", 2, 5),
  ]);
  const state = { x: 1, y: 2, z: 9 };
  const updated = block.apply(state);
  const restored = block.inverse().apply(updated);

  assert.deepEqual(updated, { x: 3, y: 5, z: 9 });
  assert.deepEqual(restored, state);
  assert.throws(() => new DeltaToken("missing", undefined, 1).apply({}), /read mismatch/);
});

test("WebGPU i32 admission rejects unsafe integer ranges", () => {
  assert.deepEqual(Array.from(assertI32Ticks([1n, -2n])), [1, -2]);
  assert.throws(() => assertI32Ticks([2n ** 40n]), /outside signed i32/);
});

test("WebGPU affine admission rejects overflowing intermediates", () => {
  const params = { split: 1, gainF: 2n, biasF: 0n, gainG: 1n, biasG: 0n };
  assert.throws(() => assertAffineI32Safe([0n, 2n ** 30n], params, "forward"), /du 0 is outside signed i32/);
  assert.deepEqual(Array.from(assertAffineI32Safe([1n, 2n], params, "forward")), [1, 2]);
});

test("WGSL kernels encode the exact inverse order", () => {
  const forward = affineCouplingWgsl("forward");
  const inverse = affineCouplingWgsl("inverse");

  assert.match(forward, /data\[u_index\] = data\[u_index\] \+ du/);
  assert.match(forward, /data\[v_index\] = data\[v_index\] \+ dv/);
  assert.match(inverse, /data\[v_index\] = data\[v_index\] - dv/);
  assert.match(inverse, /data\[u_index\] = data\[u_index\] - du/);
});
