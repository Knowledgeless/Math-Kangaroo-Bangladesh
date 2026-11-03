(() => {
  const storageKey = "mkbd-theme";
  const savedTheme = window.localStorage.getItem(storageKey);
  const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll(".theme-toggle").forEach((button) => {
      button.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} theme`);
      button.setAttribute("aria-pressed", String(theme === "dark"));
      const icon = button.querySelector(".theme-icon");
      if (icon) icon.textContent = theme === "dark" ? "☼" : "◐";
    });
  };

  applyTheme(savedTheme === "dark" ? "dark" : "light");
  document.addEventListener("click", (event) => {
    const button = event.target.closest(".theme-toggle");
    if (!button) return;
    const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    window.localStorage.setItem(storageKey, nextTheme);
    applyTheme(nextTheme);
  });
})();
