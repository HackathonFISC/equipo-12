// Ventana de consola: título, botón ··· y un menú que oculta el cuerpo.
// El menú se ancla a la esquina, como el de las capturas de referencia.
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

export type WidgetAction = {
  id?: string;
  label: string;
  onSelect: () => void;
  separated?: boolean;
};

export function ConsoleWidget({
  title,
  actions = [],
  footer,
  children,
}: {
  title: string;
  actions?: WidgetAction[];
  footer?: ReactNode;
  children: ReactNode;
}) {
  const [menu, setMenu] = useState(false);
  const [hidden, setHidden] = useState(false);
  const root = useRef<HTMLElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!menu) return;
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setMenu(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenu(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [menu]);

  const items: WidgetAction[] = [
    ...actions,
    {
      label: hidden ? "Mostrar" : "Ocultar",
      separated: actions.length > 0,
      onSelect: () => setHidden((value) => !value),
    },
  ];

  return (
    <section
      ref={root}
      className="relative rounded-lg border border-[#e4e1de] bg-white"
    >
      <header className="flex items-start justify-between gap-3 px-5 pt-4">
        <h2 className="text-xl font-semibold tracking-tight text-[#1c1c1a]">
          {title}
        </h2>
        <button
          type="button"
          aria-label="Más opciones"
          aria-haspopup="menu"
          aria-expanded={menu}
          aria-controls={menuId}
          className="px-1 text-lg leading-none tracking-[0.2em] text-[#1c1c1a]"
          onClick={() => setMenu((open) => !open)}
        >
          ···
        </button>
      </header>
      {menu ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-4 top-11 z-20 min-w-[12rem] rounded border border-[#00688b] bg-white py-1 shadow-[0_1px_4px_rgba(28,28,26,0.16)]"
        >
          {items.map((item) => (
            <button
              key={item.label}
              id={item.id}
              type="button"
              role="menuitem"
              className={`block w-full px-3 py-1.5 text-left text-sm text-[#1c1c1a] outline-none hover:bg-[#f6f4f3] focus-visible:bg-[#f6f4f3] ${item.separated ? "mt-1 border-t border-[#e3e2df]" : ""}`}
              onClick={() => {
                item.onSelect();
                setMenu(false);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
      {hidden ? <div className="h-3" /> : <div className="px-5 pb-4">{children}</div>}
      {!hidden && footer ? <div className="px-5 pb-4">{footer}</div> : null}
    </section>
  );
}
