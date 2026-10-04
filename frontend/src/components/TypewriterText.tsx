import { useTypewriter } from "../hooks/useTypewriter";

function PromptLine({ line }: { line: string }) {
  if (line.startsWith("### ")) return <h3>{line.slice(4)}</h3>;
  if (line.startsWith("## ")) return <h2>{line.slice(3)}</h2>;
  if (line.startsWith("# ")) return <h1>{line.slice(2)}</h1>;

  return <>{line}</>;
}

export default function TypewriterText({
  text,
  speed = 1.5,
}: {
  text: string;
  speed?: number;
}) {
  const { value, done } = useTypewriter(text, speed);

  return (
    <div className="prompt-body" aria-live={done ? "off" : "polite"}>
      {value.split("\n").map((line, index) => (
        <div className="prompt-line" key={`${index}-${line}`}>
          <PromptLine line={line} />
        </div>
      ))}
      {!done && <span className="typing-caret" />}
    </div>
  );
}