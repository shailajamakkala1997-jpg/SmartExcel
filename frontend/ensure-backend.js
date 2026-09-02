import http from 'http';
import { exec, spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 8005;
const BACKEND_DIR = path.resolve(__dirname, '../backend');

function checkBackendOnline() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${PORT}/`, (res) => {
      resolve(res.statusCode === 200 || res.statusCode === 404);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function startBackendIfNeeded() {
  const isOnline = await checkBackendOnline();
  if (isOnline) {
    console.log(`\x1b[32m[SmartExcel]\x1b[0m Python FastAPI backend is already running on port ${PORT}.`);
    return;
  }

  console.log(`\x1b[33m[SmartExcel]\x1b[0m Python FastAPI backend is not running on port ${PORT}. Auto-starting backend...`);

  // Path to python in virtualenv vs system python
  const venvPythonWin = path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe');
  const venvPythonNix = path.join(BACKEND_DIR, 'venv', 'bin', 'python');
  
  let pythonCmd = 'python';
  if (fs.existsSync(venvPythonWin)) {
    pythonCmd = venvPythonWin;
  } else if (fs.existsSync(venvPythonNix)) {
    pythonCmd = venvPythonNix;
  }

  if (process.platform === 'win32') {
    const command = `start "SmartExcel Backend" "${pythonCmd}" -m uvicorn main:app --host 127.0.0.1 --port ${PORT}`;
    exec(command, { cwd: BACKEND_DIR });
  } else {
    const child = spawn(pythonCmd, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
      cwd: BACKEND_DIR,
      detached: true,
      stdio: 'ignore'
    });
    child.unref();
  }

  // Give backend up to 6 seconds to spin up
  for (let i = 0; i < 12; i++) {
    await new Promise((r) => setTimeout(r, 500));
    const ready = await checkBackendOnline();
    if (ready) {
      console.log(`\x1b[32m[SmartExcel]\x1b[0m Python FastAPI backend started successfully on port ${PORT}!`);
      return;
    }
  }

  console.log(`\x1b[33m[SmartExcel]\x1b[0m Backend launch initiated. Proceeding...`);
}

try {
  await startBackendIfNeeded();
} catch (err) {
  console.error('[SmartExcel] Auto-start backend warning:', err.message);
}

