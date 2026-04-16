const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  send: (data) => {
    ipcRenderer.send("to-python", data);
  },

  receive: (callback) => {
    const listener = (_, data) => {
      if (!data) return;
      callback(data);
    };

    ipcRenderer.removeAllListeners("from-python");
    ipcRenderer.on("from-python", listener);

    return () => {
      ipcRenderer.removeListener("from-python", listener);
    };
  },

  // 🔥 ONLY ADDITION
  receiveBoot: (callback) => {
    const listener = (_, data) => {
      callback(data);
    };

    ipcRenderer.removeAllListeners("boot-animation");
    ipcRenderer.on("boot-animation", listener);

    return () => {
      ipcRenderer.removeListener("boot-animation", listener);
    };
  },

  selectFolder: async () => {
    try {
      return await ipcRenderer.invoke("select-folder");
    } catch (err) {
      console.error("Folder selection failed:", err);
      return null;
    }
  },

  enableClick: () => {
    ipcRenderer.send("enable-click");
  },

  disableClick: () => {
    ipcRenderer.send("disable-click");
  }
});