(() => {
  document.querySelectorAll("[data-rich-text-editor]").forEach((wrapper) => {
    const source = wrapper.querySelector("textarea");
    const canvas = wrapper.querySelector("[data-editor-canvas]");
    const toolbar = wrapper.querySelector("[data-rich-toolbar]");
    const form = wrapper.closest("form");
    if (!source || !canvas || !toolbar || !form) return;

    canvas.innerHTML = source.value;
    source.hidden = true;
    source.classList.add("rich-text-source");
    canvas.hidden = false;
    toolbar.hidden = false;

    let savedRange;
    const rememberSelection = () => {
      const selection = window.getSelection();
      if (selection?.rangeCount && canvas.contains(selection.getRangeAt(0).commonAncestorContainer)) {
        savedRange = selection.getRangeAt(0).cloneRange();
      }
    };
    const restoreSelection = () => {
      canvas.focus();
      if (savedRange && canvas.contains(savedRange.commonAncestorContainer)) {
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(savedRange);
      }
    };
    const syncSource = () => {
      source.value = canvas.innerHTML;
    };
    const normalizeFontSizes = () => {
      canvas.querySelectorAll("font[size]").forEach((font) => {
        const size = font.getAttribute("size");
        const textSize = size === "1" || size === "2" ? "small"
          : size === "5" ? "large"
            : size === "6" || size === "7" ? "xlarge" : "normal";
        const span = document.createElement("span");
        span.dataset.textSize = textSize;
        font.replaceWith(span);
        while (font.firstChild) span.append(font.firstChild);
      });
    };

    canvas.addEventListener("keyup", rememberSelection);
    canvas.addEventListener("mouseup", rememberSelection);
    canvas.addEventListener("input", syncSource);
    canvas.addEventListener("paste", (event) => {
      event.preventDefault();
      const text = event.clipboardData?.getData("text/plain") || "";
      document.execCommand("insertText", false, text);
      syncSource();
    });
    document.addEventListener("selectionchange", rememberSelection);
    toolbar.addEventListener("mousedown", (event) => {
      if (event.target.closest("button")) event.preventDefault();
    });
    toolbar.querySelectorAll("[data-editor-command]").forEach((button) => {
      button.addEventListener("click", () => {
        restoreSelection();
        document.execCommand(button.dataset.editorCommand, false);
        syncSource();
        rememberSelection();
      });
    });
    toolbar.querySelector("[data-editor-link]")?.addEventListener("click", () => {
      restoreSelection();
      const href = window.prompt("Enter a link URL");
      if (href?.trim()) document.execCommand("createLink", false, href.trim());
      syncSource();
      rememberSelection();
    });
    toolbar.querySelector("[data-editor-format]")?.addEventListener("change", (event) => {
      restoreSelection();
      document.execCommand("formatBlock", false, event.target.value);
      event.target.value = "p";
      syncSource();
      rememberSelection();
    });
    toolbar.querySelector("[data-editor-size]")?.addEventListener("change", (event) => {
      const commandSizes = { small: "2", normal: "3", large: "5", xlarge: "7" };
      if (!commandSizes[event.target.value]) return;
      restoreSelection();
      document.execCommand("fontSize", false, commandSizes[event.target.value]);
      normalizeFontSizes();
      event.target.value = "";
      syncSource();
      rememberSelection();
    });
    form.addEventListener("submit", syncSource);
  });

  const toggle = document.querySelector(".nav-toggle");
  const navigation = document.querySelector(".primary-nav");
  if (toggle && navigation) {
    toggle.addEventListener("click", () => {
      const isExpanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!isExpanded));
      navigation.classList.toggle("is-open", !isExpanded);
    });
  }

  document.querySelectorAll('input[type="password"]').forEach((input) => {
    const wrapper = document.createElement("span");
    wrapper.className = "password-input-wrap";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.append(input);

    const button = document.createElement("button");
    button.className = "password-visibility-toggle";
    button.type = "button";
    button.setAttribute("aria-label", "Show password");
    button.setAttribute("aria-pressed", "false");
    if (input.id) button.setAttribute("aria-controls", input.id);
    const icon = document.createElement("i");
    icon.className = "bi bi-eye";
    icon.setAttribute("aria-hidden", "true");
    button.append(icon);
    wrapper.append(button);

    button.addEventListener("click", () => {
      const isVisible = input.type === "password";
      input.type = isVisible ? "text" : "password";
      button.setAttribute("aria-label", isVisible ? "Hide password" : "Show password");
      button.setAttribute("aria-pressed", String(isVisible));
      icon.classList.toggle("bi-eye", !isVisible);
      icon.classList.toggle("bi-eye-slash", isVisible);
    });
  });

  document.querySelectorAll("[data-custom-date-picker]").forEach((input) => {
    const wrapper = document.createElement("span");
    wrapper.className = "date-picker-wrap";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.append(input);

    const toggle = document.createElement("button");
    toggle.className = "date-picker-toggle";
    toggle.type = "button";
    toggle.setAttribute("aria-label", "Choose date of birth");
    toggle.setAttribute("aria-haspopup", "dialog");
    toggle.setAttribute("aria-expanded", "false");
    const icon = document.createElement("i");
    icon.className = "bi bi-calendar3";
    icon.setAttribute("aria-hidden", "true");
    toggle.append(icon);
    wrapper.append(toggle);

    const calendar = document.createElement("div");
    calendar.className = "date-picker-calendar";
    calendar.hidden = true;
    calendar.setAttribute("role", "dialog");
    calendar.setAttribute("aria-label", "Choose date of birth");
    const header = document.createElement("div");
    header.className = "date-picker-header";
    const previous = document.createElement("button");
    previous.type = "button";
    previous.className = "date-picker-month-button";
    previous.setAttribute("aria-label", "Previous month");
    previous.innerHTML = '<i class="bi bi-chevron-left" aria-hidden="true"></i>';
    const monthLabel = document.createElement("strong");
    monthLabel.className = "date-picker-month";
    monthLabel.setAttribute("aria-live", "polite");
    const next = document.createElement("button");
    next.type = "button";
    next.className = "date-picker-month-button";
    next.setAttribute("aria-label", "Next month");
    next.innerHTML = '<i class="bi bi-chevron-right" aria-hidden="true"></i>';
    header.append(previous, monthLabel, next);
    const grid = document.createElement("div");
    grid.className = "date-picker-grid";
    grid.setAttribute("role", "grid");
    ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].forEach((day) => {
      const label = document.createElement("span");
      label.className = "date-picker-weekday";
      label.setAttribute("role", "columnheader");
      label.textContent = day;
      grid.append(label);
    });
    calendar.append(header, grid);
    wrapper.append(calendar);

    const parseDate = (value) => {
      const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
      if (!match) return null;
      const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
      return date.getFullYear() === Number(match[1])
        && date.getMonth() === Number(match[2]) - 1
        && date.getDate() === Number(match[3])
        ? date
        : null;
    };
    const formatDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let visibleMonth = parseDate(input.value) || new Date();
    visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), 1);
    const closeCalendar = (returnFocus = false) => {
      calendar.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      if (returnFocus) toggle.focus();
    };
    const renderCalendar = () => {
      const year = visibleMonth.getFullYear();
      const month = visibleMonth.getMonth();
      monthLabel.textContent = visibleMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" });
      next.disabled = visibleMonth.getFullYear() === today.getFullYear()
        && visibleMonth.getMonth() === today.getMonth();
      grid.querySelectorAll(".date-picker-day, .date-picker-blank").forEach((item) => item.remove());
      const firstDay = new Date(year, month, 1).getDay();
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      for (let blank = 0; blank < firstDay; blank += 1) {
        const cell = document.createElement("span");
        cell.className = "date-picker-blank";
        cell.setAttribute("role", "gridcell");
        grid.append(cell);
      }
      for (let day = 1; day <= daysInMonth; day += 1) {
        const date = new Date(year, month, day);
        const dayButton = document.createElement("button");
        dayButton.className = "date-picker-day";
        dayButton.type = "button";
        dayButton.setAttribute("role", "gridcell");
        dayButton.setAttribute("aria-label", date.toLocaleDateString(undefined, { dateStyle: "long" }));
        const value = formatDate(date);
        dayButton.setAttribute("aria-pressed", String(input.value === value));
        if (input.value === value) dayButton.classList.add("is-selected");
        if (date.getTime() === today.getTime()) dayButton.classList.add("is-today");
        dayButton.disabled = date > today;
        dayButton.textContent = String(day);
        dayButton.addEventListener("click", () => {
          input.value = value;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
          closeCalendar(true);
        });
        grid.append(dayButton);
      }
    };
    previous.addEventListener("click", () => {
      visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1);
      renderCalendar();
    });
    next.addEventListener("click", () => {
      const latestAllowed = new Date(today.getFullYear(), today.getMonth(), 1);
      const nextMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1);
      if (nextMonth <= latestAllowed) {
        visibleMonth = nextMonth;
        renderCalendar();
      }
    });
    toggle.addEventListener("click", () => {
      if (!calendar.hidden) {
        closeCalendar();
        return;
      }
      const selectedDate = parseDate(input.value);
      visibleMonth = selectedDate
        ? new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1)
        : new Date(today.getFullYear(), today.getMonth(), 1);
      renderCalendar();
      calendar.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      calendar.querySelector(".date-picker-day:not(:disabled)")?.focus();
    });
    calendar.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeCalendar(true);
    });
    document.addEventListener("click", (event) => {
      if (!wrapper.contains(event.target) && !calendar.hidden) closeCalendar();
    });
    renderCalendar();
  });

  document.querySelectorAll("[data-topic-formset]").forEach((form) => {
    const list = form.querySelector("[data-topic-list]");
    const template = form.querySelector("template[data-topic-empty-form]");
    const totalForms = form.querySelector('input[name$="-TOTAL_FORMS"]');
    const addButton = form.querySelector("[data-add-topic]");
    if (!list || !template || !totalForms || !addButton) return;
    addButton.addEventListener("click", () => {
      const index = Number(totalForms.value);
      const fragment = document.createElement("div");
      fragment.innerHTML = template.innerHTML.replaceAll("__prefix__", String(index));
      list.append(fragment.firstElementChild);
      totalForms.value = String(index + 1);
    });
  });

  document.querySelectorAll("[data-image-formset]").forEach((form) => {
    const list = form.querySelector("[data-image-list]");
    const template = form.querySelector("template[data-image-empty-form]");
    const totalForms = form.querySelector('input[name$="-TOTAL_FORMS"]');
    const addButton = form.querySelector("[data-add-image]");
    if (!list || !template || !totalForms || !addButton) return;
    addButton.addEventListener("click", () => {
      const index = Number(totalForms.value);
      const fragment = document.createElement("div");
      fragment.innerHTML = template.innerHTML.replaceAll("__prefix__", String(index));
      list.append(fragment.firstElementChild);
      totalForms.value = String(index + 1);
    });
  });

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
