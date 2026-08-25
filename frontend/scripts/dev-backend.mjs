import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..', '..');
const backendDir = path.join(rootDir, 'backend');
const llmRagDir = path.join(rootDir, 'llm-rag');
const requirementsFile = path.join(rootDir, 'requirements.txt');
const venvDir = path.join(rootDir, '.venv');
const isWindows = process.platform === 'win32';
const venvPython = path.join(venvDir, isWindows ? 'Scripts\\python.exe' : 'bin/python');

const MIN_MAJOR = 3;
const MIN_MINOR = 10;

function log(msg) {
  console.log(`[backend] ${msg}`);
}

function pythonVersion(cmd) {
  const res = spawnSync(cmd, ['-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], {
    encoding: 'utf8',
  });
  if (res.status !== 0 || !res.stdout) return null;
  const [major, minor] = res.stdout.trim().split('.').map(Number);
  if (!Number.isInteger(major) || !Number.isInteger(minor)) return null;
  return { major, minor, label: `${major}.${minor}` };
}

// google-genai>=2.3.0 (dipakai llm-rag) butuh Python >= 3.10, jadi `python3`
// sistem yang kebetulan masih 3.9 harus dilewati, bukan dipakai lalu gagal
// waktu pip install.
function findSystemPython() {
  const candidates = ['python3.13', 'python3.12', 'python3.11', 'python3.10', 'python3', 'python'];
  const rejected = [];
  for (const candidate of candidates) {
    const v = pythonVersion(candidate);
    if (!v) continue;
    if (v.major > MIN_MAJOR || (v.major === MIN_MAJOR && v.minor >= MIN_MINOR)) {
      return { cmd: candidate, version: v.label };
    }
    rejected.push(`${candidate} (${v.label})`);
  }
  return { cmd: null, rejected };
}

function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, { stdio: 'inherit', ...opts });
  if (res.status !== 0) {
    throw new Error(`Perintah gagal: ${cmd} ${args.join(' ')}`);
  }
}

function ensureVenv() {
  if (existsSync(venvPython)) return;
  const { cmd: systemPython, version, rejected } = findSystemPython();
  if (!systemPython) {
    const found = rejected && rejected.length ? ` Yang ketemu: ${rejected.join(', ')}.` : '';
    console.error(
      `[backend] Python ${MIN_MAJOR}.${MIN_MINOR}+ tidak ditemukan.${found}\n` +
        '[backend] Install dulu (mis. `brew install python@3.12`), lalu jalankan `npm run dev` lagi.\n' +
        '[backend] Frontend (Vite) tetap akan jalan, tapi request ke /api akan gagal sampai backend hidup.'
    );
    return;
  }
  log(`Membuat virtualenv di .venv (pakai ${systemPython}, Python ${version})...`);
  run(systemPython, ['-m', 'venv', '.venv'], { cwd: rootDir });
}

function requirementsHash() {
  return createHash('sha256').update(readFileSync(requirementsFile)).digest('hex');
}

function ensureDeps() {
  if (!existsSync(venvPython)) return; // no venv (python missing) -> skip, error already printed
  const hashFile = path.join(venvDir, '.requirements-hash');
  const currentHash = requirementsHash();
  const installedHash = existsSync(hashFile) ? readFileSync(hashFile, 'utf8').trim() : null;
  if (currentHash === installedHash) {
    log('Dependencies backend sudah terpasang & up to date.');
    return;
  }
  log('Menginstall dependencies backend (requirements.txt berubah atau belum pernah)...');
  run(venvPython, ['-m', 'pip', 'install', '-q', '--disable-pip-version-check', '-r', requirementsFile], {
    cwd: rootDir,
  });
  writeFileSync(hashFile, currentHash);
}

function startServer() {
  if (!existsSync(venvPython)) {
    log('Tidak menjalankan server backend (Python tidak tersedia). Lihat pesan di atas.');
    return;
  }
  log('Menjalankan uvicorn di http://127.0.0.1:8000 (proxied lewat Vite di /api)...');

  // PERBAIKAN 2026-08-23 — uvicorn dijalankan dengan cwd=backend/, sehingga
  // `--reload` HANYA mengawasi berkas di dalam backend/. Padahal endpoint
  // /api/explain memuat modul dari llm-rag/coldchain/. Akibatnya: setiap
  // perubahan di llm-rag (mis. explain.py) TIDAK memicu reload, dan karena
  // Python meng-cache modul yang sudah diimpor, server yang sudah lama hidup
  // terus memakai versi lama — persis gejala "Insight-nya tidak ter-update".
  // Dua direktori sekarang diawasi sekaligus.
  const child = spawn(
    venvPython,
    [
      '-m', 'uvicorn', 'api:app',
      '--host', '127.0.0.1', '--port', '8000',
      '--reload',
      '--reload-dir', backendDir,
      ...(existsSync(llmRagDir) ? ['--reload-dir', llmRagDir] : []),
    ],
    { cwd: backendDir, stdio: 'inherit' }
  );

  const forward = (signal) => {
    if (!child.killed) child.kill(signal);
  };
  process.on('SIGINT', () => forward('SIGINT'));
  process.on('SIGTERM', () => forward('SIGTERM'));

  child.on('exit', (code) => process.exit(code ?? 0));
}

try {
  ensureVenv();
  ensureDeps();
  startServer();
} catch (err) {
  console.error(`[backend] ${err.message}`);
  process.exit(1);
}
