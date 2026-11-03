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

  document.querySelectorAll("[data-hero-slider]").forEach((slider) => {
    const slides = [...slider.querySelectorAll("[data-hero-slide]")];
    const position = slider.querySelector("[data-hero-position]");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const slideEffects = [
      "hero-slide-effect-fade",
      "hero-slide-effect-from-right",
      "hero-slide-effect-from-left",
      "hero-slide-effect-zoom",
      "hero-slide-effect-reveal",
    ];
    let activeIndex = 0;
    let timer;
    const showSlide = (nextIndex) => {
      activeIndex = (nextIndex + slides.length) % slides.length;
      slides.forEach((slide, index) => {
        slide.classList.remove(...slideEffects);
        slide.hidden = index !== activeIndex;
      });
      const activeSlide = slides[activeIndex];
      if (activeSlide) {
        void activeSlide.offsetWidth;
        activeSlide.classList.add(slideEffects[activeIndex % slideEffects.length]);
      }
      if (position) position.textContent = `${activeIndex + 1} of ${slides.length}`;
    };
    const stopAutoplay = () => window.clearInterval(timer);
    const startAutoplay = () => {
      stopAutoplay();
      if (slides.length > 1 && !reducedMotion.matches && !document.hidden) {
        timer = window.setInterval(() => showSlide(activeIndex + 1), 4000);
      }
    };
    slider.querySelector("[data-hero-previous]")?.addEventListener("click", () => {
      showSlide(activeIndex - 1);
      startAutoplay();
    });
    slider.querySelector("[data-hero-next]")?.addEventListener("click", () => {
      showSlide(activeIndex + 1);
      startAutoplay();
    });
    document.addEventListener("visibilitychange", startAutoplay);
    startAutoplay();
  });

  document.querySelectorAll(".hero-file-input").forEach((input) => {
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      const preview = document.querySelector(".hero-image-frame img:not([hidden])");
      if (!file || !preview) return;
      if (preview.dataset.previewUrl) URL.revokeObjectURL(preview.dataset.previewUrl);
      preview.dataset.previewUrl = URL.createObjectURL(file);
      preview.src = preview.dataset.previewUrl;
    });
  });

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

  document.querySelectorAll("form[data-live-search] input[type='search']").forEach((input) => {
    let timer;
    input.addEventListener("input", () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const form = input.form;
        if (form && input.value !== input.defaultValue) form.requestSubmit();
      }, 350);
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
