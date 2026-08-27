(() => {
  function scrapeProduct() {
    const data = {};
    data.name = document.querySelector("#productTitle")?.innerText?.trim() ||
                document.querySelector("h1.a-size-large")?.innerText?.trim() || "";
    data.asin = (document.querySelector("[data-asin]")?.getAttribute("data-asin") ||
                 window.location.pathname.match(/\/dp\/([A-Z0-9]{10})/)?.[1]) || "";
    data.price = parseFloat(document.querySelector(".a-price .a-offscreen")?.innerText?.replace(/[^0-9.]/g, "") || "0");
    data.rating = parseFloat(document.querySelector("#acrPopover .a-size-base")?.innerText || "0");
    data.reviewCount = parseInt(document.querySelector("#acrCustomerReviewCount")?.innerText?.replace(/[^0-9]/g, "") || "0");
    data.category = document.querySelector("#wayfinding-breadcrumbs_feature_div a")?.innerText?.trim() || "";
    data.brand = document.querySelector("#bylineInfo")?.innerText?.trim()?.replace(/^(Visit the |Brand: )/i, "") || "";
    data.bullets = [...document.querySelectorAll("#feature-bullets .a-list-item")].map(el => el.innerText.trim()).filter(Boolean);
    data.description = document.querySelector("#productDescription p")?.innerText?.trim() ||
                       document.querySelector("#aplus .a-section p")?.innerText?.trim() || "";
    data.seller = document.querySelector("#sellerProfileTriggerId")?.innerText?.trim() || "";
    data.isFulfilled = !!document.querySelector("#tabular-buybox .a-color-success");
    data.image = document.querySelector("#landingImage")?.src || document.querySelector("#imgBlkFront")?.src || "";
    data.url = window.location.href;
    data.sellerInfo = {
      sellerName: document.querySelector("#sellerProfileTriggerId")?.innerText?.trim() || "",
      monthlySales: document.querySelector("#olp-upd-new .a-color-price")?.innerText?.trim() || "",
      bsr: document.querySelector("#productDetails_detailBullets_sections1 tr:nth-child(2) td:last-child")?.innerText?.trim() || "",
    };
    return data;
  }

  const data = scrapeProduct();
  if (data.name && data.asin) {
    chrome.runtime.sendMessage({ type: "SCOUT_DATA", data: data });
    const badge = document.createElement("div");
    badge.innerHTML = "Scouted by MarketLens";
    badge.style.cssText = "position:fixed;top:10px;right:10px;background:#7c3aed;color:#fff;padding:8px 16px;border-radius:6px;z-index:99999;font-size:12px;font-weight:bold;box-shadow:0 2px 8px rgba(0,0,0,0.3);";
    document.body.appendChild(badge);
    setTimeout(() => badge.remove(), 3000);
  }
})();
