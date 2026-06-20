const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

// Safely parse error response — handles both JSON and HTML error pages
async function parseError(res, fallback) {
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try {
      const err = await res.json();
      return err.detail || fallback;
    } catch { }
  }
  // HTML or unknown — map status codes to friendly messages
  if (res.status === 404) return "Session expired — please re-ingest your source.";
  if (res.status === 429) return "Rate limit reached — wait a moment and try again.";
  if (res.status === 503 || res.status === 502) return "Backend is starting up — please wait a few seconds and retry.";
  if (res.status === 504) return "Video processing timed out. It might be blocked or have no transcript. Try another video.";
  return `${fallback} (${res.status})`;
}

export async function ingestSource(source) {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source }),
  });

  if (!res.ok) {
    throw new Error(await parseError(res, "Ingestion failed"));
  }

  return res.json();
}

export async function uploadPdf(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload-pdf`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(await parseError(res, "Upload failed"));
  }

  return res.json();
}

export async function chatStream(question, sessionId, onChunk, onSources, onDone, onPipeline) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
  });

  if (!res.ok) {
    throw new Error(await parseError(res, "Chat failed"));
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith("event: sources")) {
        // Next data line will be the sources JSON
        const nextDataIdx = lines.indexOf(line) + 1;
        // handled below
      } else if (line.startsWith("event: pipeline")) {
        // Next data line will be pipeline JSON — handled below
      } else if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data === "[DONE]") {
          onDone();
        } else if (data.startsWith("[{")) {
          // This is sources JSON
          try {
            const sources = JSON.parse(data);
            onSources(sources);
          } catch (e) {
            const decoded = data.replace(/\\n/g, "\n");
            onChunk(decoded);
          }
        } else if (data.startsWith("{\"original_query")) {
          // This is pipeline JSON
          try {
            const pipeline = JSON.parse(data);
            if (onPipeline) onPipeline(pipeline);
          } catch (e) {}
        } else {
          // Decode escaped newlines back
          const decoded = data.replace(/\\n/g, "\n");
          onChunk(decoded);
        }
      }
    }
  }
}
