import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { tmpdir } from "node:os";
import { stripTypeScriptTypes } from "node:module";

const root = new URL("..", import.meta.url).pathname;
const srcDir = join(root, "src");
const distDir = join(root, "dist");
const tmpDir = join(tmpdir(), `trwm-dist-check-${Date.now()}`);

async function collectTsFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectTsFiles(path));
    } else if (entry.isFile() && entry.name.endsWith(".ts")) {
      files.push(path);
    }
  }
  return files;
}

try {
  const mismatches = [];
  for (const file of await collectTsFiles(srcDir)) {
    const rel = relative(srcDir, file).replace(/\.ts$/, ".js");
    const outFile = join(tmpDir, rel);
    const source = await readFile(file, "utf8");
    const js = trimTrailingWhitespace(stripTypeScriptTypes(source, { mode: "strip" }));
    await mkdir(dirname(outFile), { recursive: true });
    await writeFile(outFile, js, "utf8");
    const current = await readFile(join(distDir, rel), "utf8").catch(() => null);
    if (current !== js) {
      mismatches.push(rel);
    }
  }
  if (mismatches.length > 0) {
    console.error(`dist is stale for: ${mismatches.join(", ")}`);
    process.exit(1);
  }
} finally {
  await rm(tmpDir, { recursive: true, force: true });
}

function trimTrailingWhitespace(source) {
  return source.split("\n").map((line) => line.trimEnd()).join("\n");
}
