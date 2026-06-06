import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { stripTypeScriptTypes } from "node:module";

const root = new URL("..", import.meta.url).pathname;
const srcDir = join(root, "src");
const distDir = join(root, "dist");

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

await rm(distDir, { recursive: true, force: true });
await mkdir(distDir, { recursive: true });

for (const file of await collectTsFiles(srcDir)) {
  const rel = relative(srcDir, file).replace(/\.ts$/, ".js");
  const outFile = join(distDir, rel);
  const source = await readFile(file, "utf8");
  const js = trimTrailingWhitespace(stripTypeScriptTypes(source, { mode: "strip" }));
  await mkdir(dirname(outFile), { recursive: true });
  await writeFile(outFile, js, "utf8");
}

await writeFile(
  join(distDir, "README.md"),
  "Generated ESM build. Source lives in ../src. Rebuild with `node --disable-warning=ExperimentalWarning scripts/build.mjs`.\n",
  "utf8",
);

function trimTrailingWhitespace(source) {
  return source.split("\n").map((line) => line.trimEnd()).join("\n");
}
