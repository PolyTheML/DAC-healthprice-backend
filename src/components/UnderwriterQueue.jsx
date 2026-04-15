import { useState, useEffect, useCallback } from 'react';

export default function UnderwriterQueue({ backendUrl }) {
  const [queue, setQueue]       = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [acting, setActing]     = useState(null); // case_id currently being actioned

  const fetchQueue = useCallback(() => {
    setLoading(true);
    fetch(`${backendUrl}/dashboard/stats`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(json => {
        setQueue(json.hitl_queue.pending_cases);
        setError(null);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [backendUrl]);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);

  async function handleReview(caseId, approved) {
    setActing(caseId);
    try {
      const res = await fetch(`${backendUrl}/cases/${caseId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved,
          reviewer_id: 'dashboard-user',
          notes: approved ? 'Approved via dashboard' : 'Declined via dashboard',
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setExpanded(null);
      fetchQueue();
    } catch (err) {
      alert(`Review failed: ${err.message}`);
    } finally {
      setActing(null);
    }
  }

  const riskBadge = (level) => {
    const map = {
      low:     { bg: '#dcfce7', color: '#166534' },
      medium:  { bg: '#fef9c3', color: '#854d0e' },
      high:    { bg: '#fee2e2', color: '#991b1b' },
      decline: { bg: '#f3f4f6', color: '#374151' },
    };
    const s = map[level] ?? map.medium;
    return {
      display: 'inline-block',
      padding: '1px 8px',
      borderRadius: 9999,
      fontSize: 11,
      fontWeight: 600,
      background: s.bg,
      color: s.color,
      marginLeft: 8,
      textTransform: 'uppercase',
    };
  };

  if (loading) return <div style={styles.card}><p style={styles.muted}>Loading queue…</p></div>;
  if (error)   return <div style={styles.card}><p style={{ color: '#ef4444' }}>Error: {error}</p></div>;

  return (
    <div style={styles.card}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={styles.heading}>HITL Review Queue ({queue.length} pending)</h2>
        <button onClick={fetchQueue} style={styles.refreshBtn}>↻ Refresh</button>
      </div>

      {queue.length === 0 && (
        <p style={styles.muted}>No cases pending review.</p>
      )}

      {queue.map(c => (
        <div key={c.case_id} style={styles.caseRow}>
          {/* Summary row — click to expand */}
          <div
            style={styles.summaryRow}
            onClick={() => setExpanded(expanded === c.case_id ? null : c.case_id)}
          >
            <div>
              <span style={styles.caseId}>{c.case_id}</span>
              <span style={riskBadge(c.risk_level)}>{c.risk_level}</span>
            </div>
            <div style={styles.metaRight}>
              <div>Age {c.extracted_data?.age ?? '?'} · {c.extracted_data?.province || 'Unknown'}</div>
              <div style={{ fontSize: 11, color: '#6b7280' }}>{c.extracted_data?.occupation_type || '—'}</div>
              <div style={{ fontWeight: 600 }}>${(c.final_premium ?? 0).toFixed(2)}/yr</div>
            </div>
            <span style={styles.chevron}>{expanded === c.case_id ? '▲' : '▼'}</span>
          </div>

          {/* Expanded: reasoning trace + action buttons */}
          {expanded === c.case_id && (
            <div style={styles.expandedPanel}>
              <p style={styles.traceLabel}>AI Reasoning Trace</p>
              <pre style={styles.traceBox}>
                {c.reasoning_trace || 'No reasoning trace available.'}
              </pre>
              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <button
                  disabled={acting === c.case_id}
                  onClick={() => handleReview(c.case_id, true)}
                  style={styles.approveBtn}
                >
                  ✅ Approve
                </button>
                <button
                  disabled={acting === c.case_id}
                  onClick={() => handleReview(c.case_id, false)}
                  style={styles.declineBtn}
                >
                  ❌ Decline
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

const styles = {
  card: {
    padding: 20,
    background: '#fff',
    borderRadius: 8,
    boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
    marginBottom: 20,
  },
  heading:   { fontSize: 16, fontWeight: 700, margin: 0 },
  muted:     { fontSize: 12, color: '#9ca3af' },
  refreshBtn: {
    fontSize: 12,
    padding: '3px 10px',
    border: '1px solid #d1d5db',
    borderRadius: 4,
    background: '#f9fafb',
    cursor: 'pointer',
  },
  caseRow: {
    border: '1px solid #e5e7eb',
    borderRadius: 6,
    marginBottom: 8,
    overflow: 'hidden',
  },
  summaryRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 14px',
    cursor: 'pointer',
    background: '#fff',
  },
  caseId: { fontFamily: 'monospace', fontSize: 13, fontWeight: 700 },
  metaRight: { textAlign: 'right', fontSize: 12, color: '#374151' },
  chevron:   { marginLeft: 12, color: '#9ca3af', fontSize: 12 },
  expandedPanel: {
    padding: '12px 16px 14px',
    background: '#f9fafb',
    borderTop: '1px solid #e5e7eb',
  },
  traceLabel: { fontSize: 10, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 },
  traceBox: {
    fontSize: 11,
    color: '#374151',
    whiteSpace: 'pre-wrap',
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 4,
    padding: 10,
    maxHeight: 240,
    overflowY: 'auto',
  },
  approveBtn: {
    padding: '5px 14px',
    background: '#22c55e',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    fontSize: 13,
    cursor: 'pointer',
    fontWeight: 600,
  },
  declineBtn: {
    padding: '5px 14px',
    background: '#ef4444',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    fontSize: 13,
    cursor: 'pointer',
    fontWeight: 600,
  },
};
