import { useEffect, useState } from 'react'
import './Policies.css'

interface PolicyCandidate {
  policy_id: string
  category: string
  severity: string
  rule: string
  example_claim: string
  example_issue: string
  example_ticker: string
  applies_to: string[]
  created_from: string
  created_at: string
  status: string
}

interface EvalRecord {
  run_id: string
  ticker: string
  date: string
  timestamp: string
  overall_verdict: string
  confidence_in_report: number | null
  confidence_in_recommendation: number | null
  error_count: number
  critical_count: number
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#dc2626',
  major: '#ea580c',
  moderate: '#ca8a04',
  minor: '#65a30d',
}

const VERDICT_COLOR: Record<string, string> = {
  clean: '#16a34a',
  minor_issues: '#65a30d',
  needs_revision: '#ca8a04',
  do_not_trade: '#dc2626',
  unknown: '#6b7280',
}

export default function Policies() {
  const [candidates, setCandidates] = useState<PolicyCandidate[]>([])
  const [approved, setApproved] = useState<PolicyCandidate[]>([])
  const [evaluations, setEvaluations] = useState<EvalRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'pending' | 'approved' | 'history'>('pending')
  const [actionMsg, setActionMsg] = useState('')

  // silent: background refresh without the "Loading…" flash
  async function load(silent = false) {
    if (!silent) setLoading(true)
    try {
      const [cRes, aRes, eRes] = await Promise.all([
        fetch('/api/policies/candidates'),
        fetch('/api/policies/approved'),
        fetch('/api/evaluations'),
      ])
      if (cRes.ok) setCandidates(await cRes.json())
      if (aRes.ok) setApproved(await aRes.json())
      if (eRes.ok) setEvaluations(await eRes.json())
    } finally {
      setLoading(false)
    }
  }

  // Keep the lists current: reload every 30s and when the window regains focus,
  // so rules from a run that finished after this page opened show up without a refresh.
  useEffect(() => {
    load()
    const refresh = () => load(true)
    const timer = setInterval(refresh, 30_000)
    window.addEventListener('focus', refresh)
    return () => { clearInterval(timer); window.removeEventListener('focus', refresh) }
  }, [])

  async function act(policyId: string, action: 'approve' | 'reject') {
    const res = await fetch(`/api/policies/${policyId}/${action}`, { method: 'POST' })
    if (res.ok) {
      setActionMsg(`${action === 'approve' ? 'Approved' : 'Rejected'}: ${policyId}`)
      setTimeout(() => setActionMsg(''), 3000)
      load()
    }
  }

  const pendingCount = candidates.length
  const approvedCount = approved.length

  return (
    <div className="policies-page">
      <div className="card">
        <h2>Policy Memory</h2>
        <p className="policy-subtitle">
          Quality rules extracted by the Report Critic from prior analyses. Approved rules are injected
          into every future analysis run automatically.
        </p>

        {actionMsg && <div className="action-banner">{actionMsg}</div>}

        <div className="policy-tabs">
          <button
            className={`policy-tab-btn ${activeTab === 'pending' ? 'active' : ''}`}
            onClick={() => setActiveTab('pending')}
          >
            Pending Review
            {pendingCount > 0 && <span className="badge">{pendingCount}</span>}
          </button>
          <button
            className={`policy-tab-btn ${activeTab === 'approved' ? 'active' : ''}`}
            onClick={() => setActiveTab('approved')}
          >
            Approved Rules
            {approvedCount > 0 && <span className="badge badge-green">{approvedCount}</span>}
          </button>
          <button
            className={`policy-tab-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            Evaluation History
          </button>
        </div>

        {loading ? (
          <p className="policy-loading">Loading…</p>
        ) : (
          <>
            {activeTab === 'pending' && (
              <div className="policy-list">
                {candidates.length === 0 ? (
                  <p className="policy-empty">No pending policy candidates. Run an analysis to generate quality feedback.</p>
                ) : (
                  candidates.map(c => (
                    <div key={c.policy_id} className="policy-card">
                      <div className="policy-card-header">
                        <span
                          className="severity-badge"
                          style={{ background: SEVERITY_COLOR[c.severity] ?? '#6b7280' }}
                        >
                          {c.severity.toUpperCase()}
                        </span>
                        <span className="policy-category">{c.category.replace(/_/g, ' ')}</span>
                        <span className="policy-id">{c.policy_id}</span>
                        <span className="policy-ticker">from {c.example_ticker}</span>
                      </div>

                      <div className="policy-rule">
                        <strong>Rule:</strong> {c.rule}
                      </div>

                      {c.example_claim && (
                        <div className="policy-detail">
                          <strong>Example claim:</strong> <em>"{c.example_claim}"</em>
                        </div>
                      )}
                      {c.example_issue && (
                        <div className="policy-detail">
                          <strong>Issue:</strong> {c.example_issue}
                        </div>
                      )}
                      {c.applies_to?.length > 0 && (
                        <div className="policy-scope">
                          Scope: {c.applies_to.join(', ')}
                        </div>
                      )}

                      <div className="policy-actions">
                        <button className="btn-approve" onClick={() => act(c.policy_id, 'approve')}>
                          Approve
                        </button>
                        <button className="btn-reject" onClick={() => act(c.policy_id, 'reject')}>
                          Reject
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'approved' && (
              <div className="policy-list">
                {approved.length === 0 ? (
                  <p className="policy-empty">No approved rules yet. Approve candidates to build the rule library.</p>
                ) : (
                  approved.map(p => (
                    <div key={p.policy_id} className="policy-card approved">
                      <div className="policy-card-header">
                        <span
                          className="severity-badge"
                          style={{ background: SEVERITY_COLOR[p.severity] ?? '#6b7280' }}
                        >
                          {p.severity.toUpperCase()}
                        </span>
                        <span className="policy-category">{p.category.replace(/_/g, ' ')}</span>
                        <span className="policy-id">{p.policy_id}</span>
                      </div>
                      <div className="policy-rule">{p.rule}</div>
                      {p.applies_to?.length > 0 && (
                        <div className="policy-scope">Scope: {p.applies_to.join(', ')}</div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'history' && (
              <div className="eval-list">
                {evaluations.length === 0 ? (
                  <p className="policy-empty">No evaluation history yet.</p>
                ) : (
                  <table className="eval-table">
                    <thead>
                      <tr>
                        <th>Run</th>
                        <th>Ticker</th>
                        <th>Date</th>
                        <th>Verdict</th>
                        <th>Confidence</th>
                        <th>Errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evaluations.map(e => (
                        <tr key={e.run_id}>
                          <td className="run-id">{e.run_id}</td>
                          <td><strong>{e.ticker}</strong></td>
                          <td>{e.date}</td>
                          <td>
                            <span
                              className="verdict-badge"
                              style={{ color: VERDICT_COLOR[e.overall_verdict] ?? '#6b7280' }}
                            >
                              {e.overall_verdict.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td>
                            {e.confidence_in_report !== null
                              ? `${e.confidence_in_report}/5`
                              : '—'}
                          </td>
                          <td>
                            {e.error_count > 0 ? (
                              <span>
                                {e.error_count}
                                {e.critical_count > 0 && (
                                  <span style={{ color: '#dc2626' }}> ({e.critical_count} critical)</span>
                                )}
                              </span>
                            ) : (
                              <span style={{ color: '#16a34a' }}>0</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
