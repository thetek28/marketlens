chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SCOUT_DATA") {
    chrome.storage.local.set({ lastScout: message.data });
    sendResponse({ success: true });
  }
});
