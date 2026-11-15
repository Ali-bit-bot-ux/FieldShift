"use client";
import { useEffect, useRef, useSyncExternalStore } from "react";
import { ChevronDown, BookOpen } from "lucide-react";
import { sections, toolNames, type Section } from "@/lib/tools";
import { usePlanner } from "./Store";
function subscribe(listener: () => void) {
  window.addEventListener("hashchange", listener);
  return () => window.removeEventListener("hashchange", listener);
}
function current(): Section {
  const key = window.location.hash.slice(1);
  return Object.hasOwn(sections, key) ? (key as Section) : "planner";
}
export function useSection() {
  return useSyncExternalStore(subscribe, current, () => "planner" as Section);
}
export function ToolNav({ section }: { section: Section }) {
  const { lang, t } = usePlanner(),
    menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    function outside(e: Event) {
      if (!menu.current?.contains(e.target as Node))
        menu.current?.removeAttribute("open");
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, []);
  return (
    <nav
      className="tool-nav"
      aria-label={t(
        "Инструменты хозяйства",
        "Шаруашылық құралдары",
        "Farm tools",
      )}
    >
      <div className="wrap tool-nav-inner">
        <a
          href="#planner"
          aria-current={section === "planner" ? "page" : undefined}
        >
          {sections.planner[lang]}
        </a>
        <details
          ref={menu}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              menu.current?.removeAttribute("open");
              menu.current?.querySelector("summary")?.focus();
            }
          }}
        >
          <summary>
            <BookOpen size={16} />
            {section === "planner"
              ? t("Инструменты хозяйства", "Шаруашылық құралдары", "Farm tools")
              : sections[section][lang]}
            <ChevronDown size={15} />
          </summary>
          <div className="tool-menu">
            {(Object.keys(sections) as Section[])
              .filter((key) => key !== "planner")
              .map((key) => (
                <a
                  key={key}
                  href={"#" + key}
                  aria-current={section === key ? "page" : undefined}
                  onClick={() => menu.current?.removeAttribute("open")}
                >
                  <strong>{sections[key][lang]}</strong>
                  <small>{toolNames[key]}</small>
                </a>
              ))}
          </div>
        </details>
      </div>
    </nav>
  );
}
