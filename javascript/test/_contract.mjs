/**
 * The path to `contract/` — ONE place holds it, every test suite points here.
 *
 * This file used to read `../../python/tests/vectors.json`: the JavaScript package reached into
 * the Python package's insides. Publishing either package on its own breaks that path, and no
 * command reports it. Both sides now point at `contract/`, and neither owns the other's data.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const CONTRACT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'contract');

/**
 * Read one file in `contract/`. A missing file THROWS — never return empty and carry on: a suite
 * with 0 cases is still green, and everyone reading it believes something was tested.
 */
export function load(name) {
  return JSON.parse(readFileSync(join(CONTRACT_DIR, name), 'utf8'));
}
