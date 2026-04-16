const { app, BrowserWindow, ipcMain, dialog, screen } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow;
let py;

function ignoreBrokenPipe(stream) {
  if (!stream || typeof stream.on !== "function") return;

  stream.on("error", (err) => {
    if (err && err.code === "EPIPE") {
      return;
    }
    throw err;
  });
}

function safeLog(...args) {
  try {
    console.log(...args);
  } catch {
    // Ignore logging failures when stdout/stderr is unavailable.
  }
}

ignoreBrokenPipe(process.stdout);
ignoreBrokenPipe(process.stderr);

process.on("uncaughtException", (err) => {
  if (err && err.code === "EPIPE") {
    return;
  }
  throw err;
});

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().bounds;

  mainWindow = new BrowserWindow({
    width: width,
    height: height,
    x: 0,
    y: 0,
    frame: false,
    transparent: true,
    hasShadow: false,
    alwaysOnTop: true,
    fullscreenable: false,
    skipTaskbar: true,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true
    }
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));

  mainWindow.setAlwaysOnTop(true, "screen-saver", 1);
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  mainWindow.setFullScreenable(false);
  mainWindow.setIgnoreMouseEvents(true, { forward: true });

  mainWindow.webContents.on("did-finish-load", () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("boot-animation", true);
    }
  });

  py = spawn("python", ["orchestrator.py"], {
    cwd: __dirname
  });

  py.stdout.on("data", (data) => {
    let text;

    try {
      text = data.toString("utf-8");
    } catch {
      return;
    }

    const messages = text.split("\n");

    messages.forEach((msg) => {
      if (!msg.trim()) return;

      try {
        const parsed = JSON.parse(msg);

        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send("from-python", parsed);
        }
      } catch {
        safeLog("RAW:", msg);
      }
    });
  });

  py.stderr.on("data", (data) => {
    try {
      safeLog("PY ERROR:", data.toString("utf-8"));
    } catch {
      safeLog("PY ERROR: binary ignored");
    }
  });

  py.on("close", (code) => {
    safeLog("Python exited:", code);
  });

  py.on("error", (err) => {
    safeLog("Python failed to start:", err.message);
  });
}

ipcMain.on("to-python", (event, data) => {
  if (py && py.stdin && py.stdin.writable) {
    py.stdin.write(JSON.stringify(data) + "\n");
  } else {
    safeLog("Python not ready");
  }
});

ipcMain.handle("select-folder", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"]
  });

  if (result.canceled) return null;
  return result.filePaths[0];
});

ipcMain.on("enable-click", () => {
  if (mainWindow) {
    mainWindow.setIgnoreMouseEvents(false);
  }
});

ipcMain.on("disable-click", () => {
  if (mainWindow) {
    mainWindow.setIgnoreMouseEvents(true, { forward: true });
  }
});

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (py) py.kill();
  app.quit();
});
