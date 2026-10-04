import { ArrowLeft, Check, Copy, ExternalLink, FileCode2, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import TypewriterText from "../components/TypewriterText";
import ParticleField from "../components/ParticleField";

type StoredResult = {
  repository: string;
  branch: string;
  prompt: string;
};

export default function ResultPage() {
  const navigate = useNavigate();
  const [payload, setPayload] = useState<StoredResult | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem("regenesis-result");

    if (!stored) {
      navigate("/", { replace: true });
      return;
    }

    try {
      setPayload(JSON.parse(stored) as StoredResult);
    } catch {
      sessionStorage.removeItem("regenesis-result");
      navigate("/", { replace: true });
    }
  }, [navigate]);

  async function copyPrompt() {
    if (!payload) return;

    await navigator.clipboard.writeText(payload.prompt);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  if (!payload) return null;

  return (
    <main className="result-shell">
      <ParticleField />

      <header className="topbar">
        <button className="brand" onClick={() => navigate("/")} aria-label="Back to Regenesis">
            <span className="brand">
              <span className="brand-mark">R</span>
              <span className="brand-name">
                <span className="brand-re">RE</span><span className="brand-genesis">GENESIS</span>
              </span>
            </span>
        </button>

        <div className="result-actions">
          <button onClick={() => navigate("/")}>
            <ArrowLeft size={16} />
            New
          </button>
          <button className="copy-button" onClick={copyPrompt}>
            {copied ? <Check size={16} /> : <Copy size={16} />}
            {copied ? "Copied" : "Copy prompt"}
          </button>
        </div>
      </header>

      <section className="result-wrap">
        <div className="result-heading">
          <div>
            <span className="section-label">RECONSTRUCTION RESULT</span>
            <h1 className="result-heading">Prompt assembled.</h1>
          </div>

          <a
            className="repo-identity"
            href={payload.repository}
            target="_blank"
            rel="noreferrer"
            title={payload.repository}
          >
            <FileCode2 size={17} />
            <span>{payload.repository}</span>
            <b>{payload.branch}</b>
            <ExternalLink size={15} />
          </a>
        </div>

        <article className="prompt-card">
          <div className="prompt-toolbar">
            <span>REGENESIS_PROMPT</span>
            <span>{payload.prompt.length.toLocaleString()} characters</span>
          </div>

          <TypewriterText text={payload.prompt} speed={1.5} />
        </article>

        <div className="result-bottom">
          <button onClick={() => navigate("/")}>
            <RotateCcw size={16} />
            Reconstruct another repository
          </button>
        </div>
      </section>
    </main>
  );
}