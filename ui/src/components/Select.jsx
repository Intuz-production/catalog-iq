/**
 * CatalogIQ — Select Component
 *
 * Custom dropdown with dark-theme styling, keyboard support, and accessible markup.
 * Optional searchable filtering for long option lists.
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, Search } from "lucide-react";

const MENU_MAX_HEIGHT = 260;
const MENU_OFFSET = 6;

/**
 * @typedef {Object} SelectOption
 * @property {string} value
 * @property {string} label
 * @property {boolean} [disabled]
 * @property {boolean} [pinned] Keep visible even when search has no matches
 */

/**
 * @typedef {Object} SelectProps
 * @property {string} value
 * @property {(value: string, context?: { searchQuery?: string }) => void} onChange
 * @property {SelectOption[]} options
 * @property {string} [label]
 * @property {string} [placeholder]
 * @property {string} [className]
 * @property {"sm" | "md"} [size]
 * @property {boolean} [disabled]
 * @property {string} [ariaLabel]
 * @property {boolean} [searchable]
 * @property {string} [searchPlaceholder]
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
  searchable = false,
  searchPlaceholder = "Search...",
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [menuStyle, setMenuStyle] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const containerRef = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const listRef = useRef(null);
  const searchInputRef = useRef(null);
  const triggerId = useId();
  const listId = useId();

  const selectedOption = options.find((option) => option.value === value);
  const displayLabel = selectedOption?.label ?? placeholder;
  const hasValue = Boolean(selectedOption);

  const filteredOptions = useMemo(() => {
    const pinned = options.filter((option) => option.pinned);
    if (!searchable || !searchQuery.trim()) return options;

    const query = searchQuery.trim().toLowerCase();
    const matched = options.filter(
      (option) =>
        !option.pinned &&
        String(option.label || "").toLowerCase().includes(query)
    );

    // Always keep pinned options (e.g. "New group") when search has no matches.
    if (matched.length === 0) {
      return pinned.length > 0 ? pinned : [];
    }
    return [...pinned, ...matched];
  }, [options, searchable, searchQuery]);

  const enabledOptions = filteredOptions.filter((option) => !option.disabled);

  // The menu renders in a portal so a scrolling dialog cannot clip or resize around it.
  const updateMenuPosition = useCallback(() => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;

    const spaceBelow = window.innerHeight - rect.bottom - MENU_OFFSET;
    const spaceAbove = rect.top - MENU_OFFSET;
    const opensUp = spaceBelow < Math.min(MENU_MAX_HEIGHT, 180) && spaceAbove > spaceBelow;
    const available = Math.max(120, opensUp ? spaceAbove : spaceBelow);

    setMenuStyle({
      left: rect.left,
      width: rect.width,
      maxHeight: Math.min(MENU_MAX_HEIGHT + (searchable ? 48 : 0), available - 8),
      ...(opensUp
        ? { bottom: window.innerHeight - rect.top + MENU_OFFSET }
        : { top: rect.bottom + MENU_OFFSET }),
    });
  }, [searchable]);

  useEffect(() => {
    if (!open) return undefined;

    function handlePointerDown(event) {
      const insideTrigger = containerRef.current?.contains(event.target);
      const insideMenu = menuRef.current?.contains(event.target);
      if (!insideTrigger && !insideMenu) {
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
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, updateMenuPosition]);

  useEffect(() => {
    if (!open || !searchable) return;
    requestAnimationFrame(() => {
      searchInputRef.current?.focus();
    });
  }, [open, searchable]);

  function closeMenu() {
    setOpen(false);
    setActiveIndex(-1);
    setMenuStyle(null);
    setSearchQuery("");
  }

  function openMenu() {
    const selectedIndex = enabledOptions.findIndex((option) => option.value === value);
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setSearchQuery("");
    updateMenuPosition();
    setOpen(true);

    requestAnimationFrame(() => {
      const list = listRef.current;
      const activeItem = list?.querySelector("[data-active='true']");
      if (list && activeItem) {
        list.scrollTop = activeItem.offsetTop - list.clientHeight / 2 + activeItem.clientHeight / 2;
      }
    });
  }

  function handleSelect(option) {
    if (option.disabled) return;
    onChange(option.value, { searchQuery: searchQuery.trim() });
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
      if (enabledOptions.length === 0) return;
      setActiveIndex((prev) => (prev + 1) % enabledOptions.length);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (enabledOptions.length === 0) return;
      setActiveIndex((prev) => (prev - 1 + enabledOptions.length) % enabledOptions.length);
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      if (searchable && event.target === searchInputRef.current && event.key === " ") {
        return;
      }
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

  function handleSearchChange(event) {
    setSearchQuery(event.target.value);
    setActiveIndex(0);
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
        ref={triggerRef}
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

      {open && menuStyle ? createPortal(
        <div
          ref={menuRef}
          className={`select-menu-panel ${size === "sm" ? "select-menu-sm" : ""}`.trim()}
          style={menuStyle}
          onKeyDown={handleListKeyDown}
        >
          {searchable ? (
            <div className="select-search">
              <Search size={14} className="select-search-icon" aria-hidden="true" />
              <input
                ref={searchInputRef}
                type="search"
                className="select-search-input"
                value={searchQuery}
                onChange={handleSearchChange}
                placeholder={searchPlaceholder}
                aria-label={searchPlaceholder}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={(event) => event.stopPropagation()}
              />
            </div>
          ) : null}
          <ul
            ref={listRef}
            id={listId}
            className="select-menu-list"
            role="listbox"
            aria-label={ariaLabel || label || placeholder}
            tabIndex={-1}
          >
            {filteredOptions.length === 0 ? (
              <li className="select-option select-option-empty" role="presentation">
                No matches
              </li>
            ) : (
              filteredOptions.map((option) => {
                const enabledIndex = enabledOptions.findIndex(
                  (item) => item.value === option.value
                );
                const isSelected = option.value === value;
                const isActive = enabledIndex === activeIndex;
                const showEmptyHint =
                  searchable &&
                  searchQuery.trim() &&
                  option.pinned &&
                  filteredOptions.every((item) => item.pinned);

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
                    <span className="select-option-label">
                      {option.label}
                      {showEmptyHint ? (
                        <span className="select-option-hint"> — no matches, create new</span>
                      ) : null}
                    </span>
                    {isSelected ? (
                      <Check size={14} className="select-option-check" aria-hidden="true" />
                    ) : null}
                  </li>
                );
              })
            )}
          </ul>
        </div>,
        document.body
      ) : null}
    </div>
  );
}
