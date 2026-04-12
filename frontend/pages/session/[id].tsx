import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';
import { API_URL, submitInterjection, SSEEvent } from '@/lib/api';

type TimelineItem =
  | { kind: 'turn'; agent: 'attack' | 'defense'; round: number; text: string; complete: boolean }
  | { kind: 'interjection'; text: string };

export default function SessionPage() {
  const router = useRouter();
  const { id } = router.query;

  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [interjectText, setInterjectText] = useState('');
  const [sessionDone, setSessionDone] = useState(false);
  const [doneReason, setDoneReason] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [currentRound, setCurrentRound] = useState(0);
  const [numRounds, setNumRounds] = useState<number | null>(null);
  const [connecting, setConnecting] = useState(true);
  const [reportReady, setReportReady] = useState(false);

  const audioQueue = useRef<string[]>([]);
  const isPlaying = useRef(false);
  const debateEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    debateEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [timeline]);

  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const source = new EventSource(`${API_URL}/session/${id}/stream`);

    source.onmessage = (e) => {
      const event: SSEEvent = JSON.parse(e.data);

      switch (event.type) {
        case 'session_config': {
          if (event.num_rounds) setNumRounds(event.num_rounds);
          break;
        }

        case 'token': {
          setConnecting(false);
          setTimeline((prev) => {
            const last = prev[prev.length - 1];
            if (
              !last ||
              last.kind !== 'turn' ||
              last.complete ||
              last.agent !== event.agent ||
              last.round !== event.round
            ) {
              return [
                ...prev,
                {
                  kind: 'turn',
                  agent: event.agent!,
                  round: event.round!,
                  text: event.text || '',
                  complete: false,
                },
              ];
            }
            const updated = [...prev];
            const lastTurn = updated[updated.length - 1] as Extract<TimelineItem, { kind: 'turn' }>;
            updated[updated.length - 1] = {
              ...lastTurn,
              text: lastTurn.text + (event.text || ''),
            };
            return updated;
          });
          if (event.round) setCurrentRound(event.round);
          break;
        }

        case 'turn_complete': {
          setTimeline((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.kind === 'turn') {
              updated[updated.length - 1] = { ...last, complete: true };
            }
            return updated;
          });
          break;
        }

        case 'audio': {
          if (event.file) {
            audioQueue.current.push(`${API_URL}/audio/${event.file}`);
            playNextAudio();
          }
          break;
        }

        case 'audio_failed':
          break;

        case 'interjection_ack': {
          if (event.text) {
            setTimeline((prev) => [
              ...prev,
              { kind: 'interjection', text: event.text! },
            ]);
          }
          break;
        }

        case 'status': {
          if (event.message) setStatusMessage(event.message);
          break;
        }

        case 'session_complete': {
          setSessionDone(true);
          setDoneReason(
            event.reason === 'exhausted'
              ? 'The attacking agent exhausted its documentary ammunition.'
              : 'All rounds completed.',
          );
          source.close();

          // Poll for report readiness
          const pollReport = async () => {
            let attempts = 0;
            while (attempts < 30) {
              attempts++;
              try {
                const res = await fetch(`${API_URL}/session/${id}/report`);
                if (res.ok) {
                  setReportReady(true);
                  return;
                }
              } catch { /* keep polling */ }
              await new Promise((r) => setTimeout(r, 3000));
            }
          };
          pollReport();
          break;
        }

        default:
          break;
      }
    };

    source.onerror = () => {
      source.close();
    };

    return () => source.close();
  }, [id]);

  const playNextAudio = () => {
    if (isPlaying.current || audioQueue.current.length === 0) return;
    isPlaying.current = true;
    const url = audioQueue.current.shift()!;
    const audio = new Audio(url);
    audio.onended = () => {
      isPlaying.current = false;
      playNextAudio();
    };
    audio.onerror = () => {
      isPlaying.current = false;
      playNextAudio();
    };
    audio.play().catch(() => {
      isPlaying.current = false;
      playNextAudio();
    });
  };

  const handleInterject = async () => {
    if (!interjectText.trim() || !id || typeof id !== 'string') return;
    try {
      await submitInterjection(id, interjectText);
      setInterjectText('');
    } catch {
      // Silently fail -- interjection is best-effort
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleInterject();
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <div className="px-12 py-4 border-b border-border text-label uppercase tracking-wider text-text-muted flex items-center gap-1.5">
        {sessionDone ? (
          <>
            <span className="text-text-dim">DEBATE CONCLUDED</span>
            <span className="text-text-ghost">&bull;</span>
            {reportReady ? (
              <span
                className="text-text-dim cursor-pointer hover:text-text-primary transition-colors duration-100 ml-auto"
                onClick={() => router.push(`/report/${id}`)}
              >
                VIEW VULNERABILITY REPORT &rarr;
              </span>
            ) : (
              <span className="text-text-dim">GENERATING REPORT...</span>
            )}
          </>
        ) : (
          <>
            <span>ROUND <span className="text-text-dim">{currentRound} / {numRounds ?? '...'}</span></span>
            {statusMessage && (
              <>
                <span className="text-text-ghost">&bull;</span>
                <span className="text-text-dim">{statusMessage}</span>
              </>
            )}
          </>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-12 py-8 max-w-[960px] w-full">
        {connecting && timeline.length === 0 && (
          <div className="mb-8 text-label text-text-muted flex items-center gap-2">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-text-muted animate-pulse-dot" />
            CONNECTING TO CASE RECORD...
          </div>
        )}

        {timeline.map((item, i) => {
          if (item.kind === 'interjection') {
            return (
              <div key={i} className="mb-8 pl-4 border-l-2 border-l-amber">
                <div className="text-label uppercase tracking-widest text-amber mb-2">
                  JUDGE&apos;S INSTRUCTION
                </div>
                <div className="text-reading text-amber italic">
                  {item.text}
                </div>
              </div>
            );
          }

          const turn = item;
          return (
            <div
              key={i}
              className={`mb-8 pl-4 border-l-2 ${
                turn.agent === 'attack'
                  ? 'border-l-attack'
                  : 'border-l-defense'
              }`}
            >
              <div className="flex justify-between items-center mb-2">
                <div
                  className={`text-label uppercase tracking-widest flex items-center gap-2 ${
                    turn.agent === 'attack' ? 'text-attack' : 'text-defense'
                  }`}
                >
                  <span
                    className={`inline-block w-1.5 h-1.5 rounded-full ${
                      !turn.complete
                        ? `${turn.agent === 'attack' ? 'bg-attack' : 'bg-defense'} animate-pulse-dot`
                        : 'bg-text-ghost'
                    }`}
                  />
                  {turn.agent.toUpperCase()} — ROUND {turn.round}
                  {!turn.complete && (
                    <span className="text-text-muted ml-2">speaking</span>
                  )}
                </div>
              </div>
              <div className="text-reading text-[#ccc]">
                {turn.text}
                {!turn.complete && (
                  <span className="inline-block w-px h-3.5 bg-current ml-0.5 align-text-bottom animate-blink" />
                )}
              </div>
            </div>
          );
        })}

        {sessionDone && (
          <div className="mb-8 pt-4 border-t border-border">
            <div className="text-body text-text-muted">{doneReason}</div>
          </div>
        )}

        <div ref={debateEndRef} />
      </div>

      {!sessionDone && (
        <div className="border-t border-border px-12 pt-3 pb-4">
          <div className="text-label text-text-muted mb-2">
            JUDGE&apos;S BENCH &nbsp;&mdash;&nbsp; interject between rounds to direct counsel
          </div>
          <div className="flex gap-4 items-center">
          <input
            type="text"
            value={interjectText}
            onChange={(e) => setInterjectText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Interject as judge..."
            className="flex-1 bg-transparent border border-border text-text-primary font-mono text-body px-4 py-2.5 outline-none placeholder:text-text-ghost focus:border-text-dim transition-colors duration-100"
          />
          <button
            onClick={handleInterject}
            className="text-label uppercase tracking-widest text-text-muted border border-border px-5 py-2.5 hover:text-text-primary hover:border-text-dim transition-colors duration-100"
          >
            SUBMIT
          </button>
          </div>
        </div>
      )}
    </div>
  );
}
