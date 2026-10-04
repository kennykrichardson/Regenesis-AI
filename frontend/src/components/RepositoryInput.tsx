import { Github, ArrowUpRight } from "lucide-react";
import type { FormEvent } from "react";

type Props = {
  repository: string;
  branch: string;
  disabled: boolean;
  onRepositoryChange: (value: string) => void;
  onBranchChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export default function RepositoryInput({
  repository,
  branch,
  disabled,
  onRepositoryChange,
  onBranchChange,
  onSubmit,
}: Props) {
  return (
    <form className="repo-card" onSubmit={onSubmit}>
      <div className="repo-row">
        <div className="repo-field">
          <Github size={22} />
          <input
            value={repository}
            onChange={(event) => onRepositoryChange(event.target.value)}
            placeholder="Paste any GitHub repository URL"
            spellCheck={false}
            autoComplete="off"
            disabled={disabled}
            aria-label="GitHub repository URL"
          />
        </div>

        <button className="reconstruct-button" type="submit" disabled={disabled || !repository.trim()}>
          <span>{disabled ? "Reconstructing" : "Reconstruct"}</span>
          <ArrowUpRight size={19} />
        </button>
      </div>
    </form>
  );
}