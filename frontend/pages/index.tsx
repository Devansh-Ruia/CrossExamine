import { useState, useCallback, DragEvent } from 'react';
import { useRouter } from 'next/router';
import { uploadCase } from '@/lib/api';

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [witness, setWitness] = useState('');
  const [rounds, setRounds] = useState(4);
  const [voiceOn, setVoiceOn] = useState(true);
  const [status, setStatus] = useState<'idle' | 'indexing' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length > 0) setFiles((prev) => [...prev, ...dropped]);
  }, []);

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (files.length === 0 || !witness.trim()) return;
    setStatus('indexing');
    setErrorMsg('');
    try {
      const { session_id } = await uploadCase(files, witness, rounds, voiceOn);
      router.push(`/session/${session_id}`);
    } catch (err: any) {
      setStatus('error');
      setErrorMsg(err.message || 'Upload failed');
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <div className="px-12 pt-12 pb-8">
        <div className="text-[28px] font-medium tracking-wider mb-3">CROSSEXAMINE</div>
        <div className="text-body text-text-dim max-w-[720px]">
          Upload case documents. Paste a witness account. Two AI agents will argue
          over the record — one attacking the witness&apos;s story, one defending it.
          At the end you get a vulnerability report showing every contradiction the
          documents expose.
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
      {/* Left half -- file drop */}
      <div className="flex-1 border-r border-border flex flex-col p-12">
        <div className="text-label uppercase tracking-widest text-text-muted mb-1">
          Case Documents
        </div>
        <div className="text-label text-text-muted mb-6">
          PDF, TXT, or DOCX — police reports, depositions, medical records, contracts
        </div>
        <div
          className={`flex-1 border border-border bg-bg-raised flex items-center justify-center transition-colors duration-100 ${
            dragOver ? 'border-text-dim' : ''
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => {
            const input = document.createElement('input');
            input.type = 'file';
            input.multiple = true;
            input.accept = '.pdf,.txt,.docx';
            input.onchange = (e: any) => {
              const selected = Array.from(e.target.files as FileList);
              setFiles((prev) => [...prev, ...selected]);
            };
            input.click();
          }}
        >
          <span className="text-body text-text-ghost cursor-pointer">
            drop files here
          </span>
        </div>
        {files.length > 0 && (
          <div className="mt-6 border-t border-border pt-4">
            {files.map((f, i) => (
              <div
                key={`${f.name}-${i}`}
                className="flex justify-between items-center py-2 border-b border-border text-body text-text-dim"
              >
                <span>{f.name}</span>
                <button
                  onClick={() => removeFile(i)}
                  className="text-text-muted hover:text-attack transition-colors duration-100"
                >
                  x
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right half -- inputs */}
      <div className="flex-1 p-12 flex flex-col">
        <div className="text-label uppercase tracking-widest text-text-muted mb-1">
          Witness Statement
        </div>
        <div className="text-label text-text-muted mb-3">
          The account being challenged. What does the witness claim happened?
        </div>
        <textarea
          className="flex-1 min-h-[200px] bg-bg-raised border border-border text-text-primary font-mono text-body p-4 resize-none outline-none focus:border-text-dim transition-colors duration-100"
          value={witness}
          onChange={(e) => setWitness(e.target.value)}
          placeholder="Paste or summarize the witness account you want to stress-test. The more specific the better — include key claims about timing, who acted first, and what the witness says they did."
        />

        <div className="flex gap-12 mt-8 items-end">
          <div>
            <div className="text-label uppercase tracking-widest text-text-muted mb-3">
              Rounds
            </div>
            <input
              type="number"
              min={1}
              max={10}
              value={rounds}
              onChange={(e) => setRounds(Number(e.target.value))}
              className="bg-transparent border border-border text-text-primary font-mono text-body p-2 w-16 text-center outline-none focus:border-text-dim"
            />
          </div>
          <div>
            <div className="text-label uppercase tracking-widest text-text-muted mb-3">
              Voice
            </div>
            <div className="flex gap-4">
              <button
                onClick={() => setVoiceOn(true)}
                className={`text-label uppercase tracking-wider ${
                  voiceOn
                    ? 'text-text-primary border-b border-text-primary'
                    : 'text-text-muted'
                }`}
              >
                ON
              </button>
              <button
                onClick={() => setVoiceOn(false)}
                className={`text-label uppercase tracking-wider ${
                  !voiceOn
                    ? 'text-text-primary border-b border-text-primary'
                    : 'text-text-muted'
                }`}
              >
                OFF
              </button>
            </div>
          </div>
        </div>

        <div className="mt-12 flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={
              status === 'indexing' || files.length === 0 || !witness.trim()
            }
            className={`font-mono text-lg px-4 py-2 transition-colors duration-100 ${
              status === 'indexing'
                ? 'text-text-muted border border-[#333333] cursor-wait'
                : files.length === 0 || !witness.trim()
                  ? 'text-text-ghost border border-[#333333] cursor-not-allowed'
                  : 'text-text-primary border border-[#2a2a3a] hover:border-text-primary cursor-pointer'
            }`}
          >
            {status === 'indexing' ? 'INDEXING...' : 'BEGIN'}
          </button>
        </div>
        {status === 'error' && (
          <div className="mt-4 text-body text-attack text-right">{errorMsg}</div>
        )}
      </div>
      </div>
    </div>
  );
}
