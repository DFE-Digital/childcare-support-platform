import { useRef, useEffect } from "react";

export function useLastInputWasKeyboard() {
  const lastInputWasKeyboard = useRef(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.metaKey && !e.altKey && !e.ctrlKey)
        lastInputWasKeyboard.current = true;
    };
    const onPointer = () => {
      lastInputWasKeyboard.current = false;
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("mousedown", onPointer, true);
    document.addEventListener("pointerdown", onPointer, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("mousedown", onPointer, true);
      document.removeEventListener("pointerdown", onPointer, true);
    };
  }, []);

  return lastInputWasKeyboard;
}
