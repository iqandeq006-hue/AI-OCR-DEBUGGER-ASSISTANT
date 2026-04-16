const { app, BrowserWindow, ipcMain, dialog, screen } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow;
let py;

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

  // 🔥 STRONG OVERLAY MODE (FIXED)
  mainWindow.setAlwaysOnTop(true, "screen-saver", 1);
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  mainWindow.setFullScreenable(false);

  // ✅ Click-through by default
  mainWindow.setIgnoreMouseEvents(true, { forward: true });

  // 🔥 Boot animation trigger
  mainWindow.webContents.on("did-finish-load", () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("boot-animation", true);
    }
  });

  // 🔥 Python process
  py = spawn("python", ["orchestrator.py"]);

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

        // 🔥 SAFE IPC (FIXED)
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send("from-python", parsed);
        }

      } catch {
        console.log("RAW:", msg);
      }
    });
  });

  py.stderr.on("data", (data) => {
    try {
      console.log("PY ERROR:", data.toString("utf-8"));
    } catch {
      console.log("PY ERROR: binary ignored");
    }
  });

  py.on("close", (code) => {
    console.log("Python exited:", code);
  });
}

ipcMain.on("to-python", (event, data) => {
  if (py && py.stdin && py.stdin.writable) {
    py.stdin.write(JSON.stringify(data) + "\n");
  } else {
    console.log("⚠️ Python not ready");
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