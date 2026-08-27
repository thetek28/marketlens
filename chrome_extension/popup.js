let scoutedData = null;

document.getElementById("scout").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["content.js"]
  }, (results) => {
    if (chrome.runtime.lastError) {
      document.getElementById("status").className = "status error";
      document.getElementById("status").textContent = "Error: " + chrome.runtime.lastError.message;
      return;
    }
    document.getElementById("status").className = "status success";
    document.getElementById("status").textContent = "Product captured successfully!";
  });
});

document.getElementById("send").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["content.js"]
  }, (results) => {
    if (chrome.runtime.lastError) {
      document.getElementById("status").className = "status error";
      document.getElementById("status").textContent = "Error: " + chrome.runtime.lastError.message;
      return;
    }
    setTimeout(() => {
      chrome.storage.local.get("lastScout", (item) => {
        if (item.lastScout) {
          fetch("http://localhost:5000/scout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(item.lastScout)
          }).then(r => {
            document.getElementById("status").className = "status success";
            document.getElementById("status").textContent = "Sent to MarketLens!";
          }).catch(e => {
            document.getElementById("status").className = "status error";
            document.getElementById("status").textContent = "MarketLens Desktop not running";
          });
        }
      });
    }, 500);
  });
});

chrome.storage.local.get("lastScout", (item) => {
  if (item.lastScout) {
    scoutedData = item.lastScout;
    const preview = document.getElementById("preview");
    preview.style.display = "block";
    preview.innerHTML = [
      ["Name", scoutedData.name?.substring(0, 60)],
      ["ASIN", scoutedData.asin],
      ["Price", "$" + (scoutedData.price || 0).toFixed(2)],
      ["Rating", (scoutedData.rating || 0) + "★"],
      ["Reviews", scoutedData.reviewCount || 0],
      ["Brand", scoutedData.brand],
      ["Category", scoutedData.category],
      ["Seller", scoutedData.seller],
    ].map(([l, v]) => `<div class="data-row"><span class="label">${l}</span><span class="value">${v || "N/A"}</span></div>`).join("");
    document.getElementById("status").className = "status success";
    document.getElementById("status").textContent = "Product data ready";
  }
});
