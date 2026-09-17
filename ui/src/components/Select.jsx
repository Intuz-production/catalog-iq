/**
 * CatalogIQ — Select Component
 *
 * Custom dropdown with dark-theme styling, keyboard support, and accessible markup.
 */

import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

/**
 * @typedef {Object} SelectOption
 * @property {string} value
 * @property {string} label
 * @property {boolean} [disabled]
 */

/**
 * @typedef {Object} SelectProps
 * @property {string} value
 * @property {(value: string) => void} onChange
 * @property {SelectOption[]} options
 * @property {string} [label]
 * @property {string} [placeholder]
 * @property {string} [className]
 * @property {"sm" | "md"} [size]
 * @property {boolean} [disabled]
 * @property {string} [ariaLabel]
 */

// This is a component to render a styled custom dropdown select
export default function Select({
  value,
  onChange,
  options,
  label,
  placeholder = "Select an option",
  className = "",
  size = "md",
  disabled = false,
  ariaLabel,
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef(null);
  const listRef = useRef(null);
  const triggerId = useId();
  const listId = useId();

  const selectedOption = options.find((option) => option.value === value);
  const displayLabel = selectedOption?.label ?? placeholder;
  const hasValue = Boolean(selectedOption);

  const enabledOptions = options.filter((option) => !option.disabled);

  useEffect(() => {
    if (!open) return undefined;

    function handlePointerDown(event) {
      if (!containerRef.current?.contains(event.target)) {
        closeMenu();
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        closeMenu();
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function closeMenu() {
    setOpen(false);
    setActiveIndex(-1);
  }

  function openMenu() {
    const selectedIndex = enabledOptions.findIndex((option) => option.value === value);
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setOpen(true);

    requestAnimationFrame(() => {
      const activeItem = listRef.current?.querySelector("[data-active='true']");
      activeItem?.scrollIntoView({ block: "nearest" });
    });
  }

  function handleSelect(option) {
    if (option.disabled) return;
    onChange(option.value);
    closeMenu();
  }

  function handleTriggerKeyDown(event) {
    if (disabled) return;

    if (event.key === "Enter" || event.key === " " || event.key === "ArrowDown") {
      event.preventDefault();
      openMenu();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      openMenu();
    }
  }

  function handleListKeyDown(event) {
    if (!open) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % enabledOptions.length);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => (prev - 1 + enabledOptions.length) % enabledOptions.length);
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const option = enabledOptions[activeIndex];
      if (option) handleSelect(option);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu();
    }
  }

  const sizeClass = size === "sm" ? "select-sm" : "select-md";

  return (
    <div
      ref={containerRef}
      className={`select-field ${sizeClass} ${className}`.trim()}
    >
      {label ? (
        <label className="select-label" htmlFor={triggerId}>
          {label}
        </label>
      ) : null}

      <button
        id={triggerId}
        type="button"
        className={`select-trigger ${open ? "select-trigger-open" : ""} ${!hasValue ? "select-trigger-placeholder" : ""}`}
        onClick={() => {
          if (disabled) return;
          if (open) closeMenu();
          else openMenu();
        }}
        onKeyDown={handleTriggerKeyDown}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={ariaLabel || label || placeholder}
        disabled={disabled}
      >
        <span className="select-trigger-text">{displayLabel}</span>
        <ChevronDown
          size={size === "sm" ? 14 : 16}
          className={`select-chevron ${open ? "select-chevron-open" : ""}`}
          aria-hidden="true"
        />
      </button>

      {open ? (
        <ul
          ref={listRef}
          id={listId}
          className="select-menu"
          role="listbox"
          aria-label={ariaLabel || label || placeholder}
          tabIndex={-1}
          onKeyDown={handleListKeyDown}
        >
          {options.map((option) => {
            const enabledIndex = enabledOptions.findIndex((item) => item.value === option.value);
            const isSelected = option.value === value;
            const isActive = enabledIndex === activeIndex;

            return (
              <li
                key={option.value || "__empty__"}
                role="option"
                aria-selected={isSelected}
                aria-disabled={option.disabled || undefined}
                data-active={isActive ? "true" : "false"}
                className={[
                  "select-option",
                  isSelected ? "select-option-selected" : "",
                  isActive ? "select-option-active" : "",
                  option.disabled ? "select-option-disabled" : "",
                ].filter(Boolean).join(" ")}
                onMouseEnter={() => {
                  if (!option.disabled && enabledIndex >= 0) {
                    setActiveIndex(enabledIndex);
                  }
                }}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => handleSelect(option)}
              >
                <span className="select-option-label">{option.label}</span>
                {isSelected ? <Check size={14} className="select-option-check" aria-hidden="true" /> : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
