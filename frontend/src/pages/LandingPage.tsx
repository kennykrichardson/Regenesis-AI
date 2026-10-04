import { useState, type FormEvent } from "react";
import { ArrowDown, Github, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import Loader from "../components/Loader";
import ParticleField from "../components/ParticleField";
import RepositoryInput from "../components/RepositoryInput";
import { buildPrompt, extractPrompt } from "../services/api";

export default function LandingPage() {
  const navigate = useNavigate();
  const [repository, setRepository] = useState("");
  const [branch, setBranch] = useState("main");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!repository.trim() || loading) return;

    setLoading(true);
    setError("");

    try {
      const result = await buildPrompt(repository.trim(), branch);
      const prompt = extractPrompt(result);

      sessionStorage.setItem(
        "regenesis-result",
        JSON.stringify({
          repository: repository.trim(),
          branch: branch.trim() || "main",
          prompt,
        }),
      );

      navigate("/result");
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Unable to reconstruct the repository.",
      );
      setLoading(false);
    }
  }

  return (
    <>
      <AnimatePresence>{loading && <Loader />}</AnimatePresence>

      <main className="site-shell">
        <ParticleField />

        <header className="topbar">
          <button className="brand" onClick={() => navigate("/")} aria-label="Regenesis home">
            <span className="brand">
              <span className="brand-mark">R</span>
              <span className="brand-name">
                <span className="brand-re">RE</span><span className="brand-genesis">GENESIS</span>
              </span>
            </span>
          </button>

          <div className="topbar-actions">
            <a href="https://github.com/kennykrichardson" target="_blank" rel="noreferrer">
              <Github size={16} />
              GitHub
            </a>
          </div>
        </header>

        <section className="hero">
          <motion.h1
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            Reverse engineer
            <br />
            <span>repositories.</span>
          </motion.h1>

          <motion.p
            className="hero-copy"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.08 }}
          >
            Give Regenesis a GitHub repository. It retrieves the source,
            follows its structure, and builds a reconstruction prompt you can
            hand to another coding agent.
          </motion.p>

          <RepositoryInput
            repository={repository}
            branch={branch}
            disabled={loading}
            onRepositoryChange={setRepository}
            onBranchChange={setBranch}
            onSubmit={handleSubmit}
          />

          {error && <p className="error-message">{error}</p>}
          <div className="hero-foot">
          <div className="hero-kicker">
            <span>ENGINEERED WITH ⚡ BY</span>
            <a className="hero-named-kenny" href="https://github.com/kennykrichardson" target="_blank" rel="noreferrer">
              KENNY RICHARDSON
            </a>
          </div>
          </div>
        </section>
        
        <div className="site-footer">
        <footer className="hero-footkicker">
          <span>REGENESIS • SOURCE RECONSTRUCTION ENGINE</span>
          <span>[2026]</span>
        </footer>
        </div>
      </main>
    </>
  );
}