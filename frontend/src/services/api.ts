const API_URL = import.meta.env.VITE_API_URL;

export type PromptRequest = {
  repository: string;
  branch?: string;
};

export type PromptResponse = {
  prompt?: string;
  response?: string;
  repository?: string;
  branch?: string;
  [key: string]: unknown;
};

export async function buildPrompt(
  repository: string,
  branch = "main",
): Promise<PromptResponse> {
  const response = await fetch(`${API_URL}/prompt`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      repository,
      branch: branch.trim() || "main",
    } satisfies PromptRequest),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<PromptResponse>;
}

export function extractPrompt(data: PromptResponse): string {
  if (typeof data.prompt === "string") return data.prompt;
  if (typeof data.response === "string") return data.response;

  return JSON.stringify(data, null, 2);
}