(() => {
  const toggle = document.querySelector(".nav-toggle");
  const navigation = document.querySelector(".primary-nav");
  if (toggle && navigation) {
    toggle.addEventListener("click", () => {
      const isExpanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!isExpanded));
      navigation.classList.toggle("is-open", !isExpanded);
    });
  }

  document.querySelectorAll("[data-toast]").forEach((toast) => {
    const dismiss = () => {
      toast.classList.add("is-leaving");
      window.setTimeout(() => toast.remove(), 220);
    };
    const timer = window.setTimeout(dismiss, 4000);
    toast.querySelector(".toast-dismiss")?.addEventListener("click", () => {
      window.clearTimeout(timer);
      dismiss();
    });
  });

  document.querySelectorAll("[data-faq-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      const selected = button.dataset.faqFilter;
      document.querySelectorAll("[data-faq-filter]").forEach((filter) => {
        const isActive = filter === button;
        filter.classList.toggle("is-active", isActive);
        filter.setAttribute("aria-pressed", String(isActive));
      });
      document.querySelectorAll("[data-faq-category]").forEach((category) => {
        category.hidden = selected !== "all" && category.dataset.faqCategory !== selected;
      });
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll("[data-auto-open]").forEach((dialog) => {
    if (typeof dialog.showModal === "function") dialog.showModal();
  });
  document.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });

  document.querySelectorAll("[data-syllabus-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      const selectedId = tab.dataset.syllabusTab;
      document.querySelectorAll("[data-syllabus-tab]").forEach((otherTab) => {
        const isSelected = otherTab === tab;
        otherTab.classList.toggle("is-active", isSelected);
        otherTab.setAttribute("aria-selected", String(isSelected));
        otherTab.setAttribute("tabindex", isSelected ? "0" : "-1");
      });
      document.querySelectorAll("[data-syllabus-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.syllabusPanel !== selectedId;
      });
    });
    tab.addEventListener("keydown", (event) => {
      const tabs = [...document.querySelectorAll("[data-syllabus-tab]")];
      const currentIndex = tabs.indexOf(tab);
      let nextIndex;
      if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
      if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = tabs.length - 1;
      if (nextIndex !== undefined) {
        event.preventDefault();
        tabs[nextIndex].focus();
        tabs[nextIndex].click();
      }
    });
  });
})();
