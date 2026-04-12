import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { fetchReport, Vulnerability, ReportMetadata } from '@/lib/api';

const SEVERITY_BORDER: Record<string, string> = {
  high: 'border-l-attack',
  medium: 'border-l-amber',
  low: 'border-l-low',
};

export default function ReportPage() {
  const router = useRouter();
  const { id } = router.query;
  const [vulns, setVulns] = useState<Vulnerability[]>([]);
  const [meta, setMeta] = useState<ReportMetadata | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id || typeof id !== 'string') return;
    let cancelled = false;

    const poll = async () => {
      try {
        const data = await fetchReport(id);
        if (!cancelled) {
          setVulns(data.vulnerabilities);
          setMeta(data.metadata);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setTimeout(poll, 2000);
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [id]);

  const copyJSON = () => {
    navigator.clipboard.writeText(JSON.stringify(vulns, null, 2));
  };

  const exportPDF = async () => {
    const { jsPDF } = await import('jspdf');
    const doc = new jsPDF({ unit: 'mm', format: 'a4' });
    const margin = 20;
    let y = margin;
    const pageWidth = doc.internal.pageSize.getWidth();
    const contentWidth = pageWidth - margin * 2;

    doc.setFont('courier', 'bold');
    doc.setFontSize(16);
    doc.text('VULNERABILITY REPORT', margin, y);
    y += 8;

    if (meta) {
      doc.setFont('courier', 'normal');
      doc.setFontSize(8);
      doc.text(
        `Session ${meta.session_id} | ${meta.date} | ${meta.doc_count} docs | ${meta.rounds_completed} rounds`,
        margin,
        y,
      );
      y += 10;
    }

    doc.setDrawColor(100);
    doc.line(margin, y, pageWidth - margin, y);
    y += 8;

    for (const v of vulns) {
      if (y > 260) {
        doc.addPage();
        y = margin;
      }

      doc.setFont('courier', 'bold');
      doc.setFontSize(10);
      doc.text(`[${v.severity.toUpperCase()}]${v.conceded ? '  CONCEDED BY DEFENSE' : ''}`, margin, y);
      y += 6;

      const fields = [
        ['CLAIM', v.claim],
        ['CONTRADICTION', v.contradiction],
        ['SOURCE', v.source],
        ['WHY IT MATTERS', v.explanation],
      ];

      for (const [label, value] of fields) {
        doc.setFont('courier', 'bold');
        doc.setFontSize(7);
        doc.text(label, margin, y);
        y += 4;
        doc.setFont('courier', 'normal');
        doc.setFontSize(9);
        const lines = doc.splitTextToSize(value, contentWidth);
        doc.text(lines, margin, y);
        y += lines.length * 4 + 2;
      }
      y += 6;
    }

    doc.save('vulnerability-report.pdf');
  };

  if (loading) {
    return (
      <div className="p-12">
        <span className="text-body text-text-muted">LOADING</span>
      </div>
    );
  }

  const counts = {
    high: vulns.filter((v) => v.severity === 'high').length,
    medium: vulns.filter((v) => v.severity === 'medium').length,
    low: vulns.filter((v) => v.severity === 'low').length,
    conceded: vulns.filter((v) => v.conceded).length,
  };

  return (
    <div className="p-12 max-w-[960px]">
      <div className="flex justify-between items-start">
        <div className="text-[32px] font-medium tracking-wider">
          VULNERABILITY REPORT
        </div>
        <div className="flex gap-3 pt-2">
          <button
            onClick={copyJSON}
            className="text-label uppercase tracking-widest text-text-muted border border-border px-4 py-2 hover:text-text-primary hover:border-text-dim transition-colors duration-100"
          >
            COPY JSON
          </button>
          <button
            onClick={exportPDF}
            className="text-label uppercase tracking-widest text-text-muted border border-border px-4 py-2 hover:text-text-primary hover:border-text-dim transition-colors duration-100"
          >
            EXPORT PDF
          </button>
        </div>
      </div>

      {meta && (
        <div className="text-label uppercase tracking-wider text-text-ghost mt-3">
          Session {meta.session_id} &bull; {meta.date} &bull;{' '}
          {meta.doc_count} documents &bull; {meta.rounds_completed} rounds
        </div>
      )}

      <hr className="border-border mt-8 mb-8" />

      <div className="text-label uppercase tracking-wider text-text-muted mb-12 flex items-center gap-1.5">
        <span>HIGH: <span className="text-attack font-semibold">{counts.high}</span></span>
        <span className="text-text-ghost">&bull;</span>
        <span>MEDIUM: <span className="text-amber font-semibold">{counts.medium}</span></span>
        <span className="text-text-ghost">&bull;</span>
        <span>LOW: <span className="text-low font-semibold">{counts.low}</span></span>
        <span className="text-text-ghost">&bull;</span>
        <span>CONCEDED: <span className="text-amber font-semibold">{counts.conceded}</span></span>
      </div>

      {vulns.map((v, i) => (
        <div
          key={i}
          className={`mb-10 pl-4 border-l-2 ${SEVERITY_BORDER[v.severity]}`}
        >
          <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
            <span
              className={`text-label uppercase tracking-widest font-semibold ${
                v.severity === 'high' ? 'text-attack' : v.severity === 'medium' ? 'text-amber' : 'text-low'
              }`}
            >
              {v.severity.toUpperCase()}
            </span>
            {v.conceded && (
              <span className="text-label uppercase tracking-wider text-amber">
                CONCEDED BY DEFENSE
              </span>
            )}
          </div>

          <VulnField label="CLAIM" value={v.claim} />
          <VulnField label="CONTRADICTION" value={v.contradiction} />
          <VulnField label="SOURCE" value={v.source} />
          <VulnField label="WHY IT MATTERS" value={v.explanation} />
        </div>
      ))}

      {vulns.length === 0 && (
        <div className="text-body text-text-muted">
          No vulnerabilities found. The witness account survived adversarial scrutiny.
        </div>
      )}
    </div>
  );
}

function VulnField({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-2.5">
      <div className="text-label uppercase tracking-widest text-text-muted mb-1">
        {label}
      </div>
      <div className="text-body text-[#bbb]">{value}</div>
    </div>
  );
}
