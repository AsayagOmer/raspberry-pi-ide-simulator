// Raspberry Pi 5 simulator: a Pseudoterminal backed by the Python backend (python -m pi5sim).
const vscode = require('vscode');
const cp = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

/** Python sources: bundled into ./python for a packaged .vsix, else the repo's ../src. */
function pythonSrcDir(context) {
  const bundled = path.join(context.extensionPath, 'python');
  return fs.existsSync(bundled) ? bundled : path.join(context.extensionPath, '..', 'src');
}

function workspaceHome() {
  const f = vscode.workspace.workspaceFolders;
  return f && f.length ? f[0].uri.fsPath : os.homedir();
}

let extensionRoot = '';

function pythonPath() {
  const configured = vscode.workspace.getConfiguration('piSim').get('pythonPath');
  if (configured) return configured;
  // The workspace .venv first, then the simulator repo's .venv (when run from a checkout).
  for (const dir of [workspaceHome(), path.join(extensionRoot, '..')]) {
    for (const p of [path.join(dir, '.venv', 'Scripts', 'python.exe'), path.join(dir, '.venv', 'bin', 'python')]) {
      if (fs.existsSync(p)) return p;
    }
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

/** One backend process; fans its JSON messages out to listeners. */
class Backend {
  constructor(context) {
    this.context = context;
    extensionRoot = context.extensionPath;
    this.listeners = new Set();
    this.proc = null;
  }

  start() {
    if (this.proc) return;
    const src = pythonSrcDir(this.context);
    const env = {
      ...process.env,
      PYTHONPATH: src,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUNBUFFERED: '1',
      PI5SIM_WEBCAM: vscode.workspace.getConfiguration('piSim').get('useWebcam') ? '1' : '0',
    };
    const proc = cp.spawn(pythonPath(), ['-m', 'pi5sim', workspaceHome()], { cwd: path.dirname(src), env });
    this.proc = proc;
    let buf = '';
    proc.stdout.setEncoding('utf8');
    proc.stdout.on('data', (chunk) => {
      buf += chunk;
      let i;
      while ((i = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, i);
        buf = buf.slice(i + 1);
        if (!line.trim()) continue;
        try { this.emit(JSON.parse(line)); } catch { this.emit({ t: 'term', data: line + '\r\n' }); }
      }
    });
    proc.stderr.setEncoding('utf8');
    proc.stderr.on('data', (d) => this.emit({ t: 'term', data: d.replace(/\r?\n/g, '\r\n') }));
    proc.on('error', (e) => this.emit({ t: 'term', data: `\r\nCould not start ${pythonPath()}: ${e.message}\r\nSet "piSim.pythonPath" to a Python 3.10+ with the simulator requirements installed.\r\n` }));
    proc.on('exit', (code) => {
      if (this.proc === proc) this.proc = null;
      this.emit({ t: 'exit', code });
    });
  }

  send(msg) {
    if (this.proc && this.proc.stdin.writable) this.proc.stdin.write(JSON.stringify(msg) + '\n');
  }

  emit(msg) { for (const l of this.listeners) l(msg); }

  on(listener) {
    this.listeners.add(listener);
    return { dispose: () => this.listeners.delete(listener) };
  }

  stop() {
    if (this.proc) this.proc.kill();
    this.proc = null;
  }
}

function createPty(backend) {
  const writeEmitter = new vscode.EventEmitter();
  const closeEmitter = new vscode.EventEmitter();
  let sub;
  return {
    onDidWrite: writeEmitter.event,
    onDidClose: closeEmitter.event,
    open() {
      sub = backend.on((msg) => {
        if (msg.t === 'term') writeEmitter.fire(msg.data);
        if (msg.t === 'exit') writeEmitter.fire(`\r\n[simulator exited with code ${msg.code}]\r\n`);
      });
      backend.start();
    },
    handleInput(data) { backend.send({ t: 'stdin', data }); },
    close() {
      if (sub) sub.dispose();
      backend.stop();
    },
  };
}

function activate(context) {
  const backend = new Backend(context);
  context.subscriptions.push({ dispose: () => backend.stop() });

  const terminalOptions = () => ({ name: 'Raspberry Pi 5', pty: createPty(backend), iconPath: new vscode.ThemeIcon('circuit-board') });
  let terminal;
  const openTerminal = () => {
    if (!terminal || terminal.exitStatus !== undefined) terminal = vscode.window.createTerminal(terminalOptions());
    terminal.show();
  };
  context.subscriptions.push(
    vscode.commands.registerCommand('piSim.openTerminal', openTerminal),
    vscode.window.registerTerminalProfileProvider('piSim.terminal', {
      provideTerminalProfile: () => new vscode.TerminalProfile(terminalOptions()),
    }),
    vscode.window.onDidCloseTerminal((t) => { if (t === terminal) terminal = undefined; }),
  );
  return { backend, openTerminal };
}

function deactivate() {}

module.exports = { activate, deactivate, Backend };
