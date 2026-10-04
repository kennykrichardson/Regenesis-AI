import { useEffect, useState } from "react";

export function useTypewriter(text: string, speed = 2) {
  const [value, setValue] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!text) {
      setValue("");
      setDone(true);
      return;
    }

    let frame = 0;
    let index = 0;
    let last = performance.now();
    let cancelled = false;

    setValue("");
    setDone(false);

    const tick = (now: number) => {
      if (cancelled) return;

      const elapsed = now - last;
      if (elapsed >= speed) {
        const amount = Math.max(1, Math.floor(elapsed / speed));
        index = Math.min(text.length, index + amount);
        setValue(text.slice(0, index));
        last = now;
      }

      if (index >= text.length) {
        setDone(true);
        return;
      }

      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);

    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [text, speed]);

  return { value, done };
}