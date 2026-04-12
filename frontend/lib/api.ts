// Backend URL -- configurable via env var for deployment,
// defaults to localhost:8000 for dev
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function uploadCase(
  files: File[],
  witnessStatement: string,
  numRounds: number,
  voiceEnabled: boolean,
): Promise<{ session_id: string }> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  form.append('witness_statement', witnessStatement);
  form.append('num_rounds', String(numRounds));
  form.append('voice_enabled', String(voiceEnabled));

  const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${text}`);
  }
  return res.json();
}

export async function submitInterjection(
  sessionId: string,
  text: string,
): Promise<void> {
  const res = await fetch(`${API_URL}/session/${sessionId}/interject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error('Interjection failed');
}

export async function fetchReport(
  sessionId: string,
): Promise<{ vulnerabilities: Vulnerability[]; metadata: ReportMetadata }> {
  const res = await fetch(`${API_URL}/session/${sessionId}/report`);
  if (!res.ok) throw new Error('Report not ready');
  return res.json();
}

// Types shared across frontend
export interface Vulnerability {
  claim: string;
  contradiction: string;
  source: string;
  severity: 'high' | 'medium' | 'low';
  explanation: string;
  conceded: boolean;
}

export interface ReportMetadata {
  session_id: string;
  date: string;
  doc_count: number;
  rounds_completed: number;
}

export interface SSEEvent {
  type:
    | 'token'
    | 'turn_complete'
    | 'audio'
    | 'audio_failed'
    | 'interjection_ack'
    | 'session_complete'
    | 'status'
    | 'session_config';
  agent?: 'attack' | 'defense';
  round?: number;
  text?: string;
  file?: string;
  audio_status?: 'pending';
  reason?: 'all_rounds' | 'exhausted';
  message?: string;
  num_rounds?: number;
  session_id?: string;
}
