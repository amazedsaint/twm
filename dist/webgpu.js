import {
                            
                  
  affineForward,
  affineInverse,
  assertAffineI32Safe,
  i32ArrayToTicks,
} from "./reversible.js";

                                                      

export function webGpuAvailable()          {
  return Boolean(globalThis.navigator?.gpu);
}

export function affineCouplingWgsl(direction                   )         {
  if (direction === "forward") {
    return `
struct Params {
  split: u32,
  gainF: i32,
  biasF: i32,
  gainG: i32,
  biasG: i32,
};
@group(0) @binding(0) var<storage, read_write> data: array<i32>;
@group(0) @binding(1) var<uniform> params: Params;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  let i = id.x;
  if (i >= params.split) { return; }
  let u_index = i;
  let v_index = params.split + i;
  let du = params.gainF * data[v_index] + params.biasF;
  data[u_index] = data[u_index] + du;
  let dv = params.gainG * data[u_index] + params.biasG;
  data[v_index] = data[v_index] + dv;
}`;
  }
  return `
struct Params {
  split: u32,
  gainF: i32,
  biasF: i32,
  gainG: i32,
  biasG: i32,
};
@group(0) @binding(0) var<storage, read_write> data: array<i32>;
@group(0) @binding(1) var<uniform> params: Params;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  let i = id.x;
  if (i >= params.split) { return; }
  let u_index = i;
  let v_index = params.split + i;
  let dv = params.gainG * data[u_index] + params.biasG;
  data[v_index] = data[v_index] - dv;
  let du = params.gainF * data[v_index] + params.biasF;
  data[u_index] = data[u_index] - du;
}`;
}

export function runAffineCouplingCpu(
  z            ,
  params                      ,
  direction                   ,
)             {
  return direction === "forward" ? affineForward(z, params) : affineInverse(z, params);
}

export async function runAffineCouplingWebGpu(
  z            ,
  params                      ,
  direction                   ,
)                      {
  const gpu = globalThis.navigator?.gpu;
  if (!gpu) {
    throw new Error("WebGPU is not available in this runtime");
  }
  if (z.length !== params.split * 2) {
    throw new RangeError("WebGPU affine coupling requires equal halves");
  }
  const data = assertAffineI32Safe(z, params, direction);
  const adapter = await gpu.requestAdapter();
  if (!adapter) {
    throw new Error("WebGPU adapter request failed");
  }
  const device = await adapter.requestDevice();
  const shader = device.createShaderModule({ code: affineCouplingWgsl(direction) });
  const pipeline = device.createComputePipeline({
    layout: "auto",
    compute: { module: shader, entryPoint: "main" },
  });
  const storageBuffer = device.createBuffer({
    size: data.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST,
  });
  device.queue.writeBuffer(storageBuffer, 0, data);
  const paramsBuffer = device.createBuffer({
    size: 20,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  });
  const paramsData = new ArrayBuffer(20);
  const view = new DataView(paramsData);
  view.setUint32(0, params.split, true);
  view.setInt32(4, Number(params.gainF), true);
  view.setInt32(8, Number(params.biasF), true);
  view.setInt32(12, Number(params.gainG), true);
  view.setInt32(16, Number(params.biasG), true);
  device.queue.writeBuffer(paramsBuffer, 0, paramsData);
  const outputBuffer = device.createBuffer({
    size: data.byteLength,
    usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
  });
  const bindGroup = device.createBindGroup({
    layout: pipeline.getBindGroupLayout(0),
    entries: [
      { binding: 0, resource: { buffer: storageBuffer } },
      { binding: 1, resource: { buffer: paramsBuffer } },
    ],
  });
  const encoder = device.createCommandEncoder();
  const pass = encoder.beginComputePass();
  pass.setPipeline(pipeline);
  pass.setBindGroup(0, bindGroup);
  pass.dispatchWorkgroups(Math.ceil(params.split / 64));
  pass.end();
  encoder.copyBufferToBuffer(storageBuffer, 0, outputBuffer, 0, data.byteLength);
  device.queue.submit([encoder.finish()]);
  await outputBuffer.mapAsync(GPUMapMode.READ);
  const result = new Int32Array(outputBuffer.getMappedRange().slice(0));
  outputBuffer.unmap();
  storageBuffer.destroy();
  paramsBuffer.destroy();
  outputBuffer.destroy();
  return i32ArrayToTicks(result);
}
